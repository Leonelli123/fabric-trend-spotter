"""Trend analysis engine - analyzes scraped listings to identify trends."""

import logging
import json
from collections import Counter, defaultdict
from config import FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS
from database import save_trend_snapshot

logger = logging.getLogger(__name__)


def analyze_trends(listings, google_data=None):
    """
    Analyze listings to extract trends across fabric types, patterns, and colors.
    Returns structured trend data and saves snapshots to DB.
    """
    if google_data is None:
        google_data = {}

    fabric_stats = _count_term_occurrences(listings, FABRIC_TYPES, "fabric_type")
    pattern_stats = _count_term_occurrences(listings, PATTERN_TYPES, "pattern")
    color_stats = _count_term_occurrences(listings, COLOR_TERMS, "color")

    # Enrich with Google Trends data
    _enrich_with_google(fabric_stats, google_data)
    _enrich_with_google(pattern_stats, google_data)
    _enrich_with_google(color_stats, google_data)

    # Calculate composite trend scores
    _calculate_scores(fabric_stats)
    _calculate_scores(pattern_stats)
    _calculate_scores(color_stats)

    # Sort by score descending
    fabric_stats.sort(key=lambda x: x["score"], reverse=True)
    pattern_stats.sort(key=lambda x: x["score"], reverse=True)
    color_stats.sort(key=lambda x: x["score"], reverse=True)

    # Save to database
    all_snapshots = fabric_stats + pattern_stats + color_stats
    save_trend_snapshot(all_snapshots)

    # Generate actionable insights
    insights = _generate_insights(fabric_stats, pattern_stats, color_stats, google_data)

    return {
        "fabric_types": fabric_stats[:20],
        "patterns": pattern_stats[:20],
        "colors": color_stats[:20],
        "insights": insights,
        "total_listings_analyzed": len(listings),
        "sources": list(set(l["source"] for l in listings)),
    }


def _count_term_occurrences(listings, terms, category):
    """Count how many listings mention each term and gather price/popularity data."""
    stats = []
    for term in terms:
        term_lower = term.lower()
        matching = []
        for listing in listings:
            title_lower = listing.get("title", "").lower()
            tags = [t.lower() for t in listing.get("tags", [])]
            if term_lower in title_lower or term_lower in tags:
                matching.append(listing)

        if not matching:
            continue

        prices = [l["price"] for l in matching if l.get("price")]
        favorites = [l["favorites"] for l in matching if l.get("favorites")]
        reviews = [l["reviews"] for l in matching if l.get("reviews")]

        # Break down by source
        by_source = defaultdict(int)
        for l in matching:
            by_source[l["source"]] += 1

        stats.append({
            "category": category,
            "term": term,
            "mention_count": len(matching),
            "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
            "avg_favorites": (
                round(sum(favorites) / len(favorites)) if favorites else 0
            ),
            "avg_reviews": round(sum(reviews) / len(reviews)) if reviews else 0,
            "source": "all",
            "by_source": dict(by_source),
            "price_range": (
                {"min": min(prices), "max": max(prices)} if prices else None
            ),
            "google_interest": 0,
            "google_trending_up": False,
            "score": 0,
        })

    return stats


def _enrich_with_google(stats, google_data):
    """Add Google Trends data to stats."""
    for item in stats:
        key = f"{item['term']} fabric"
        if key in google_data:
            gd = google_data[key]
            item["google_interest"] = gd.get("recent_interest", 0)
            item["google_trending_up"] = gd.get("trending_up", False)


def _calculate_scores(stats):
    """
    Calculate a composite trend score for each term.

    Score factors:
    - mention_count: How many listings mention it (market supply/demand)
    - avg_favorites: Popularity signal from Etsy
    - google_interest: Search interest signal
    - google_trending_up: Bonus for upward trend
    - source diversity: Appearing across multiple sources is a stronger signal
    """
    if not stats:
        return

    # Normalize each factor to 0-100 range
    max_mentions = max(s["mention_count"] for s in stats) or 1
    max_favs = max(s["avg_favorites"] for s in stats) or 1
    max_google = max(s["google_interest"] for s in stats) or 1

    for item in stats:
        mention_score = (item["mention_count"] / max_mentions) * 30
        fav_score = (item["avg_favorites"] / max_favs) * 25
        google_score = (item["google_interest"] / max_google) * 25
        trending_bonus = 10 if item["google_trending_up"] else 0
        source_diversity = min(len(item.get("by_source", {})) * 5, 10)

        item["score"] = round(
            mention_score + fav_score + google_score + trending_bonus + source_diversity,
            1,
        )


def _generate_insights(fabric_stats, pattern_stats, color_stats, google_data):
    """Generate human-readable actionable insights."""
    insights = []

    # Top rising trends
    for category, stats, label in [
        ("fabric_type", fabric_stats, "Fabric"),
        ("pattern", pattern_stats, "Pattern"),
        ("color", color_stats, "Color"),
    ]:
        trending_up = [s for s in stats if s.get("google_trending_up")]
        if trending_up:
            top = trending_up[0]
            insights.append({
                "type": "rising",
                "icon": "trending_up",
                "title": f"Rising {label}: {top['term'].title()}",
                "detail": (
                    f"'{top['term'].title()}' is trending upward on Google with "
                    f"{top['mention_count']} marketplace listings. "
                    f"Average price: ${top['avg_price']:.2f}."
                    if top.get("avg_price")
                    else f"'{top['term'].title()}' is trending upward on Google with "
                    f"{top['mention_count']} marketplace listings."
                ),
                "action": (
                    f"Consider stocking {top['term']} fabrics - demand is growing."
                ),
                "score": top["score"],
            })

    # High-demand items (most listings + highest favorites)
    all_stats = fabric_stats + pattern_stats + color_stats
    if all_stats:
        top_demand = sorted(all_stats, key=lambda x: x["mention_count"], reverse=True)
        top = top_demand[0]
        insights.append({
            "type": "hot",
            "icon": "fire",
            "title": f"Hottest Overall: {top['term'].title()}",
            "detail": (
                f"'{top['term'].title()}' dominates with {top['mention_count']} "
                f"listings across {len(top.get('by_source', {}))} sources."
            ),
            "action": (
                f"This is a safe bet - high demand and wide availability for "
                f"'{top['term']}' products."
            ),
            "score": top["score"],
        })

    # Niche opportunities (decent Google interest but low listing count)
    niche_candidates = [
        s
        for s in all_stats
        if s["google_interest"] > 30 and s["mention_count"] < 5
    ]
    if niche_candidates:
        niche = max(niche_candidates, key=lambda x: x["google_interest"])
        insights.append({
            "type": "opportunity",
            "icon": "lightbulb",
            "title": f"Niche Opportunity: {niche['term'].title()}",
            "detail": (
                f"'{niche['term'].title()}' has strong search interest "
                f"(Google: {niche['google_interest']}) but only "
                f"{niche['mention_count']} marketplace listings."
            ),
            "action": (
                f"Low competition + high interest = opportunity. "
                f"Consider creating '{niche['term']}' products."
            ),
            "score": niche["google_interest"],
        })

    # Price insights
    priced = [s for s in all_stats if s.get("avg_price")]
    if priced:
        highest_price = max(priced, key=lambda x: x["avg_price"])
        insights.append({
            "type": "price",
            "icon": "dollar",
            "title": f"Premium Segment: {highest_price['term'].title()}",
            "detail": (
                f"'{highest_price['term'].title()}' commands the highest average "
                f"price at ${highest_price['avg_price']:.2f}/yard."
            ),
            "action": (
                f"Higher margins possible with '{highest_price['term']}' products."
            ),
            "score": highest_price["score"],
        })

    insights.sort(key=lambda x: x.get("score", 0), reverse=True)
    return insights
