"""Google Trends data for fabric-related search interest."""

import logging
import time
from config import FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS

logger = logging.getLogger(__name__)


def fetch_google_trends():
    """Fetch Google Trends data for fabric-related keywords."""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.warning("pytrends not installed, skipping Google Trends")
        return {}

    pytrends = TrendReq(hl="en-US", tz=360)
    results = {}

    # Build keyword groups (Google Trends allows max 5 per request)
    fabric_keywords = [f"{ft} fabric" for ft in FABRIC_TYPES[:15]]
    pattern_keywords = [f"{pt} fabric" for pt in PATTERN_TYPES[:15]]
    color_keywords = [f"{ct} fabric" for ct in COLOR_TERMS[:10]]

    all_groups = []
    all_keywords = fabric_keywords + pattern_keywords + color_keywords
    for i in range(0, len(all_keywords), 5):
        all_groups.append(all_keywords[i : i + 5])

    for group in all_groups:
        try:
            pytrends.build_payload(group, timeframe="today 3-m", geo="US")
            interest = pytrends.interest_over_time()
            if interest is not None and not interest.empty:
                for kw in group:
                    if kw in interest.columns:
                        avg_interest = interest[kw].mean()
                        recent_interest = interest[kw].iloc[-4:].mean()
                        results[kw] = {
                            "avg_interest": round(avg_interest, 1),
                            "recent_interest": round(recent_interest, 1),
                            "trending_up": recent_interest > avg_interest * 1.1,
                            "history": [
                                {"date": str(d.date()), "value": int(v)}
                                for d, v in interest[kw].items()
                                if str(d) != "isPartial"
                            ],
                        }
            time.sleep(2)  # Be polite to Google
        except Exception as e:
            logger.warning("Google Trends error for %s: %s", group, e)
            time.sleep(5)

    logger.info("Fetched Google Trends for %d keywords", len(results))
    return results
