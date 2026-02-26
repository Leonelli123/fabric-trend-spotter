"""Spoonflower scraper for trending fabric designs."""

import logging
from bs4 import BeautifulSoup
from scrapers.base import get_session, fetch_page, extract_price

logger = logging.getLogger(__name__)

SPOONFLOWER_BASE = "https://www.spoonflower.com"
TRENDING_URLS = [
    "/fabric/best-selling",
    "/fabric/new",
    "/fabric?sort=bestSelling&on=fabric",
]

SEARCH_QUERIES = [
    "floral", "geometric", "botanical", "abstract", "vintage",
    "modern", "minimalist", "cottagecore", "tropical",
]


def scrape_spoonflower():
    """Scrape Spoonflower for trending fabric designs."""
    session = get_session()
    listings = []

    # Scrape trending/bestselling pages
    for path in TRENDING_URLS:
        url = SPOONFLOWER_BASE + path
        logger.info("Scraping Spoonflower: %s", url)
        resp = fetch_page(session, url)
        if not resp:
            continue
        listings.extend(_parse_spoonflower_page(resp.text))

    # Search for specific design trends
    for query in SEARCH_QUERIES:
        search_url = f"{SPOONFLOWER_BASE}/fabric"
        logger.info("Searching Spoonflower for: %s", query)
        resp = fetch_page(session, search_url, params={
            "search": query,
            "sort": "bestSelling",
            "on": "fabric",
        })
        if not resp:
            continue
        listings.extend(_parse_spoonflower_page(resp.text))

    logger.info("Scraped %d Spoonflower listings", len(listings))
    return listings


def _parse_spoonflower_page(html):
    """Parse a Spoonflower page for fabric listings."""
    soup = BeautifulSoup(html, "html.parser")
    listings = []

    # Spoonflower design cards
    cards = soup.select(
        ".design-card, [data-testid='design-card'], "
        ".product-card, .fabric-card, .design-thumbnail"
    )

    for card in cards[:30]:
        try:
            title_el = card.select_one(
                ".design-card__title, .product-title, h3, h2, a[title]"
            )
            title = ""
            if title_el:
                title = title_el.get("title") or title_el.get_text(strip=True)
            if not title:
                continue

            link_el = card.select_one("a[href]")
            url = ""
            if link_el:
                href = link_el.get("href", "")
                url = href if href.startswith("http") else SPOONFLOWER_BASE + href

            price_el = card.select_one("[class*='price'], .design-card__price")
            price = extract_price(price_el.get_text()) if price_el else None

            img_el = card.select_one("img[src]")
            image_url = img_el.get("src", "") if img_el else ""

            tags = _extract_tags_from_title(title)

            # Spoonflower designs often have the designer name
            designer_el = card.select_one(
                ".design-card__designer, .designer-name, [class*='designer']"
            )
            designer = designer_el.get_text(strip=True) if designer_el else ""
            if designer:
                tags.append(f"designer:{designer}")

            listings.append({
                "source": "spoonflower",
                "title": title,
                "url": url,
                "price": price,
                "currency": "USD",
                "favorites": 0,
                "reviews": 0,
                "rating": None,
                "image_url": image_url,
                "tags": tags,
            })
        except Exception as e:
            logger.debug("Error parsing Spoonflower card: %s", e)

    # Fallback: try JSON data embedded in the page
    import json
    for script in soup.select("script"):
        if script.string and "designs" in (script.string or ""):
            try:
                # Some Spoonflower pages embed JSON data
                text = script.string
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(text[start:end])
                    designs = _find_designs_in_json(data)
                    for d in designs[:30]:
                        listings.append({
                            "source": "spoonflower",
                            "title": d.get("name", d.get("title", "")),
                            "url": d.get("url", ""),
                            "price": d.get("price"),
                            "currency": "USD",
                            "favorites": d.get("favorites", 0),
                            "reviews": 0,
                            "rating": None,
                            "image_url": d.get("image", ""),
                            "tags": _extract_tags_from_title(
                                d.get("name", d.get("title", ""))
                            ),
                        })
            except (json.JSONDecodeError, ValueError):
                pass

    return listings


def _find_designs_in_json(data, results=None):
    """Recursively find design objects in nested JSON."""
    if results is None:
        results = []
    if isinstance(data, dict):
        if "designId" in data or ("name" in data and "fabric" in str(data)):
            results.append(data)
        for v in data.values():
            _find_designs_in_json(v, results)
    elif isinstance(data, list):
        for item in data:
            _find_designs_in_json(item, results)
    return results


def _extract_tags_from_title(title):
    """Extract relevant keywords from a listing title."""
    title_lower = title.lower()
    tags = []
    from config import FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS
    for term in FABRIC_TYPES + PATTERN_TYPES + COLOR_TERMS:
        if term.lower() in title_lower:
            tags.append(term)
    return tags
