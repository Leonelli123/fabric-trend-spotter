"""Pinterest scraper for fabric trend discovery.

Pinterest is one of the strongest signals for fabric/textile trends because
the platform skews heavily toward craft, sewing, home decor, and fashion.

Approach:
- Search Pinterest for fabric-related queries
- Extract pin data from search results (titles, save counts, images)
- Pins become listings that feed into the existing analysis pipeline
- Aggregate Pinterest-specific trend signals (most saved, trending topics)
"""

import logging
import json
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
from scrapers.base import get_session, fetch_page, extract_number
from config import FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS

logger = logging.getLogger(__name__)

PINTEREST_SEARCH_URL = "https://www.pinterest.com/search/pins/"

# Fabric-focused search queries for Pinterest
PINTEREST_QUERIES = [
    "trending fabric 2026",
    "fabric trends sewing",
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
    "fabric color trends",
    "sustainable fabric sewing",
    "designer fabric prints",
]

# Pinterest-specific trend hashtags/topics to monitor
PINTEREST_TREND_TOPICS = [
    "fabric trends", "sewing trends", "quilting trends",
    "textile design", "fabric prints", "pattern design",
    "home fabric", "apparel fabric", "craft fabric",
    "linen aesthetic", "cottagecore sewing", "modern quilting",
]


def scrape_pinterest():
    """Scrape Pinterest search results for fabric trend data.

    Returns a list of listing dicts compatible with the analysis pipeline.
    """
    session = get_session()
    # Pinterest needs specific headers
    session.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })

    all_listings = []
    consecutive_failures = 0

    for query in PINTEREST_QUERIES:
        if consecutive_failures >= 3:
            logger.warning(
                "Stopping Pinterest scrape after %d consecutive failures. "
                "Got %d listings so far.", consecutive_failures, len(all_listings)
            )
            break

        logger.info("Scraping Pinterest for: %s", query)
        resp = fetch_page(session, PINTEREST_SEARCH_URL, params={"q": query})

        if not resp:
            consecutive_failures += 1
            continue

        listings = _parse_pinterest_response(resp.text, query)

        if listings:
            all_listings.extend(listings)
            consecutive_failures = 0
            logger.info("Pinterest '%s': got %d pins", query, len(listings))
        else:
            consecutive_failures += 1
            logger.warning("Pinterest '%s': no pins extracted", query)

        # Polite delay between requests
        time.sleep(2)

    # Deduplicate by title
    seen_titles = set()
    unique_listings = []
    for listing in all_listings:
        title_key = listing["title"].lower().strip()[:80]
        if title_key and title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_listings.append(listing)

    logger.info(
        "Pinterest scrape complete: %d unique listings from %d total",
        len(unique_listings), len(all_listings)
    )
    return unique_listings


def _parse_pinterest_response(html, query):
    """Parse Pinterest search results page.

    Pinterest embeds pin data in multiple ways:
    1. JSON-LD structured data
    2. __PWS_DATA__ script tag (React state)
    3. Standard HTML pin elements
    """
    listings = []
    soup = BeautifulSoup(html, "html.parser")

    # Method 1: Try extracting from embedded JSON data
    listings.extend(_extract_from_pws_data(soup))

    # Method 2: Try JSON-LD structured data
    listings.extend(_extract_from_json_ld(soup))

    # Method 3: Parse HTML pin cards as fallback
    if not listings:
        listings.extend(_extract_from_html(soup, query))

    return listings


def _extract_from_pws_data(soup):
    """Extract pin data from Pinterest's __PWS_DATA__ React state."""
    listings = []

    for script in soup.find_all("script", {"id": "__PWS_DATA__"}):
        try:
            data = json.loads(script.string)
            pins = _find_pins_in_data(data)
            for pin in pins:
                listing = _pin_to_listing(pin)
                if listing:
                    listings.append(listing)
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    return listings


def _find_pins_in_data(data, depth=0):
    """Recursively search for pin objects in nested Pinterest data."""
    pins = []
    if depth > 10:
        return pins

    if isinstance(data, dict):
        # Check if this dict looks like a pin
        if data.get("type") == "pin" or (
            "id" in data and "description" in data and "images" in data
        ):
            pins.append(data)

        # Check for grid items or search results
        for key in ("results", "data", "pins", "resource_response",
                     "grid_items", "items", "nodes"):
            if key in data:
                pins.extend(_find_pins_in_data(data[key], depth + 1))

        # Recurse into nested dicts
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                pins.extend(_find_pins_in_data(value, depth + 1))

    elif isinstance(data, list):
        for item in data[:100]:  # Limit to prevent runaway recursion
            pins.extend(_find_pins_in_data(item, depth + 1))

    return pins


def _pin_to_listing(pin):
    """Convert a Pinterest pin data dict to our standard listing format."""
    title = pin.get("title") or pin.get("description") or pin.get("grid_title") or ""
    if not title or len(title) < 5:
        return None

    # Get image URL
    image_url = ""
    images = pin.get("images", {})
    if isinstance(images, dict):
        for size_key in ("orig", "736x", "564x", "474x", "236x"):
            if size_key in images:
                image_url = images[size_key].get("url", "")
                if image_url:
                    break

    # Get save/repin count as a proxy for popularity
    saves = pin.get("repin_count", 0) or pin.get("aggregated_pin_data", {}).get(
        "aggregated_stats", {}
    ).get("saves", 0)

    # Get link
    url = pin.get("link", "") or pin.get("rich_summary", {}).get("url", "")
    pin_id = pin.get("id", "")
    if not url and pin_id:
        url = f"https://www.pinterest.com/pin/{pin_id}/"

    # Extract tags from title
    tags = _extract_fabric_tags(title)

    return {
        "source": "pinterest",
        "title": title[:300],
        "url": url,
        "price": None,
        "currency": "USD",
        "favorites": saves,
        "reviews": 0,
        "rating": None,
        "image_url": image_url,
        "tags": tags,
    }


def _extract_from_json_ld(soup):
    """Extract pin data from JSON-LD structured data."""
    listings = []

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    listing = _json_ld_to_listing(item)
                    if listing:
                        listings.append(listing)
            elif isinstance(data, dict):
                listing = _json_ld_to_listing(data)
                if listing:
                    listings.append(listing)
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    return listings


def _json_ld_to_listing(item):
    """Convert a JSON-LD item to a listing."""
    item_type = item.get("@type", "")
    if item_type not in ("ImageObject", "CreativeWork", "Product", "Article"):
        return None

    title = item.get("name", "") or item.get("headline", "")
    if not title or len(title) < 5:
        return None

    image_url = item.get("image", "")
    if isinstance(image_url, list):
        image_url = image_url[0] if image_url else ""
    if isinstance(image_url, dict):
        image_url = image_url.get("url", "")

    return {
        "source": "pinterest",
        "title": title[:300],
        "url": item.get("url", ""),
        "price": None,
        "currency": "USD",
        "favorites": 0,
        "reviews": 0,
        "rating": None,
        "image_url": image_url,
        "tags": _extract_fabric_tags(title),
    }


def _extract_from_html(soup, query):
    """Parse Pinterest HTML pin cards as a fallback."""
    listings = []

    # Try various pin card selectors
    pin_cards = soup.select(
        "[data-test-id='pin'], [data-test-pin-id], "
        ".pinWrapper, .Collection-Item, article"
    )

    for card in pin_cards[:30]:
        try:
            # Title from alt text or aria-label
            title = ""
            img = card.select_one("img[alt]")
            if img:
                title = img.get("alt", "")
                image_url = img.get("src", "")
            else:
                image_url = ""

            if not title:
                title_el = card.select_one("[title], h3, h4")
                if title_el:
                    title = title_el.get_text(strip=True)

            if not title or len(title) < 5:
                continue

            # Link
            link_el = card.select_one("a[href*='/pin/']")
            url = ""
            if link_el:
                href = link_el.get("href", "")
                url = href if href.startswith("http") else f"https://www.pinterest.com{href}"

            listings.append({
                "source": "pinterest",
                "title": title[:300],
                "url": url,
                "price": None,
                "currency": "USD",
                "favorites": 0,
                "reviews": 0,
                "rating": None,
                "image_url": image_url,
                "tags": _extract_fabric_tags(title),
            })
        except Exception as e:
            logger.debug("Error parsing Pinterest card: %s", e)

    return listings


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

    Similar to Instagram analysis but based on pin saves/repins
    instead of hashtag engagement.

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
        saves = listing.get("favorites", 0)
        combined = title_lower + " " + " ".join(tags)

        # Signal strength is based on save count
        signal_strength = 1 + (saves * 0.1)  # Base 1 + saves bonus

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

    # Top pins by saves
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
            if l.get("favorites", 0) > 0 or l.get("image_url")
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
