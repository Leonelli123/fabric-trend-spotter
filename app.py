"""Flask web application for the Fabric Trend Spotter dashboard."""

import logging
import json
import hashlib
import hmac
import base64
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
    fetch_instagram_trends, analyze_instagram_data, ig_is_configured,
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

    # Instagram social data
    ig_data = scrape_status.get("ig_result", {})

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
        ig_data=ig_data,
        ig_configured=ig_is_configured(),
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
    """Privacy policy page (required for Meta app review)."""
    return render_template("privacy.html", current_date=datetime.now().strftime("%B %d, %Y"))


@app.route("/terms")
def terms_of_service():
    """Terms of Service page (required for Meta app review)."""
    return render_template("terms.html", current_date=datetime.now().strftime("%B %d, %Y"))


@app.route("/deauthorize", methods=["POST"])
def deauthorize_callback():
    """Meta deauthorize callback - called when a user removes the app.

    Meta sends a signed_request POST parameter. We don't store user data,
    so we just acknowledge the request and return a confirmation.
    """
    signed_request = request.form.get("signed_request", "")
    if signed_request:
        logger.info("Received deauthorize callback from Meta")
    return jsonify({"status": "ok", "message": "No user data to remove"})


@app.route("/data-deletion", methods=["POST", "GET"])
def data_deletion():
    """Meta data deletion callback / status page.

    POST: Meta sends a signed_request when user requests data deletion.
          We return a confirmation_code and a status URL.
    GET:  Status check page - shows deletion was completed (we store no user data).
    """
    if request.method == "GET":
        code = request.args.get("code", "none")
        return render_template(
            "data_deletion_status.html",
            confirmation_code=code,
            current_date=datetime.now().strftime("%B %d, %Y"),
        )

    # POST from Meta
    signed_request = request.form.get("signed_request", "")
    confirmation_code = "FTS-DEL-" + hashlib.sha256(
        (signed_request + datetime.now().isoformat()).encode()
    ).hexdigest()[:12].upper()

    logger.info("Data deletion request received, code: %s", confirmation_code)

    # Return the response Meta expects
    return jsonify({
        "url": request.url_root.rstrip("/") + f"/data-deletion?code={confirmation_code}",
        "confirmation_code": confirmation_code,
    })


@app.route("/api/instagram-trends")
def api_instagram_trends():
    """API endpoint for Instagram hashtag trend data."""
    ig_data = scrape_status.get("ig_result", {})
    if not ig_data:
        return jsonify({
            "configured": ig_is_configured(),
            "message": "No Instagram data yet. Run a scrape to fetch hashtag trends."
            if ig_is_configured()
            else "Instagram API not configured. Set INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ID.",
        })
    return jsonify(ig_data)


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

        # Step 4: Save and analyze
        if all_listings:
            save_listings(all_listings)

        logger.info(
            "Analyzing %d listings (%d seed + %d live)...",
            len(all_listings), len(seed_listings), live_count,
        )
        result = analyze_trends(all_listings, google_data)

        # Step 5: Run forecasting
        logger.info("Running trend forecasts...")
        forecasts = run_forecasts(result, google_data)

        emerging = [f for f in forecasts if f["lifecycle"] == "emerging"]
        rising = [f for f in forecasts if f["lifecycle"] == "rising"]

        # Step 6: Instagram Social Trends (optional - requires Meta app approval)
        ig_result = {}
        try:
            if ig_is_configured():
                logger.info("Fetching Instagram hashtag trends...")
                raw_ig = fetch_instagram_trends()
                if raw_ig:
                    ig_result = analyze_instagram_data(raw_ig)
                    scrape_status["ig_result"] = ig_result
                    source_status["Instagram"] = {
                        "status": "ok",
                        "count": ig_result.get("total_hashtags_tracked", 0),
                        "note": f"{ig_result.get('total_hashtags_tracked', 0)} hashtags",
                    }
                    logger.info(
                        "Instagram: %d hashtags analyzed",
                        ig_result.get("total_hashtags_tracked", 0),
                    )
                else:
                    source_status["Instagram"] = {
                        "status": "empty",
                        "count": 0,
                        "note": "No data returned (rate limited?)",
                    }
            else:
                source_status["Instagram"] = {
                    "status": "empty",
                    "count": 0,
                    "note": "Not configured (set INSTAGRAM_ACCESS_TOKEN)",
                }
        except Exception as e:
            source_status["Instagram"] = {
                "status": "error",
                "count": 0,
                "note": str(e)[:100],
            }
            logger.warning("Instagram failed: %s", e)

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
            "ig_hashtags": ig_result.get("total_hashtags_tracked", 0),
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


if __name__ == "__main__":
    init_db()
    app.run(debug=config.DEBUG, port=5000)
