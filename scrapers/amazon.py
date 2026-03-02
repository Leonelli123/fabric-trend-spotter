"""Amazon scraper for bestselling fabric listings."""

import logging
from bs4 import BeautifulSoup
from scrapers.base import get_session, fetch_page, extract_price, extract_number

logger = logging.getLogger(__name__)

AMAZON_SEARCH_URL = "https://www.amazon.com/s"

SEARCH_QUERIES = [
    "fabric by the yard bestseller",
    "quilting fabric popular",
    "cotton fabric by the yard",
    "upholstery fabric",
    "apparel fabric trending",
]


def scrape_amazon():
    """Scrape Amazon for bestselling fabric listings."""
    session = get_session()
    listings = []

    for query in SEARCH_QUERIES:
        logger.info("Scraping Amazon for: %s", query)
        resp = fetch_page(session, AMAZON_SEARCH_URL, params={
            "k": query,
            "s": "exact-aware-popularity-rank",
        })
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        # Amazon search result cards
        cards = soup.select(
            "[data-component-type='s-search-result'], "
            ".s-result-item[data-asin]"
        )

        for card in cards[:20]:
            try:
                listing = _parse_amazon_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug("Error parsing Amazon card: %s", e)

        soup.decompose()  # free BS4 tree immediately

    logger.info("Scraped %d Amazon listings", len(listings))
    return listings


def _parse_amazon_card(card):
    """Parse a single Amazon search result card."""
    asin = card.get("data-asin", "")
    if not asin:
        return None

    title_el = card.select_one(
        "h2 a span, .a-text-normal, [data-cy='title-recipe'] span"
    )
    title = title_el.get_text(strip=True) if title_el else ""
    if not title:
        return None

    # Filter: only keep fabric-related listings
    title_lower = title.lower()
    fabric_keywords = ["fabric", "yard", "quilting", "cotton", "linen", "sewing"]
    if not any(kw in title_lower for kw in fabric_keywords):
        return None

    link_el = card.select_one("h2 a[href]")
    url = ""
    if link_el:
        href = link_el.get("href", "")
        url = href if href.startswith("http") else f"https://www.amazon.com{href}"

    price_el = card.select_one(".a-price .a-offscreen, .a-price-whole")
    price = extract_price(price_el.get_text()) if price_el else None

    rating_el = card.select_one(".a-icon-alt, [data-cy='reviews-ratings-count']")
    rating = None
    if rating_el:
        text = rating_el.get_text()
        import re
        m = re.search(r"([\d.]+)\s*out\s*of", text)
        if m:
            rating = float(m.group(1))

    reviews_el = card.select_one(
        ".a-size-base.s-underline-text, [data-cy='reviews-ratings-count']"
    )
    reviews = extract_number(reviews_el.get_text()) if reviews_el else 0

    img_el = card.select_one("img.s-image")
    image_url = img_el.get("src", "") if img_el else ""

    tags = _extract_tags_from_title(title)

    return {
        "source": "amazon",
        "title": title,
        "url": url,
        "price": price,
        "currency": "USD",
        "favorites": 0,
        "reviews": reviews,
        "rating": rating,
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
