"""Data quality and validation layer.

Ensures trends are based on statistically meaningful data, not noise.
Filters spam, weights by source credibility, detects outliers, and
requires minimum evidence before calling something a "trend".
"""

import logging
import math
from collections import defaultdict

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Minimum thresholds - what counts as a real trend vs noise
# --------------------------------------------------------------------------
# For OVERALL trends (across all sources)
MIN_LISTINGS_FOR_TREND = 3          # Need at least 3 listings
MIN_SOURCES_FOR_HIGH_CONFIDENCE = 2  # Must appear on 2+ platforms
MIN_UNIQUE_SELLERS_APPROX = 2       # Estimated via URL diversity

# For SEGMENT-specific trends (smaller pool, so lower bar)
MIN_LISTINGS_FOR_SEGMENT_TREND = 2

# For forecasts
MIN_LISTINGS_FOR_FORECAST = 3
MIN_CONFIDENCE_TO_SHOW = 20         # Don't show forecasts below 20% confidence

# --------------------------------------------------------------------------
# Listing quality scoring - not all listings are equal
# --------------------------------------------------------------------------

def score_listing_quality(listing):
    """
    Score a single listing's credibility (0.0 to 1.0).

    High quality signals:
    - Many reviews (established seller)
    - High rating
    - Many favorites (validated by community)
    - Has a real price (not $0 or absurd)
    - Has real images
    - Has meaningful tags

    Low quality signals:
    - Zero reviews (brand new or fake)
    - No price
    - Suspiciously low or high price
    - Title is too short or generic
    - No image
    """
    score = 0.0
    max_score = 0.0

    # Reviews: strongest credibility signal (established seller)
    max_score += 30
    reviews = listing.get("reviews", 0)
    if reviews >= 100:
        score += 30
    elif reviews >= 20:
        score += 22
    elif reviews >= 5:
        score += 15
    elif reviews >= 1:
        score += 8
    # 0 reviews = 0 points

    # Favorites: community validation
    max_score += 25
    favorites = listing.get("favorites", 0)
    if favorites >= 50:
        score += 25
    elif favorites >= 10:
        score += 18
    elif favorites >= 3:
        score += 10
    elif favorites >= 1:
        score += 5

    # Rating quality
    max_score += 15
    rating = listing.get("rating")
    if rating and rating >= 4.5:
        score += 15
    elif rating and rating >= 4.0:
        score += 10
    elif rating and rating >= 3.0:
        score += 5

    # Price sanity (fabric is typically $5-$50/yard)
    max_score += 15
    price = listing.get("price")
    if price and 3.0 <= price <= 80.0:
        score += 15  # Reasonable fabric price
    elif price and 1.0 <= price <= 150.0:
        score += 8   # Plausible but unusual
    elif price and price > 0:
        score += 3   # Has a price but suspicious range
    # No price or $0 = 0 points

    # Title quality (short = probably junk)
    max_score += 10
    title = listing.get("title", "")
    word_count = len(title.split())
    if word_count >= 5:
        score += 10
    elif word_count >= 3:
        score += 6
    elif word_count >= 1:
        score += 2

    # Has image
    max_score += 5
    if listing.get("image_url", "").startswith("http"):
        score += 5

    return round(score / max_score, 3) if max_score > 0 else 0.0


# --------------------------------------------------------------------------
# Listing filtering - remove junk before analysis
# --------------------------------------------------------------------------

def filter_listings(listings):
    """
    Filter out low-quality and duplicate listings.
    Returns (clean_listings, removed_count, removal_reasons).
    """
    clean = []
    removed = 0
    reasons = defaultdict(int)

    # Deduplication: track by normalized title + source
    seen = set()

    for listing in listings:
        title = listing.get("title", "").strip()

        # Skip empty titles
        if not title or len(title) < 5:
            removed += 1
            reasons["empty_or_short_title"] += 1
            continue

        # Skip duplicates (same title + same source)
        dedup_key = (title.lower()[:80], listing.get("source", ""))
        if dedup_key in seen:
            removed += 1
            reasons["duplicate"] += 1
            continue
        seen.add(dedup_key)

        # Skip listings with absurd prices (likely not fabric by the yard)
        price = listing.get("price")
        if price is not None and (price <= 0 or price > 500):
            removed += 1
            reasons["price_outlier"] += 1
            continue

        # Score quality and attach it
        quality = score_listing_quality(listing)
        listing["quality_score"] = quality

        clean.append(listing)

    logger.info(
        "Data quality: kept %d of %d listings (removed %d: %s)",
        len(clean), len(listings), removed, dict(reasons),
    )
    return clean, removed, dict(reasons)


# --------------------------------------------------------------------------
# Trend validation - require real evidence
# --------------------------------------------------------------------------

def validate_trend(stat, is_segment=False):
    """
    Check if a trend has enough evidence to be reported.
    Returns (is_valid, confidence_tier, quality_notes).

    Confidence tiers:
    - "verified":  3+ sources OR 10+ listings with good quality
    - "strong":    2 sources OR 6+ listings with decent quality
    - "moderate":  Meets minimum threshold, some quality signals
    - "weak":      Below minimum but has Google Trends corroboration
    - None:        Not enough evidence, should be filtered out
    """
    min_listings = MIN_LISTINGS_FOR_SEGMENT_TREND if is_segment else MIN_LISTINGS_FOR_TREND
    mention_count = stat.get("mention_count", 0)
    source_count = len(stat.get("by_source", {}))
    avg_quality = stat.get("avg_quality", 0)
    has_google = stat.get("google_interest", 0) > 0
    google_trending = stat.get("google_trending_up", False)

    notes = []

    # Hard filter: not enough listings at all
    if mention_count < min_listings:
        # Exception: if Google Trends strongly supports it, allow with "weak" tier
        if has_google and google_trending and mention_count >= 1:
            notes.append(
                f"Only {mention_count} listing(s) but Google Trends confirms interest"
            )
            return True, "weak", notes
        return False, None, [f"Only {mention_count} listing(s), need {min_listings}+"]

    # Verified: strong multi-platform evidence
    if source_count >= 3 and mention_count >= 8:
        notes.append(f"Found on {source_count} platforms with {mention_count} listings")
        return True, "verified", notes

    if source_count >= 2 and mention_count >= 10:
        notes.append(
            f"Strong evidence: {mention_count} listings across {source_count} sources"
        )
        return True, "verified", notes

    # Strong: good multi-source or high volume
    if source_count >= 2 and mention_count >= 5:
        notes.append(f"Confirmed on {source_count} platforms")
        return True, "strong", notes

    if mention_count >= 8 and avg_quality >= 0.4:
        notes.append(f"{mention_count} quality listings (avg quality: {avg_quality:.0%})")
        return True, "strong", notes

    # Moderate: meets minimum, some supporting signals
    if mention_count >= min_listings:
        if has_google:
            notes.append("Corroborated by Google Trends data")
            return True, "moderate" if source_count >= 2 else "moderate", notes
        if avg_quality >= 0.3:
            notes.append(f"{mention_count} listings with decent quality")
            return True, "moderate", notes
        # Meets minimum but low quality and no Google confirmation
        notes.append(
            f"{mention_count} listings but limited corroboration "
            f"(single source, no Google data)"
        )
        return True, "weak", notes

    return False, None, [f"Insufficient evidence ({mention_count} listings)"]


# --------------------------------------------------------------------------
# Weighted statistics - quality-weighted averages
# --------------------------------------------------------------------------

def weighted_average(values, weights):
    """Calculate weighted average. Falls back to simple average if weights are zero."""
    if not values:
        return None
    total_weight = sum(weights)
    if total_weight == 0:
        return sum(values) / len(values)
    return sum(v * w for v, w in zip(values, weights)) / total_weight


def estimate_unique_sellers(listings):
    """
    Estimate number of unique sellers from URL patterns.
    Different URL bases = likely different sellers.
    """
    seller_signatures = set()
    for l in listings:
        url = l.get("url", "")
        if not url:
            continue
        # Extract shop/seller portion from URL
        if "etsy.com" in url:
            # Etsy URLs: /listing/ID/title -> different IDs = potentially same shop
            # but /shop/NAME -> different NAME = different seller
            parts = url.split("/")
            if "listing" in parts:
                idx = parts.index("listing")
                # Use a hash of listing ID as proxy (imperfect but useful)
                if idx + 1 < len(parts):
                    seller_signatures.add(("etsy", parts[idx + 1][:6]))
            else:
                seller_signatures.add(("etsy", url[:50]))
        elif "amazon.com" in url:
            # Different ASINs = likely different products/sellers
            if "/dp/" in url:
                asin = url.split("/dp/")[1][:10]
                seller_signatures.add(("amazon", asin))
            else:
                seller_signatures.add(("amazon", url[:50]))
        elif "spoonflower.com" in url:
            seller_signatures.add(("spoonflower", url[:60]))
        else:
            seller_signatures.add(("other", url[:40]))

    return len(seller_signatures)


# --------------------------------------------------------------------------
# Outlier detection for prices
# --------------------------------------------------------------------------

def remove_price_outliers(prices):
    """
    Remove extreme price outliers using IQR method.
    Returns filtered list of prices.
    """
    if len(prices) < 4:
        return prices  # Not enough data for outlier detection

    sorted_prices = sorted(prices)
    q1_idx = len(sorted_prices) // 4
    q3_idx = (3 * len(sorted_prices)) // 4
    q1 = sorted_prices[q1_idx]
    q3 = sorted_prices[q3_idx]
    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    filtered = [p for p in prices if lower <= p <= upper]
    return filtered if filtered else prices  # Don't return empty
