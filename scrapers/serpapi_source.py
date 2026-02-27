"""SerpAPI-powered data sources for high-volume, reliable data collection.

SerpAPI ($50/mo, 5000 searches) handles anti-bot detection and provides
clean JSON from Google, Etsy, Amazon, and more. This module uses three
SerpAPI endpoints:

1. Google Trends API — real-time search interest for fabric keywords
2. Google Shopping API — product listings with images, prices, and reviews
3. Google Images API — visual trend boards for each trend term

Each function checks for SERPAPI_KEY and returns empty if not configured,
allowing the rest of the pipeline to fall back to direct scrapers.
"""

import logging
import time
import requests
from datetime import datetime
from config import (
    SERPAPI_KEY, FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS, STYLE_TERMS,
)

logger = logging.getLogger(__name__)

SERPAPI_BASE = "https://serpapi.com/search.json"


def _has_key():
    return bool(SERPAPI_KEY)


def _call(params, label="SerpAPI"):
    """Make a SerpAPI request with error handling."""
    if not _has_key():
        return None
    params["api_key"] = SERPAPI_KEY
    try:
        resp = requests.get(SERPAPI_BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            logger.warning("%s error: %s", label, data["error"])
            return None
        return data
    except requests.RequestException as e:
        logger.warning("%s request failed: %s", label, e)
        return None


# =========================================================================
# 1. GOOGLE TRENDS via SerpAPI
# =========================================================================

def fetch_serpapi_trends():
    """Fetch Google Trends interest data via SerpAPI.

    Returns dict matching pytrends format:
        {keyword: {avg_interest, recent_interest, trending_up, interest}}
    """
    if not _has_key():
        return {}

    results = {}
    # Priority keywords — fabric + pattern + color + style
    all_keywords = (
        [
            "cotton fabric", "linen fabric", "jersey fabric", "velvet fabric",
            "quilting fabric", "organic cotton fabric", "double gauze fabric",
            "silk fabric", "bamboo fabric", "tencel fabric",
        ]
        + [
            "floral fabric", "botanical fabric", "geometric fabric",
            "striped fabric", "plaid fabric", "cottagecore fabric",
            "watercolor fabric", "ditsy fabric", "toile fabric",
            "abstract fabric",
        ]
        + [
            "sage green fabric", "terracotta fabric", "lavender fabric",
            "dusty rose fabric", "navy fabric", "emerald fabric",
            "cream fabric", "rust fabric", "forest green fabric",
            "teal fabric", "blush pink fabric", "ivory fabric",
        ]
        + [
            "sustainable fabric", "minimalist fabric", "bohemian fabric",
            "Scandinavian textile", "cottagecore sewing", "quiet luxury fabric",
        ]
    )

    consecutive_failures = 0
    for kw in all_keywords:
        if consecutive_failures >= 5:
            logger.warning(
                "SerpAPI Trends: stopping after %d consecutive failures. Got %d keywords.",
                consecutive_failures, len(results),
            )
            break

        data = _call({
            "engine": "google_trends",
            "q": kw,
            "data_type": "TIMESERIES",
            "date": "today 3-m",
            "geo": "US",
        }, label=f"Trends:{kw}")

        if not data:
            consecutive_failures += 1
            time.sleep(0.5)
            continue

        consecutive_failures = 0

        # Parse the interest_over_time data
        timeline = data.get("interest_over_time", {}).get("timeline_data", [])
        if timeline:
            all_values = []
            for point in timeline:
                for val_entry in point.get("values", []):
                    if val_entry.get("query", "").lower() == kw.lower():
                        try:
                            all_values.append(int(val_entry.get("value", "0")))
                        except (ValueError, TypeError):
                            pass

            if all_values:
                avg_interest = sum(all_values) / len(all_values)
                recent = all_values[-4:] if len(all_values) >= 4 else all_values
                recent_interest = sum(recent) / len(recent)

                results[kw] = {
                    "avg_interest": round(avg_interest, 1),
                    "recent_interest": round(recent_interest, 1),
                    "trending_up": recent_interest > avg_interest * 1.1,
                    "interest": round(recent_interest, 1),
                }

        time.sleep(0.3)  # Stay within rate limits

    logger.info("SerpAPI Trends: fetched %d/%d keywords", len(results), len(all_keywords))
    return results


# =========================================================================
# 2. GOOGLE SHOPPING — product listings with images and prices
# =========================================================================

SHOPPING_QUERIES = [
    # High-volume Etsy/Amazon type queries
    "fabric by the yard",
    "cotton fabric prints",
    "jersey fabric digital print",
    "quilting fabric trending",
    "designer fabric by the yard",
    "organic cotton fabric",
    "linen fabric by the yard",
    "floral cotton fabric",
    "botanical fabric print",
    "geometric print fabric",
    # Niche for our cotton jersey focus
    "cotton jersey knit fabric",
    "Scandinavian fabric print",
    "modern quilting cotton",
    "watercolor fabric by the yard",
    "cottagecore fabric sewing",
    "sage green fabric",
    "terracotta fabric",
    "lavender floral fabric",
]


def fetch_serpapi_shopping():
    """Fetch product listings from Google Shopping via SerpAPI.

    Returns listings in standard format with images, prices, and reviews.
    Each query returns ~40 products with images.
    """
    if not _has_key():
        return []

    all_listings = []
    seen_urls = set()
    consecutive_failures = 0

    for query in SHOPPING_QUERIES:
        if consecutive_failures >= 4:
            logger.warning(
                "SerpAPI Shopping: stopping after %d failures. Got %d listings.",
                consecutive_failures, len(all_listings),
            )
            break

        data = _call({
            "engine": "google_shopping",
            "q": query,
            "gl": "us",
            "hl": "en",
            "num": "40",
        }, label=f"Shopping:{query}")

        if not data:
            consecutive_failures += 1
            time.sleep(0.5)
            continue

        consecutive_failures = 0
        results = data.get("shopping_results", [])

        for item in results:
            url = item.get("link", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = item.get("title", "")
            if not title:
                continue

            # Determine source from URL
            source = "google_shopping"
            url_lower = url.lower()
            if "etsy.com" in url_lower:
                source = "etsy"
            elif "amazon.com" in url_lower:
                source = "amazon"
            elif "spoonflower.com" in url_lower:
                source = "spoonflower"
            elif "fabric.com" in url_lower or "joann.com" in url_lower:
                source = "fabric_retailer"

            # Extract price
            price = None
            price_raw = item.get("extracted_price") or item.get("price")
            if isinstance(price_raw, (int, float)):
                price = float(price_raw)
            elif isinstance(price_raw, str):
                import re
                match = re.search(r"[\d,.]+", price_raw.replace(",", ""))
                if match:
                    try:
                        price = float(match.group())
                    except ValueError:
                        pass

            # Extract tags from title
            tags = _extract_tags(title)

            listing = {
                "source": source,
                "title": title,
                "url": url,
                "price": price,
                "currency": "USD",
                "favorites": 0,
                "reviews": item.get("reviews", 0) or 0,
                "rating": item.get("rating"),
                "image_url": item.get("thumbnail", ""),
                "tags": tags,
            }
            all_listings.append(listing)

        logger.info("SerpAPI Shopping '%s': %d results", query, len(results))
        time.sleep(0.3)

    logger.info(
        "SerpAPI Shopping total: %d unique listings from %d queries",
        len(all_listings), len(SHOPPING_QUERIES),
    )
    return all_listings


# =========================================================================
# 3. GOOGLE IMAGES — visual trend boards
# =========================================================================

def fetch_serpapi_trend_images(terms=None):
    """Fetch trend-relevant images from Google Images via SerpAPI.

    Args:
        terms: List of trend terms to fetch images for. If None, uses
               top fabric/pattern/color terms.

    Returns list of image dicts ready for save_trend_images():
        [{term, category, image_url, source, listing_title, listing_url, price}]
    """
    if not _has_key():
        return []

    if terms is None:
        # Default: top colors + patterns + styles for visual trend board
        terms = [
            # Colors
            ("sage green fabric", "color"),
            ("terracotta fabric", "color"),
            ("lavender fabric", "color"),
            ("dusty rose fabric", "color"),
            ("emerald fabric", "color"),
            ("rust fabric", "color"),
            ("cream fabric", "color"),
            ("navy fabric", "color"),
            # Patterns
            ("floral print fabric", "pattern"),
            ("botanical print fabric", "pattern"),
            ("geometric fabric print", "pattern"),
            ("watercolor fabric", "pattern"),
            ("ditsy fabric print", "pattern"),
            ("cottagecore fabric", "pattern"),
            ("toile fabric", "pattern"),
            ("abstract fabric print", "pattern"),
            # Styles
            ("Scandinavian fabric design", "style"),
            ("minimalist textile", "style"),
            ("bohemian fabric", "style"),
        ]
    elif isinstance(terms, list) and terms and isinstance(terms[0], str):
        # Auto-classify plain string terms
        terms = [(_classify_term_query(t), t) for t in terms]
        terms = [(q, cat) for q, cat in terms]

    all_images = []
    consecutive_failures = 0

    for query, category in terms:
        if consecutive_failures >= 4:
            logger.warning(
                "SerpAPI Images: stopping after %d failures. Got %d images.",
                consecutive_failures, len(all_images),
            )
            break

        data = _call({
            "engine": "google_images",
            "q": query,
            "gl": "us",
            "hl": "en",
            "num": "10",
        }, label=f"Images:{query}")

        if not data:
            consecutive_failures += 1
            time.sleep(0.5)
            continue

        consecutive_failures = 0
        image_results = data.get("images_results", [])

        # Extract the clean term from query (remove "fabric", "print", "design")
        term = (
            query.lower()
            .replace(" fabric", "")
            .replace(" print", "")
            .replace(" design", "")
            .replace(" textile", "")
            .strip()
        )

        for img in image_results[:8]:
            image_url = img.get("original", "") or img.get("thumbnail", "")
            if not image_url:
                continue

            all_images.append({
                "term": term,
                "category": category,
                "image_url": image_url,
                "source": "google_images",
                "listing_title": img.get("title", "")[:200],
                "listing_url": img.get("link", ""),
                "price": None,
            })

        logger.info(
            "SerpAPI Images '%s': %d images", query, min(len(image_results), 8),
        )
        time.sleep(0.3)

    logger.info(
        "SerpAPI Images total: %d images for %d terms",
        len(all_images), len(terms),
    )
    return all_images


# =========================================================================
# 4. ETSY SEARCH via SerpAPI — reliable Etsy data from cloud IPs
# =========================================================================

ETSY_SERPAPI_QUERIES = [
    "fabric by the yard site:etsy.com",
    "cotton jersey fabric site:etsy.com",
    "quilting cotton trending site:etsy.com",
    "organic cotton fabric site:etsy.com",
    "floral fabric site:etsy.com",
    "botanical print fabric site:etsy.com",
    "geometric print fabric site:etsy.com",
    "designer fabric yard site:etsy.com",
    "modern quilting fabric site:etsy.com",
    "digital print cotton site:etsy.com",
    "Scandinavian fabric site:etsy.com",
    "sage green fabric site:etsy.com",
    "cottagecore fabric site:etsy.com",
]


def fetch_serpapi_etsy():
    """Fetch Etsy listings via Google Search (SerpAPI).

    This is the most reliable way to get Etsy data from cloud IPs since
    SerpAPI handles all anti-bot detection. Returns standard listings with
    images, prices from Google's rich snippets.
    """
    if not _has_key():
        return []

    all_listings = []
    seen_urls = set()
    consecutive_failures = 0

    for query in ETSY_SERPAPI_QUERIES:
        if consecutive_failures >= 4:
            break

        data = _call({
            "engine": "google",
            "q": query,
            "gl": "us",
            "hl": "en",
            "num": "30",
        }, label=f"Etsy-SERP:{query}")

        if not data:
            consecutive_failures += 1
            time.sleep(0.5)
            continue

        consecutive_failures = 0

        # Parse organic results
        for result in data.get("organic_results", []):
            url = result.get("link", "")
            if "etsy.com/listing/" not in url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = result.get("title", "")
            snippet = result.get("snippet", "")

            # Try to get price from rich snippet
            price = None
            rich = result.get("rich_snippet", {})
            if rich:
                for attr in rich.get("top", {}).get("detected_extensions", {}).values():
                    if isinstance(attr, (int, float)):
                        price = float(attr)
                        break
                price_text = rich.get("top", {}).get("extensions", [])
                for ext in (price_text if isinstance(price_text, list) else []):
                    if "$" in str(ext):
                        import re
                        m = re.search(r"[\d,.]+", str(ext))
                        if m:
                            try:
                                price = float(m.group().replace(",", ""))
                            except ValueError:
                                pass

            # Extract image from thumbnail
            image_url = result.get("thumbnail", "")

            # Extract rating
            rating = None
            if rich:
                rating = rich.get("top", {}).get("detected_extensions", {}).get("rating")

            reviews = 0
            if rich:
                reviews = rich.get("top", {}).get("detected_extensions", {}).get("reviews", 0) or 0

            tags = _extract_tags(title + " " + snippet)

            all_listings.append({
                "source": "etsy",
                "title": title[:200],
                "url": url,
                "price": price,
                "currency": "USD",
                "favorites": 0,
                "reviews": int(reviews) if reviews else 0,
                "rating": float(rating) if rating else None,
                "image_url": image_url,
                "tags": tags,
            })

        # Also parse shopping results if present
        for item in data.get("shopping_results", []):
            url = item.get("link", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            if "etsy.com" not in url.lower():
                continue

            title = item.get("title", "")
            price = item.get("extracted_price")
            if isinstance(price, str):
                import re
                m = re.search(r"[\d,.]+", price.replace(",", ""))
                price = float(m.group()) if m else None

            all_listings.append({
                "source": "etsy",
                "title": title[:200],
                "url": url,
                "price": float(price) if price else None,
                "currency": "USD",
                "favorites": 0,
                "reviews": item.get("reviews", 0) or 0,
                "rating": item.get("rating"),
                "image_url": item.get("thumbnail", ""),
                "tags": _extract_tags(title),
            })

        logger.info("SerpAPI Etsy '%s': found %d listings so far", query[:40], len(all_listings))
        time.sleep(0.3)

    logger.info(
        "SerpAPI Etsy total: %d unique listings from %d queries",
        len(all_listings), len(ETSY_SERPAPI_QUERIES),
    )
    return all_listings


# =========================================================================
# Helpers
# =========================================================================

def _extract_tags(text):
    """Extract trend-relevant tags from text."""
    if not text:
        return []
    text_lower = text.lower()
    tags = []
    for term in FABRIC_TYPES + PATTERN_TYPES + COLOR_TERMS + STYLE_TERMS:
        if term.lower() in text_lower:
            tags.append(term)
    return tags


def _classify_term_query(term):
    """Build a search query from a trend term and classify its category."""
    term_lower = term.lower()
    for color in COLOR_TERMS:
        if color.lower() in term_lower:
            return f"{term} fabric", "color"
    for pattern in PATTERN_TYPES:
        if pattern.lower() in term_lower:
            return f"{term} fabric print", "pattern"
    for style in STYLE_TERMS:
        if style.lower() in term_lower:
            return f"{term} textile", "style"
    return f"{term} fabric", "fabric_type"


def get_serpapi_summary():
    """Return a summary of what SerpAPI can provide."""
    if not _has_key():
        return {
            "configured": False,
            "note": "Set SERPAPI_KEY env var for 10x data volume",
        }
    return {
        "configured": True,
        "endpoints": ["Google Trends", "Google Shopping", "Google Images", "Etsy via SERP"],
        "note": "High-volume data collection active",
    }
