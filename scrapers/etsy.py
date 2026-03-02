"""Etsy scraper for trending fabric listings.

Three scraping strategies in order of reliability:
1. Etsy Open API v3 (if ETSY_API_KEY is set)
2. Etsy internal search API (JSON endpoint their frontend uses)
3. Web scraping with enhanced anti-detection + JSON-LD fallback
"""

import logging
import re
import json
import time
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

# More targeted queries for the jersey/print niche
NICHE_QUERIES = [
    "cotton jersey fabric print",
    "organic cotton jersey",
    "digital print fabric by the yard",
    "floral cotton fabric",
    "botanical fabric by the yard",
    "geometric print fabric",
    "Scandinavian fabric print",
    "modern quilting fabric",
]


def scrape_etsy():
    """Scrape Etsy for trending fabric listings.

    Tries three strategies in order of reliability.
    """
    if ETSY_API_KEY:
        logger.info("Using Etsy Open API v3")
        return _scrape_via_api()

    # Try internal JSON API first (more reliable from cloud)
    logger.info("No API key. Trying Etsy internal search API...")
    listings = _scrape_via_internal_api()
    if listings and len(listings) >= 10:
        logger.info("Etsy internal API returned %d listings", len(listings))
        return listings

    # Fall back to enhanced web scraping
    logger.info("Internal API got %d listings, trying web scraping...", len(listings))
    web_listings = _scrape_via_web()
    all_listings = listings + web_listings

    if not all_listings:
        logger.warning(
            "All Etsy scraping methods failed (likely IP-blocked). "
            "Etsy data will be empty this run."
        )
    return all_listings


def _scrape_via_api():
    """Use Etsy Open API v3 when key is available."""
    import requests

    listings = []
    headers = {"x-api-key": ETSY_API_KEY}
    for query in (SEARCH_QUERIES[:4] + NICHE_QUERIES[:4]):
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


def _scrape_via_internal_api():
    """Try Etsy's internal search API that their frontend uses.

    Etsy's Next.js frontend fetches search results from an internal endpoint
    that returns JSON. This is more reliable than HTML scraping because it
    doesn't require JavaScript rendering.
    """
    import requests

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    })

    listings = []
    consecutive_failures = 0

    # First, establish a session by visiting the homepage
    try:
        session.get("https://www.etsy.com/", timeout=10)
        time.sleep(1)
    except requests.RequestException:
        pass  # Continue anyway

    queries = SEARCH_QUERIES[:5] + NICHE_QUERIES[:3]
    for query in queries:
        if consecutive_failures >= 3:
            logger.warning(
                "Stopping Etsy internal API after %d failures", consecutive_failures
            )
            break

        try:
            # Etsy serves search pages that embed JSON data in a __NEXT_DATA__ script
            resp = session.get(
                ETSY_SEARCH_URL,
                params={
                    "q": query,
                    "ref": "search_bar",
                    "order": "most_relevant",
                },
                timeout=15,
                allow_redirects=True,
            )

            if resp.status_code != 200:
                consecutive_failures += 1
                logger.warning("Etsy returned %d for '%s'", resp.status_code, query)
                time.sleep(2)
                continue

            html = resp.text

            # Strategy A: Extract from __NEXT_DATA__ JSON (Next.js pages)
            next_data = _extract_next_data(html)
            if next_data:
                page_listings = _parse_next_data_listings(next_data)
                if page_listings:
                    listings.extend(page_listings)
                    consecutive_failures = 0
                    logger.info(
                        "Etsy __NEXT_DATA__ for '%s': %d listings",
                        query, len(page_listings),
                    )
                    time.sleep(1.5)
                    continue

            # Strategy B: Extract from JSON-LD structured data
            ld_listings = _extract_json_ld(html)
            if ld_listings:
                listings.extend(ld_listings)
                consecutive_failures = 0
                logger.info(
                    "Etsy JSON-LD for '%s': %d listings", query, len(ld_listings),
                )
                time.sleep(1.5)
                continue

            # Strategy C: Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            html_listings = _parse_html_listings(soup)
            soup.decompose()  # free BS4 tree immediately
            if html_listings:
                listings.extend(html_listings)
                consecutive_failures = 0
                logger.info(
                    "Etsy HTML parse for '%s': %d listings",
                    query, len(html_listings),
                )
                time.sleep(1.5)
                continue

            consecutive_failures += 1
            logger.warning("Etsy '%s': all parse strategies returned nothing", query)
            time.sleep(2)

        except Exception as e:
            consecutive_failures += 1
            logger.warning("Etsy internal API error for '%s': %s", query, e)
            time.sleep(2)

    return listings


def _extract_next_data(html):
    """Extract __NEXT_DATA__ JSON from Etsy's Next.js page."""
    match = re.search(
        r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


def _parse_next_data_listings(next_data):
    """Parse listings from Etsy's __NEXT_DATA__ structure."""
    listings = []

    # Navigate the Next.js data structure to find listing data
    # Etsy's structure varies but listings are typically in props.pageProps
    try:
        props = next_data.get("props", {}).get("pageProps", {})

        # Try different known data paths
        search_results = (
            props.get("data", {}).get("searchResults", [])
            or props.get("searchResults", [])
            or props.get("data", {}).get("results", [])
        )

        if not search_results and isinstance(props.get("data"), dict):
            # Sometimes nested deeper
            for key, val in props["data"].items():
                if isinstance(val, list) and len(val) > 0:
                    if isinstance(val[0], dict) and ("title" in val[0] or "listing_id" in val[0]):
                        search_results = val
                        break

        for item in search_results[:50]:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "") or item.get("name", "")
            if not title or len(title) < 5:
                continue

            listing_id = item.get("listing_id", "") or item.get("id", "")
            url = item.get("url", "")
            if not url and listing_id:
                url = f"https://www.etsy.com/listing/{listing_id}"

            price_raw = (
                item.get("price", {}).get("amount")
                or item.get("price", {}).get("value")
                or item.get("price")
            )
            price = None
            if isinstance(price_raw, (int, float)):
                price = price_raw / 100 if price_raw > 100 else price_raw
            elif isinstance(price_raw, str):
                price = extract_price(price_raw)

            currency = item.get("price", {}).get("currency_code", "USD") if isinstance(item.get("price"), dict) else "USD"

            favorites = item.get("num_favorers", 0) or item.get("favorites", 0) or 0
            reviews = item.get("num_reviews", 0) or item.get("reviews", 0) or 0

            image_url = ""
            images = item.get("images", item.get("image", []))
            if isinstance(images, list) and images:
                image_url = images[0].get("url_570xN", "") or images[0].get("url", "")
            elif isinstance(images, dict):
                image_url = images.get("url_570xN", "") or images.get("url", "")
            elif isinstance(images, str):
                image_url = images

            tags = item.get("tags", [])
            if not tags:
                tags = _extract_tags_from_title(title)

            listings.append({
                "source": "etsy",
                "title": title,
                "url": url,
                "price": price,
                "currency": currency,
                "favorites": favorites,
                "reviews": reviews,
                "rating": None,
                "image_url": image_url,
                "tags": tags,
            })

    except (KeyError, TypeError, AttributeError) as e:
        logger.debug("Error parsing __NEXT_DATA__: %s", e)

    return listings


def _extract_json_ld(html):
    """Extract listings from JSON-LD structured data in the page."""
    listings = []
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "ItemList":
                for item in data.get("itemListElement", []):
                    product = item.get("item", {})
                    if not product:
                        continue
                    title = product.get("name", "")
                    if not title:
                        continue
                    listings.append({
                        "source": "etsy",
                        "title": title,
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
                        "tags": _extract_tags_from_title(title),
                    })
            elif isinstance(data, dict) and data.get("@type") == "Product":
                title = data.get("name", "")
                if title:
                    listings.append({
                        "source": "etsy",
                        "title": title,
                        "url": data.get("url", ""),
                        "price": extract_price(
                            str(data.get("offers", {}).get("price", ""))
                        ),
                        "currency": data.get("offers", {}).get("priceCurrency", "USD"),
                        "favorites": 0,
                        "reviews": 0,
                        "rating": None,
                        "image_url": data.get("image", ""),
                        "tags": _extract_tags_from_title(title),
                    })
        except (json.JSONDecodeError, AttributeError):
            pass

    soup.decompose()
    return listings


def _parse_html_listings(soup):
    """Parse listings from HTML using multiple selector strategies."""
    listings = []

    # Strategy 1: data-listing-id cards
    cards = soup.select("[data-listing-id]")

    # Strategy 2: v2/v3 listing cards
    if not cards:
        cards = soup.select(
            ".v2-listing-card, .search-listing-card, "
            "[data-search-results] .listing-link, "
            ".wt-grid__item-xs-6"
        )

    # Strategy 3: Generic product cards
    if not cards:
        cards = soup.select(
            "div[class*='listing'] a[href*='/listing/'], "
            "li[class*='listing'] a[href*='/listing/']"
        )

    for card in cards[:40]:
        try:
            listing = _parse_listing_card(card)
            if listing:
                listings.append(listing)
        except Exception as e:
            logger.debug("Error parsing Etsy card: %s", e)

    return listings


def _scrape_via_web():
    """Legacy web scraping fallback."""
    session = get_session()
    listings = []

    for query in SEARCH_QUERIES:
        logger.info("Scraping Etsy web for: %s", query)
        resp = fetch_page(session, ETSY_SEARCH_URL, params={
            "q": query,
            "ref": "search_bar",
            "order": "most_relevant",
        })
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        result_cards = soup.select("[data-listing-id]")
        if not result_cards:
            result_cards = soup.select(".v2-listing-card, .search-listing-card")

        for card in result_cards[:25]:
            try:
                listing = _parse_listing_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug("Error parsing Etsy card: %s", e)

        for script in soup.select('script[type="application/ld+json"]'):
            try:
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

        soup.decompose()  # free BS4 tree immediately

    logger.info("Scraped %d Etsy listings via web", len(listings))
    return listings


def _parse_listing_card(card):
    """Parse a single Etsy listing card."""
    title_el = card.select_one(
        ".v2-listing-card__title, .listing-card__title, "
        "[data-listing-card-title], h3, h2"
    )
    title = title_el.get_text(strip=True) if title_el else ""
    if not title:
        # Try getting title from img alt text
        img = card.select_one("img[alt]")
        title = img.get("alt", "") if img else ""
    if not title:
        return None

    link_el = card.select_one("a[href*='/listing/'], a[href]")
    url = link_el["href"] if link_el else ""
    if url and not url.startswith("http"):
        url = "https://www.etsy.com" + url

    price_el = card.select_one(
        ".currency-value, .lc-price .wt-text-title-01, "
        "span[class*='price'], p[class*='price']"
    )
    price = extract_price(price_el.get_text()) if price_el else None

    img_el = card.select_one("img[src]")
    image_url = img_el.get("src", "") if img_el else ""

    fav_el = card.select_one("[class*='favorite'], [class*='heart']")
    favorites = extract_number(fav_el.get_text()) if fav_el else 0

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
    from config import FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS
    for term in FABRIC_TYPES + PATTERN_TYPES + COLOR_TERMS:
        if term.lower() in title_lower:
            tags.append(term)
    return tags
