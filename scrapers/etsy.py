"""Etsy scraper for trending fabric listings."""

import logging
import re
from bs4 import BeautifulSoup
from scrapers.base import get_session, fetch_page, extract_price, extract_number
from config import ETSY_API_KEY

logger = logging.getLogger(__name__)

ETSY_SEARCH_URL = "https://www.etsy.com/search"
ETSY_API_URL = "https://openapi.etsy.com/v3/application"

SEARCH_QUERIES = [
    "trending fabric by the yard",
    "popular quilting fabric",
    "bestselling fabric 2026",
    "fabric by the yard",
    "designer fabric",
    "upholstery fabric trending",
    "apparel fabric popular",
    "cotton fabric new",
]


def scrape_etsy():
    """Scrape Etsy for trending fabric listings."""
    if ETSY_API_KEY:
        return _scrape_via_api()
    return _scrape_via_web()


def _scrape_via_api():
    """Use Etsy Open API v3 when key is available."""
    import requests

    listings = []
    headers = {"x-api-key": ETSY_API_KEY}
    for query in SEARCH_QUERIES[:4]:
        try:
            resp = requests.get(
                f"{ETSY_API_URL}/listings/active",
                headers=headers,
                params={
                    "keywords": query,
                    "sort_on": "score",
                    "limit": 25,
                    "includes": "Images",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("results", []):
                listings.append({
                    "source": "etsy",
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "price": item.get("price", {}).get("amount", 0) / 100,
                    "currency": item.get("price", {}).get("currency_code", "USD"),
                    "favorites": item.get("num_favorers", 0),
                    "reviews": item.get("quantity_sold", 0),
                    "rating": None,
                    "image_url": "",
                    "tags": item.get("tags", []),
                })
        except Exception as e:
            logger.warning("Etsy API error for '%s': %s", query, e)
    return listings


def _scrape_via_web():
    """Scrape Etsy search results from the web."""
    session = get_session()
    listings = []

    for query in SEARCH_QUERIES:
        logger.info("Scraping Etsy for: %s", query)
        resp = fetch_page(session, ETSY_SEARCH_URL, params={
            "q": query,
            "ref": "search_bar",
            "order": "most_relevant",
        })
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        # Etsy uses data-listing-id on result cards
        result_cards = soup.select("[data-listing-id]")
        if not result_cards:
            # Fallback: try generic card selectors
            result_cards = soup.select(".v2-listing-card, .search-listing-card")

        for card in result_cards[:25]:
            try:
                listing = _parse_listing_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug("Error parsing Etsy card: %s", e)

        # Also try parsing from JSON-LD structured data
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "ItemList":
                    for item in data.get("itemListElement", []):
                        product = item.get("item", {})
                        if product:
                            listings.append({
                                "source": "etsy",
                                "title": product.get("name", ""),
                                "url": product.get("url", ""),
                                "price": extract_price(
                                    str(product.get("offers", {}).get("price", ""))
                                ),
                                "currency": product.get("offers", {}).get(
                                    "priceCurrency", "USD"
                                ),
                                "favorites": 0,
                                "reviews": 0,
                                "rating": None,
                                "image_url": product.get("image", ""),
                                "tags": [],
                            })
            except (json.JSONDecodeError, AttributeError):
                pass

    logger.info("Scraped %d Etsy listings", len(listings))
    return listings


def _parse_listing_card(card):
    """Parse a single Etsy listing card."""
    title_el = card.select_one(
        ".v2-listing-card__title, .listing-card__title, h3, h2"
    )
    title = title_el.get_text(strip=True) if title_el else ""
    if not title:
        return None

    link_el = card.select_one("a[href]")
    url = link_el["href"] if link_el else ""
    if url and not url.startswith("http"):
        url = "https://www.etsy.com" + url

    price_el = card.select_one(
        ".currency-value, .lc-price .wt-text-title-01, span[class*='price']"
    )
    price = extract_price(price_el.get_text()) if price_el else None

    img_el = card.select_one("img[src]")
    image_url = img_el.get("src", "") if img_el else ""

    # Try to find favorites count
    fav_el = card.select_one("[class*='favorite'], [class*='heart']")
    favorites = extract_number(fav_el.get_text()) if fav_el else 0

    # Extract implicit tags from title
    tags = _extract_tags_from_title(title)

    return {
        "source": "etsy",
        "title": title,
        "url": url,
        "price": price,
        "currency": "USD",
        "favorites": favorites,
        "reviews": 0,
        "rating": None,
        "image_url": image_url,
        "tags": tags,
    }


def _extract_tags_from_title(title):
    """Extract relevant keywords from a listing title."""
    title_lower = title.lower()
    tags = []
    # Check for fabric types, patterns, and colors
    from config import FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS
    for term in FABRIC_TYPES + PATTERN_TYPES + COLOR_TERMS:
        if term.lower() in title_lower:
            tags.append(term)
    return tags
