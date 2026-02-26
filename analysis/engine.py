"""Trend analysis engine - analyzes scraped listings to identify trends.

All trends pass through the quality layer:
1. Listings are filtered and quality-scored before analysis
2. Term occurrences are weighted by listing credibility
3. Trends must meet minimum evidence thresholds
4. Each trend gets a confidence tier so users know how much to trust it
"""

import logging
from collections import defaultdict
from config import FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS, SEGMENTS
from database import save_trend_snapshot, save_trend_images
from analysis.quality import (
    filter_listings, validate_trend, weighted_average,
    estimate_unique_sellers, remove_price_outliers,
    MIN_LISTINGS_FOR_SEGMENT_TREND,
)

logger = logging.getLogger(__name__)


def analyze_trends(listings, google_data=None):
    """
    Analyze listings to extract trends across fabric types, patterns, and colors.
    Returns structured trend data and saves snapshots to DB.
    """
    if google_data is None:
        google_data = {}

    # STEP 1: Clean the data
    clean_listings, removed_count, removal_reasons = filter_listings(listings)
    logger.info(
        "Quality filter: %d clean listings from %d total (removed %d)",
        len(clean_listings), len(listings), removed_count,
    )

    # Classify listings into segments
    _classify_segments(clean_listings)

    # Extract images (only from quality listings with images)
    _extract_trend_images(clean_listings)

    # STEP 2: Count and score, with quality weighting
    fabric_stats = _count_term_occurrences(clean_listings, FABRIC_TYPES, "fabric_type")
    pattern_stats = _count_term_occurrences(clean_listings, PATTERN_TYPES, "pattern")
    color_stats = _count_term_occurrences(clean_listings, COLOR_TERMS, "color")

    # Enrich with Google Trends data
    _enrich_with_google(fabric_stats, google_data)
    _enrich_with_google(pattern_stats, google_data)
    _enrich_with_google(color_stats, google_data)

    # STEP 3: Validate and filter - only real trends survive
    fabric_stats = _validate_and_score(fabric_stats)
    pattern_stats = _validate_and_score(pattern_stats)
    color_stats = _validate_and_score(color_stats)

    # Sort by score descending
    fabric_stats.sort(key=lambda x: x["score"], reverse=True)
    pattern_stats.sort(key=lambda x: x["score"], reverse=True)
    color_stats.sort(key=lambda x: x["score"], reverse=True)

    # Save to database
    all_snapshots = fabric_stats + pattern_stats + color_stats
    save_trend_snapshot(all_snapshots)

    # Per-segment analysis (lower thresholds, but still validated)
    segment_trends = {}
    for seg_key, seg_config in SEGMENTS.items():
        seg_listings = [l for l in clean_listings if l.get("segment") == seg_key]
        if len(seg_listings) < 2:
            continue
        seg_fabric = _count_term_occurrences(
            seg_listings, seg_config["priority_fabrics"], "fabric_type"
        )
        seg_pattern = _count_term_occurrences(
            seg_listings, seg_config["priority_patterns"], "pattern"
        )
        seg_color = _count_term_occurrences(seg_listings, COLOR_TERMS, "color")

        seg_all = seg_fabric + seg_pattern + seg_color
        _enrich_with_google(seg_all, google_data)
        seg_all = _validate_and_score(seg_all, is_segment=True)

        for item in seg_all:
            item["segment"] = seg_key
        save_trend_snapshot(seg_all)

        seg_fabric = [s for s in seg_all if s["category"] == "fabric_type"]
        seg_pattern = [s for s in seg_all if s["category"] == "pattern"]
        seg_color = [s for s in seg_all if s["category"] == "color"]

        segment_trends[seg_key] = {
            "label": seg_config["label"],
            "icon": seg_config["icon"],
            "fabric_types": seg_fabric[:10],
            "patterns": seg_pattern[:10],
            "colors": seg_color[:10],
            "listing_count": len(seg_listings),
        }

    # Generate actionable insights (only from validated trends)
    insights = _generate_insights(fabric_stats, pattern_stats, color_stats, google_data)

    return {
        "fabric_types": fabric_stats[:20],
        "patterns": pattern_stats[:20],
        "colors": color_stats[:20],
        "insights": insights,
        "segment_trends": segment_trends,
        "total_listings_analyzed": len(clean_listings),
        "total_listings_raw": len(listings),
        "removed_count": removed_count,
        "removal_reasons": removal_reasons,
        "sources": list(set(l["source"] for l in clean_listings)),
    }


def _validate_and_score(stats, is_segment=False):
    """Validate each trend and calculate quality-weighted scores."""
    validated = []

    for item in stats:
        is_valid, tier, notes = validate_trend(item, is_segment=is_segment)
        if not is_valid:
            logger.debug(
                "Filtered out '%s': %s", item["term"], "; ".join(notes)
            )
            continue

        item["confidence_tier"] = tier
        item["quality_notes"] = notes

        validated.append(item)

    # Now calculate scores among only the validated trends
    _calculate_scores(validated)
    return validated


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
    """Extract images from listings and associate them with trend terms.
    Only uses listings above a minimum quality threshold."""
    images = []
    seen_urls = set()

    # Sort by quality so the best images come first
    sorted_listings = sorted(
        listings,
        key=lambda l: l.get("quality_score", 0),
        reverse=True,
    )

    for listing in sorted_listings:
        img_url = listing.get("image_url", "")
        if not img_url or img_url in seen_urls:
            continue
        if not img_url.startswith("http"):
            continue
        # Skip very low quality listings for the gallery
        if listing.get("quality_score", 0) < 0.15:
            continue

        seen_urls.add(img_url)
        tags = listing.get("tags", [])
        title_lower = listing.get("title", "").lower()

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
                    break

    if images:
        save_trend_images(images)


def _count_term_occurrences(listings, terms, category):
    """Count how many listings mention each term with quality-weighted stats."""
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

        # Quality weights for each matching listing
        qualities = [l.get("quality_score", 0.3) for l in matching]

        # Quality-weighted price averaging (better sellers' prices matter more)
        raw_prices = [l["price"] for l in matching if l.get("price")]
        clean_prices = remove_price_outliers(raw_prices)
        price_qualities = [
            l.get("quality_score", 0.3)
            for l in matching if l.get("price") and l["price"] in clean_prices
        ]
        avg_price = weighted_average(clean_prices, price_qualities) if clean_prices else None

        # Quality-weighted favorites
        fav_values = [l["favorites"] for l in matching if l.get("favorites")]
        fav_weights = [
            l.get("quality_score", 0.3)
            for l in matching if l.get("favorites")
        ]
        avg_favorites = weighted_average(fav_values, fav_weights) if fav_values else 0

        reviews = [l["reviews"] for l in matching if l.get("reviews")]

        by_source = defaultdict(int)
        for l in matching:
            by_source[l["source"]] += 1

        # Estimate unique sellers
        unique_sellers = estimate_unique_sellers(matching)

        # Overall quality of the evidence for this term
        avg_quality = sum(qualities) / len(qualities) if qualities else 0

        # Collect sample images (sorted by quality)
        sample_images = []
        for l in sorted(matching, key=lambda x: x.get("quality_score", 0), reverse=True):
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
            "unique_sellers": unique_sellers,
            "avg_price": round(avg_price, 2) if avg_price else None,
            "avg_favorites": round(avg_favorites) if avg_favorites else 0,
            "avg_reviews": (
                round(sum(reviews) / len(reviews)) if reviews else 0
            ),
            "avg_quality": round(avg_quality, 3),
            "source": "all",
            "by_source": dict(by_source),
            "source_count": len(by_source),
            "price_range": (
                {"min": round(min(clean_prices), 2), "max": round(max(clean_prices), 2)}
                if clean_prices else None
            ),
            "google_interest": 0,
            "google_trending_up": False,
            "score": 0,
            "velocity": 0,
            "lifecycle": "unknown",
            "segment": "general",
            "confidence_tier": "moderate",
            "quality_notes": [],
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
    """
    Calculate composite trend score, weighted by data quality.

    Score components (out of 100):
    - Marketplace presence (25): How many listings, weighted by quality
    - Community validation (20): Favorites, reviews from credible sellers
    - Search demand (20): Google Trends interest
    - Momentum (15): Google trending up + acceleration
    - Source diversity (10): Multi-platform confirmation
    - Seller diversity (10): Multiple independent sellers, not just one shop
    """
    if not stats:
        return

    max_mentions = max(s["mention_count"] for s in stats) or 1
    max_favs = max(s["avg_favorites"] for s in stats) or 1
    max_google = max(s["google_interest"] for s in stats) or 1
    max_sellers = max(s.get("unique_sellers", 1) for s in stats) or 1

    for item in stats:
        # Quality multiplier: high-quality evidence gets full weight
        quality_mult = 0.5 + (item.get("avg_quality", 0.3) * 0.5)  # 0.5 to 1.0

        # Marketplace presence (quality-weighted)
        presence = (item["mention_count"] / max_mentions) * 25 * quality_mult

        # Community validation
        validation = (item["avg_favorites"] / max_favs) * 20

        # Search demand
        search = (item["google_interest"] / max_google) * 20

        # Momentum bonus
        momentum = 0
        if item.get("google_trending_up"):
            momentum += 10
        if item.get("google_interest", 0) > 50:
            momentum += 5

        # Source diversity (need multiple platforms to confirm)
        source_count = len(item.get("by_source", {}))
        source_div = min(source_count * 5, 10)

        # Seller diversity (not just one shop pushing this term)
        seller_count = item.get("unique_sellers", 1)
        seller_div = min((seller_count / max(max_sellers, 1)) * 10, 10)

        raw_score = presence + validation + search + momentum + source_div + seller_div

        # Confidence penalty: weak trends get score dampened
        tier = item.get("confidence_tier", "moderate")
        tier_mult = {
            "verified": 1.0,
            "strong": 0.9,
            "moderate": 0.75,
            "weak": 0.5,
        }.get(tier, 0.75)

        item["score"] = round(raw_score * tier_mult, 1)


def _generate_insights(fabric_stats, pattern_stats, color_stats, google_data):
    """Generate human-readable actionable insights.
    Only generates insights from validated trends with real evidence."""
    insights = []

    for category, stats, label in [
        ("fabric_type", fabric_stats, "Fabric"),
        ("pattern", pattern_stats, "Pattern"),
        ("color", color_stats, "Color"),
    ]:
        # Only pick trends with at least moderate confidence
        credible_rising = [
            s for s in stats
            if s.get("google_trending_up")
            and s.get("confidence_tier") in ("verified", "strong", "moderate")
        ]
        if credible_rising:
            top = credible_rising[0]
            tier = top.get("confidence_tier", "moderate")
            detail = (
                f"'{top['term'].title()}' is trending upward on Google with "
                f"{top['mention_count']} listings from "
                f"{top.get('unique_sellers', '?')} sellers."
            )
            if top.get("avg_price"):
                detail += f" Average price: ${top['avg_price']:.2f}."
            detail += f" [{tier.upper()} confidence]"
            insights.append({
                "type": "rising",
                "icon": "trending_up",
                "title": f"Rising {label}: {top['term'].title()}",
                "detail": detail,
                "action": (
                    f"Consider stocking {top['term']} fabrics - demand is growing."
                ),
                "score": top["score"],
                "confidence_tier": tier,
                "images": top.get("sample_images", [])[:3],
            })

    all_stats = fabric_stats + pattern_stats + color_stats
    # Only consider trends with real evidence for the "hottest" pick
    strong_stats = [
        s for s in all_stats
        if s.get("confidence_tier") in ("verified", "strong")
    ]
    if strong_stats:
        top = max(strong_stats, key=lambda x: x["mention_count"])
        insights.append({
            "type": "hot",
            "icon": "fire",
            "title": f"Hottest Overall: {top['term'].title()}",
            "detail": (
                f"'{top['term'].title()}' has {top['mention_count']} "
                f"listings from {top.get('unique_sellers', '?')} sellers "
                f"across {top.get('source_count', 1)} platforms. "
                f"[{top.get('confidence_tier', 'moderate').upper()} confidence]"
            ),
            "action": (
                f"This is well-validated - high demand and multi-source confirmation "
                f"for '{top['term']}' products."
            ),
            "score": top["score"],
            "confidence_tier": top.get("confidence_tier"),
            "images": top.get("sample_images", [])[:3],
        })

    # Niche opportunities: decent Google interest but low listing count
    # Still need SOME marketplace evidence
    niche_candidates = [
        s for s in all_stats
        if s["google_interest"] > 30
        and s["mention_count"] <= 8
        and s.get("confidence_tier") in ("verified", "strong", "moderate")
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
                f"{niche['mention_count']} marketplace listings. "
                f"[{niche.get('confidence_tier', 'moderate').upper()} confidence]"
            ),
            "action": (
                f"Low competition + high interest = opportunity. "
                f"Consider creating '{niche['term']}' products."
            ),
            "score": niche["google_interest"],
            "confidence_tier": niche.get("confidence_tier"),
            "images": niche.get("sample_images", [])[:3],
        })

    priced = [
        s for s in all_stats
        if s.get("avg_price")
        and s.get("confidence_tier") in ("verified", "strong", "moderate")
    ]
    if priced:
        highest_price = max(priced, key=lambda x: x["avg_price"])
        insights.append({
            "type": "price",
            "icon": "dollar",
            "title": f"Premium Segment: {highest_price['term'].title()}",
            "detail": (
                f"'{highest_price['term'].title()}' commands "
                f"${highest_price['avg_price']:.2f}/yard average "
                f"(from {highest_price['mention_count']} listings). "
                f"[{highest_price.get('confidence_tier', 'moderate').upper()} confidence]"
            ),
            "action": (
                f"Higher margins possible with '{highest_price['term']}' products."
            ),
            "score": highest_price["score"],
            "confidence_tier": highest_price.get("confidence_tier"),
            "images": highest_price.get("sample_images", [])[:3],
        })

    insights.sort(key=lambda x: x.get("score", 0), reverse=True)
    return insights
