"""Industry trend report scraper for authoritative fabric/textile signals.

These are the sources that SET trends, not just reflect them:
- Pantone color reports (Color of the Year, seasonal palettes)
- Fashion week runway analysis (trickle-down to fabric 6-12 months later)
- Textile industry blogs and trend publications
- Première Vision / textile trade show coverage

These signals get high weight in the scoring algorithm because they're
leading indicators with proven track records of predicting fabric demand.
"""

import logging
import json
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup
from scrapers.base import get_session, fetch_page
from config import (
    FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS, STYLE_TERMS,
)

logger = logging.getLogger(__name__)

# Authoritative trend sources - each has a track record of setting/predicting trends
# Organized by tier: higher tiers are leading indicators, lower tiers are real-time demand
TREND_SOURCES = [
    # --- TIER 1: Color & Trend Forecasting Authorities (6-18 months ahead) ---
    {
        "name": "Pantone",
        "url": "https://www.pantone.com/articles/fashion-color-trend-report",
        "type": "color_authority",
        "authority_score": 10,  # Highest - Pantone literally sets color trends
    },
    {
        "name": "Coloro Key Colors",
        "url": "https://www.coloro.com/key-colors",
        "type": "color_authority",
        "authority_score": 10,
    },
    {
        "name": "Heuritech",
        "url": "https://www.heuritech.com/articles",
        "type": "forecasting",
        "authority_score": 9,
    },
    {
        "name": "Italtex Trends",
        "url": "https://www.italtextrends.com/blogs/latest-trends",
        "type": "forecasting",
        "authority_score": 8,
    },

    # --- TIER 2: Trade Show / Industry Intelligence (3-12 months ahead) ---
    {
        "name": "Premiere Vision",
        "url": "https://www.premierevision.com/en",
        "type": "trade_show",
        "authority_score": 9,
    },
    {
        "name": "Texworld Paris",
        "url": "https://texpertisenetwork.messefrankfurt.com",
        "type": "trade_show",
        "authority_score": 9,
    },
    {
        "name": "Textile Magazine",
        "url": "https://www.textilemagazine.com/category/trends/",
        "type": "industry",
        "authority_score": 8,
    },
    {
        "name": "Trend-Monitor Textiles",
        "url": "https://www.trend-monitor.co.uk/trend-topics/textiles-fabrics/",
        "type": "forecasting",
        "authority_score": 8,
    },

    # --- TIER 3: Print & Pattern Design (directly relevant to jersey prints) ---
    {
        "name": "Patternbank",
        "url": "https://patternbank.com/trends",
        "type": "print_design",
        "authority_score": 9,
    },
    {
        "name": "Plumager",
        "url": "https://plumager.com/blogs/plumager-print-design",
        "type": "print_design",
        "authority_score": 8,
    },
    {
        "name": "Print and Pattern",
        "url": "https://www.printandpattern.com",
        "type": "print_design",
        "authority_score": 7,
    },
    {
        "name": "Textile Design Lab",
        "url": "https://www.textiledesignlab.com/blog",
        "type": "print_design",
        "authority_score": 7,
    },

    # --- TIER 4: Fashion Publications (trickle-down to fabric, 3-6 months) ---
    {
        "name": "Dezeen Textiles",
        "url": "https://www.dezeen.com/tag/textiles/",
        "type": "design",
        "authority_score": 7,
    },
    {
        "name": "Fashionating World",
        "url": "https://www.fashionatingworld.com",
        "type": "fashion",
        "authority_score": 7,
    },
    {
        "name": "Knitting Industry Creative",
        "url": "https://creative.knittingindustry.com",
        "type": "industry",
        "authority_score": 6,
    },

    # --- TIER 5: Sewing & Maker Community (real demand signals, 0-3 months) ---
    {
        "name": "Seamwork Magazine",
        "url": "https://www.seamwork.com/magazine",
        "type": "community",
        "authority_score": 6,
    },
    {
        "name": "The Fold Line",
        "url": "https://thefoldline.com/category/fabric-shopping/",
        "type": "community",
        "authority_score": 6,
    },
    {
        "name": "Mood Fabrics Blog",
        "url": "https://www.moodfabrics.com/blog",
        "type": "community",
        "authority_score": 7,
    },
    {
        "name": "All About Fabrics",
        "url": "https://www.allaboutfabrics.com/blogs/news",
        "type": "community",
        "authority_score": 6,
    },
    {
        "name": "WeAllSew",
        "url": "https://weallsew.com",
        "type": "community",
        "authority_score": 6,
    },
]

# Search-based sources (Google News, etc.) for recent trend articles
TREND_SEARCH_QUERIES = [
    "fabric trends 2026",
    "textile trends forecast",
    "Pantone color year fabric",
    "Première Vision textile trends",
    "Scandinavian textile design trends",
    "cotton jersey print trends",
    "digital print fabric trends",
    "surface pattern design trends 2026",
    "sustainable fabric trends organic cotton",
    "print and pattern trends sewing",
]


def fetch_trend_reports():
    """Scrape trend-setting publications for fabric/textile signals.

    Returns a dict with:
    - trend_signals: extracted trend terms with authority scores
    - articles: source articles that informed the signals
    """
    session = get_session()
    all_signals = []
    all_articles = []

    # Phase 1: Scrape authoritative trend sources
    for source in TREND_SOURCES:
        try:
            logger.info("Fetching trend source: %s", source["name"])
            resp = fetch_page(session, source["url"])
            if resp:
                signals, articles = _extract_trend_signals(
                    resp.text, source["name"], source["authority_score"],
                    source["type"],
                )
                all_signals.extend(signals)
                all_articles.extend(articles)
                logger.info(
                    "%s: extracted %d signals from %d articles",
                    source["name"], len(signals), len(articles),
                )
            time.sleep(2)
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", source["name"], e)

    # Phase 2: Google News search for recent trend articles
    for query in TREND_SEARCH_QUERIES[:5]:  # Limit to avoid rate limiting
        try:
            logger.info("Searching Google News for: %s", query)
            news_signals = _search_google_news(session, query)
            all_signals.extend(news_signals)
            time.sleep(2)
        except Exception as e:
            logger.warning("Google News search failed for '%s': %s", query, e)

    # Aggregate and deduplicate signals
    aggregated = _aggregate_signals(all_signals)

    logger.info(
        "Trend reports: %d aggregated signals from %d raw signals, %d articles",
        len(aggregated), len(all_signals), len(all_articles),
    )

    return {
        "signals": aggregated,
        "articles": all_articles[:20],
        "sources_scraped": len(TREND_SOURCES),
        "fetched_at": datetime.now().isoformat(),
    }


def _extract_trend_signals(html, source_name, authority_score, source_type):
    """Extract fabric/textile trend signals from an article page."""
    soup = BeautifulSoup(html, "html.parser")
    signals = []
    articles = []

    # Remove nav, header, footer, sidebar to focus on article content
    for tag in soup.select("nav, header, footer, aside, .sidebar, .menu, .ad"):
        tag.decompose()

    # Find article-like elements
    article_elements = soup.select(
        "article, .post, .entry, .article-content, "
        ".post-content, main, .content"
    )

    if not article_elements:
        article_elements = [soup.body] if soup.body else [soup]

    for article in article_elements[:10]:
        text = article.get_text(separator=" ", strip=True)
        if len(text) < 100:
            continue

        # Get article title and URL
        title_el = article.select_one("h1, h2, h3, .title, .headline")
        title = title_el.get_text(strip=True) if title_el else ""
        link_el = article.select_one("a[href]")
        url = link_el.get("href", "") if link_el else ""

        if title and len(title) > 10:
            articles.append({
                "title": title[:200],
                "url": url,
                "source": source_name,
                "type": source_type,
            })

        # Extract trend terms from the text
        text_lower = text.lower()

        # Check all term categories
        for term_list, category in [
            (FABRIC_TYPES, "fabric_type"),
            (PATTERN_TYPES, "pattern"),
            (COLOR_TERMS, "color"),
            (STYLE_TERMS, "style"),
        ]:
            for term in term_list:
                if term.lower() in text_lower:
                    # Count occurrences for stronger signal
                    count = text_lower.count(term.lower())
                    # Authority-weighted signal strength
                    strength = min(count, 5) * authority_score

                    signals.append({
                        "term": term,
                        "category": category,
                        "source": source_name,
                        "source_type": source_type,
                        "authority_score": authority_score,
                        "mention_count": count,
                        "strength": strength,
                    })

    return signals, articles


def _search_google_news(session, query):
    """Search Google News for recent fabric/textile trend articles."""
    signals = []

    # Use Google News RSS which doesn't require API key
    url = "https://news.google.com/rss/search"
    params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}

    resp = fetch_page(session, url, params=params)
    if not resp:
        return signals

    soup = BeautifulSoup(resp.text, "xml")
    items = soup.find_all("item")

    for item in items[:5]:
        title = item.find("title")
        description = item.find("description")
        text = ""
        if title:
            text += title.get_text() + " "
        if description:
            text += description.get_text()

        if not text:
            continue

        text_lower = text.lower()

        for term_list, category in [
            (FABRIC_TYPES, "fabric_type"),
            (PATTERN_TYPES, "pattern"),
            (COLOR_TERMS, "color"),
            (STYLE_TERMS, "style"),
        ]:
            for term in term_list:
                if term.lower() in text_lower:
                    signals.append({
                        "term": term,
                        "category": category,
                        "source": "Google News",
                        "source_type": "news",
                        "authority_score": 5,
                        "mention_count": 1,
                        "strength": 5,
                    })

    return signals


def _aggregate_signals(signals):
    """Aggregate signals by term, combining authority scores."""
    by_term = {}

    for sig in signals:
        term = sig["term"]
        if term not in by_term:
            by_term[term] = {
                "term": term,
                "category": sig["category"],
                "total_strength": 0,
                "source_count": 0,
                "sources": [],
                "authority_weighted_score": 0,
            }

        entry = by_term[term]
        entry["total_strength"] += sig["strength"]
        entry["authority_weighted_score"] += sig["authority_score"] * sig["mention_count"]

        if sig["source"] not in entry["sources"]:
            entry["sources"].append(sig["source"])
            entry["source_count"] += 1

    # Sort by authority-weighted score
    result = sorted(
        by_term.values(),
        key=lambda x: x["authority_weighted_score"],
        reverse=True,
    )

    return result
