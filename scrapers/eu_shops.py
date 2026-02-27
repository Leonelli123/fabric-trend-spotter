"""European fabric shop scraper — real shops, real data.

Phase 1 covers the 8 highest-impact shops (one scraper covers up to 7 markets)
plus 5 key competitor brands.  Each shop returns standardised listing dicts
that feed straight into the existing analysis pipeline.

Resilience strategy:
- Each shop wrapped in try/except — one failure never blocks the rest
- Rate-limited (REQUEST_DELAY between pages)
- Falls back gracefully if a shop changes layout or blocks requests
"""

import logging
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
from scrapers.base import get_session, fetch_page, extract_price
from config import (
    EU_SHOPS, COMPETITOR_BRANDS, EUROPEAN_COUNTRIES,
    FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS, STYLE_TERMS,
    REQUEST_DELAY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Multilingual tag extraction
# ---------------------------------------------------------------------------

# Local-language fabric terms → canonical English tags
_LOCAL_FABRIC_TERMS = {
    # German
    "baumwolle": "cotton", "baumwollstoff": "cotton", "baumwolljersey": "jersey",
    "jersey": "jersey", "french terry": "terry", "sweatstoff": "terry",
    "dresowka": "terry", "musselin": "muslin", "doppelmusselin": "double gauze",
    "leinen": "linen", "leinenstoff": "linen", "viskose": "rayon",
    "samt": "velvet", "cord": "corduroy", "breitcord": "corduroy",
    "canvas": "canvas", "popeline": "poplin", "flanell": "flannel",
    "fleece": "fleece", "strickstoff": "knit", "jacquard": "jacquard",
    "seide": "silk", "taft": "taffeta", "organza": "organza",
    "tüll": "tulle", "interlock": "jersey", "bio": "organic cotton",
    "meterware": None, "stoff": None,
    # Dutch
    "katoen": "cotton", "tricot": "jersey", "katoenen": "cotton",
    "linnen": "linen", "mousseline": "muslin", "fluweel": "velvet",
    "poplin": "poplin", "wafelkatoen": "cotton",
    "spijkerstof": "denim", "bamboe": "bamboo",
    # French
    "coton": "cotton", "tissu": None, "lin": "linen", "viscose": "rayon",
    "velours": "velvet", "mousseline": "muslin", "soie": "silk",
    "gaze": "double gauze", "double gaze": "double gauze",
    "toile": "canvas", "popeline": "poplin", "jersey": "jersey",
    "crêpe": "crepe", "satin": "satin", "taffetas": "taffeta",
    "jacquard": "jacquard", "broderie": "lace", "matelassé": "quilting",
    # Swedish
    "bomull": "cotton", "bomullstyg": "cotton", "trikå": "jersey",
    "jerseytyg": "jersey", "linne": "linen", "linnetyg": "linen",
    "sammet": "velvet", "fleece": "fleece", "dubbelgasväv": "double gauze",
    # Finnish
    "puuvilla": "cotton", "puuvillakangas": "cotton", "trikoo": "jersey",
    "trikookangas": "jersey", "pellava": "linen", "pellavakangas": "linen",
    "sametti": "velvet", "mussliini": "muslin",
    # Danish
    "bomuld": "cotton", "bomuldsstof": "cotton", "jerseystof": "jersey",
    "hør": "linen", "fløjl": "velvet", "muslin": "muslin",
    # Norwegian
    "bomullsstoff": "cotton", "linstoff": "linen",
    "ullstoff": "wool", "fleecestoff": "fleece",
    # Polish
    "bawełna": "cotton", "bawełniana": "cotton", "dzianina": "jersey",
    "dresówka": "terry", "len": "linen", "wiskoza": "rayon",
    "aksamit": "velvet", "muślin": "muslin",
    # Czech
    "bavlna": "cotton", "bavlněná": "cotton", "úplet": "jersey",
    "plátno": "canvas", "satén": "satin",
}

_LOCAL_PATTERN_TERMS = {
    # German
    "blumen": "floral", "blumenmuster": "floral", "gestreift": "stripe",
    "kariert": "plaid", "gepunktet": "polka dot", "geometrisch": "geometric",
    "abstrakt": "abstract", "vintage": "vintage", "retro": "retro",
    "botanisch": "botanical",
    # Dutch
    "bloemen": "floral", "gestreept": "stripe", "bloemenprint": "floral",
    "geometrisch": "geometric", "paisley": "paisley",
    # French
    "fleurs": "floral", "fleuri": "floral", "rayé": "stripe",
    "carreaux": "plaid", "pois": "polka dot", "géométrique": "geometric",
    "liberty": "liberty", "toile de jouy": "toile", "provençal": "floral",
    "bohème": "bohemian",
    # Swedish
    "blommigt": "floral", "randigt": "stripe", "mönster": None,
    # Finnish
    "kukkakuvio": "floral",
    # Polish
    "kwiaty": "floral", "paski": "stripe",
    # Common across languages
    "floral": "floral", "tropical": "tropical", "batik": "batik",
    "ikat": "ikat", "toile": "toile", "ditsy": "ditsy",
}

_LOCAL_COLOR_TERMS = {
    # German
    "salbeigrün": "sage green", "altrosa": "dusty rose", "senfgelb": "mustard",
    "terracotta": "terracotta", "marine": "navy", "ocker": "ochre",
    "tannengrün": "forest green", "dunkelgrün": "forest green",
    "smaragd": "emerald", "bordeaux": "burgundy", "rost": "rust",
    "creme": "cream", "naturel": "cream", "natur": "cream",
    # Dutch
    "saliegroen": "sage green", "oudroze": "dusty rose",
    "smaragdgroen": "emerald", "oker": "ochre", "mosterd": "mustard",
    # French
    "vert sauge": "sage green", "vert amande": "sage green",
    "rose poudré": "dusty rose", "terracotta": "terracotta",
    "moutarde": "mustard", "bordeaux": "burgundy", "bleu orage": "navy",
    "champagne": "champagne", "camel": "terracotta",
    # Swedish
    "salvia": "sage green", "duvblå": "baby blue", "olivgrön": "olive",
    # Finnish
    "petrooli": "teal", "mustikka": "navy",
    # Danish
    "salvie": "sage green", "støvet rosa": "dusty rose", "sennep": "mustard",
    # Polish
    "butelkowa zieleń": "forest green", "musztardowy": "mustard",
    "pudrowy": "dusty rose",
}


def _extract_tags_multilingual(text):
    """Extract canonical English tags from multilingual product text."""
    tags = set()
    text_lower = text.lower()

    # Check local-language terms first (most specific)
    for term_map in (_LOCAL_FABRIC_TERMS, _LOCAL_PATTERN_TERMS, _LOCAL_COLOR_TERMS):
        for local_term, english_tag in term_map.items():
            if english_tag and local_term in text_lower:
                tags.add(english_tag)

    # Also match English config terms directly
    for term_list in (FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS, STYLE_TERMS):
        for term in term_list:
            if term.lower() in text_lower:
                tags.add(term)

    return list(tags)


def _classify_segment(tags):
    """Guess segment from tags."""
    tag_set = set(tags)
    if tag_set & {"quilting", "patchwork", "fat quarter"}:
        return "quilting"
    if tag_set & {"velvet", "canvas", "jacquard", "upholstery fabric", "curtain"}:
        return "home_decor"
    if tag_set & {"tulle", "organza", "satin", "taffeta", "cosplay"}:
        return "cosplay"
    if tag_set & {"jersey", "knit", "linen", "rayon", "crepe", "silk", "poplin", "denim"}:
        return "apparel"
    return "craft"


# ---------------------------------------------------------------------------
# Generic HTML product parser
# ---------------------------------------------------------------------------

def _parse_product_elements(html, shop_key, country, currency):
    """Parse product listings from a generic shop HTML page.

    Tries multiple common e-commerce element patterns to find product cards.
    Returns a list of standardised listing dicts.
    """
    soup = BeautifulSoup(html, "html.parser")
    listings = []

    # Common product card selectors across Shopware, WooCommerce, Magento, etc.
    card_selectors = [
        ".product--box",                    # Shopware 5
        ".product-box",                     # Shopware 6
        "[data-product-id]",                # generic data attr
        ".product-item",                    # Magento
        ".product-card",                    # various
        ".product",                         # generic
        "li.product",                       # WooCommerce
        ".woocommerce-loop-product__link",  # WooCommerce
        ".collection-product",              # Shopify
        ".product-grid-item",               # various
        ".item.product",                    # various
        ".product-miniature",               # PrestaShop
        "article.product",                  # semantic
    ]

    product_elements = []
    for selector in card_selectors:
        product_elements = soup.select(selector)
        if product_elements:
            break

    # Fallback: look for repeating links with images inside a list/grid
    if not product_elements:
        product_elements = soup.select(".products a, .product-list a, .category-products a")

    for el in product_elements[:40]:  # Cap per page
        try:
            # Title
            title_el = el.select_one(
                ".product--title, .product-title, .product-name, "
                ".product-item-link, h2, h3, .name, [itemprop='name']"
            )
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                # Try the first meaningful text or alt of img
                img = el.select_one("img[alt]")
                title = img.get("alt", "").strip() if img else ""
            if not title or len(title) < 5:
                continue

            # URL
            link = el.select_one("a[href]") if el.name != "a" else el
            url = link.get("href", "") if link else ""
            if url and not url.startswith("http"):
                shop_cfg = EU_SHOPS.get(shop_key, {})
                base = shop_cfg.get("base_url", "")
                url = base.rstrip("/") + "/" + url.lstrip("/")

            # Price
            price_el = el.select_one(
                ".product--price, .price, .product-price, .amount, "
                "[itemprop='price'], .current-price, .special-price, "
                ".price-new, .price--default"
            )
            price_text = price_el.get_text(strip=True) if price_el else ""
            price = extract_price(price_text)

            # Image
            img_el = el.select_one("img[src], img[data-src], img[data-lazy-src]")
            image_url = ""
            if img_el:
                image_url = (
                    img_el.get("src")
                    or img_el.get("data-src")
                    or img_el.get("data-lazy-src")
                    or ""
                )

            # Popularity signals
            favorites = 0
            reviews = 0
            rating = None

            # Reviews / rating
            rating_el = el.select_one("[itemprop='ratingValue'], .star-rating, .rating")
            if rating_el:
                rv = extract_price(rating_el.get_text())
                if rv and 0 < rv <= 5:
                    rating = rv

            review_el = el.select_one("[itemprop='reviewCount'], .review-count, .reviews")
            if review_el:
                reviews = int(re.sub(r"[^\d]", "", review_el.get_text()) or 0)

            # "New" flag
            is_new = bool(el.select_one(
                ".badge--new, .new, .label-new, .product-flag--new, .badge-new"
            ))

            # "Bestseller" flag
            is_bestseller = bool(el.select_one(
                ".badge--bestseller, .bestseller, .label-bestseller, .badge-top"
            ))
            # Also check text content for bestseller indicators
            el_text = el.get_text(separator=" ", strip=True).lower()
            if "bestseller" in el_text or "best seller" in el_text or "topseller" in el_text:
                is_bestseller = True

            # Extract tags from title
            tags = _extract_tags_multilingual(title)

            # Boost signals
            if is_new:
                favorites += 50  # Synthetic signal: "new" = likely trending
            if is_bestseller:
                favorites += 100  # Synthetic signal: proven seller

            listing = {
                "source": f"eu_shop_{shop_key}",
                "title": title[:200],
                "url": url,
                "price": price,
                "currency": currency,
                "favorites": favorites,
                "reviews": reviews,
                "rating": rating,
                "image_url": image_url,
                "tags": tags,
                "segment": _classify_segment(tags),
                "country": country,
                "is_new": is_new,
                "is_bestseller": is_bestseller,
                "scraped_at": datetime.now().isoformat(),
            }
            listings.append(listing)

        except Exception as e:
            logger.debug("Failed to parse product element: %s", e)
            continue

    return listings


# ---------------------------------------------------------------------------
# Per-shop scraper logic
# ---------------------------------------------------------------------------

def _scrape_shop_pages(session, shop_key, shop_cfg):
    """Scrape bestsellers + new arrivals from a single shop across its countries."""
    all_listings = []
    base_url = shop_cfg["base_url"]
    countries = shop_cfg["countries"]

    # Common page suffixes to try for bestsellers and new arrivals
    bestseller_paths = [
        "/bestseller", "/bestsellers", "/topseller",
        "/stoffe/bestseller/", "/best-sellers",
        "/collections/best-sellers",
        "/meilleures-ventes", "/nieuw", "/nytt",
    ]
    new_arrivals_paths = [
        "/new", "/new-arrivals", "/neuheiten", "/nieuw",
        "/nouvelles-arrivees", "/nouveautes",
        "/stoffe/neuheiten/", "/collections/new",
        "/nyheter", "/nye-produkter",
    ]
    jersey_paths = [
        "/jersey", "/stoffe/jersey/", "/tricot",
        "/trikot", "/trikoo", "/tissus-jersey",
        "/jerseystoffe", "/tricot-stoffen",
    ]

    for country in countries:
        country_cfg = EUROPEAN_COUNTRIES.get(country, {})
        currency = country_cfg.get("currency", "EUR")

        # Build country-specific base URL
        if "locale_paths" in shop_cfg:
            locale = shop_cfg["locale_paths"].get(country, "")
            country_base = base_url + locale
        else:
            country_base = base_url

        # Try bestseller page
        for path in bestseller_paths:
            url = country_base.rstrip("/") + path
            resp = fetch_page(session, url)
            if resp and resp.status_code == 200:
                listings = _parse_product_elements(
                    resp.text, shop_key, country, currency,
                )
                # Mark all as bestsellers if found on bestseller page
                for l in listings:
                    l["is_bestseller"] = True
                    l["favorites"] = max(l["favorites"], 100)
                if listings:
                    all_listings.extend(listings)
                    logger.info(
                        "%s %s bestsellers: %d products",
                        shop_cfg["name"], country, len(listings),
                    )
                    break  # Found working bestseller page
            time.sleep(REQUEST_DELAY)

        # Try new arrivals page
        for path in new_arrivals_paths:
            url = country_base.rstrip("/") + path
            resp = fetch_page(session, url)
            if resp and resp.status_code == 200:
                listings = _parse_product_elements(
                    resp.text, shop_key, country, currency,
                )
                for l in listings:
                    l["is_new"] = True
                    l["favorites"] = max(l["favorites"], 50)
                if listings:
                    all_listings.extend(listings)
                    logger.info(
                        "%s %s new arrivals: %d products",
                        shop_cfg["name"], country, len(listings),
                    )
                    break
            time.sleep(REQUEST_DELAY)

        # Try jersey-specific page (critical for our business)
        for path in jersey_paths:
            url = country_base.rstrip("/") + path
            resp = fetch_page(session, url)
            if resp and resp.status_code == 200:
                listings = _parse_product_elements(
                    resp.text, shop_key, country, currency,
                )
                if listings:
                    # Ensure jersey tag is present
                    for l in listings:
                        if "jersey" not in l["tags"]:
                            l["tags"].append("jersey")
                    all_listings.extend(listings)
                    logger.info(
                        "%s %s jersey: %d products",
                        shop_cfg["name"], country, len(listings),
                    )
                    break
            time.sleep(REQUEST_DELAY)

    return all_listings


def _scrape_competitor_brand(session, brand_key, brand_cfg):
    """Scrape a competitor brand for their latest collections/products."""
    all_listings = []
    url = brand_cfg["url"]
    country = brand_cfg["country"]
    currency = EUROPEAN_COUNTRIES.get(country, {}).get("currency", "EUR")

    # Try known Shopify pattern first (many small brands use Shopify)
    shopify_url = url.rstrip("/") + "/products.json?limit=50"
    resp = fetch_page(session, shopify_url)
    if resp and resp.status_code == 200:
        try:
            data = resp.json()
            products = data.get("products", [])
            for p in products[:30]:
                title = p.get("title", "")
                tags = _extract_tags_multilingual(title + " " + " ".join(p.get("tags", [])))
                # Also check product type
                ptype = p.get("product_type", "").lower()
                if ptype:
                    tags.extend(_extract_tags_multilingual(ptype))
                tags = list(set(tags))

                price = None
                variants = p.get("variants", [])
                if variants:
                    try:
                        price = float(variants[0].get("price", 0))
                    except (ValueError, TypeError):
                        pass

                images = p.get("images", [])
                image_url = images[0].get("src", "") if images else ""

                listing = {
                    "source": f"competitor_{brand_key}",
                    "title": title[:200],
                    "url": f"{url.rstrip('/')}/products/{p.get('handle', '')}",
                    "price": price,
                    "currency": currency,
                    "favorites": 0,
                    "reviews": 0,
                    "rating": None,
                    "image_url": image_url,
                    "tags": tags,
                    "segment": _classify_segment(tags),
                    "country": country,
                    "is_new": p.get("published_at", "")[:7] == datetime.now().strftime("%Y-%m"),
                    "is_bestseller": False,
                    "scraped_at": datetime.now().isoformat(),
                }
                all_listings.append(listing)

            if all_listings:
                logger.info(
                    "Competitor %s (Shopify): %d products",
                    brand_cfg["name"], len(all_listings),
                )
                return all_listings
        except (ValueError, KeyError):
            pass  # Not Shopify or failed parse

    # Fall back to HTML scraping
    for path in ["", "/shop", "/products", "/fabric", "/stoffe", "/collections/all"]:
        page_url = url.rstrip("/") + path
        resp = fetch_page(session, page_url)
        if resp and resp.status_code == 200:
            listings = _parse_product_elements(resp.text, brand_key, country, currency)
            if listings:
                for l in listings:
                    l["source"] = f"competitor_{brand_key}"
                all_listings.extend(listings)
                logger.info(
                    "Competitor %s: %d products from %s",
                    brand_cfg["name"], len(listings), path or "/",
                )
                break
        time.sleep(REQUEST_DELAY)

    return all_listings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_eu_shops(priority=1):
    """Scrape European fabric shops at the given priority level.

    Args:
        priority: 1 = Phase 1 (8 highest-impact shops), 2 = all shops

    Returns:
        dict with:
          listings  — list of product listing dicts
          stats     — per-shop scrape results
          competitors — competitor brand listings
    """
    session = get_session()
    all_listings = []
    stats = {}

    # Filter shops by priority
    target_shops = {
        k: v for k, v in EU_SHOPS.items()
        if v.get("priority", 99) <= priority
    }

    logger.info(
        "Scraping %d EU shops (priority <= %d)...",
        len(target_shops), priority,
    )

    for shop_key, shop_cfg in target_shops.items():
        try:
            logger.info("Scraping %s (%s)...", shop_cfg["name"], shop_key)
            listings = _scrape_shop_pages(session, shop_key, shop_cfg)
            all_listings.extend(listings)
            stats[shop_key] = {
                "name": shop_cfg["name"],
                "status": "ok" if listings else "empty",
                "count": len(listings),
                "countries": shop_cfg["countries"],
            }
            if listings:
                logger.info(
                    "%s: %d products across %s",
                    shop_cfg["name"], len(listings),
                    ", ".join(shop_cfg["countries"]),
                )
            else:
                logger.warning("%s: no products found", shop_cfg["name"])
        except Exception as e:
            stats[shop_key] = {
                "name": shop_cfg["name"],
                "status": "error",
                "count": 0,
                "error": str(e)[:100],
            }
            logger.warning("%s failed: %s", shop_cfg["name"], e)

    logger.info(
        "EU shops done: %d total listings from %d shops",
        len(all_listings), len(target_shops),
    )

    return {
        "listings": all_listings,
        "stats": stats,
        "shop_count": len(target_shops),
        "total_listings": len(all_listings),
        "scraped_at": datetime.now().isoformat(),
    }


def scrape_competitors():
    """Scrape the top 5 direct competitor brands.

    Returns:
        dict with:
          listings — competitor product listings
          stats    — per-brand results
    """
    session = get_session()
    all_listings = []
    stats = {}

    # Only scrape direct competitors (tier == "direct"), top 5
    direct = {
        k: v for k, v in COMPETITOR_BRANDS.items()
        if v.get("tier") == "direct"
    }
    top5_keys = ["lillestoff", "elvelyckan", "albstoffe", "seeyouatsix", "paapii"]
    targets = {k: direct[k] for k in top5_keys if k in direct}

    logger.info("Scraping %d competitor brands...", len(targets))

    for brand_key, brand_cfg in targets.items():
        try:
            logger.info("Scraping competitor: %s", brand_cfg["name"])
            listings = _scrape_competitor_brand(session, brand_key, brand_cfg)
            all_listings.extend(listings)
            stats[brand_key] = {
                "name": brand_cfg["name"],
                "status": "ok" if listings else "empty",
                "count": len(listings),
                "country": brand_cfg["country"],
            }
        except Exception as e:
            stats[brand_key] = {
                "name": brand_cfg["name"],
                "status": "error",
                "count": 0,
                "error": str(e)[:100],
            }
            logger.warning("Competitor %s failed: %s", brand_cfg["name"], e)

    logger.info(
        "Competitors done: %d total listings from %d brands",
        len(all_listings), len(targets),
    )

    return {
        "listings": all_listings,
        "stats": stats,
        "brand_count": len(targets),
        "total_listings": len(all_listings),
        "scraped_at": datetime.now().isoformat(),
    }


def get_eu_shop_summary():
    """Return a summary of all configured EU shops and competitors.

    Useful for the dashboard to show source coverage.
    """
    shops_by_country = {}
    for shop_cfg in EU_SHOPS.values():
        for country in shop_cfg["countries"]:
            shops_by_country.setdefault(country, []).append(shop_cfg["name"])

    competitors_by_tier = {}
    for brand_cfg in COMPETITOR_BRANDS.values():
        tier = brand_cfg.get("tier", "unknown")
        competitors_by_tier.setdefault(tier, []).append(brand_cfg["name"])

    return {
        "total_shops": len(EU_SHOPS),
        "total_competitors": len(COMPETITOR_BRANDS),
        "shops_by_country": {k: len(v) for k, v in shops_by_country.items()},
        "competitors_by_tier": {k: len(v) for k, v in competitors_by_tier.items()},
    }
