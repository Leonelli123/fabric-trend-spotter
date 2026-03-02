"""Spoonflower scraper using Pythias search API.

Spoonflower migrated to a Next.js client-side rendered site. The old
HTML scraping approach no longer works. This version calls their
internal Pythias search API directly.
"""

import logging
import time
from config import FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS, STYLE_TERMS

logger = logging.getLogger(__name__)

PYTHIAS_URL = "https://pythias.spoonflower.com/search/v3/designs"

# Topic filters available on Spoonflower
TOPIC_FILTERS = [
    "animals", "geometric", "abstract", "stripes", "plaid",
    "holiday", "vintage", "nature", "floral", "botanical",
]

# Sort options to get different signals
SORT_OPTIONS = [
    ("bestSelling", "m"),   # best sellers = strongest demand signal
]


def scrape_spoonflower():
    """Scrape Spoonflower for trending fabric designs via their search API."""
    import requests

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.spoonflower.com/",
        "Origin": "https://www.spoonflower.com",
    })

    all_designs = {}  # keyed by designId to deduplicate
    consecutive_failures = 0

    # Fetch bestselling and most favorited
    for sort_key, test_variant in SORT_OPTIONS:
        if consecutive_failures >= 3:
            break
        designs = _fetch_designs(session, {
            "sort": sort_key,
            "page_locale": "en",
            "testVariant": test_variant,
            "page_size": "48",
            "page_offset": "1",
        })
        if designs is None:
            consecutive_failures += 1
            continue
        consecutive_failures = 0
        for d in designs:
            all_designs[d["designId"]] = d
        time.sleep(1)

    # Fetch by topic filters for broader coverage
    for topic in TOPIC_FILTERS:
        if consecutive_failures >= 3:
            break
        designs = _fetch_designs(session, {
            "sort": "bestSelling",
            "topic": topic,
            "page_locale": "en",
            "testVariant": "m",
            "page_size": "24",
            "page_offset": "1",
        })
        if designs is None:
            consecutive_failures += 1
            continue
        consecutive_failures = 0
        for d in designs:
            all_designs[d["designId"]] = d
        time.sleep(0.8)

    # Convert to standard listing format
    listings = []
    for design in all_designs.values():
        listing = _design_to_listing(design)
        if listing:
            listings.append(listing)

    logger.info("Scraped %d unique Spoonflower designs", len(listings))
    return listings


def _fetch_designs(session, params):
    """Fetch designs from the Pythias API."""
    try:
        resp = session.get(PYTHIAS_URL, params=params, timeout=5)
        if resp.status_code != 200:
            logger.warning("Spoonflower API returned %d", resp.status_code)
            return None
        data = resp.json()
        results = data.get("page_results", [])
        sort = params.get("sort", "?")
        topic = params.get("topic", "all")
        logger.info("Spoonflower %s/%s: %d designs", sort, topic, len(results))
        return results
    except Exception as e:
        logger.warning("Spoonflower API error: %s", e)
        return None


def _design_to_listing(design):
    """Convert a Spoonflower API design object to a standard listing."""
    name = design.get("name", "")
    if not name or len(name) < 3:
        return None

    design_id = design.get("designId", "")
    slug = design.get("slug", "")
    url = f"https://www.spoonflower.com/en/fabric/{slug}" if slug else ""

    # Build image URL from thumbnail
    thumbnail = design.get("thumbnail", "")
    image_url = f"https://images.spoonflower.com/thumbnail/{thumbnail}" if thumbnail else ""

    # Extract engagement signals
    favorites = design.get("numFavorites", 0) or 0
    orders = design.get("orders", 0) or 0

    # Extract designer info
    user = design.get("user", {})
    designer = user.get("screenName", "")

    # Extract tags from design tags + name
    tags = _extract_tags(name, design.get("tags", []))
    if designer:
        tags.append(f"designer:{designer}")

    return {
        "source": "spoonflower",
        "title": name,
        "url": url,
        "price": None,  # API doesn't return prices (fabric priced on checkout)
        "currency": "USD",
        "favorites": favorites,
        "reviews": orders,  # use orders as a proxy for reviews/demand
        "rating": None,
        "image_url": image_url,
        "tags": tags,
    }


def _extract_tags(title, api_tags):
    """Extract trend-relevant tags from title and Spoonflower's own tags."""
    tags = []
    combined = (title + " " + " ".join(api_tags or [])).lower()

    for term in FABRIC_TYPES + PATTERN_TYPES + COLOR_TERMS + STYLE_TERMS:
        if term.lower() in combined:
            tags.append(term)

    # Also extract common Spoonflower-specific themes
    theme_map = {
        "cottagecore": "cottagecore",
        "boho": "bohemian",
        "whimsical": "whimsical",
        "vintage": "vintage",
        "retro": "retro",
        "modern": "modern",
        "minimalist": "minimalist",
        "maximalist": "maximalist",
        "folk": "folk art",
        "tropical": "tropical",
        "botanical": "botanical",
        "celestial": "celestial",
        "watercolor": "watercolor",
        "ditsy": "ditsy",
        "toile": "toile",
    }
    for keyword, tag in theme_map.items():
        if keyword in combined and tag not in tags:
            tags.append(tag)

    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique_tags.append(t)
    return unique_tags
