"""Base utilities shared across scrapers."""

import time
import logging
import requests
from config import USER_AGENT, REQUEST_DELAY, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


def get_session():
    """Create a requests session with common headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })
    return session


def fetch_page(session, url, params=None):
    """Fetch a page with rate limiting and error handling."""
    time.sleep(REQUEST_DELAY)
    try:
        resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def extract_price(text):
    """Extract a numeric price from text like '$12.99' or '12.99 USD'."""
    import re
    if not text:
        return None
    match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def extract_number(text):
    """Extract a number from text like '1,234 favorites'."""
    import re
    if not text:
        return 0
    match = re.search(r"[\d,]+", text.replace(",", ""))
    if match:
        try:
            return int(match.group().replace(",", ""))
        except ValueError:
            return 0
    return 0
