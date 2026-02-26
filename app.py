"""Flask web application for the Fabric Trend Spotter dashboard."""

import logging
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from database import init_db, get_latest_trends, get_trend_history, get_recent_listings, get_scrape_stats
from scrapers import scrape_etsy, scrape_amazon, scrape_spoonflower, fetch_google_trends
from analysis import analyze_trends
from database import save_listings
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
        "fabric_types": get_latest_trends("fabric_type", 15),
        "patterns": get_latest_trends("pattern", 15),
        "colors": get_latest_trends("color", 15),
    }
    stats = get_scrape_stats()
    return render_template(
        "dashboard.html",
        trends=trends,
        stats=stats,
        scrape_status=scrape_status,
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
    limit = int(request.args.get("limit", 20))
    trends = get_latest_trends(category, limit)
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
    limit = int(request.args.get("limit", 50))
    listings = get_recent_listings(source, limit)
    return jsonify(listings)


@app.route("/api/status")
def api_status():
    """API endpoint for scrape status."""
    return jsonify(scrape_status)


def _run_scrape():
    """Run all scrapers and analyze the results."""
    global scrape_status
    scrape_status["running"] = True
    scrape_status["error"] = None

    try:
        logger.info("Starting data scrape...")
        all_listings = []

        # Run scrapers
        for name, scraper in [
            ("Etsy", scrape_etsy),
            ("Amazon", scrape_amazon),
            ("Spoonflower", scrape_spoonflower),
        ]:
            try:
                logger.info("Scraping %s...", name)
                listings = scraper()
                all_listings.extend(listings)
                logger.info("Got %d listings from %s", len(listings), name)
            except Exception as e:
                logger.error("Error scraping %s: %s", name, e)

        # Save listings
        if all_listings:
            save_listings(all_listings)

        # Fetch Google Trends
        google_data = {}
        try:
            logger.info("Fetching Google Trends...")
            google_data = fetch_google_trends()
        except Exception as e:
            logger.error("Error fetching Google Trends: %s", e)

        # Analyze
        logger.info("Analyzing %d listings...", len(all_listings))
        result = analyze_trends(all_listings, google_data)

        scrape_status["last_run"] = datetime.now().isoformat()
        scrape_status["last_result"] = {
            "total_listings": result["total_listings_analyzed"],
            "sources": result["sources"],
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
        }
        logger.info("Scrape complete! Analyzed %d listings.", len(all_listings))

    except Exception as e:
        logger.error("Scrape failed: %s", e)
        scrape_status["error"] = str(e)
    finally:
        scrape_status["running"] = False


if __name__ == "__main__":
    init_db()
    app.run(debug=config.DEBUG, port=5000)
