"""Trend analysis engine - analyzes scraped listings to identify trends."""

import logging
import json
from collections import Counter, defaultdict
from config import FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS, SEGMENTS
from database import save_trend_snapshot, save_trend_images

logger = logging.getLogger(__name__)


def analyze_trends(listings, google_data=None):
    """
    Analyze listings to extract trends across fabric types, patterns, and colors.
    Returns structured trend data and saves snapshots to DB.
    """
    if google_data is None:
        google_data = {}

    # Classify listings into segments
    _classify_segments(listings)

    # Extract images for visual gallery
    _extract_trend_images(listings)

    # Overall analysis
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

    # Per-segment analysis
    segment_trends = {}
    for seg_key, seg_config in SEGMENTS.items():
        seg_listings = [l for l in listings if l.get("segment") == seg_key]
        if not seg_listings:
            continue
        seg_fabric = _count_term_occurrences(
            seg_listings, seg_config["priority_fabrics"], "fabric_type"
        )
        seg_pattern = _count_term_occurrences(
            seg_listings, seg_config["priority_patterns"], "pattern"
        )
        seg_color = _count_term_occurrences(seg_listings, COLOR_TERMS, "color")
        _calculate_scores(seg_fabric)
        _calculate_scores(seg_pattern)
        _calculate_scores(seg_color)
        seg_fabric.sort(key=lambda x: x["score"], reverse=True)
        seg_pattern.sort(key=lambda x: x["score"], reverse=True)
        seg_color.sort(key=lambda x: x["score"], reverse=True)

        # Tag with segment
        for item in seg_fabric + seg_pattern + seg_color:
            item["segment"] = seg_key
        save_trend_snapshot(seg_fabric + seg_pattern + seg_color)

        segment_trends[seg_key] = {
            "label": seg_config["label"],
            "icon": seg_config["icon"],
            "fabric_types": seg_fabric[:10],
            "patterns": seg_pattern[:10],
            "colors": seg_color[:10],
            "listing_count": len(seg_listings),
        }

    # Generate actionable insights
    insights = _generate_insights(fabric_stats, pattern_stats, color_stats, google_data)

    return {
        "fabric_types": fabric_stats[:20],
        "patterns": pattern_stats[:20],
        "colors": color_stats[:20],
        "insights": insights,
        "segment_trends": segment_trends,
        "total_listings_analyzed": len(listings),
        "sources": list(set(l["source"] for l in listings)),
    }


def _classify_segments(listings):
    """Classify each listing into market segments based on keywords."""
    for listing in listings:
        title_lower = listing.get("title", "").lower()
        tags_lower = " ".join(t.lower() for t in listing.get("tags", []))
        combined = title_lower + " " + tags_lower

        best_segment = "general"
        best_score = 0

        for seg_key, seg_config in SEGMENTS.items():
            score = 0
            for kw in seg_config["keywords"]:
                if kw.lower() in combined:
                    score += 2
            for ft in seg_config.get("priority_fabrics", []):
                if ft.lower() in combined:
                    score += 1
            for pt in seg_config.get("priority_patterns", []):
                if pt.lower() in combined:
                    score += 1

            if score > best_score:
                best_score = score
                best_segment = seg_key

        listing["segment"] = best_segment


def _extract_trend_images(listings):
    """Extract images from listings and associate them with trend terms."""
    images = []
    seen_urls = set()

    for listing in listings:
        img_url = listing.get("image_url", "")
        if not img_url or img_url in seen_urls:
            continue
        if not img_url.startswith("http"):
            continue

        seen_urls.add(img_url)
        tags = listing.get("tags", [])
        title_lower = listing.get("title", "").lower()

        # Associate image with matched terms
        for term_list, category in [
            (FABRIC_TYPES, "fabric_type"),
            (PATTERN_TYPES, "pattern"),
            (COLOR_TERMS, "color"),
        ]:
            for term in term_list:
                if term.lower() in title_lower or term.lower() in [
                    t.lower() for t in tags
                ]:
                    images.append({
                        "term": term,
                        "category": category,
                        "image_url": img_url,
                        "source": listing.get("source", ""),
                        "listing_title": listing.get("title", ""),
                        "listing_url": listing.get("url", ""),
                        "price": listing.get("price"),
                        "segment": listing.get("segment", "general"),
                    })
                    break  # One category per image is enough

    if images:
        save_trend_images(images)


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

        by_source = defaultdict(int)
        for l in matching:
            by_source[l["source"]] += 1

        # Collect sample images for this term
        sample_images = []
        for l in matching:
            if l.get("image_url") and l["image_url"].startswith("http"):
                sample_images.append({
                    "url": l["image_url"],
                    "title": l.get("title", ""),
                    "source": l.get("source", ""),
                    "listing_url": l.get("url", ""),
                })
                if len(sample_images) >= 6:
                    break

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
                {"min": round(min(prices), 2), "max": round(max(prices), 2)}
                if prices else None
            ),
            "google_interest": 0,
            "google_trending_up": False,
            "score": 0,
            "velocity": 0,
            "lifecycle": "unknown",
            "segment": "general",
            "sample_images": sample_images,
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
    """Calculate a composite trend score for each term."""
    if not stats:
        return

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

    for category, stats, label in [
        ("fabric_type", fabric_stats, "Fabric"),
        ("pattern", pattern_stats, "Pattern"),
        ("color", color_stats, "Color"),
    ]:
        trending_up = [s for s in stats if s.get("google_trending_up")]
        if trending_up:
            top = trending_up[0]
            detail = (
                f"'{top['term'].title()}' is trending upward on Google with "
                f"{top['mention_count']} marketplace listings."
            )
            if top.get("avg_price"):
                detail += f" Average price: ${top['avg_price']:.2f}."
            insights.append({
                "type": "rising",
                "icon": "trending_up",
                "title": f"Rising {label}: {top['term'].title()}",
                "detail": detail,
                "action": (
                    f"Consider stocking {top['term']} fabrics - demand is growing."
                ),
                "score": top["score"],
                "images": top.get("sample_images", [])[:3],
            })

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
            "images": top.get("sample_images", [])[:3],
        })

    niche_candidates = [
        s for s in all_stats
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
            "images": niche.get("sample_images", [])[:3],
        })

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
            "images": highest_price.get("sample_images", [])[:3],
        })

    insights.sort(key=lambda x: x.get("score", 0), reverse=True)
    return insights
