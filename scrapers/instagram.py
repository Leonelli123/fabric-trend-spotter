"""Instagram Graph API integration for fabric hashtag trend tracking.

Requires a Meta-approved Instagram Graph API token with permissions:
  - instagram_basic
  - pages_show_list
  - instagram_manage_insights (for hashtag search)

Setup:
  1. Create a Meta developer app at https://developers.facebook.com
  2. Get app approved for instagram_basic + pages_show_list
  3. Generate a long-lived token
  4. Set environment variables:
     - INSTAGRAM_ACCESS_TOKEN: Your long-lived access token
     - INSTAGRAM_BUSINESS_ID: Your Instagram Business Account ID
"""

import os
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_BUSINESS_ID = os.environ.get("INSTAGRAM_BUSINESS_ID", "")
GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Fabric-related hashtags to track
FABRIC_HASHTAGS = [
    # General fabric & sewing
    "fabriclove", "sewingfabric", "fabricaddict", "fabricstash",
    "sewingcommunity", "imakeclothes", "handmadewardrobe",
    "sewcialists", "memade", "diyfashion",
    # Fabric types
    "linenfabric", "cottonfabric", "silkfabric", "velvetfabric",
    "denimfabric", "jerseyfabric", "doublegauze", "libertyoflondon",
    # Patterns & prints
    "floralfabric", "fabricprint", "botanicalprint", "vintagefabric",
    "ditsynfloral", "geometricprint", "animalprint", "toiledejouy",
    # Quilting
    "quiltingfabric", "modernquilting", "quiltersofinstagram",
    "fatquarter", "patchworkfabric", "quiltingcotton",
    # Colors & aesthetics
    "fabriccolors", "cottagecorefabric", "bohofabric",
    "earthtonefabric", "pastelfabric", "jeweltones",
    # Trends
    "fabrictrends", "textiletrends", "sewingtrends",
    "fabricshopping", "newfabric", "fabrichaul",
]

# Rate limit: 30 unique hashtags per 7 days per IG user
# We track which hashtags we've queried to stay within limits
MAX_HASHTAGS_PER_WEEK = 30
REQUESTS_PER_HOUR = 200


def is_configured():
    """Check if Instagram API credentials are configured."""
    return bool(INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ID)


def _make_request(url, params=None):
    """Make a request to the Graph API with error handling."""
    import requests

    if params is None:
        params = {}
    params["access_token"] = INSTAGRAM_ACCESS_TOKEN

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        if "error" in data:
            error = data["error"]
            code = error.get("code", 0)
            msg = error.get("message", "Unknown error")

            # Rate limit hit
            if code == 4 or code == 32:
                logger.warning("Instagram API rate limit hit: %s", msg)
                return None

            # Token expired
            if code == 190:
                logger.error("Instagram token expired. Please refresh your token.")
                return None

            logger.warning("Instagram API error %d: %s", code, msg)
            return None

        return data
    except Exception as e:
        logger.warning("Instagram API request failed: %s", e)
        return None


def search_hashtag(hashtag):
    """Search for a hashtag ID by name.

    Note: Each unique hashtag search counts toward the 30/week limit.
    """
    url = f"{GRAPH_API_BASE}/ig_hashtag_search"
    params = {
        "user_id": INSTAGRAM_BUSINESS_ID,
        "q": hashtag,
    }
    data = _make_request(url, params)
    if data and "data" in data and data["data"]:
        return data["data"][0]["id"]
    return None


def get_hashtag_recent_media(hashtag_id, fields=None):
    """Get recent media for a hashtag.

    Returns up to 50 recent media objects (API limit).
    """
    if fields is None:
        fields = "id,caption,media_type,timestamp,like_count,comments_count"

    url = f"{GRAPH_API_BASE}/{hashtag_id}/recent_media"
    params = {
        "user_id": INSTAGRAM_BUSINESS_ID,
        "fields": fields,
    }
    data = _make_request(url, params)
    if data and "data" in data:
        return data["data"]
    return []


def get_hashtag_top_media(hashtag_id, fields=None):
    """Get top/popular media for a hashtag.

    Returns up to 50 top media objects.
    """
    if fields is None:
        fields = "id,caption,media_type,timestamp,like_count,comments_count"

    url = f"{GRAPH_API_BASE}/{hashtag_id}/top_media"
    params = {
        "user_id": INSTAGRAM_BUSINESS_ID,
        "fields": fields,
    }
    data = _make_request(url, params)
    if data and "data" in data:
        return data["data"]
    return []


def fetch_instagram_trends(hashtags=None, max_hashtags=25):
    """Fetch trend data from Instagram hashtags.

    Args:
        hashtags: List of hashtag strings to search. Defaults to FABRIC_HASHTAGS.
        max_hashtags: Max number of unique hashtags to query (stay under 30/week).

    Returns:
        dict: {
            "hashtag_name": {
                "hashtag_id": str,
                "recent_count": int,
                "top_media": [...],
                "recent_media": [...],
                "engagement_score": float,
                "fetched_at": str,
            }
        }
    """
    if not is_configured():
        logger.info(
            "Instagram API not configured. Set INSTAGRAM_ACCESS_TOKEN and "
            "INSTAGRAM_BUSINESS_ID environment variables."
        )
        return {}

    if hashtags is None:
        hashtags = FABRIC_HASHTAGS[:max_hashtags]
    else:
        hashtags = hashtags[:max_hashtags]

    results = {}
    request_count = 0

    for tag in hashtags:
        # Respect rate limits
        if request_count >= REQUESTS_PER_HOUR - 10:
            logger.warning("Approaching Instagram rate limit, stopping early.")
            break

        logger.info("Searching Instagram hashtag: #%s", tag)
        hashtag_id = search_hashtag(tag)
        request_count += 1

        if not hashtag_id:
            logger.warning("Hashtag #%s not found or rate limited", tag)
            continue

        # Brief pause between API calls
        time.sleep(0.5)

        # Get recent media
        recent = get_hashtag_recent_media(hashtag_id)
        request_count += 1
        time.sleep(0.5)

        # Get top media
        top = get_hashtag_top_media(hashtag_id)
        request_count += 1

        # Calculate engagement score from recent media
        engagement_score = 0
        if recent:
            total_likes = sum(m.get("like_count", 0) for m in recent)
            total_comments = sum(m.get("comments_count", 0) for m in recent)
            engagement_score = round(
                (total_likes + total_comments * 2) / max(len(recent), 1), 1
            )

        results[tag] = {
            "hashtag_id": hashtag_id,
            "recent_count": len(recent),
            "top_count": len(top),
            "recent_media": recent[:10],  # Keep top 10 for display
            "top_media": top[:10],
            "engagement_score": engagement_score,
            "fetched_at": datetime.now().isoformat(),
        }

        logger.info(
            "#%s: %d recent, %d top, engagement=%.1f",
            tag, len(recent), len(top), engagement_score,
        )

        # Rate limiting pause
        time.sleep(1)

    logger.info(
        "Instagram: fetched %d hashtags, %d API requests used",
        len(results), request_count,
    )
    return results


def analyze_instagram_data(ig_data):
    """Analyze Instagram hashtag data to extract fabric trend signals.

    Args:
        ig_data: Dict from fetch_instagram_trends()

    Returns:
        dict with trend signals organized by category
    """
    if not ig_data:
        return {}

    from config import FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS

    # Map hashtags to trend categories
    fabric_signals = {}
    pattern_signals = {}
    color_signals = {}

    # Hashtag-to-category mapping
    hashtag_fabric_map = {
        "linenfabric": "linen", "cottonfabric": "cotton", "silkfabric": "silk",
        "velvetfabric": "velvet", "denimfabric": "denim", "jerseyfabric": "jersey",
        "doublegauze": "double gauze", "quiltingcotton": "cotton",
    }
    hashtag_pattern_map = {
        "floralfabric": "floral", "fabricprint": "abstract",
        "botanicalprint": "botanical", "vintagefabric": "vintage",
        "ditsynfloral": "ditsy", "geometricprint": "geometric",
        "animalprint": "animal print", "toiledejouy": "toile",
    }
    hashtag_color_map = {
        "earthtonefabric": "earth tone", "pastelfabric": "pastel",
        "jeweltones": "jewel tone",
    }

    for tag, data in ig_data.items():
        engagement = data.get("engagement_score", 0)
        recent_count = data.get("recent_count", 0)
        signal_strength = engagement * 0.6 + recent_count * 0.4

        # Check fabric type hashtags
        if tag in hashtag_fabric_map:
            term = hashtag_fabric_map[tag]
            fabric_signals[term] = fabric_signals.get(term, 0) + signal_strength

        # Check pattern hashtags
        if tag in hashtag_pattern_map:
            term = hashtag_pattern_map[tag]
            pattern_signals[term] = pattern_signals.get(term, 0) + signal_strength

        # Check color hashtags
        if tag in hashtag_color_map:
            term = hashtag_color_map[tag]
            color_signals[term] = color_signals.get(term, 0) + signal_strength

        # Also scan captions from recent media for trend terms
        for media in data.get("recent_media", []):
            caption = (media.get("caption") or "").lower()
            if not caption:
                continue

            for fabric in FABRIC_TYPES:
                if fabric in caption:
                    fabric_signals[fabric] = fabric_signals.get(fabric, 0) + 1

            for pattern in PATTERN_TYPES:
                if pattern in caption:
                    pattern_signals[pattern] = pattern_signals.get(pattern, 0) + 1

            for color in COLOR_TERMS:
                if color in caption:
                    color_signals[color] = color_signals.get(color, 0) + 1

    # Sort by signal strength
    def sorted_signals(signals):
        return sorted(
            [{"term": k, "ig_score": round(v, 1)} for k, v in signals.items()],
            key=lambda x: x["ig_score"],
            reverse=True,
        )

    # Build top hashtags summary
    top_hashtags = sorted(
        [
            {
                "hashtag": f"#{k}",
                "engagement": v.get("engagement_score", 0),
                "recent_count": v.get("recent_count", 0),
                "top_count": v.get("top_count", 0),
            }
            for k, v in ig_data.items()
        ],
        key=lambda x: x["engagement"],
        reverse=True,
    )

    return {
        "fabric_signals": sorted_signals(fabric_signals),
        "pattern_signals": sorted_signals(pattern_signals),
        "color_signals": sorted_signals(color_signals),
        "top_hashtags": top_hashtags[:15],
        "total_hashtags_tracked": len(ig_data),
        "fetched_at": datetime.now().isoformat(),
    }
