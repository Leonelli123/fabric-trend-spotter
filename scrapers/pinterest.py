"""Pinterest scraper for fabric trend discovery.

Pinterest is one of the strongest signals for fabric/textile trends because
the platform skews heavily toward craft, sewing, home decor, and fashion.

Approach:
- Use Pinterest's internal search API (same endpoint their frontend calls)
- Requires: (1) session cookies from homepage, (2) CSRF token in headers
- Extract pin data: descriptions, images, save counts, outbound links
- Pins become listings that feed into the existing analysis pipeline
"""

import logging
import json
import time
import requests
from datetime import datetime
from config import FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS

logger = logging.getLogger(__name__)

PINTEREST_SEARCH_API = "https://www.pinterest.com/resource/BaseSearchResource/get/"

# Fabric-focused search queries for Pinterest
PINTEREST_QUERIES = [
    "fabric trends",
    "trending fabric 2026",
    "quilting fabric popular",
    "linen fabric aesthetic",
    "cotton fabric prints",
    "velvet fabric decor",
    "floral fabric pattern",
    "botanical print fabric",
    "cottagecore fabric sewing",
    "modern quilting fabric",
    "upholstery fabric trending",
    "dress fabric ideas",
    "sustainable fabric",
    "designer fabric prints",
    "fabric by the yard",
]


def _create_pinterest_session():
    """Create a session with Pinterest cookies and CSRF token.

    Pinterest's internal API requires:
    1. Valid session cookies (obtained by visiting the homepage)
    2. CSRF token sent in the X-CSRFToken header
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })

    # Visit homepage to get cookies
    try:
        resp = session.get("https://www.pinterest.com/", timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Failed to initialize Pinterest session: %s", e)
        return None

    csrf = session.cookies.get("csrftoken", "")
    if not csrf:
        logger.warning("No CSRF token from Pinterest homepage")
        return None

    # Set headers for the internal API
    session.headers.update({
        "Accept": "application/json, text/javascript, */*, q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrf,
        "X-Pinterest-AppState": "active",
        "X-Pinterest-PWS-Handler": "www/search/[scope].js",
    })

    return session


def _search_pinterest(session, query):
    """Execute a single Pinterest search query via their internal API.

    Returns a list of pin dicts from the response.
    """
    encoded_query = requests.utils.quote(query)
    source_url = f"/search/pins/?q={encoded_query}"
    session.headers["X-Pinterest-Source-Url"] = source_url
    session.headers["Referer"] = f"https://www.pinterest.com{source_url}"

    params = {
        "source_url": source_url,
        "data": json.dumps({
            "options": {
                "query": query,
                "scope": "pins",
                "no_fetch_context_on_resource": False,
            },
            "context": {},
        }),
    }

    try:
        resp = session.get(PINTEREST_SEARCH_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        logger.warning("Pinterest API error for '%s': %s", query, e)
        return []

    # Extract pins from the response.
    # Pinterest returns two result formats:
    #   1. type="story" — grouped results with pins nested in objects[]
    #   2. type="pin" — standalone pin at the top level
    pins = []
    results = (
        data.get("resource_response", {}).get("data", {}).get("results", [])
    )

    for result in results:
        if not isinstance(result, dict):
            continue

        # Standalone pin result
        if result.get("type") == "pin":
            pins.append(result)
            continue

        # Story result with nested pin objects
        objects = result.get("objects", [])
        if isinstance(objects, list):
            for obj in objects:
                if isinstance(obj, dict) and obj.get("type") == "pin":
                    pins.append(obj)

    return pins


def scrape_pinterest():
    """Scrape Pinterest search results for fabric trend data.

    Returns a list of listing dicts compatible with the analysis pipeline.
    """
    session = _create_pinterest_session()
    if not session:
        logger.warning("Could not create Pinterest session, skipping")
        return []

    all_listings = []
    consecutive_failures = 0

    for query in PINTEREST_QUERIES:
        if consecutive_failures >= 3:
            logger.warning(
                "Stopping Pinterest scrape after %d consecutive failures. "
                "Got %d listings so far.", consecutive_failures, len(all_listings)
            )
            break

        logger.info("Searching Pinterest for: %s", query)
        pins = _search_pinterest(session, query)

        if pins:
            for pin in pins:
                listing = _pin_to_listing(pin)
                if listing:
                    all_listings.append(listing)
            consecutive_failures = 0
            logger.info("Pinterest '%s': got %d pins", query, len(pins))
        else:
            consecutive_failures += 1
            logger.warning("Pinterest '%s': no pins returned", query)

        # Polite delay between API requests
        time.sleep(2)

    # Deduplicate by pin ID (stored in URL) or title
    seen = set()
    unique_listings = []
    for listing in all_listings:
        key = listing.get("url", "") or listing["title"].lower().strip()[:80]
        if key and key not in seen:
            seen.add(key)
            unique_listings.append(listing)

    logger.info(
        "Pinterest scrape complete: %d unique listings from %d total",
        len(unique_listings), len(all_listings),
    )
    return unique_listings


def _pin_to_listing(pin):
    """Convert a Pinterest pin API object to our standard listing format."""
    # Description is the primary text for pins
    title = (
        pin.get("description")
        or pin.get("grid_title")
        or pin.get("title")
        or pin.get("seo_alt_text")
        or ""
    )
    if not title or len(title.strip()) < 5:
        return None

    # Get image URL (prefer original, fall back to smaller sizes)
    image_url = ""
    images = pin.get("images", {})
    if isinstance(images, dict):
        for size_key in ("orig", "736x", "564x", "474x", "236x"):
            if size_key in images:
                image_url = images[size_key].get("url", "")
                if image_url:
                    break

    # Get save/repin count
    saves = pin.get("repin_count", 0) or 0
    # Also check aggregated stats
    agg = pin.get("aggregated_pin_data")
    if isinstance(agg, dict):
        agg_stats = agg.get("aggregated_stats", {})
        if isinstance(agg_stats, dict):
            agg_saves = agg_stats.get("saves", 0)
            if agg_saves and agg_saves > saves:
                saves = agg_saves

    # Get outbound link (where the pin points to)
    url = pin.get("link", "") or ""
    pin_id = pin.get("id", "")
    if not url and pin_id:
        url = f"https://www.pinterest.com/pin/{pin_id}/"

    # Extract tags from title text
    tags = _extract_fabric_tags(title)

    return {
        "source": "pinterest",
        "title": title[:300].strip(),
        "url": url,
        "price": None,
        "currency": "USD",
        "favorites": saves,
        "reviews": 0,
        "rating": None,
        "image_url": image_url,
        "tags": tags,
    }


def _extract_fabric_tags(text):
    """Extract fabric-related tags from text."""
    if not text:
        return []
    text_lower = text.lower()
    tags = []
    for term in FABRIC_TYPES + PATTERN_TYPES + COLOR_TERMS:
        if term.lower() in text_lower:
            tags.append(term)
    return tags


def analyze_pinterest_data(listings):
    """Analyze Pinterest listings to extract fabric trend signals.

    Based on pin saves/repins as the engagement metric.

    Args:
        listings: List of Pinterest listing dicts from scrape_pinterest()

    Returns:
        dict with trend signals organized by category
    """
    if not listings:
        return {}

    fabric_signals = {}
    pattern_signals = {}
    color_signals = {}

    for listing in listings:
        title_lower = listing.get("title", "").lower()
        tags = [t.lower() for t in listing.get("tags", [])]
        saves = listing.get("favorites", 0) or 0
        combined = title_lower + " " + " ".join(tags)

        # Signal strength: base 1 per pin + saves bonus
        signal_strength = 1 + (saves * 0.1)

        for term in FABRIC_TYPES:
            if term.lower() in combined:
                fabric_signals[term] = fabric_signals.get(term, 0) + signal_strength

        for term in PATTERN_TYPES:
            if term.lower() in combined:
                pattern_signals[term] = pattern_signals.get(term, 0) + signal_strength

        for term in COLOR_TERMS:
            if term.lower() in combined:
                color_signals[term] = color_signals.get(term, 0) + signal_strength

    def sorted_signals(signals):
        return sorted(
            [{"term": k, "pinterest_score": round(v, 1)} for k, v in signals.items()],
            key=lambda x: x["pinterest_score"],
            reverse=True,
        )

    # Top pins by saves, with images
    top_pins = sorted(
        [
            {
                "title": l["title"][:80],
                "saves": l.get("favorites", 0),
                "image_url": l.get("image_url", ""),
                "url": l.get("url", ""),
                "tags": l.get("tags", [])[:5],
            }
            for l in listings
            if l.get("image_url")
        ],
        key=lambda x: x["saves"],
        reverse=True,
    )

    return {
        "fabric_signals": sorted_signals(fabric_signals),
        "pattern_signals": sorted_signals(pattern_signals),
        "color_signals": sorted_signals(color_signals),
        "top_pins": top_pins[:20],
        "total_pins_analyzed": len(listings),
        "fetched_at": datetime.now().isoformat(),
    }
