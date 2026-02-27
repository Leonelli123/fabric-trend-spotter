"""Trend forecasting engine - predicts where trends are heading.

Uses velocity (rate of change), acceleration (change in velocity),
cross-platform convergence, and lifecycle classification to forecast
which fabric trends will grow before they go mainstream.
"""

import logging
import math
from collections import defaultdict
from config import LIFECYCLE_THRESHOLDS, SEGMENTS
from database import get_trend_history, save_forecasts

logger = logging.getLogger(__name__)


def run_forecasts(current_trends, google_data=None):
    """
    Generate forecasts for all tracked terms.

    Forecasting approach:
    1. Calculate velocity (score change over time)
    2. Calculate acceleration (velocity change over time)
    3. Detect cross-platform convergence signals
    4. Classify lifecycle stage
    5. Predict future score trajectory
    """
    if google_data is None:
        google_data = {}

    forecasts = []
    all_terms = (
        current_trends.get("fabric_types", []) +
        current_trends.get("patterns", []) +
        current_trends.get("colors", []) +
        current_trends.get("styles", [])
    )

    for item in all_terms:
        term = item["term"]
        category = item["category"]
        current_score = item["score"]

        # Get historical data for velocity calculation
        history = get_trend_history(term, days=60)
        velocity = _calculate_velocity(history, current_score)
        acceleration = _calculate_acceleration(history)

        # Analyze cross-platform signals
        signals = _detect_signals(item, google_data)

        # Classify lifecycle stage
        lifecycle = _classify_lifecycle(current_score, velocity, acceleration)

        # Predict future score
        predicted_score = _predict_score(
            current_score, velocity, acceleration, signals, lifecycle
        )

        # Calculate confidence based on data quality
        confidence = _calculate_confidence(history, signals, item)

        forecasts.append({
            "term": term,
            "category": category,
            "current_score": current_score,
            "predicted_score": round(predicted_score, 1),
            "velocity": round(velocity, 3),
            "acceleration": round(acceleration, 3),
            "lifecycle": lifecycle,
            "confidence": round(confidence, 1),
            "signals": signals,
        })

    # Sort by predicted growth potential
    forecasts.sort(
        key=lambda f: f["predicted_score"] - f["current_score"], reverse=True
    )

    save_forecasts(forecasts)
    return forecasts


def _calculate_velocity(history, current_score):
    """
    Calculate the rate of change in trend score.
    Positive = growing, Negative = declining.
    Returns normalized velocity (-1 to +1 range).

    Uses weighted average of recent changes for smoothing — prevents
    single-day noise from causing lifecycle oscillation.
    """
    if len(history) < 2:
        # No history: conservative estimate, not an inflated 0.5
        return 0.05 if current_score > 10 else 0.0

    scores = [h["score"] for h in history] + [current_score]

    if len(scores) >= 4:
        # Weighted velocity: recent changes matter more
        # Compare last quarter vs first quarter of history
        quarter = max(len(scores) // 4, 1)
        old_avg = sum(scores[:quarter]) / quarter
        new_avg = sum(scores[-quarter:]) / quarter
    else:
        old_avg = scores[0]
        new_avg = current_score

    if old_avg <= 0:
        return 0.1 if new_avg > 5 else 0.0

    velocity = (new_avg - old_avg) / max(old_avg, 1)
    return max(-1.0, min(1.0, velocity))


def _calculate_acceleration(history):
    """
    Calculate the change in velocity (is growth speeding up or slowing down?).
    Positive acceleration = growth is accelerating (strong buy signal).
    """
    if len(history) < 3:
        return 0.0

    scores = [h["score"] for h in history]
    mid = len(scores) // 2

    # Velocity in first half
    first_half = scores[:mid]
    second_half = scores[mid:]

    if not first_half or not second_half:
        return 0.0

    v1 = (first_half[-1] - first_half[0]) / max(len(first_half), 1)
    v2 = (second_half[-1] - second_half[0]) / max(len(second_half), 1)

    return max(-1.0, min(1.0, v2 - v1))


def _detect_signals(item, google_data):
    """
    Detect multiple convergent signals that indicate a trend is building.
    Returns a list of signal descriptions with strength ratings.
    """
    signals = []

    # Signal 1: Google Trends rising
    if item.get("google_trending_up"):
        signals.append({
            "source": "google_trends",
            "type": "rising_search",
            "description": f"Google search interest for '{item['term']}' is rising",
            "strength": "strong",
            "lead_months": 3,
        })

    # Signal 2: Multi-platform presence
    sources = item.get("by_source", {})
    if len(sources) >= 3:
        signals.append({
            "source": "cross_platform",
            "type": "convergence",
            "description": (
                f"'{item['term']}' found on {len(sources)} platforms "
                f"(strong convergence signal)"
            ),
            "strength": "strong",
            "lead_months": 2,
        })
    elif len(sources) >= 2:
        signals.append({
            "source": "cross_platform",
            "type": "convergence",
            "description": f"'{item['term']}' appearing on {len(sources)} platforms",
            "strength": "moderate",
            "lead_months": 3,
        })

    # Signal 3: High Google interest but low marketplace listings
    google_key = f"{item['term']} fabric"
    google_info = google_data.get(google_key, {})
    if google_info.get("recent_interest", 0) > 40 and item["mention_count"] < 10:
        signals.append({
            "source": "demand_gap",
            "type": "undersupply",
            "description": (
                f"High search demand (Google: {google_info['recent_interest']}) "
                f"but only {item['mention_count']} listings = market gap"
            ),
            "strength": "strong",
            "lead_months": 1,
        })

    # Signal 4: High favorites-to-listings ratio (demand exceeds supply)
    if item.get("avg_favorites", 0) > 50 and item["mention_count"] < 20:
        signals.append({
            "source": "engagement",
            "type": "high_demand",
            "description": (
                f"High engagement ({item['avg_favorites']} avg favorites) "
                f"relative to supply"
            ),
            "strength": "moderate",
            "lead_months": 2,
        })

    # Signal 5: Price premium (consumers paying more = strong demand)
    if item.get("avg_price") and item["avg_price"] > 15:
        signals.append({
            "source": "pricing",
            "type": "premium",
            "description": (
                f"Premium pricing (${item['avg_price']:.2f}/yard) suggests "
                f"strong willingness to pay"
            ),
            "strength": "moderate",
            "lead_months": 1,
        })

    # Signal 7: Pinterest presence (visual trend leading indicator)
    pinterest_count = sources.get("pinterest", 0)
    if pinterest_count >= 5:
        signals.append({
            "source": "pinterest",
            "type": "visual_trend",
            "description": (
                f"'{item['term']}' found in {pinterest_count} Pinterest pins "
                f"(strong visual trend signal)"
            ),
            "strength": "strong",
            "lead_months": 2,
        })
    elif pinterest_count >= 2:
        signals.append({
            "source": "pinterest",
            "type": "visual_trend",
            "description": (
                f"'{item['term']}' appearing on Pinterest ({pinterest_count} pins)"
            ),
            "strength": "moderate",
            "lead_months": 3,
        })

    # Signal 6: Segment-specific relevance
    for seg_key, seg_config in SEGMENTS.items():
        priority_terms = (
            seg_config.get("priority_fabrics", []) +
            seg_config.get("priority_patterns", [])
        )
        if item["term"].lower() in [t.lower() for t in priority_terms]:
            signals.append({
                "source": "segment_fit",
                "type": "segment_relevance",
                "description": (
                    f"Relevant to {seg_config['label']} segment"
                ),
                "strength": "info",
                "lead_months": 0,
            })

    return signals


def _classify_lifecycle(score, velocity, acceleration):
    """
    Classify where a trend sits in its lifecycle.

    Uses thresholds from config.LIFECYCLE_THRESHOLDS as the single source
    of truth. Classification order matters — first match wins.

    Stages:
    - emerging:  Low score but positive velocity. The trend is just starting.
    - rising:    Growing score and positive velocity. Get in now.
    - peak:      High score but velocity slowing. Market is saturated.
    - declining: Score dropping. Time to move on.
    - stable:    Consistent score, low velocity. Evergreen demand.
    """
    t = LIFECYCLE_THRESHOLDS

    # Declining: score is dropping meaningfully
    if velocity < t["declining"]["max_velocity"]:
        return "declining"

    # Emerging: new trend with growth momentum but still small
    if velocity >= t["emerging"]["min_velocity"] and score <= t["emerging"]["max_score"]:
        return "emerging"

    # Rising: growing and has room to grow more
    if (velocity >= t["rising"]["min_velocity"]
            and score >= t["rising"]["min_score"]
            and score <= t["rising"]["max_score"]):
        return "rising"

    # Peak: high score but growth stalled
    if score >= t["peak"]["min_score"] and velocity <= t["peak"]["max_velocity"]:
        return "peak"

    # Stable: consistent demand, not moving much
    if (score >= t["stable"]["min_score"]
            and velocity <= t["stable"]["max_velocity"]
            and velocity >= t["stable"]["min_velocity"]):
        return "stable"

    # Fallbacks
    if velocity > 0 and score < 20:
        return "emerging"
    if velocity > 0:
        return "rising"
    return "stable"


def _predict_score(current_score, velocity, acceleration, signals, lifecycle):
    """
    Predict what the trend score will be in 30 days.
    Uses velocity + acceleration + signal strength as a simple model.
    """
    # Base prediction: current trajectory
    velocity_component = velocity * current_score * 0.5

    # Acceleration modifier
    accel_component = acceleration * current_score * 0.2

    # Signal boost: strong signals add prediction confidence
    signal_boost = 0
    for sig in signals:
        if sig["strength"] == "strong":
            signal_boost += 5
        elif sig["strength"] == "moderate":
            signal_boost += 2

    # Lifecycle modifiers
    lifecycle_mod = {
        "emerging": 1.3,   # Emerging trends get a boost
        "rising": 1.15,    # Rising trends continue upward
        "peak": 0.95,      # Peak trends start declining
        "declining": 0.8,  # Declining trends accelerate downward
        "stable": 1.0,     # Stable trends stay stable
    }.get(lifecycle, 1.0)

    predicted = (current_score + velocity_component + accel_component + signal_boost)
    predicted *= lifecycle_mod

    # Clamp to valid range
    return max(0, min(100, predicted))


def _calculate_confidence(history, signals, item):
    """
    Calculate confidence level (0-100%) in the forecast.
    Integrates data quality, history depth, signal count, and source diversity.
    """
    confidence = 15  # Lower base - must be earned

    # Historical data depth
    data_points = len(history)
    confidence += min(data_points * 5, 20)

    # Signal count
    strong_signals = sum(1 for s in signals if s["strength"] == "strong")
    mod_signals = sum(1 for s in signals if s["strength"] == "moderate")
    confidence += strong_signals * 8 + mod_signals * 4

    # Source diversity (multi-platform = much more reliable)
    sources = len(item.get("by_source", {}))
    confidence += min(sources * 7, 21)

    # Google data available
    if item.get("google_interest", 0) > 0:
        confidence += 8

    # Pinterest data available (visual trends are strong fabric signals)
    pinterest_count = item.get("by_source", {}).get("pinterest", 0)
    if pinterest_count >= 5:
        confidence += 6
    elif pinterest_count >= 2:
        confidence += 3

    # Data quality from the analysis layer
    tier = item.get("confidence_tier", "moderate")
    tier_bonus = {
        "verified": 15,
        "strong": 10,
        "moderate": 5,
        "weak": -10,
    }.get(tier, 0)
    confidence += tier_bonus

    # Seller diversity (not just one shop)
    sellers = item.get("unique_sellers", 1)
    if sellers >= 5:
        confidence += 8
    elif sellers >= 3:
        confidence += 5
    elif sellers <= 1:
        confidence -= 5

    # Quality of underlying listings
    avg_quality = item.get("avg_quality", 0)
    confidence += int(avg_quality * 10)  # 0-10 bonus

    return max(5, min(95, confidence))
