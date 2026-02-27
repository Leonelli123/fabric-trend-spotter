"""Flask web application for the Fabric Trend Spotter dashboard."""

import logging
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from database import (
    init_db, get_latest_trends, get_trend_history, get_recent_listings,
    get_scrape_stats, get_forecasts, get_trend_images,
)
from scrapers import (
    scrape_etsy, scrape_amazon, scrape_spoonflower,
    fetch_google_trends, fetch_european_trends,
    get_seed_listings, get_european_seed_listings,
    scrape_pinterest, analyze_pinterest_data,
    fetch_trend_reports,
)
from analysis import analyze_trends, analyze_european_trends, run_forecasts
from database import save_listings
from config import SEGMENTS, EUROPEAN_COUNTRIES, EUROPEAN_REGIONS
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Initialize database on import (needed for gunicorn)
init_db()

# Track scraping state
scrape_status = {
    "running": False,
    "last_run": None,
    "last_result": None,
    "error": None,
}


@app.route("/")
def dashboard():
    """Main dashboard page."""
    trends = {
        "fabric_types": get_latest_trends("fabric_type", limit=15),
        "patterns": get_latest_trends("pattern", limit=15),
        "colors": get_latest_trends("color", limit=15),
        "styles": get_latest_trends("style", limit=15),
    }
    forecasts = get_forecasts(limit=20)
    stats = get_scrape_stats()

    # Get images for visual gallery
    images = get_trend_images(limit=40)

    # Get segment data
    segment_data = {}
    for seg_key in SEGMENTS:
        seg_trends = get_latest_trends(segment=seg_key, limit=10)
        if seg_trends:
            segment_data[seg_key] = {
                "config": SEGMENTS[seg_key],
                "trends": seg_trends,
            }

    # Get European market data from latest snapshots
    eu_data = scrape_status.get("eu_result", {})

    # Pinterest social/visual trend data
    pinterest_data = scrape_status.get("pinterest_result", {})

    # Action board and insights
    action_board = scrape_status.get("action_board", {})
    insights = scrape_status.get("insights", [])

    return render_template(
        "dashboard.html",
        trends=trends,
        forecasts=forecasts,
        images=images,
        stats=stats,
        scrape_status=scrape_status,
        segments=SEGMENTS,
        segment_data=segment_data,
        eu_data=eu_data,
        eu_countries=EUROPEAN_COUNTRIES,
        eu_regions=EUROPEAN_REGIONS,
        pinterest_data=pinterest_data,
        action_board=action_board,
        insights=insights,
    )


@app.route("/api/scrape", methods=["POST"])
def trigger_scrape():
    """Trigger a new data scrape in the background."""
    if scrape_status["running"]:
        return jsonify({"status": "already_running"}), 409

    thread = threading.Thread(target=_run_scrape, daemon=True)
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/trends")
def api_trends():
    """API endpoint for trend data."""
    category = request.args.get("category")
    segment = request.args.get("segment")
    limit = int(request.args.get("limit", 20))
    trends = get_latest_trends(category, segment, limit)
    return jsonify(trends)


@app.route("/api/trend-history/<term>")
def api_trend_history(term):
    """API endpoint for a term's trend history."""
    days = int(request.args.get("days", 30))
    history = get_trend_history(term, days)
    return jsonify(history)


@app.route("/api/listings")
def api_listings():
    """API endpoint for recent listings."""
    source = request.args.get("source")
    segment = request.args.get("segment")
    limit = int(request.args.get("limit", 50))
    listings = get_recent_listings(source, segment, limit)
    return jsonify(listings)


@app.route("/api/forecasts")
def api_forecasts():
    """API endpoint for trend forecasts."""
    category = request.args.get("category")
    lifecycle = request.args.get("lifecycle")
    limit = int(request.args.get("limit", 30))
    forecasts = get_forecasts(category, lifecycle, limit)
    return jsonify(forecasts)


@app.route("/api/images")
def api_images():
    """API endpoint for trend images."""
    term = request.args.get("term")
    category = request.args.get("category")
    segment = request.args.get("segment")
    limit = int(request.args.get("limit", 40))
    images = get_trend_images(term, category, segment, limit)
    return jsonify(images)


@app.route("/api/european-trends")
def api_european_trends():
    """API endpoint for European market trend data."""
    country = request.args.get("country")
    eu_data = scrape_status.get("eu_result", {})
    try:
        if country:
            country_data = eu_data.get("countries", {}).get(country, {})
            return jsonify(country_data)
        # Return summary to avoid serialization issues with full data
        summary = {
            "total_listings": eu_data.get("total_listings", 0),
            "total_countries": eu_data.get("total_countries", 0),
            "countries": list(eu_data.get("countries", {}).keys()),
            "regions": list(eu_data.get("regions", {}).keys()),
        }
        return jsonify(summary)
    except Exception:
        return jsonify({"error": "EU data not yet available"})


@app.route("/privacy")
def privacy_policy():
    """Privacy policy page."""
    return render_template("privacy.html", current_date=datetime.now().strftime("%B %d, %Y"))


@app.route("/terms")
def terms_of_service():
    """Terms of Service page."""
    return render_template("terms.html", current_date=datetime.now().strftime("%B %d, %Y"))


@app.route("/api/pinterest-trends")
def api_pinterest_trends():
    """API endpoint for Pinterest fabric trend data."""
    pinterest_data = scrape_status.get("pinterest_result", {})
    if not pinterest_data:
        return jsonify({
            "message": "No Pinterest data yet. Click Refresh Data to scrape Pinterest trends.",
        })
    return jsonify(pinterest_data)


@app.route("/api/status")
def api_status():
    """API endpoint for scrape status."""
    return jsonify(scrape_status)


def _run_scrape():
    """Run all scrapers and analyze the results.

    Strategy:
    1. Always load seed data as a baseline (so the dashboard is never empty)
    2. Attempt live scrapers - treat failures gracefully
    3. Fetch Google Trends with backoff
    4. Run analysis and forecasting on combined data
    5. Report clearly which sources succeeded/failed
    """
    global scrape_status
    scrape_status["running"] = True
    scrape_status["error"] = None

    source_status = {}

    try:
        logger.info("Starting data collection...")
        all_listings = []

        # Step 1: Seed data - always available baseline
        seed_listings = get_seed_listings()
        all_listings.extend(seed_listings)
        source_status["Seed Data"] = {
            "status": "ok",
            "count": len(seed_listings),
            "note": "Curated baseline trends",
        }
        logger.info("Loaded %d seed listings as baseline", len(seed_listings))

        # Step 2: Attempt live scrapers (failures are expected from cloud IPs)
        live_count = 0
        for name, scraper in [
            ("Etsy", scrape_etsy),
            ("Amazon", scrape_amazon),
            ("Spoonflower", scrape_spoonflower),
            ("Pinterest", scrape_pinterest),
        ]:
            try:
                logger.info("Attempting %s...", name)
                listings = scraper()
                if listings:
                    all_listings.extend(listings)
                    live_count += len(listings)
                    source_status[name] = {
                        "status": "ok",
                        "count": len(listings),
                    }
                    logger.info("Got %d listings from %s", len(listings), name)
                else:
                    source_status[name] = {
                        "status": "empty",
                        "count": 0,
                        "note": "No listings returned (likely blocked)",
                    }
                    logger.warning("%s returned no listings", name)
            except Exception as e:
                source_status[name] = {
                    "status": "error",
                    "count": 0,
                    "note": str(e)[:100],
                }
                logger.warning("%s failed: %s", name, e)

        # Step 3: Google Trends (works with backoff)
        google_data = {}
        try:
            logger.info("Fetching Google Trends...")
            google_data = fetch_google_trends()
            source_status["Google Trends"] = {
                "status": "ok" if google_data else "empty",
                "count": len(google_data),
                "note": f"{len(google_data)} keywords" if google_data else "Rate limited",
            }
        except Exception as e:
            source_status["Google Trends"] = {
                "status": "error",
                "count": 0,
                "note": str(e)[:100],
            }
            logger.warning("Google Trends failed: %s", e)

        # Step 3b: Industry trend reports (authoritative sources)
        trend_report = {}
        try:
            logger.info("Fetching industry trend reports...")
            trend_report = fetch_trend_reports()
            signals = trend_report.get("signals", [])
            if signals:
                # Pass trend report signals through google_data dict for the analysis engine
                google_data["_trend_report_signals"] = signals
                source_status["Trend Reports"] = {
                    "status": "ok",
                    "count": len(signals),
                    "note": f"{len(signals)} signals from {trend_report.get('sources_scraped', 0)} sources",
                }
                logger.info("Trend reports: %d signals extracted", len(signals))
            else:
                source_status["Trend Reports"] = {
                    "status": "empty",
                    "count": 0,
                    "note": "No signals extracted",
                }
        except Exception as e:
            source_status["Trend Reports"] = {
                "status": "error",
                "count": 0,
                "note": str(e)[:100],
            }
            logger.warning("Trend reports failed: %s", e)

        # Step 4: Save and analyze
        if all_listings:
            save_listings(all_listings)

        logger.info(
            "Analyzing %d listings (%d seed + %d live)...",
            len(all_listings), len(seed_listings), live_count,
        )
        result = analyze_trends(all_listings, google_data)

        # Store insights for dashboard action board
        scrape_status["insights"] = result.get("insights", [])

        # Step 5: Run forecasting
        logger.info("Running trend forecasts...")
        forecasts = run_forecasts(result, google_data)

        emerging = [f for f in forecasts if f["lifecycle"] == "emerging"]
        rising = [f for f in forecasts if f["lifecycle"] == "rising"]

        # Generate action board recommendations
        scrape_status["action_board"] = _build_action_board(
            result, forecasts, google_data
        )

        # Step 6: Pinterest Social/Visual Trends
        pinterest_result = {}
        try:
            # Get Pinterest listings from the scraper step above
            pinterest_listings = [l for l in all_listings if l.get("source") == "pinterest"]
            if pinterest_listings:
                logger.info("Analyzing %d Pinterest pins...", len(pinterest_listings))
                pinterest_result = analyze_pinterest_data(pinterest_listings)
                scrape_status["pinterest_result"] = pinterest_result
                logger.info(
                    "Pinterest analysis: %d pins, %d fabric signals, %d pattern signals",
                    pinterest_result.get("total_pins_analyzed", 0),
                    len(pinterest_result.get("fabric_signals", [])),
                    len(pinterest_result.get("pattern_signals", [])),
                )
            else:
                logger.info("No Pinterest data to analyze (scraper may have been blocked)")
        except Exception as e:
            logger.warning("Pinterest analysis failed: %s", e)

        # Step 7: European Markets
        logger.info("Loading European market data...")
        eu_listings = get_european_seed_listings()
        if eu_listings:
            save_listings(eu_listings)
        source_status["EU Markets"] = {
            "status": "ok",
            "count": len(eu_listings),
            "note": f"{len(EUROPEAN_COUNTRIES)} countries",
        }

        # European Google Trends (optional, may be rate-limited)
        eu_google = {}
        try:
            logger.info("Fetching European Google Trends...")
            eu_google = fetch_european_trends()
            if eu_google:
                source_status["EU Google Trends"] = {
                    "status": "ok",
                    "count": sum(len(v) for v in eu_google.values()),
                    "note": f"{len(eu_google)} countries",
                }
        except Exception as e:
            logger.warning("European Google Trends failed: %s", e)

        logger.info("Analyzing European trends...")
        eu_result = analyze_european_trends(eu_listings, eu_google)
        scrape_status["eu_result"] = eu_result

        # Build status report
        ok_sources = [k for k, v in source_status.items() if v["status"] == "ok"]
        failed_sources = [
            k for k, v in source_status.items() if v["status"] in ("error", "empty")
        ]

        scrape_status["last_run"] = datetime.now().isoformat()
        scrape_status["last_result"] = {
            "total_listings": result["total_listings_analyzed"],
            "sources": result["sources"],
            "live_listings": live_count,
            "seed_listings": len(seed_listings),
            "eu_listings": len(eu_listings),
            "eu_countries": eu_result.get("total_countries", 0),
            "google_keywords": len(google_data),
            "top_fabric": (
                result["fabric_types"][0]["term"] if result["fabric_types"] else "N/A"
            ),
            "top_pattern": (
                result["patterns"][0]["term"] if result["patterns"] else "N/A"
            ),
            "top_color": (
                result["colors"][0]["term"] if result["colors"] else "N/A"
            ),
            "insights_count": len(result.get("insights", [])),
            "emerging_count": len(emerging),
            "rising_count": len(rising),
            "segments_analyzed": len(result.get("segment_trends", {})),
            "pinterest_pins": pinterest_result.get("total_pins_analyzed", 0),
            "source_status": source_status,
            "ok_sources": ok_sources,
            "failed_sources": failed_sources,
        }
        logger.info(
            "Collection complete! %d US listings (%d live), %d EU listings "
            "(%d countries), %d forecasts. Sources OK: %s. Failed: %s",
            len(all_listings), live_count, len(eu_listings),
            eu_result.get("total_countries", 0), len(forecasts),
            ok_sources, failed_sources,
        )

    except Exception as e:
        logger.error("Scrape failed: %s", e, exc_info=True)
        scrape_status["error"] = str(e)
    finally:
        scrape_status["running"] = False


def _build_action_board(result, forecasts, google_data):
    """Build unified action board with design briefs and 4-bucket forecasts.

    Phase 1 redesign: replaces 5 role tabs with a single prioritized list,
    adds cross-referenced Design Briefs (color × pattern × style), and
    simplifies lifecycle to 4 buckets.
    """
    from datetime import datetime

    fabrics = result.get("fabric_types", [])
    patterns = result.get("patterns", [])
    colors = result.get("colors", [])
    styles = result.get("styles", [])

    # Map forecasts into 4 simplified buckets
    design_now = []   # emerging + rising = act on these
    watch = []        # stable / new with low confidence
    phase_out = []    # declining
    evergreen = []    # peak + high-confidence stable (proven demand)

    for f in forecasts:
        lc = f["lifecycle"]
        if lc in ("emerging", "rising"):
            design_now.append(f)
        elif lc == "declining":
            phase_out.append(f)
        elif lc == "peak" and f["current_score"] >= 30:
            evergreen.append(f)
        elif lc == "stable" and f["current_score"] >= 25 and f["confidence"] >= 40:
            evergreen.append(f)
        else:
            watch.append(f)

    # --- Summary stats ---
    summary = {
        "total_trends_tracked": len(fabrics) + len(patterns) + len(colors) + len(styles),
        "design_now_count": len(design_now),
        "watch_count": len(watch),
        "phase_out_count": len(phase_out),
        "evergreen_count": len(evergreen),
        "top_fabric": fabrics[0]["term"] if fabrics else "N/A",
        "top_pattern": patterns[0]["term"] if patterns else "N/A",
        "top_color": colors[0]["term"] if colors else "N/A",
        "top_style": styles[0]["term"] if styles else "N/A",
    }

    # --- Design Briefs: cross-reference colors × patterns × styles ---
    design_briefs = _generate_design_briefs(
        colors, patterns, styles, fabrics, forecasts, google_data
    )

    # --- Unified action list (all actions in one flat list, sorted by priority) ---
    actions = []

    # Actions from Design Now bucket
    for f in design_now[:6]:
        actions.append({
            "action": "order" if f["lifecycle"] == "rising" else "sample",
            "priority": "high" if f["lifecycle"] == "rising" else "medium",
            "term": f["term"],
            "category": f["category"],
            "bucket": "design_now",
            "reason": (
                f"{'Rising' if f['lifecycle'] == 'rising' else 'Emerging'} "
                f"(velocity +{f['velocity']*100:.0f}%) — score "
                f"{f['current_score']} heading to {f['predicted_score']}. "
                f"Confidence: {f['confidence']}%."
            ),
            "sort_score": f["predicted_score"] - f["current_score"] + f["current_score"] * 0.3,
        })

    # Promote evergreen items (high demand, proven)
    for f in evergreen[:4]:
        actions.append({
            "action": "promote",
            "priority": "medium",
            "term": f["term"],
            "category": f["category"],
            "bucket": "evergreen",
            "reason": (
                f"Proven demand (score {f['current_score']}). "
                f"Reliable seller — keep in stock and promote."
            ),
            "sort_score": f["current_score"] * 0.5,
        })

    # Phase out warnings
    for f in phase_out[:4]:
        actions.append({
            "action": "reduce",
            "priority": "high",
            "term": f["term"],
            "category": f["category"],
            "bucket": "phase_out",
            "reason": (
                f"Declining (velocity {f['velocity']*100:.0f}%). "
                f"Don't reorder — sell through remaining stock."
            ),
            "sort_score": abs(f["velocity"]) * 100,
        })

    # Premium pricing opportunities
    priced = [t for t in fabrics + patterns + colors + styles if t.get("avg_price", 0) > 20]
    priced.sort(key=lambda x: x.get("avg_price", 0), reverse=True)
    for t in priced[:2]:
        actions.append({
            "action": "premium",
            "priority": "medium",
            "term": t["term"],
            "category": t.get("category", ""),
            "bucket": "evergreen",
            "avg_price": t["avg_price"],
            "reason": f"Commands ${t['avg_price']:.2f}/unit avg — premium positioning opportunity.",
            "sort_score": t["avg_price"],
        })

    # Sort: high priority first, then by sort_score descending
    priority_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: (priority_order.get(a["priority"], 1), -a.get("sort_score", 0)))

    # --- Seasonal context ---
    month = datetime.now().month
    if month in (12, 1, 2):
        season = "Winter/Early Spring"
        seasonal_colors = ["ivory", "cream", "burgundy", "forest green", "navy",
                          "charcoal", "brown", "mocha"]
        seasonal_fabrics = ["wool", "flannel", "velvet", "fleece", "corduroy"]
    elif month in (3, 4, 5):
        season = "Spring/Summer Prep"
        seasonal_colors = ["blush pink", "lavender", "sage green", "baby blue",
                          "coral", "yellow", "mint"]
        seasonal_fabrics = ["cotton", "lawn", "linen", "voile", "chiffon"]
    elif month in (6, 7, 8):
        season = "Summer/Fall Prep"
        seasonal_colors = ["terracotta", "rust", "olive", "mustard", "burnt orange",
                          "forest green", "teal"]
        seasonal_fabrics = ["linen", "rayon", "jersey", "cotton", "gauze"]
    else:
        season = "Fall/Winter Prep"
        seasonal_colors = ["burgundy", "navy", "charcoal", "emerald", "brown",
                          "plum", "rust"]
        seasonal_fabrics = ["velvet", "wool", "flannel", "corduroy", "fleece"]

    seasonal = {
        "season": season,
        "recommended_colors": seasonal_colors,
        "recommended_fabrics": seasonal_fabrics,
        "reason": f"Based on seasonal buying patterns for {season}.",
    }

    # --- Macro trends ---
    macro_trends = []
    macro_terms = ["sustainable", "organic", "minimalist", "quiet luxury",
                   "natural", "eco", "biodegradable", "linen", "hemp", "bamboo"]
    for t in styles + fabrics:
        if t["term"].lower() in macro_terms and t.get("score", 0) > 10:
            macro_trends.append({
                "term": t["term"],
                "score": t["score"],
                "category": t.get("category", "style"),
                "horizon": "6-12 months",
            })

    return {
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
        "actions": actions,
        "design_briefs": design_briefs,
        "buckets": {
            "design_now": design_now,
            "watch": watch,
            "phase_out": phase_out,
            "evergreen": evergreen,
        },
        "seasonal": seasonal,
        "macro_trends": macro_trends,
    }


def _generate_design_briefs(colors, patterns, styles, fabrics, forecasts, google_data):
    """Generate cross-referenced Design Briefs: color × pattern × style.

    Each brief is an actionable package combining trending dimensions into
    a single design direction with opportunity scoring.
    """
    briefs = []

    # Build lookup for forecast data
    fc_by_term = {}
    for f in forecasts:
        fc_by_term[f["term"].lower()] = f

    # Build lookup for google trending
    google_up = set()
    for key, val in google_data.items():
        if key.startswith("_"):
            continue
        if isinstance(val, dict) and val.get("trending_up"):
            google_up.add(key.split(" ")[0].lower())

    top_colors = colors[:8]
    top_patterns = patterns[:8]
    top_styles = styles[:5] if styles else []

    # Generate briefs by pairing top colors with top patterns,
    # filtered through style aesthetics
    used_combos = set()
    for color in top_colors:
        color_term = color["term"]
        color_score = color.get("score", 0)
        color_fc = fc_by_term.get(color_term.lower(), {})

        for pattern in top_patterns:
            pattern_term = pattern["term"]
            pattern_score = pattern.get("score", 0)
            pattern_fc = fc_by_term.get(pattern_term.lower(), {})

            combo_key = (color_term.lower(), pattern_term.lower())
            if combo_key in used_combos:
                continue

            # Pick the best-matching style for this combo
            best_style = None
            best_style_score = 0
            for style in top_styles:
                style_score = style.get("score", 0)
                if style_score > best_style_score:
                    best_style = style
                    best_style_score = style_score

            # Calculate opportunity score
            # Higher = more demand, less competition, better lifecycle position
            demand_signal = (color_score + pattern_score) / 2
            lifecycle_bonus = 0
            for fc in [color_fc, pattern_fc]:
                lc = fc.get("lifecycle", "")
                if lc == "emerging":
                    lifecycle_bonus += 15
                elif lc == "rising":
                    lifecycle_bonus += 10
                elif lc == "peak":
                    lifecycle_bonus += 2

            # Google trending bonus
            google_bonus = 0
            if color_term.lower().split()[0] in google_up:
                google_bonus += 10
            if pattern_term.lower().split()[0] in google_up:
                google_bonus += 10

            # Gap analysis: low listing count relative to search interest = gap
            color_gap = max(0, (color.get("google_interest", 0) - color.get("mention_count", 0) * 3))
            pattern_gap = max(0, (pattern.get("google_interest", 0) - pattern.get("mention_count", 0) * 3))
            gap_score = (color_gap + pattern_gap) / 2

            opportunity_score = demand_signal + lifecycle_bonus + google_bonus + gap_score

            if opportunity_score < 10:
                continue

            used_combos.add(combo_key)

            # Build the signal summary
            signals = []
            if color_fc.get("lifecycle") in ("emerging", "rising"):
                signals.append(f"{color_term.title()} is {color_fc['lifecycle']}")
            if pattern_fc.get("lifecycle") in ("emerging", "rising"):
                signals.append(f"{pattern_term.title()} is {pattern_fc['lifecycle']}")
            if color_term.lower().split()[0] in google_up:
                signals.append(f"Search demand up for {color_term.title()}")
            if pattern_term.lower().split()[0] in google_up:
                signals.append(f"Search demand up for {pattern_term.title()}")
            if gap_score > 5:
                signals.append("Market gap detected — low supply vs. demand")

            # Determine priority
            if opportunity_score >= 40:
                priority = "high"
            elif opportunity_score >= 20:
                priority = "medium"
            else:
                priority = "low"

            brief = {
                "color": color_term,
                "pattern": pattern_term,
                "style": best_style["term"] if best_style else None,
                "opportunity_score": round(opportunity_score, 1),
                "priority": priority,
                "signals": signals,
                "color_score": color_score,
                "pattern_score": pattern_score,
                "style_score": best_style_score,
                "color_lifecycle": color_fc.get("lifecycle", "unknown"),
                "pattern_lifecycle": pattern_fc.get("lifecycle", "unknown"),
            }
            briefs.append(brief)

    # Sort by opportunity score
    briefs.sort(key=lambda b: b["opportunity_score"], reverse=True)
    return briefs[:12]


if __name__ == "__main__":
    init_db()
    app.run(debug=config.DEBUG, port=5000)
