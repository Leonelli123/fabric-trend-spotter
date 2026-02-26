"""Google Trends data for fabric-related search interest.

This is the most reliable data source since it uses an API rather than
web scraping. Google Trends data serves as a leading indicator - search
interest often rises 1-3 months before marketplace listings increase.
"""

import logging
import time
from config import FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS

logger = logging.getLogger(__name__)

# Prioritized keywords - most important ones first so if we hit rate
# limits we at least have the most valuable data
PRIORITY_FABRIC_KEYWORDS = [
    "linen fabric", "cotton fabric", "double gauze fabric", "velvet fabric",
    "silk fabric", "jersey fabric", "denim fabric", "flannel fabric",
    "rayon fabric", "chiffon fabric", "canvas fabric", "satin fabric",
]

PRIORITY_PATTERN_KEYWORDS = [
    "floral fabric", "geometric fabric", "botanical fabric", "cottagecore fabric",
    "watercolor fabric", "batik fabric", "ditsy fabric", "abstract fabric",
    "vintage fabric", "toile fabric", "mushroom fabric", "celestial fabric",
]

PRIORITY_COLOR_KEYWORDS = [
    "sage green fabric", "dusty rose fabric", "terracotta fabric",
    "navy fabric", "emerald fabric", "lavender fabric",
    "mustard fabric", "olive fabric", "rust fabric",
]


def fetch_google_trends():
    """Fetch Google Trends data for fabric-related keywords.

    Uses exponential backoff and prioritized keyword batches to maximize
    data collection even under rate limiting.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.warning("pytrends not installed, skipping Google Trends")
        return {}

    results = {}
    all_keywords = (
        PRIORITY_FABRIC_KEYWORDS +
        PRIORITY_PATTERN_KEYWORDS +
        PRIORITY_COLOR_KEYWORDS
    )

    # Process in batches of 5 (Google Trends API limit)
    groups = [all_keywords[i:i + 5] for i in range(0, len(all_keywords), 5)]
    consecutive_failures = 0
    base_delay = 3  # Start with 3 second delay

    for batch_idx, group in enumerate(groups):
        # Stop if we're getting consistently rate-limited
        if consecutive_failures >= 3:
            logger.warning(
                "Stopping Google Trends after %d consecutive failures. "
                "Got data for %d keywords.", consecutive_failures, len(results)
            )
            break

        delay = base_delay * (2 ** consecutive_failures)
        time.sleep(min(delay, 30))

        try:
            pytrends = TrendReq(hl="en-US", tz=360)
            pytrends.build_payload(group, timeframe="today 3-m", geo="US")
            interest = pytrends.interest_over_time()

            if interest is not None and not interest.empty:
                for kw in group:
                    if kw in interest.columns:
                        avg_interest = interest[kw].mean()
                        recent_interest = interest[kw].iloc[-7:].mean()
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
                consecutive_failures = 0
                logger.info(
                    "Google Trends batch %d/%d: got %d keywords",
                    batch_idx + 1, len(groups), len(group),
                )
            else:
                consecutive_failures += 1

        except Exception as e:
            consecutive_failures += 1
            logger.warning(
                "Google Trends batch %d failed (attempt %d): %s",
                batch_idx + 1, consecutive_failures, e,
            )

    logger.info(
        "Google Trends complete: %d/%d keywords fetched",
        len(results), len(all_keywords),
    )
    return results
