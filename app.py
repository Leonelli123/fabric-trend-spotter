"""Flask web application for the Fabric Trend Spotter dashboard."""

import gc
import logging
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from database import (
    init_db, get_latest_trends, get_trend_history, get_recent_listings,
    get_scrape_stats, get_forecasts, get_trend_images,
    get_price_history, get_price_stats_by_country,
    get_trend_deltas,
)
from scrapers import (
    scrape_etsy, scrape_amazon, scrape_spoonflower,
    fetch_google_trends, fetch_european_trends,
    get_seed_listings, get_european_seed_listings,
    scrape_pinterest, analyze_pinterest_data,
    fetch_trend_reports,
    scrape_eu_shops, scrape_competitors, get_eu_shop_summary,
    fetch_serpapi_trends, fetch_serpapi_shopping,
    fetch_serpapi_trend_images, fetch_serpapi_etsy,
    get_serpapi_summary,
)
from database import save_trend_images
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

    # European market data
    eu_data = scrape_status.get("eu_result", {})

    # Action board (weekly tasks, briefs, signals, gaps, forecasts)
    action_board = scrape_status.get("action_board", {})

    return render_template(
        "dashboard.html",
        trends=trends,
        scrape_status=scrape_status,
        eu_data=eu_data,
        action_board=action_board,
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


@app.route("/report/<country_code>")
def trend_report(country_code):
    """Generate a print-friendly B2B trend report for a wholesale market."""
    country_code = country_code.upper()
    eu_data = scrape_status.get("eu_result", {})
    countries = eu_data.get("countries", {})

    if country_code not in countries:
        return f"No data for {country_code}. Run a data refresh first.", 404

    ci = countries[country_code]
    action_board = scrape_status.get("action_board", {})
    forecasts = get_forecasts(limit=50)
    fc_lookup = {f["term"].lower(): f for f in forecasts}

    # Build top 5 color × pattern combos for this market
    combos = []
    for color in ci.get("colors", [])[:5]:
        for pattern in ci.get("patterns", [])[:5]:
            c_fc = fc_lookup.get(color["term"].lower(), {})
            p_fc = fc_lookup.get(pattern["term"].lower(), {})
            c_lc = c_fc.get("lifecycle", "unknown")
            p_lc = p_fc.get("lifecycle", "unknown")
            # Skip if either is declining
            if c_lc == "declining" or p_lc == "declining":
                continue
            score = color.get("score", 0) + pattern.get("score", 0)
            for lc in [c_lc, p_lc]:
                if lc == "emerging":
                    score += 10
                elif lc == "rising":
                    score += 7
            combos.append({
                "color": color["term"],
                "pattern": pattern["term"],
                "color_score": color.get("score", 0),
                "pattern_score": pattern.get("score", 0),
                "combined_score": score,
                "color_lifecycle": c_lc,
                "pattern_lifecycle": p_lc,
            })
    combos.sort(key=lambda c: c["combined_score"], reverse=True)
    top_combos = combos[:5]

    # Seasonal data
    calendar = action_board.get("seasonal_calendar", [])
    current_season = calendar[0] if calendar else None
    next_season = calendar[1] if len(calendar) > 1 else None

    return render_template(
        "report.html",
        country_code=country_code,
        country=ci,
        top_combos=top_combos,
        current_season=current_season,
        next_season=next_season,
        generated_at=datetime.now().strftime("%B %d, %Y"),
        buckets=action_board.get("buckets", {}),
    )


@app.route("/api/trend-report")
@app.route("/api/trend-report/<country_code>")
def api_trend_report(country_code=None):
    """API endpoint returning B2B trend report data as JSON.

    Usage:
      GET /api/trend-report          — list available markets
      GET /api/trend-report/DK       — full trend report for Denmark
    """
    eu_data = scrape_status.get("eu_result", {})
    countries = eu_data.get("countries", {})

    if not country_code:
        available = []
        for cc, ci in countries.items():
            available.append({
                "code": cc,
                "name": ci.get("name", cc),
                "flag": ci.get("flag", ""),
                "listing_count": ci.get("listing_count", 0),
                "report_url": f"/report/{cc}",
                "api_url": f"/api/trend-report/{cc}",
            })
        return jsonify({"available_markets": available})

    country_code = country_code.upper()
    if country_code not in countries:
        return jsonify({"error": f"No data for {country_code}"}), 404

    ci = countries[country_code]
    action_board = scrape_status.get("action_board", {})
    forecasts = get_forecasts(limit=50)
    fc_lookup = {f["term"].lower(): f for f in forecasts}

    # Build top 5 color × pattern combos
    combos = []
    for color in ci.get("colors", [])[:5]:
        for pattern in ci.get("patterns", [])[:5]:
            c_fc = fc_lookup.get(color["term"].lower(), {})
            p_fc = fc_lookup.get(pattern["term"].lower(), {})
            c_lc = c_fc.get("lifecycle", "unknown")
            p_lc = p_fc.get("lifecycle", "unknown")
            if c_lc == "declining" or p_lc == "declining":
                continue
            score = color.get("score", 0) + pattern.get("score", 0)
            for lc in [c_lc, p_lc]:
                if lc == "emerging":
                    score += 10
                elif lc == "rising":
                    score += 7
            combos.append({
                "color": color["term"],
                "pattern": pattern["term"],
                "combined_score": score,
                "color_lifecycle": c_lc,
                "pattern_lifecycle": p_lc,
            })
    combos.sort(key=lambda c: c["combined_score"], reverse=True)

    calendar = action_board.get("seasonal_calendar", [])

    return jsonify({
        "country_code": country_code,
        "country_name": ci.get("name", country_code),
        "generated_at": datetime.now().isoformat(),
        "listing_count": ci.get("listing_count", 0),
        "top_combos": combos[:5],
        "top_colors": ci.get("colors", [])[:8],
        "top_patterns": ci.get("patterns", [])[:8],
        "top_fabric_types": ci.get("fabric_types", [])[:8],
        "local_marketplaces": ci.get("local_marketplaces", []),
        "seasonal_preview": calendar[:2] if calendar else [],
        "forecast_buckets": {
            k: [{"term": f["term"], "score": f.get("predicted_score", f.get("current_score", 0)),
                 "lifecycle": f.get("lifecycle", "unknown")} for f in v[:6]]
            for k, v in action_board.get("buckets", {}).items()
        },
        "report_html_url": f"/report/{country_code}",
    })


@app.route("/api/status")
def api_status():
    """API endpoint for scrape status."""
    return jsonify(scrape_status)


# ======================================================================
# WooCommerce Inventory Intelligence
# ======================================================================

# Cache for WooCommerce analysis (refreshed on demand)
woo_cache = {
    "analysis": None,
    "recommendations": None,
    "projections": None,
    "last_refresh": None,
    "refreshing": False,
    "error": None,
}

# Cache for e-conomic financial analysis (refreshed on demand)
eco_cache = {
    "analysis": None,
    "reconciliation": None,
    "last_refresh": None,
    "refreshing": False,
    "error": None,
}


# ======================================================================
# Automatic Scheduled Refresh (every 6 hours + on startup)
# ======================================================================

def _scheduled_refresh():
    """Auto-refresh WooCommerce then e-conomic data sequentially.

    Running these in ONE thread (not two) keeps peak memory in check on
    the 512 MB Render plan — each refresh can use ~100-200 MB during data
    pull, and running them concurrently would double the peak.
    """
    logger.info("Scheduled refresh: starting sequential data pull...")
    if config.WOOCOMMERCE_URL and config.WOOCOMMERCE_KEY and not woo_cache["refreshing"]:
        _run_woo_analysis()  # blocks until done, then frees memory
    if config.ECONOMIC_APP_SECRET and config.ECONOMIC_GRANT_TOKEN and not eco_cache["refreshing"]:
        _run_eco_analysis()  # runs after woo is fully cleaned up


def _start_scheduler():
    """Start the background scheduler for automatic data refreshes."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler(daemon=True)
        # Refresh every 6 hours
        scheduler.add_job(_scheduled_refresh, "interval", hours=6,
                          id="data_refresh", replace_existing=True)
        # Also run once on startup (30 second delay to let the app boot)
        scheduler.add_job(_scheduled_refresh, "date",
                          run_date=datetime.now() + timedelta(seconds=30),
                          id="startup_refresh")
        scheduler.start()
        logger.info("Scheduler started: auto-refresh every 6 hours + on startup")
    except Exception as e:
        logger.warning("Could not start scheduler: %s (data refresh will be manual only)", e)


# Start scheduler (runs inside the worker process with preload_app=False)
_start_scheduler()


@app.route("/inventory")
def inventory_dashboard():
    """WooCommerce Inventory Intelligence dashboard."""
    return render_template(
        "inventory.html",
        woo_cache=woo_cache,
        woo_configured=bool(config.WOOCOMMERCE_URL and config.WOOCOMMERCE_KEY),
        eco_cache=eco_cache,
        eco_configured=bool(config.ECONOMIC_APP_SECRET and config.ECONOMIC_GRANT_TOKEN),
    )


@app.route("/financials")
def financials_dashboard():
    """e-conomic Financial Intelligence dashboard."""
    return render_template(
        "financials.html",
        eco_cache=eco_cache,
        eco_configured=bool(config.ECONOMIC_APP_SECRET and config.ECONOMIC_GRANT_TOKEN),
    )


@app.route("/api/inventory/refresh", methods=["POST"])
def inventory_refresh():
    """Trigger a WooCommerce data refresh."""
    if woo_cache["refreshing"]:
        return jsonify({"status": "already_running"}), 409
    if not config.WOOCOMMERCE_URL or not config.WOOCOMMERCE_KEY:
        return jsonify({
            "status": "not_configured",
            "message": (
                "Set WOOCOMMERCE_URL, WOOCOMMERCE_KEY, and "
                "WOOCOMMERCE_SECRET environment variables."
            ),
        }), 400

    thread = threading.Thread(target=_run_woo_analysis, daemon=True)
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/inventory/status")
def inventory_status():
    """Check WooCommerce analysis status."""
    return jsonify({
        "refreshing": woo_cache["refreshing"],
        "last_refresh": woo_cache["last_refresh"],
        "error": woo_cache["error"],
        "has_data": woo_cache["analysis"] is not None,
    })


@app.route("/api/inventory/data")
def inventory_data():
    """Full inventory intelligence data."""
    if not woo_cache["analysis"]:
        return jsonify({"error": "No data yet. Click Refresh to analyze."}), 404
    return jsonify({
        "analysis": {
            "summary": woo_cache["analysis"].get("summary", {}),
            "dead_stock": woo_cache["analysis"].get("dead_stock", [])[:50],
            "winners": woo_cache["analysis"].get("winners", {}),
            "attributes": woo_cache["analysis"].get("attributes", {}),
            "categories": woo_cache["analysis"].get("categories", []),
            "seasonal": woo_cache["analysis"].get("seasonal", {}),
            "geography": woo_cache["analysis"].get("geography", {}),
        },
        "recommendations": woo_cache["recommendations"],
        "projections": woo_cache["projections"],
        "last_refresh": woo_cache["last_refresh"],
    })


@app.route("/api/inventory/velocity")
def inventory_velocity():
    """Sales velocity for all products."""
    if not woo_cache["analysis"]:
        return jsonify([])
    velocity = woo_cache["analysis"].get("velocity", [])
    limit = int(request.args.get("limit", 50))
    sort = request.args.get("sort", "rev_per_week")
    direction = request.args.get("dir", "desc")

    if sort in velocity[0] if velocity else False:
        velocity = sorted(
            velocity,
            key=lambda v: v.get(sort, 0),
            reverse=(direction == "desc"),
        )
    return jsonify(velocity[:limit])


@app.route("/api/inventory/recommendations")
def inventory_recommendations():
    """Action recommendations."""
    if not woo_cache["recommendations"]:
        return jsonify({"error": "No data yet."}), 404
    return jsonify(woo_cache["recommendations"])


# ======================================================================
# e-conomic Financial Intelligence API
# ======================================================================

@app.route("/api/economic/refresh", methods=["POST"])
def economic_refresh():
    """Trigger an e-conomic data refresh."""
    if eco_cache["refreshing"]:
        return jsonify({"status": "already_running"}), 409
    if not config.ECONOMIC_APP_SECRET or not config.ECONOMIC_GRANT_TOKEN:
        return jsonify({
            "status": "not_configured",
            "message": (
                "Set ECONOMIC_APP_SECRET and ECONOMIC_GRANT_TOKEN "
                "environment variables. See config.py for setup instructions."
            ),
        }), 400

    thread = threading.Thread(target=_run_eco_analysis, daemon=True)
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/economic/status")
def economic_status():
    """Check e-conomic analysis status."""
    return jsonify({
        "refreshing": eco_cache["refreshing"],
        "last_refresh": eco_cache["last_refresh"],
        "error": eco_cache["error"],
        "has_data": eco_cache["analysis"] is not None,
        "configured": bool(config.ECONOMIC_APP_SECRET and config.ECONOMIC_GRANT_TOKEN),
    })


@app.route("/api/economic/data")
def economic_data():
    """Full e-conomic financial intelligence data."""
    if not eco_cache["analysis"]:
        return jsonify({"error": "No data yet. Click Refresh to analyze."}), 404
    return jsonify({
        "analysis": eco_cache["analysis"],
        "reconciliation": eco_cache["reconciliation"],
        "last_refresh": eco_cache["last_refresh"],
    })


@app.route("/api/economic/receivables")
def economic_receivables():
    """Accounts receivable / outstanding invoices."""
    if not eco_cache["analysis"]:
        return jsonify({"error": "No data yet."}), 404
    return jsonify(eco_cache["analysis"].get("accounts_receivable", {}))


@app.route("/api/economic/customers")
def economic_customers():
    """Customer profitability ranking."""
    if not eco_cache["analysis"]:
        return jsonify({"error": "No data yet."}), 404
    customers = eco_cache["analysis"].get("customer_profitability", [])
    limit = int(request.args.get("limit", 50))
    return jsonify(customers[:limit])


@app.route("/api/economic/revenue")
def economic_revenue():
    """Revenue breakdown (monthly, growth)."""
    if not eco_cache["analysis"]:
        return jsonify({"error": "No data yet."}), 404
    return jsonify(eco_cache["analysis"].get("revenue", {}))


@app.route("/api/economic/cash-flow")
def economic_cash_flow():
    """Cash flow timing and payment term analysis."""
    if not eco_cache["analysis"]:
        return jsonify({"error": "No data yet."}), 404
    return jsonify(eco_cache["analysis"].get("cash_flow", {}))


@app.route("/api/economic/reconciliation")
def economic_reconciliation():
    """WooCommerce vs e-conomic revenue reconciliation."""
    if not eco_cache["reconciliation"]:
        return jsonify({"error": "No reconciliation data yet."}), 404
    return jsonify(eco_cache["reconciliation"])


@app.route("/api/forecast")
def strategic_forecast():
    """Strategic forecasting — merges WooCommerce + e-conomic into actionable advice."""
    from strategic_forecast import StrategicForecaster
    forecaster = StrategicForecaster(
        woo_analysis=woo_cache.get("analysis"),
        woo_recommendations=woo_cache.get("recommendations"),
        woo_projections=woo_cache.get("projections"),
        eco_analysis=eco_cache.get("analysis"),
        eco_reconciliation=eco_cache.get("reconciliation"),
    )
    return jsonify(forecaster.generate_full_forecast())


def _run_eco_analysis():
    """Background task: connect to e-conomic, pull data, analyze, reconcile."""
    global eco_cache
    eco_cache["refreshing"] = True
    eco_cache["error"] = None

    try:
        from economic_intel.connector import EconomicConnector
        from economic_intel.analyzer import FinancialAnalyzer
        from economic_intel.reconciler import DataReconciler

        logger.info("Connecting to e-conomic...")
        eco = EconomicConnector(
            app_secret=config.ECONOMIC_APP_SECRET,
            grant_token=config.ECONOMIC_GRANT_TOKEN,
        )

        # Test connection first
        conn_test = eco.test_connection()
        if not conn_test["connected"]:
            raise ConnectionError(
                f"e-conomic connection failed: {conn_test.get('error', 'Unknown')}"
            )
        logger.info("Connected to e-conomic: %s (agreement %s)",
                     conn_test["company_name"], conn_test["agreement_number"])

        # Pull data (read-only)
        invoices = eco.get_booked_invoices(days_back=365)
        customers = eco.get_customers()
        products = eco.get_products()
        drafts = eco.get_draft_invoices()
        logger.info(
            "e-conomic: %d booked invoices, %d customers, %d products, %d drafts",
            len(invoices), len(customers), len(products), len(drafts),
        )

        # Analyze
        analyzer = FinancialAnalyzer(invoices, customers, products)
        analysis = analyzer.run_full_analysis()

        # Add draft invoice info to analysis
        analysis["draft_invoices"] = {
            "count": len(drafts),
            "total_net": round(sum(d.get("net_amount", 0) for d in drafts), 2),
            "drafts": drafts[:20],
        }

        # Reconcile with WooCommerce if available
        reconciliation = None
        if woo_cache["analysis"]:
            reconciler = DataReconciler(
                woo_analysis=woo_cache["analysis"],
                eco_analysis=analysis,
            )
            reconciliation = reconciler.reconcile()
        else:
            # Eco-only reconciliation (still useful)
            reconciler = DataReconciler(eco_analysis=analysis)
            reconciliation = reconciler.reconcile()

        eco_cache["analysis"] = analysis
        eco_cache["reconciliation"] = reconciliation
        eco_cache["last_refresh"] = datetime.now().isoformat()

        logger.info(
            "e-conomic analysis complete: %d invoices, %d customers, "
            "revenue: %s",
            len(invoices), len(customers),
            analysis.get("summary", {}).get("total_net_revenue", 0),
        )

        # Free raw API data (analysis results are kept in cache)
        del invoices, customers, products, drafts, analyzer, reconciler, eco
        gc.collect()

    except Exception as e:
        logger.error("e-conomic analysis failed: %s", e, exc_info=True)
        eco_cache["error"] = str(e)
    finally:
        eco_cache["refreshing"] = False


def _run_woo_analysis():
    """Background task: connect to WooCommerce, pull data, analyze."""
    global woo_cache
    woo_cache["refreshing"] = True
    woo_cache["error"] = None

    try:
        from woo_intel.connector import WooConnector
        from woo_intel.analyzer import InventoryAnalyzer
        from woo_intel.recommender import ActionRecommender
        from woo_intel.projections import RevenueProjector

        logger.info("Connecting to WooCommerce at %s...", config.WOOCOMMERCE_URL)
        woo = WooConnector(
            url=config.WOOCOMMERCE_URL,
            key=config.WOOCOMMERCE_KEY,
            secret=config.WOOCOMMERCE_SECRET,
            timeout=60,
        )

        # Pull data
        products = woo.get_all_products()
        orders = woo.get_orders(days_back=365)
        logger.info("WooCommerce: %d products, %d orders", len(products), len(orders))

        # Analyze
        analyzer = InventoryAnalyzer(products, orders)
        analysis = analyzer.run_full_analysis()

        # Recommend
        recommender = ActionRecommender(analysis)
        recommendations = recommender.generate_all()

        # Project
        projector = RevenueProjector(analysis, orders)
        projections = {
            "revenue": projector.project_revenue(weeks_ahead=12),
            "cash_flow": projector.get_cash_flow_health(),
            "category_turnover": projector.get_inventory_turnover_by_category(),
        }

        # Trim large lists before caching to save memory
        # (API endpoints already cap these, but the cache itself was unbounded)
        if "velocity" in analysis:
            analysis["velocity"] = analysis["velocity"][:200]
        if "dead_stock" in analysis:
            analysis["dead_stock"] = analysis["dead_stock"][:100]

        woo_cache["analysis"] = analysis
        woo_cache["recommendations"] = recommendations
        woo_cache["projections"] = projections
        woo_cache["last_refresh"] = datetime.now().isoformat()

        logger.info(
            "WooCommerce analysis complete: %d products, %d orders, "
            "%d recommendations",
            len(products), len(orders),
            len(recommendations.get("product_recommendations", [])),
        )

        # Free raw API data (analysis results are kept in cache)
        del products, orders, analyzer, recommender, projector, woo
        gc.collect()

    except Exception as e:
        logger.error("WooCommerce analysis failed: %s", e, exc_info=True)
        woo_cache["error"] = str(e)
    finally:
        woo_cache["refreshing"] = False


def _collect_listing_images(listings):
    """Extract images from scraped listings and save to trend_images table.

    Groups listings by their tags and saves images for each detected trend term.
    This builds the visual trend board from Etsy, Amazon, Spoonflower, etc.
    """
    from config import FABRIC_TYPES, PATTERN_TYPES, COLOR_TERMS, STYLE_TERMS

    images = []
    seen_urls = set()

    # Category mapping for tag classification
    color_set = {c.lower() for c in COLOR_TERMS}
    pattern_set = {p.lower() for p in PATTERN_TYPES}
    style_set = {s.lower() for s in STYLE_TERMS}

    for listing in listings:
        image_url = listing.get("image_url", "")
        if not image_url or image_url in seen_urls:
            continue
        seen_urls.add(image_url)

        tags = listing.get("tags", [])
        if isinstance(tags, str):
            import json as _json
            try:
                tags = _json.loads(tags)
            except (ValueError, TypeError):
                tags = []

        title = listing.get("title", "")
        source = listing.get("source", "")

        for tag in tags[:5]:  # Limit to avoid too many entries per listing
            tag_lower = tag.lower()
            if tag_lower in color_set:
                category = "color"
            elif tag_lower in pattern_set:
                category = "pattern"
            elif tag_lower in style_set:
                category = "style"
            else:
                category = "fabric_type"

            images.append({
                "term": tag_lower,
                "category": category,
                "image_url": image_url,
                "source": source,
                "listing_title": title[:200],
                "listing_url": listing.get("url", ""),
                "price": listing.get("price"),
            })

    if images:
        save_trend_images(images)
        logger.info("Collected %d trend images from %d listings", len(images), len(listings))


def _run_scrape():
    """Run all scrapers and analyze the results.

    Strategy (free-first approach):
    1. Always load seed data as a baseline (so the dashboard is never empty)
    2. Attempt live scrapers - treat failures gracefully
       - Free: Etsy (direct + API), Pinterest, Spoonflower, Amazon
       - Paid (optional): SerpAPI for high-volume data if SERPAPI_KEY is set
    3. Fetch Google Trends (pytrends free → curated fallback)
    4. Run analysis and forecasting on combined data
    5. Report clearly which sources succeeded/failed

    Recommended free stack covers 80% of insight value:
    - Google Trends (curated fallback): seasonal patterns, search demand
    - Etsy Open API v3: direct B2C competitor/market data
    - Pinterest API v5: visual trend signals, rising aesthetics
    - Seed data + EU shops: European market coverage
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
        # Circuit breaker: if first 2 scrapers both fail, we're on a blocked
        # IP — skip the rest instead of wasting 10+ minutes on timeouts.
        live_count = 0
        scraper_failures = 0
        scrapers = [
            ("Etsy", scrape_etsy),
            ("Amazon", scrape_amazon),
            ("Spoonflower", scrape_spoonflower),
            ("Pinterest", scrape_pinterest),
        ]
        for name, scraper in scrapers:
            if scraper_failures >= 2:
                source_status[name] = {
                    "status": "skipped",
                    "count": 0,
                    "note": "Skipped (cloud IP blocked by earlier scrapers)",
                }
                logger.info("Skipping %s (circuit breaker: %d failures)", name, scraper_failures)
                continue
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
                    scraper_failures = 0  # reset on success
                    del listings
                else:
                    source_status[name] = {
                        "status": "empty",
                        "count": 0,
                        "note": "No listings returned (likely blocked)",
                    }
                    scraper_failures += 1
                    logger.warning("%s returned no listings", name)
            except Exception as e:
                source_status[name] = {
                    "status": "error",
                    "count": 0,
                    "note": str(e)[:100],
                }
                scraper_failures += 1
                logger.warning("%s failed: %s", name, e)
            gc.collect()

        # Step 2b: SerpAPI high-volume data (if configured)
        serpapi_summary = get_serpapi_summary()
        if serpapi_summary.get("configured"):
            logger.info("SerpAPI configured — using high-volume data collection")

            # SerpAPI Shopping — 500+ product listings with images
            try:
                shopping_listings = fetch_serpapi_shopping()
                if shopping_listings:
                    all_listings.extend(shopping_listings)
                    live_count += len(shopping_listings)
                    source_status["SerpAPI Shopping"] = {
                        "status": "ok",
                        "count": len(shopping_listings),
                        "note": f"{len(shopping_listings)} products with images",
                    }
                else:
                    source_status["SerpAPI Shopping"] = {
                        "status": "empty", "count": 0,
                    }
            except Exception as e:
                source_status["SerpAPI Shopping"] = {
                    "status": "error", "count": 0, "note": str(e)[:100],
                }
                logger.warning("SerpAPI Shopping failed: %s", e)

            # SerpAPI Etsy — reliable Etsy data from cloud IPs
            try:
                etsy_serp = fetch_serpapi_etsy()
                if etsy_serp:
                    all_listings.extend(etsy_serp)
                    live_count += len(etsy_serp)
                    source_status["SerpAPI Etsy"] = {
                        "status": "ok",
                        "count": len(etsy_serp),
                        "note": f"{len(etsy_serp)} Etsy listings via SERP",
                    }
                else:
                    source_status["SerpAPI Etsy"] = {
                        "status": "empty", "count": 0,
                    }
            except Exception as e:
                source_status["SerpAPI Etsy"] = {
                    "status": "error", "count": 0, "note": str(e)[:100],
                }
                logger.warning("SerpAPI Etsy failed: %s", e)

            # SerpAPI Trend Images — visual trend board
            try:
                trend_images = fetch_serpapi_trend_images()
                if trend_images:
                    save_trend_images(trend_images)
                    source_status["Trend Images"] = {
                        "status": "ok",
                        "count": len(trend_images),
                        "note": f"{len(trend_images)} trend images collected",
                    }
                    logger.info("Saved %d trend images", len(trend_images))
                else:
                    source_status["Trend Images"] = {
                        "status": "empty", "count": 0,
                    }
            except Exception as e:
                source_status["Trend Images"] = {
                    "status": "error", "count": 0, "note": str(e)[:100],
                }
                logger.warning("SerpAPI Images failed: %s", e)
        else:
            logger.info("SerpAPI not configured (set SERPAPI_KEY for 10x data volume)")

        # Step 2c: Collect images from all listing sources
        _collect_listing_images(all_listings)

        # Step 3: Google Trends (works with backoff + curated fallback)
        google_data = {}
        try:
            # Use SerpAPI for Google Trends if available, otherwise pytrends
            if serpapi_summary.get("configured"):
                logger.info("Fetching Google Trends via SerpAPI...")
                google_data = fetch_serpapi_trends()
                if not google_data:
                    logger.info("SerpAPI Trends empty, falling back to pytrends...")
                    google_data = fetch_google_trends()
            else:
                logger.info("Fetching Google Trends via pytrends...")
                google_data = fetch_google_trends()
            # Check if we got live data or fell back to curated
            has_history = any(
                isinstance(v, dict) and "history" in v
                for v in google_data.values()
                if not str(v).startswith("_")
            )
            source_status["Google Trends"] = {
                "status": "ok" if google_data else "empty",
                "count": len(google_data),
                "note": (
                    f"{len(google_data)} keywords (live)"
                    if has_history
                    else f"{len(google_data)} keywords (curated fallback)"
                ) if google_data else "Rate limited",
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

        seed_count = len(seed_listings)
        total_count = len(all_listings)
        logger.info(
            "Analyzing %d listings (%d seed + %d live)...",
            total_count, seed_count, live_count,
        )
        result = analyze_trends(all_listings, google_data)

        # Store insights for dashboard action board (cap to save memory)
        scrape_status["insights"] = result.get("insights", [])[:50]

        # Step 5: Run forecasting
        logger.info("Running trend forecasts...")
        forecasts = run_forecasts(result, google_data)

        emerging = [f for f in forecasts if f["lifecycle"] == "emerging"]
        rising = [f for f in forecasts if f["lifecycle"] == "rising"]

        # Step 6: Pinterest Social/Visual Trends
        pinterest_pins = 0
        try:
            pinterest_listings = [l for l in all_listings if l.get("source") == "pinterest"]
            if pinterest_listings:
                logger.info("Analyzing %d Pinterest pins...", len(pinterest_listings))
                pinterest_result = analyze_pinterest_data(pinterest_listings)
                scrape_status["pinterest_result"] = pinterest_result
                pinterest_pins = pinterest_result.get("total_pins_analyzed", 0)
                logger.info(
                    "Pinterest analysis: %d pins, %d fabric signals, %d pattern signals",
                    pinterest_pins,
                    len(pinterest_result.get("fabric_signals", [])),
                    len(pinterest_result.get("pattern_signals", [])),
                )
                del pinterest_result, pinterest_listings
            else:
                logger.info("No Pinterest data to analyze (scraper may have been blocked)")
        except Exception as e:
            logger.warning("Pinterest analysis failed: %s", e)

        # --- Free all_listings now (saved to DB, analyzed, Pinterest done) ---
        del all_listings, seed_listings
        gc.collect()
        logger.info("Memory: freed raw listing data after analysis")

        # Step 7: European Markets (seed data + live shop scraping)
        logger.info("Loading European market data...")
        eu_listings = get_european_seed_listings()
        eu_seed_count = len(eu_listings)
        source_status["EU Seed Data"] = {
            "status": "ok",
            "count": eu_seed_count,
            "note": f"{len(EUROPEAN_COUNTRIES)} countries baseline",
        }

        # Step 7b: Scrape real EU shops + competitors
        # Skip live scraping entirely if US scrapers all failed — if Etsy/Amazon
        # are blocked from this cloud IP, small EU shops will be too.
        eu_shop_count = 0
        competitor_count = 0
        skip_live_eu = (scraper_failures >= 2 and live_count == 0)

        if skip_live_eu:
            logger.info(
                "Skipping EU live scraping (US scrapers blocked → EU shops "
                "will be too). Using seed data only."
            )
            source_status["EU Shops"] = {
                "status": "skipped", "count": 0,
                "note": "Skipped (cloud IP blocked)",
            }
            source_status["Competitors"] = {
                "status": "skipped", "count": 0,
                "note": "Skipped (cloud IP blocked)",
            }
        else:
            try:
                logger.info("Scraping EU shops (Phase 1)...")
                eu_shop_result = scrape_eu_shops(priority=1)
                eu_shop_listings = eu_shop_result.get("listings", [])
                eu_shop_count = len(eu_shop_listings)
                eu_listings.extend(eu_shop_listings)
                source_status["EU Shops"] = {
                    "status": "ok" if eu_shop_listings else "empty",
                    "count": eu_shop_count,
                    "note": f"{eu_shop_result.get('shop_count', 0)} shops scraped",
                }
                scrape_status["eu_shop_stats"] = eu_shop_result.get("stats", {})
                del eu_shop_listings, eu_shop_result
            except Exception as e:
                source_status["EU Shops"] = {
                    "status": "error", "count": 0,
                    "note": str(e)[:100],
                }
                logger.warning("EU shop scraping failed: %s", e)

            gc.collect()

            try:
                logger.info("Scraping competitor brands...")
                comp_result = scrape_competitors()
                competitor_listings = comp_result.get("listings", [])
                competitor_count = len(competitor_listings)
                eu_listings.extend(competitor_listings)
                source_status["Competitors"] = {
                    "status": "ok" if competitor_listings else "empty",
                    "count": competitor_count,
                    "note": f"{comp_result.get('brand_count', 0)} brands",
                }
                scrape_status["competitor_stats"] = comp_result.get("stats", {})
                del competitor_listings, comp_result
            except Exception as e:
                source_status["Competitors"] = {
                    "status": "error", "count": 0,
                    "note": str(e)[:100],
                }
                logger.warning("Competitor scraping failed: %s", e)

        if eu_listings:
            save_listings(eu_listings)

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

        # Free eu_listings — analysis is done, results stored in eu_result
        eu_listing_count = len(eu_listings)
        del eu_listings, eu_google
        gc.collect()

        # Generate action board (after EU data so weekly tasks can cite markets)
        scrape_status["action_board"] = _build_action_board(
            result, forecasts, google_data, eu_result
        )

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
            "seed_listings": seed_count,
            "eu_listings": eu_listing_count,
            "eu_shop_listings": eu_shop_count,
            "competitor_listings": competitor_count,
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
            "pinterest_pins": pinterest_pins,
            "serpapi_configured": serpapi_summary.get("configured", False),
            "source_status": source_status,
            "ok_sources": ok_sources,
            "failed_sources": failed_sources,
        }
        logger.info(
            "Collection complete! %d US listings (%d live), %d EU listings "
            "(%d seed + %d shops + %d competitors, %d countries), "
            "%d forecasts. Sources OK: %s. Failed: %s",
            total_count, live_count, eu_listing_count,
            eu_seed_count, eu_shop_count, competitor_count,
            eu_result.get("total_countries", 0), len(forecasts),
            ok_sources, failed_sources,
        )

        # --- Final memory cleanup ---
        del forecasts, google_data, result, eu_result, trend_report
        gc.collect()
        logger.info("Memory cleanup: freed temporary scrape data")

    except Exception as e:
        logger.error("Scrape failed: %s", e, exc_info=True)
        scrape_status["error"] = str(e)
    finally:
        scrape_status["running"] = False


def _build_action_board(result, forecasts, google_data, eu_data=None):
    """Build the 7-section dashboard data for a 2-person cotton jersey print company.

    Sections:
      1. weekly_actions  — 5-7 concrete tasks with data-backed reasons
      2. design_briefs   — prioritized color × pattern × style combos
      3. market_signals  — trending colors, patterns, styles combined
      4. etsy_intel      — B2C market opportunities (US/UK/DE/NL)
      5. wholesale_pulse — B2B wholesale trends (DK/FI/DE)
      6. opportunity_gaps — high demand + low supply
      7. seasonal_calendar — what to prepare for next month/quarter
    Also: summary stats and 4-bucket forecasts.
    """
    from datetime import datetime
    import calendar

    fabrics = result.get("fabric_types", [])
    patterns = result.get("patterns", [])
    colors = result.get("colors", [])
    styles = result.get("styles", [])
    all_trends = fabrics + patterns + colors + styles

    # --- 4-bucket forecasts ---
    design_now = []
    watch = []
    phase_out = []
    evergreen = []
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

    summary = {
        "total_trends_tracked": len(all_trends),
        "design_now_count": len(design_now),
        "watch_count": len(watch),
        "phase_out_count": len(phase_out),
        "evergreen_count": len(evergreen),
        "top_fabric": fabrics[0]["term"] if fabrics else "N/A",
        "top_pattern": patterns[0]["term"] if patterns else "N/A",
        "top_color": colors[0]["term"] if colors else "N/A",
        "top_style": styles[0]["term"] if styles else "N/A",
    }

    # --- Compute briefs, gaps, and intel first (weekly actions depends on them) ---
    design_briefs = _generate_design_briefs(
        colors, patterns, styles, fabrics, forecasts, google_data
    )
    market_signals = _build_market_signals(colors, patterns, styles, forecasts)
    opportunity_gaps = _build_opportunity_gaps(all_trends, forecasts, google_data, eu_data)
    seasonal_calendar = _build_seasonal_calendar()
    etsy_intel = _build_etsy_intel(result, forecasts, google_data, eu_data)
    cross_channel = _build_cross_channel_intel(result, forecasts, google_data, eu_data)
    price_intel = _build_price_intel(result, forecasts, eu_data)
    competitor_watch = _build_competitor_watch(result, forecasts, eu_data)
    trend_deltas = _build_trend_deltas(result, forecasts)
    trend_board = _build_trend_board(result, forecasts)

    # --- Weekly actions: concrete tasks citing specific data ---
    weekly_actions = _build_weekly_actions(
        design_briefs, design_now, phase_out, evergreen,
        colors, patterns, styles, forecasts, google_data,
        eu_data, opportunity_gaps,
    )

    return {
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
        "weekly_actions": weekly_actions,
        "design_briefs": design_briefs,
        "market_signals": market_signals,
        "etsy_intel": etsy_intel,
        "cross_channel": cross_channel,
        "price_intel": price_intel,
        "competitor_watch": competitor_watch,
        "trend_deltas": trend_deltas,
        "trend_board": trend_board,
        "opportunity_gaps": opportunity_gaps,
        "seasonal_calendar": seasonal_calendar,
        "buckets": {
            "design_now": design_now[:25],
            "watch": watch[:25],
            "phase_out": phase_out[:25],
            "evergreen": evergreen[:25],
        },
    }


def _build_weekly_actions(design_briefs, design_now, phase_out, evergreen,
                          colors, patterns, styles, forecasts, google_data,
                          eu_data, opportunity_gaps):
    """Generate 5-7 concrete tasks with data-backed reasons.

    Each task names exact trend combos, cites specific percentages,
    references specific markets (DK, FI, DE, Etsy), and gives a
    concrete action a solo operator can execute this week.
    """
    actions = []
    fc_lookup = {f["term"].lower(): f for f in forecasts}
    eu_countries = eu_data.get("countries", {}) if eu_data else {}
    used_terms = set()  # avoid recommending same trend in multiple tasks

    def _vel_pct(term):
        """Format velocity as '+28%' or '-12%'."""
        fc = fc_lookup.get(term.lower(), {})
        vel = fc.get("velocity", 0)
        if abs(vel) > 0.03:
            return f"{'+' if vel > 0 else ''}{vel * 100:.0f}%"
        return None

    def _google_interest(term):
        """Get Google Trends interest and direction for a term."""
        for key, val in google_data.items():
            if key.startswith("_"):
                continue
            if isinstance(val, dict) and term.lower().split()[0] in key.lower():
                return val.get("interest", 0), val.get("trending_up", False)
        return 0, False

    def _eu_hits(term):
        """Find which EU country codes show this trend in their top lists."""
        hits = []
        for cc, ci in eu_countries.items():
            for t in ci.get("top_trends", [])[:8]:
                if term.lower() in t.get("term", "").lower():
                    hits.append(cc)
                    break
        return hits

    # === 1. DESIGN — top brief with cross-market evidence ===
    if design_briefs:
        brief = design_briefs[0]
        color, pattern = brief["color"], brief["pattern"]
        style = brief.get("style", "")
        used_terms.update([color.lower(), pattern.lower()])

        reasons = []
        for term in [color, pattern]:
            v = _vel_pct(term)
            if v and not v.startswith("-"):
                reasons.append(f"{term.title()} {v}")

        hits = list(dict.fromkeys(_eu_hits(color) + _eu_hits(pattern)))
        if hits:
            reasons.append(f"demand in {', '.join(hits[:3])}")

        if not reasons:
            reasons.append(f"opportunity score {brief['opportunity_score']}")

        style_suffix = f" {style}" if style else ""
        actions.append({
            "type": "Design",
            "icon": "design",
            "task": f"Create 2-3 {color.title()} {pattern}{style_suffix} patterns",
            "reason": ", ".join(reasons),
            "priority": "high",
        })

    # === 2. LIST — second brief, photograph and list on Etsy ===
    if len(design_briefs) > 1:
        brief = design_briefs[1]
        color, pattern = brief["color"], brief["pattern"]
        used_terms.update([color.lower(), pattern.lower()])

        reasons = []
        for term in [color, pattern]:
            fc = fc_lookup.get(term.lower(), {})
            lc = fc.get("lifecycle", "")
            if lc in ("rising", "peak"):
                v = _vel_pct(term)
                reasons.append(
                    f"{term.title()} {lc}" + (f" ({v})" if v else "")
                )

        gi, trending = _google_interest(color)
        if gi > 30:
            reasons.append(f"Google interest {gi}/100")

        if not reasons:
            reasons.append(f"score {brief['opportunity_score']}")

        actions.append({
            "type": "List",
            "icon": "list",
            "task": (
                f"Photograph and list {color.title()} {pattern} "
                f"prints on Etsy"
            ),
            "reason": ", ".join(reasons),
            "priority": "high",
        })

    # === 3. PITCH — wholesale opportunity from DK/FI/DE ===
    ws_codes = ["DK", "FI", "DE"]
    best_pitch = None
    for cc in ws_codes:
        ci = eu_countries.get(cc)
        if not ci:
            continue
        for t in ci.get("top_trends", [])[:5]:
            term = t.get("term", "")
            fc = fc_lookup.get(term.lower(), {})
            lc = fc.get("lifecycle", "")
            vel = fc.get("velocity", 0)
            if lc in ("emerging", "rising") and vel > 0:
                if best_pitch is None or vel > best_pitch["velocity"]:
                    best_pitch = {
                        "cc": cc,
                        "name": ci.get("name", cc),
                        "term": term,
                        "lifecycle": lc,
                        "velocity": vel,
                    }

    if best_pitch:
        v = (
            f" +{best_pitch['velocity'] * 100:.0f}%"
            if best_pitch["velocity"] > 0.03 else ""
        )
        actions.append({
            "type": "Pitch",
            "icon": "pitch",
            "task": (
                f"Send trend update to {best_pitch['name']} "
                f"wholesale clients"
            ),
            "reason": (
                f"{best_pitch['term'].title()} "
                f"{best_pitch['lifecycle']}{v} in {best_pitch['cc']}"
            ),
            "priority": "medium",
        })
    elif patterns:
        top = patterns[0]["term"].title()
        combo = (
            f"{top} {styles[0]['term'].title()}" if styles else top
        )
        actions.append({
            "type": "Pitch",
            "icon": "pitch",
            "task": "Email wholesale contacts in DK, FI, and DE",
            "reason": f"Lead with {combo} — top-scoring trend this week",
            "priority": "medium",
        })

    # === 4. PROMOTE — clearance on declining trends ===
    if phase_out:
        dec = phase_out[0]
        term = dec["term"]
        vel = dec.get("velocity", 0)
        vel_str = f" {vel * 100:.0f}%" if vel < -0.03 else ""
        used_terms.add(term.lower())

        actions.append({
            "type": "Promote",
            "icon": "promote",
            "task": f"Put {term.title()} listings on 15-20% sale",
            "reason": (
                f"Peaked and now declining{vel_str} — "
                f"clear stock before demand drops further"
            ),
            "priority": "high",
        })

    # === 5. WATCH — emerging trend, not ready to commit ===
    emerging = [
        f for f in design_now
        if f["lifecycle"] == "emerging"
        and f["term"].lower() not in used_terms
    ]
    if emerging:
        w = emerging[0]
        used_terms.add(w["term"].lower())

        extra = ""
        gi, trending_up = _google_interest(w["term"])
        if trending_up:
            extra = ", Google search rising"
        elif gi > 20:
            extra = f", Google interest {gi}/100"

        w_vel = w.get("velocity", 0) or 0
        vel_str = (
            f"+{w_vel * 100:.0f}%"
            if w_vel > 0 else "low"
        )
        actions.append({
            "type": "Watch",
            "icon": "watch",
            "task": (
                f"{w['term'].title()} emerging — save references, "
                f"don't commit stock yet"
            ),
            "reason": f"Early signal at {vel_str} velocity{extra}",
            "priority": "medium",
        })

    # === 6. OPTIMIZE — refresh proven evergreen sellers ===
    unused_ev = [
        e for e in evergreen if e["term"].lower() not in used_terms
    ]
    if unused_ev:
        ev = unused_ev[0]
        actions.append({
            "type": "Optimize",
            "icon": "optimize",
            "task": (
                f"Refresh {ev['term'].title()} listing titles, "
                f"tags, and photos"
            ),
            "reason": (
                f"Proven seller (score {ev['current_score']}, stable) "
                f"— keep SEO fresh to hold ranking"
            ),
            "priority": "low",
        })

    # === 7. RESEARCH — investigate opportunity gap ===
    gap_list = opportunity_gaps.get("_legacy", opportunity_gaps) if isinstance(opportunity_gaps, dict) else opportunity_gaps
    unused_gaps = [
        g for g in gap_list
        if g["term"].lower() not in used_terms
    ]
    if unused_gaps:
        gap = unused_gaps[0]
        parts = [f"gap strength {gap['gap_strength']}"]
        gi_val = gap.get("google_interest", 0)
        mention = gap.get("mention_count", 0)
        if gi_val and mention:
            parts.append(
                f"Google interest {gi_val} vs only {mention} listings"
            )
        actions.append({
            "type": "Research",
            "icon": "research",
            "task": (
                f"Investigate {gap['term'].title()} — "
                f"high demand, low competition"
            ),
            "reason": " — ".join(parts),
            "priority": "low",
        })

    return actions[:7]


def _build_market_signals(colors, patterns, styles, forecasts):
    """Combine top colors, patterns, and styles into a unified signal view."""
    fc_lookup = {f["term"].lower(): f for f in forecasts}

    signals = {"colors": [], "patterns": [], "styles": []}

    for c in colors[:8]:
        fc = fc_lookup.get(c["term"].lower(), {})
        signals["colors"].append({
            "term": c["term"],
            "score": c.get("score", 0),
            "lifecycle": fc.get("lifecycle", c.get("lifecycle", "unknown")),
            "velocity": fc.get("velocity", 0),
            "mention_count": c.get("mention_count", 0),
        })

    for p in patterns[:8]:
        fc = fc_lookup.get(p["term"].lower(), {})
        signals["patterns"].append({
            "term": p["term"],
            "score": p.get("score", 0),
            "lifecycle": fc.get("lifecycle", p.get("lifecycle", "unknown")),
            "velocity": fc.get("velocity", 0),
            "mention_count": p.get("mention_count", 0),
        })

    for s in styles[:6]:
        fc = fc_lookup.get(s["term"].lower(), {})
        signals["styles"].append({
            "term": s["term"],
            "score": s.get("score", 0),
            "lifecycle": fc.get("lifecycle", s.get("lifecycle", "unknown")),
            "velocity": fc.get("velocity", 0),
            "mention_count": s.get("mention_count", 0),
        })

    return signals


def _build_opportunity_gaps(all_trends, forecasts, google_data, eu_data=None):
    """Find trends with high demand but low supply using gap_score = demand / supply.

    Returns a dict with three sections:
      supply_demand — gap_score ranked gaps (Google demand vs listing supply)
      cross_market  — trends hot in one geography but absent in another
      cross_channel — trends strong in one channel (B2B/B2C) but weak in the other
    """
    fc_lookup = {f["term"].lower(): f for f in forecasts}
    eu_countries = eu_data.get("countries", {}) if eu_data else {}

    # --- Pinterest signal lookup ---
    pinterest_terms = set()
    pinterest_data = scrape_status.get("pinterest_result", {})
    for sig_list in [
        pinterest_data.get("fabric_signals", []),
        pinterest_data.get("pattern_signals", []),
        pinterest_data.get("color_signals", []),
    ]:
        for sig in sig_list:
            term = sig.get("term", "").lower()
            if term:
                pinterest_terms.add(term)

    # --- Google interest lookup ---
    def _google_val(term):
        for key, val in google_data.items():
            if key.startswith("_"):
                continue
            if isinstance(val, dict) and term.lower().split()[0] in key.lower():
                return val.get("interest", 0), val.get("trending_up", False)
        return 0, False

    # --- EU score lookups ---
    b2b_markets = ["DK", "FI", "DE"]
    b2c_markets = ["DE", "NL"]
    us_scores = {t["term"].lower(): t for t in all_trends}
    b2b_scores = {}
    for cc in b2b_markets:
        ci = eu_countries.get(cc, {})
        for t in ci.get("top_trends", [])[:15]:
            b2b_scores.setdefault(t["term"].lower(), {})[cc] = t.get("score", 0)
    b2c_eu_scores = {}
    for cc in b2c_markets:
        ci = eu_countries.get(cc, {})
        for t in ci.get("top_trends", [])[:15]:
            b2c_eu_scores.setdefault(t["term"].lower(), {})[cc] = t.get("score", 0)

    # ================================================================
    # 1. SUPPLY/DEMAND GAPS — gap_score = demand_score / supply_score
    # ================================================================
    supply_demand = []
    for t in all_trends:
        term_lower = t["term"].lower()
        score = t.get("score", 0)
        mention_count = t.get("mention_count", 0)
        gi, gi_up = _google_val(t["term"])

        fc = fc_lookup.get(term_lower, {})
        lifecycle = fc.get("lifecycle", t.get("lifecycle", "unknown"))
        if lifecycle == "declining":
            continue

        # Demand signals: Google interest + trend score + Pinterest presence
        demand_score = 0
        demand_signals = []
        if gi > 0:
            demand_score += gi
            demand_signals.append(f"Google {gi}/100" + (" ↑" if gi_up else ""))
        demand_score += score * 0.8
        if score > 20:
            demand_signals.append(f"trend score {score}")
        if term_lower in pinterest_terms:
            demand_score += 20
            demand_signals.append("Pinterest trending")
        if gi_up:
            demand_score += 15  # bonus for rising search

        # Supply signals: listing count (low = undersupplied)
        supply_score = max(mention_count * 5, 1)  # scale mentions to comparable range
        if mention_count > 0:
            demand_signals.append(f"{mention_count} listings")

        # gap_score = demand / supply — higher means more undersupplied
        gap_score = round(demand_score / supply_score, 2) if supply_score > 0 else 0

        if gap_score < 1.0 and demand_score < 30:
            continue  # not a meaningful gap

        supply_demand.append({
            "term": t["term"],
            "category": t.get("category", ""),
            "score": score,
            "gap_score": gap_score,
            "demand_score": round(demand_score, 1),
            "supply_score": round(supply_score, 1),
            "google_interest": gi,
            "google_rising": gi_up,
            "pinterest": term_lower in pinterest_terms,
            "mention_count": mention_count,
            "lifecycle": lifecycle,
            "demand_signals": demand_signals,
            "reason": (
                f"Demand {round(demand_score)} vs supply {round(supply_score)}"
                + (f" — Google {gi}" if gi else "")
                + (f", Pinterest active" if term_lower in pinterest_terms else "")
                + f" — only {mention_count} listings."
            ),
        })

    supply_demand.sort(key=lambda g: g["gap_score"], reverse=True)
    supply_demand = supply_demand[:12]

    # ================================================================
    # 2. CROSS-MARKET GAPS — trending in US but absent/weak in EU
    # ================================================================
    cross_market = []
    seen_cm = set()
    for t in all_trends[:25]:
        term_lower = t["term"].lower()
        if term_lower in seen_cm:
            continue
        seen_cm.add(term_lower)

        us_score = t.get("score", 0)
        if us_score < 25:
            continue
        fc = fc_lookup.get(term_lower, {})
        lifecycle = fc.get("lifecycle", "unknown")
        if lifecycle == "declining":
            continue

        gi, gi_up = _google_val(t["term"])

        # Check where this trend IS and ISN'T present in EU
        present_in = []
        absent_from = []
        all_eu_codes = list(set(b2b_markets + b2c_markets))
        for cc in all_eu_codes:
            ci = eu_countries.get(cc, {})
            found = False
            for eu_t in ci.get("top_trends", [])[:15]:
                if term_lower in eu_t.get("term", "").lower():
                    present_in.append(cc)
                    found = True
                    break
            if not found:
                absent_from.append(cc)

        if not absent_from or us_score < 30:
            continue

        # Flow direction detection
        if not present_in:
            flow = "us_only"
            flow_label = f"Hot in US (score {us_score}) but not yet in any EU market"
        elif len(absent_from) > len(present_in):
            flow = "early_eu"
            flow_label = (
                f"In {', '.join(present_in)} but not "
                f"{', '.join(absent_from)} — expanding"
            )
        else:
            flow = "partial"
            flow_label = f"Missing from {', '.join(absent_from)}"

        cross_market.append({
            "term": t["term"],
            "category": t.get("category", ""),
            "us_score": us_score,
            "lifecycle": lifecycle,
            "flow": flow,
            "flow_label": flow_label,
            "present_in": present_in,
            "absent_from": absent_from,
            "google_interest": gi,
            "google_rising": gi_up,
            "gap_score": round(us_score / max(len(present_in) * 15, 1), 1),
            "action": (
                f"List {t['term'].title()} on Etsy {', '.join(absent_from[:2])}"
                if any(c in absent_from for c in b2c_markets)
                else f"Pitch {t['term'].title()} to {', '.join(absent_from[:2])} wholesale"
            ),
        })

    cross_market.sort(key=lambda g: g["gap_score"], reverse=True)
    cross_market = cross_market[:8]

    # ================================================================
    # 3. CROSS-CHANNEL GAPS — strong in B2B but weak in B2C or vice versa
    # ================================================================
    cross_channel = []
    all_terms = set(list(us_scores.keys()) + list(b2b_scores.keys()))
    for term in all_terms:
        fc = fc_lookup.get(term, {})
        lifecycle = fc.get("lifecycle", "unknown")
        if lifecycle == "declining":
            continue

        us_t = us_scores.get(term, {})
        etsy_score = us_t.get("score", 0) if us_t else 0
        b2b_max = max(b2b_scores.get(term, {}).values()) if term in b2b_scores else 0
        b2b_mkts = list(b2b_scores.get(term, {}).keys()) if term in b2b_scores else []

        # B2C strong, B2B weak
        if etsy_score >= 35 and b2b_max < etsy_score * 0.5:
            cross_channel.append({
                "term": term,
                "category": us_t.get("category", "") if us_t else "",
                "lifecycle": lifecycle,
                "direction": "b2c_to_b2b",
                "b2c_score": etsy_score,
                "b2b_score": b2b_max,
                "gap_score": round(etsy_score / max(b2b_max, 1), 1),
                "action": f"Pitch {term.title()} to DK/FI wholesale — Etsy score {etsy_score} vs B2B {b2b_max}",
            })
        # B2B strong, B2C weak
        elif b2b_max >= 30 and etsy_score < b2b_max * 0.5:
            cross_channel.append({
                "term": term,
                "category": us_t.get("category", "") if us_t else "",
                "lifecycle": lifecycle,
                "direction": "b2b_to_b2c",
                "b2c_score": etsy_score,
                "b2b_score": b2b_max,
                "gap_score": round(b2b_max / max(etsy_score, 1), 1),
                "b2b_markets": b2b_mkts,
                "action": f"List {term.title()} on Etsy — wholesale score {b2b_max} in {', '.join(b2b_mkts)} but Etsy only {etsy_score}",
            })

    cross_channel.sort(key=lambda g: g["gap_score"], reverse=True)
    cross_channel = cross_channel[:8]

    # Legacy flat list for backward-compat (weekly actions still reads it)
    legacy_gaps = []
    for g in supply_demand[:10]:
        legacy_gaps.append({
            "term": g["term"],
            "category": g["category"],
            "score": g["score"],
            "google_interest": g["google_interest"],
            "mention_count": g["mention_count"],
            "gap_strength": g["gap_score"],
            "lifecycle": g["lifecycle"],
            "reason": g["reason"],
        })

    return {
        "supply_demand": supply_demand,
        "cross_market": cross_market,
        "cross_channel": cross_channel,
        "_legacy": legacy_gaps,
    }


def _build_cross_channel_intel(result, forecasts, google_data, eu_data=None):
    """Detect trends flowing through the pipeline and cross-channel opportunities.

    Pipeline: Pinterest → Etsy US → Etsy EU → Wholesale EU
    Returns:
      pipeline     — trends with detected pipeline position + suggested action
      b2c_to_b2b   — Etsy/US trends to pitch to wholesale clients
      b2b_to_b2c   — wholesale/EU trends to list on Etsy
      etsy_perf    — Etsy performance metrics (favorites/reviews by trend)
    """
    fc_lookup = {f["term"].lower(): f for f in forecasts}
    eu_countries = eu_data.get("countries", {}) if eu_data else {}

    colors = result.get("colors", [])
    patterns = result.get("patterns", [])
    styles = result.get("styles", [])
    all_trends = colors + patterns + styles

    # Build score lookup for US/global trends
    us_scores = {t["term"].lower(): t for t in all_trends}

    # Build score lookup for B2B wholesale markets (DK, FI, DE)
    b2b_markets = ["DK", "FI", "DE"]
    b2b_scores = {}  # term -> {market: score, ...}
    for cc in b2b_markets:
        ci = eu_countries.get(cc, {})
        for t in ci.get("top_trends", [])[:15]:
            key = t["term"].lower()
            b2b_scores.setdefault(key, {})[cc] = t.get("score", 0)

    # Build score lookup for B2C Etsy markets (DE, NL, US implied)
    b2c_markets = ["DE", "NL"]
    b2c_eu_scores = {}
    for cc in b2c_markets:
        ci = eu_countries.get(cc, {})
        for t in ci.get("top_trends", [])[:15]:
            key = t["term"].lower()
            b2c_eu_scores.setdefault(key, {})[cc] = t.get("score", 0)

    # --- PIPELINE DETECTION ---
    pipeline = []
    seen = set()
    for t in all_trends[:20]:
        term = t["term"].lower()
        if term in seen:
            continue
        seen.add(term)

        fc = fc_lookup.get(term, {})
        lc = fc.get("lifecycle", "unknown")
        if lc == "declining":
            continue

        us_score = t.get("score", 0)
        b2b_present = term in b2b_scores
        b2c_eu_present = term in b2c_eu_scores
        b2b_max = max(b2b_scores.get(term, {}).values()) if b2b_present else 0
        b2c_eu_max = max(b2c_eu_scores.get(term, {}).values()) if b2c_eu_present else 0

        # Google interest as leading indicator
        gi = 0
        for key, val in google_data.items():
            if key.startswith("_"):
                continue
            if isinstance(val, dict) and term.split()[0] in key.lower():
                gi = val.get("interest", 0)
                break

        # Determine pipeline stage
        if us_score > 40 and not b2c_eu_present and not b2b_present:
            stage = "us_only"
            action = f"Hot in US (score {us_score}) but not yet in EU — list on Etsy DE/NL early"
            urgency = "high"
        elif us_score > 30 and b2c_eu_present and not b2b_present:
            stage = "etsy_eu"
            markets = ", ".join(b2c_eu_scores.get(term, {}).keys())
            action = f"Selling on Etsy in {markets} — pitch to DK/FI wholesale clients now"
            urgency = "high"
        elif b2c_eu_present and b2b_present and b2b_max < us_score * 0.7:
            stage = "crossing"
            action = f"Crossing from Etsy to wholesale (B2B score {b2b_max} vs US {us_score}) — get ahead"
            urgency = "medium"
        elif b2b_present and not b2c_eu_present and us_score < 30:
            stage = "b2b_first"
            action = f"Strong in wholesale but weak on Etsy — list on Etsy to capture B2C demand"
            urgency = "medium"
        elif gi > 50 and us_score < 25:
            stage = "search_only"
            action = f"Google interest {gi} but low Etsy presence — early mover opportunity"
            urgency = "medium"
        else:
            continue

        pipeline.append({
            "term": t["term"],
            "category": t.get("category", ""),
            "lifecycle": lc,
            "stage": stage,
            "us_score": us_score,
            "b2b_score": b2b_max,
            "b2c_eu_score": b2c_eu_max,
            "google_interest": gi,
            "action": action,
            "urgency": urgency,
        })

    pipeline.sort(key=lambda p: p["us_score"], reverse=True)

    # --- B2C → B2B: Etsy trends to pitch wholesale ---
    b2c_to_b2b = []
    for t in all_trends[:15]:
        term = t["term"].lower()
        fc = fc_lookup.get(term, {})
        lc = fc.get("lifecycle", "unknown")
        if lc == "declining":
            continue
        us_score = t.get("score", 0)
        if us_score < 30:
            continue
        # Check if NOT strong in wholesale
        b2b_max = max(b2b_scores.get(term, {}).values()) if term in b2b_scores else 0
        if b2b_max >= us_score * 0.8:
            continue  # already strong in wholesale
        markets_str = ""
        if term in b2c_eu_scores:
            markets_str = " + Etsy " + ", ".join(b2c_eu_scores[term].keys())
        b2c_to_b2b.append({
            "term": t["term"],
            "category": t.get("category", ""),
            "lifecycle": lc,
            "us_score": us_score,
            "b2b_score": b2b_max,
            "reason": (
                f"{t['term'].title()} scores {us_score} on Etsy US{markets_str} "
                f"but only {b2b_max} in wholesale — pitch to DK/FI clients"
            ),
        })
    b2c_to_b2b.sort(key=lambda x: x["us_score"] - x["b2b_score"], reverse=True)

    # --- B2B → B2C: Wholesale trends to list on Etsy ---
    b2b_to_b2c = []
    for term, market_scores in b2b_scores.items():
        b2b_max = max(market_scores.values())
        us_t = us_scores.get(term, {})
        us_score = us_t.get("score", 0) if us_t else 0
        fc = fc_lookup.get(term, {})
        lc = fc.get("lifecycle", "unknown")
        if lc == "declining" or b2b_max < 30:
            continue
        if us_score >= b2b_max * 0.8:
            continue  # already strong on Etsy
        top_market = max(market_scores, key=market_scores.get)
        b2b_to_b2c.append({
            "term": term,
            "category": us_t.get("category", "") if us_t else "",
            "lifecycle": lc,
            "b2b_score": b2b_max,
            "us_score": us_score,
            "top_market": top_market,
            "reason": (
                f"{term.title()} scores {b2b_max} in {top_market} wholesale "
                f"but only {us_score} on Etsy — list early to capture demand"
            ),
        })
    b2b_to_b2c.sort(key=lambda x: x["b2b_score"] - x["us_score"], reverse=True)

    # --- ETSY PERFORMANCE METRICS ---
    etsy_perf = []
    for t in all_trends[:15]:
        favs = t.get("avg_favorites", 0)
        reviews = t.get("avg_reviews", 0) or t.get("mention_count", 0)
        price = t.get("avg_price", 0)
        if favs <= 0 and price <= 0:
            continue
        fc = fc_lookup.get(t["term"].lower(), {})
        etsy_perf.append({
            "term": t["term"],
            "category": t.get("category", ""),
            "score": t.get("score", 0),
            "avg_favorites": favs,
            "avg_reviews": reviews,
            "avg_price": round(price, 2) if price else 0,
            "lifecycle": fc.get("lifecycle", "unknown"),
        })
    etsy_perf.sort(key=lambda x: x["avg_favorites"], reverse=True)

    return {
        "pipeline": pipeline[:8],
        "b2c_to_b2b": b2c_to_b2b[:6],
        "b2b_to_b2c": b2b_to_b2c[:6],
        "etsy_perf": etsy_perf[:10],
    }


def _build_seasonal_calendar():
    """Build a seasonal preparation calendar with current + next 2 quarters."""
    from datetime import datetime
    import calendar as cal_mod

    now = datetime.now()
    month = now.month

    # Season definitions with design-lead-time context
    seasons = {
        "Q1 (Jan-Mar)": {
            "label": "Winter / Early Spring",
            "design_focus": "Valentine's prints, spring florals, Easter pastels",
            "colors": ["blush pink", "lavender", "sage green", "baby blue", "cream", "coral"],
            "patterns": ["floral", "botanical", "watercolor", "ditsy", "gingham"],
            "fabrics": ["cotton", "lawn", "jersey", "voile"],
            "prep_note": "Design spring collections NOW. Lead time: 4-6 weeks to Etsy listing.",
        },
        "Q2 (Apr-Jun)": {
            "label": "Spring / Summer",
            "design_focus": "Summer brights, tropical, nautical, outdoor living",
            "colors": ["coral", "teal", "mustard", "emerald", "burnt orange", "seafoam"],
            "patterns": ["tropical", "geometric", "stripe", "abstract", "tie dye"],
            "fabrics": ["linen", "cotton", "jersey", "gauze", "rayon"],
            "prep_note": "Peak Etsy buying season. Maximize listings and paid ads.",
        },
        "Q3 (Jul-Sep)": {
            "label": "Summer / Fall Prep",
            "design_focus": "Back-to-school, fall warmth, Halloween, harvest themes",
            "colors": ["terracotta", "rust", "olive", "burgundy", "forest green", "ochre"],
            "patterns": ["plaid", "botanical", "folk art", "vintage", "cottagecore"],
            "fabrics": ["flannel", "cotton", "jersey", "corduroy"],
            "prep_note": "Design fall/winter prints. Wholesale buyers order now for Q4.",
        },
        "Q4 (Oct-Dec)": {
            "label": "Fall / Holiday Season",
            "design_focus": "Holiday gifting, Christmas, cozy winter, New Year",
            "colors": ["navy", "burgundy", "forest green", "ivory", "charcoal", "gold"],
            "patterns": ["plaid", "damask", "celestial", "minimalist", "geometric"],
            "fabrics": ["velvet", "flannel", "fleece", "jersey", "minky"],
            "prep_note": "Highest sales volume. Focus on fulfillment speed and stock levels.",
        },
    }

    # Determine current and next quarters
    current_q = (month - 1) // 3  # 0-indexed
    q_keys = list(seasons.keys())
    calendar_items = []
    for i in range(3):
        q_idx = (current_q + i) % 4
        key = q_keys[q_idx]
        item = dict(seasons[key])
        item["quarter"] = key
        item["is_current"] = (i == 0)
        item["is_next"] = (i == 1)
        calendar_items.append(item)

    return calendar_items


def _build_etsy_intel(result, forecasts, google_data, eu_data=None):
    """Build Etsy listing intelligence: SEO tags, timing, pricing, entry signals.

    Returns a dict with four sections:
      seo_tags     — best-performing tags per category for cotton jersey prints
      timing       — when to list specific themes (month-by-month)
      pricing      — avg prices by category with market comparison
      entry_signals— high-demand, low-seller markets to enter
    """
    fc_lookup = {f["term"].lower(): f for f in forecasts}
    eu_countries = eu_data.get("countries", {}) if eu_data else {}

    colors = result.get("colors", [])
    patterns = result.get("patterns", [])
    styles = result.get("styles", [])
    fabrics = result.get("fabric_types", [])

    # --- SEO TAGS: best tags from trending data ---
    seo_tags = []
    all_trends = colors + patterns + styles
    all_trends.sort(key=lambda t: t.get("score", 0), reverse=True)
    for t in all_trends[:12]:
        fc = fc_lookup.get(t["term"].lower(), {})
        lc = fc.get("lifecycle", "unknown")
        # Build tag suggestions from the trend term
        term = t["term"]
        category = t.get("category", "")
        base_tags = [term, f"{term} fabric", f"{term} cotton jersey"]
        if category == "color":
            base_tags.append(f"{term} print")
        elif category == "pattern":
            base_tags.extend([f"{term} design", f"{term} textile"])
        elif category == "style":
            base_tags.extend([f"{term} aesthetic", f"{term} style fabric"])

        gi, trending = 0, False
        for key, val in google_data.items():
            if key.startswith("_"):
                continue
            if isinstance(val, dict) and term.lower().split()[0] in key.lower():
                gi = val.get("interest", 0)
                trending = val.get("trending_up", False)
                break

        seo_tags.append({
            "term": term,
            "category": category,
            "score": t.get("score", 0),
            "lifecycle": lc,
            "tags": base_tags[:4],
            "google_interest": gi,
            "google_trending": trending,
        })

    # --- LISTING TIMING: when to list specific themes ---
    from datetime import datetime
    month = datetime.now().month
    timing_map = {
        1: {"theme": "Valentine's Day", "list_by": "Jan 15", "terms": ["blush pink", "floral", "romantic"]},
        2: {"theme": "Spring Preview", "list_by": "Feb 15", "terms": ["sage green", "botanical", "pastel"]},
        3: {"theme": "Easter / Spring", "list_by": "Mar 1", "terms": ["lavender", "ditsy", "gingham"]},
        4: {"theme": "Summer Brights", "list_by": "Apr 1", "terms": ["coral", "tropical", "stripe"]},
        5: {"theme": "Outdoor / Beach", "list_by": "May 1", "terms": ["teal", "nautical", "tie dye"]},
        6: {"theme": "Back-to-School Prep", "list_by": "Jun 15", "terms": ["geometric", "plaid", "retro"]},
        7: {"theme": "Fall Preview", "list_by": "Jul 15", "terms": ["terracotta", "rust", "botanical"]},
        8: {"theme": "Halloween", "list_by": "Aug 15", "terms": ["celestial", "folk art", "vintage"]},
        9: {"theme": "Autumn / Harvest", "list_by": "Sep 1", "terms": ["burgundy", "plaid", "cottagecore"]},
        10: {"theme": "Holiday Gifting", "list_by": "Oct 1", "terms": ["forest green", "damask", "gold"]},
        11: {"theme": "Christmas Rush", "list_by": "Nov 1", "terms": ["navy", "ivory", "minimalist"]},
        12: {"theme": "New Year / Winter", "list_by": "Dec 1", "terms": ["charcoal", "geometric", "japandi"]},
    }
    timing = []
    for offset in range(4):
        m = ((month - 1 + offset) % 12) + 1
        entry = timing_map.get(m, {})
        timing.append({
            "month_num": m,
            "month_name": datetime(2024, m, 1).strftime("%B"),
            "is_current": offset == 0,
            "theme": entry.get("theme", ""),
            "list_by": entry.get("list_by", ""),
            "terms": entry.get("terms", []),
        })

    # --- PRICING: market averages by category ---
    pricing = []
    for cat_name, cat_data in [
        ("Colors", colors), ("Patterns", patterns), ("Styles", styles),
    ]:
        priced = [t for t in cat_data if t.get("avg_price") and t["avg_price"] > 0]
        if priced:
            prices = [t["avg_price"] for t in priced]
            avg = sum(prices) / len(prices)
            low = min(prices)
            high = max(prices)
            pricing.append({
                "category": cat_name,
                "avg_price": round(avg, 2),
                "low": round(low, 2),
                "high": round(high, 2),
                "sample_count": len(priced),
                "top_priced": sorted(priced, key=lambda t: t["avg_price"], reverse=True)[0]["term"],
            })

    # --- ENTRY SIGNALS: high demand + low sellers per EU market ---
    entry_signals = []
    etsy_markets = ["NL", "DE"]  # markets where Etsy is big
    for cc in etsy_markets:
        ci = eu_countries.get(cc)
        if not ci:
            continue
        listing_count = ci.get("listing_count", 0)
        for t in ci.get("top_trends", [])[:5]:
            term = t["term"]
            score = t.get("score", 0)
            fc = fc_lookup.get(term.lower(), {})
            lc = fc.get("lifecycle", "unknown")
            if lc == "declining":
                continue
            # Low seller count relative to demand = entry opportunity
            mention = t.get("mention_count", 0)
            if score > 20 and mention < 15:
                entry_signals.append({
                    "term": term,
                    "market": cc,
                    "market_name": ci.get("name", cc),
                    "score": score,
                    "sellers": mention,
                    "lifecycle": lc,
                    "reason": (
                        f"{term.title()} scores {score} in {ci.get('name', cc)} "
                        f"with only ~{mention} sellers"
                    ),
                })
    entry_signals.sort(key=lambda s: s["score"], reverse=True)

    return {
        "seo_tags": seo_tags,
        "timing": timing,
        "pricing": pricing,
        "entry_signals": entry_signals[:6],
    }


def _build_price_intel(result, forecasts, eu_data=None):
    """Build price intelligence: per-trend pricing, cross-market comparison, margin map.

    Returns a dict with:
      per_trend    — top trends with pricing breakdown (avg, range, sample count)
      cross_market — same trend priced across multiple countries
      margin_map   — B2B wholesale vs B2C Etsy price gaps per trend
      tiers        — premium / mid / budget tier categorization
    """
    fc_lookup = {f["term"].lower(): f for f in forecasts}
    eu_countries = eu_data.get("countries", {}) if eu_data else {}

    colors = result.get("colors", [])
    patterns = result.get("patterns", [])
    styles = result.get("styles", [])
    fabrics = result.get("fabric_types", [])
    all_trends = colors + patterns + styles + fabrics

    # --- PER-TREND PRICING: top trends with price data ---
    per_trend = []
    for t in all_trends:
        price = t.get("avg_price")
        if not price or price <= 0:
            continue
        fc = fc_lookup.get(t["term"].lower(), {})
        pr = t.get("price_range", {})
        per_trend.append({
            "term": t["term"],
            "category": t.get("category", ""),
            "avg_price": round(price, 2),
            "price_low": round(pr["min"], 2) if pr else None,
            "price_high": round(pr["max"], 2) if pr else None,
            "mention_count": t.get("mention_count", 0),
            "score": t.get("score", 0),
            "lifecycle": fc.get("lifecycle", "unknown"),
        })
    per_trend.sort(key=lambda x: x["avg_price"], reverse=True)
    per_trend = per_trend[:15]

    # --- CROSS-MARKET PRICING: same trend across countries ---
    # Gather per-country trend data with prices
    country_prices = {}  # {term_lower: {country: {avg_price, currency, score}}}
    # US/global trends
    for t in all_trends:
        if t.get("avg_price") and t["avg_price"] > 0:
            key = t["term"].lower()
            country_prices.setdefault(key, {})
            country_prices[key]["US"] = {
                "avg_price": round(t["avg_price"], 2),
                "currency": "USD",
                "score": t.get("score", 0),
            }

    # EU country trends
    for cc, ci in eu_countries.items():
        currency = ci.get("currency", "EUR")
        for cat_key in ["fabric_types", "patterns", "colors"]:
            for t in ci.get(cat_key, []):
                if t.get("avg_price") and t["avg_price"] > 0:
                    key = t["term"].lower()
                    country_prices.setdefault(key, {})
                    country_prices[key][cc] = {
                        "avg_price": round(t["avg_price"], 2),
                        "currency": currency,
                        "score": t.get("score", 0),
                    }

    # Only keep terms present in 2+ markets
    cross_market = []
    for term, markets in country_prices.items():
        if len(markets) < 2:
            continue
        fc = fc_lookup.get(term, {})
        prices_list = sorted(
            [{"market": m, **d} for m, d in markets.items()],
            key=lambda x: x["avg_price"],
            reverse=True,
        )
        highest = prices_list[0]
        lowest = prices_list[-1]
        spread_pct = round(
            ((highest["avg_price"] - lowest["avg_price"]) / lowest["avg_price"]) * 100
        ) if lowest["avg_price"] > 0 else 0

        cross_market.append({
            "term": term,
            "market_count": len(markets),
            "prices": prices_list,
            "highest_market": highest["market"],
            "lowest_market": lowest["market"],
            "spread_pct": spread_pct,
            "lifecycle": fc.get("lifecycle", "unknown"),
        })
    cross_market.sort(key=lambda x: x["spread_pct"], reverse=True)
    cross_market = cross_market[:10]

    # --- MARGIN MAP: B2B wholesale vs B2C Etsy pricing ---
    margin_map = []
    b2b_markets = ["DK", "FI", "DE"]
    for term, markets in country_prices.items():
        us_data = markets.get("US")
        if not us_data:
            continue
        b2c_price = us_data["avg_price"]

        # Check if this term has pricing in any B2B market
        b2b_prices = []
        for cc in b2b_markets:
            if cc in markets:
                b2b_prices.append({
                    "market": cc,
                    "avg_price": markets[cc]["avg_price"],
                    "currency": markets[cc]["currency"],
                })

        if not b2b_prices:
            continue

        avg_b2b = sum(p["avg_price"] for p in b2b_prices) / len(b2b_prices)
        fc = fc_lookup.get(term, {})
        margin_map.append({
            "term": term,
            "b2c_price": b2c_price,
            "b2c_currency": "USD",
            "b2b_avg_price": round(avg_b2b, 2),
            "b2b_prices": b2b_prices,
            "spread": round(b2c_price - avg_b2b, 2),
            "spread_pct": round(((b2c_price - avg_b2b) / avg_b2b) * 100) if avg_b2b > 0 else 0,
            "lifecycle": fc.get("lifecycle", "unknown"),
        })
    margin_map.sort(key=lambda x: abs(x["spread_pct"]), reverse=True)
    margin_map = margin_map[:8]

    # --- PRICE TIERS: premium / mid / budget ---
    tiers = {"premium": [], "mid": [], "budget": []}
    if per_trend:
        prices = [t["avg_price"] for t in per_trend]
        p33 = sorted(prices)[len(prices) // 3] if len(prices) >= 3 else (min(prices) + max(prices)) / 2
        p66 = sorted(prices)[2 * len(prices) // 3] if len(prices) >= 3 else (min(prices) + max(prices)) / 2

        for t in per_trend:
            entry = {
                "term": t["term"],
                "category": t["category"],
                "avg_price": t["avg_price"],
                "lifecycle": t["lifecycle"],
            }
            if t["avg_price"] >= p66:
                tiers["premium"].append(entry)
            elif t["avg_price"] >= p33:
                tiers["mid"].append(entry)
            else:
                tiers["budget"].append(entry)

    return {
        "per_trend": per_trend,
        "cross_market": cross_market,
        "margin_map": margin_map,
        "tiers": tiers,
    }


def _build_trend_board(result, forecasts):
    """Build visual trend board data — images grouped by top trend terms.

    Returns a dict with:
      boards — list of {term, category, lifecycle, score, images: [...]}
               each board has up to 6 images for that trend
    """
    fc_lookup = {f["term"].lower(): f for f in forecasts}

    colors = result.get("colors", [])
    patterns = result.get("patterns", [])
    styles = result.get("styles", [])

    # Top trends to show boards for
    top_terms = []
    for cat_list, cat_name in [(colors, "color"), (patterns, "pattern"), (styles, "style")]:
        for t in cat_list[:5]:
            fc = fc_lookup.get(t["term"].lower(), {})
            top_terms.append({
                "term": t["term"],
                "category": cat_name,
                "score": t.get("score", 0),
                "lifecycle": fc.get("lifecycle", "unknown"),
            })

    top_terms.sort(key=lambda x: x["score"], reverse=True)
    top_terms = top_terms[:12]

    boards = []
    for t in top_terms:
        images = get_trend_images(term=t["term"].lower(), limit=6)
        if not images:
            # Try partial match — search term might be in the image term
            all_images = get_trend_images(category=t["category"], limit=50)
            images = [
                img for img in all_images
                if t["term"].lower() in img.get("term", "").lower()
                   or img.get("term", "").lower() in t["term"].lower()
            ][:6]

        boards.append({
            "term": t["term"],
            "category": t["category"],
            "score": t["score"],
            "lifecycle": t["lifecycle"],
            "images": [
                {
                    "url": img.get("image_url", ""),
                    "title": img.get("listing_title", "")[:60],
                    "listing_url": img.get("listing_url", ""),
                    "source": img.get("source", ""),
                    "price": img.get("price"),
                }
                for img in images
            ],
            "image_count": len(images),
        })

    # Only return boards that have images
    boards_with_images = [b for b in boards if b["images"]]
    boards_empty = [b for b in boards if not b["images"]]

    return {
        "boards": boards_with_images + boards_empty[:4],  # Show empty ones too for context
        "total_images": sum(b["image_count"] for b in boards),
        "terms_with_images": len(boards_with_images),
    }


def _build_trend_deltas(result, forecasts):
    """Build week-over-week trend delta data for the dashboard.

    Returns a dict with:
      movers    — top 10 biggest movers (both up and down)
      risers    — trends with biggest positive delta
      fallers   — trends with biggest negative delta
      new_entries — trends that appeared for the first time
      summary   — aggregate stats (avg delta, total risers/fallers)
    """
    fc_lookup = {f["term"].lower(): f for f in forecasts}
    raw_deltas = get_trend_deltas(days_back=7)

    # Filter to trends with meaningful data
    meaningful = [d for d in raw_deltas if d["current_score"] > 0]

    risers = [d for d in meaningful if d["delta"] > 0 and d["has_previous"]]
    risers.sort(key=lambda d: d["delta"], reverse=True)

    fallers = [d for d in meaningful if d["delta"] < 0 and d["has_previous"]]
    fallers.sort(key=lambda d: d["delta"])

    new_entries = [d for d in meaningful if not d["has_previous"] and d["current_score"] >= 15]
    new_entries.sort(key=lambda d: d["current_score"], reverse=True)

    # Top movers = biggest absolute change
    movers = [d for d in meaningful if d["has_previous"] and abs(d["delta"]) >= 2]
    movers.sort(key=lambda d: abs(d["delta"]), reverse=True)

    # Enrich with lifecycle data
    for d in movers + risers + fallers + new_entries:
        fc = fc_lookup.get(d["term"].lower(), {})
        d["lifecycle"] = fc.get("lifecycle", d.get("lifecycle", "unknown"))

    # Summary stats
    all_deltas = [d["delta"] for d in meaningful if d["has_previous"]]
    summary = {
        "total_tracked": len(meaningful),
        "total_risers": len(risers),
        "total_fallers": len(fallers),
        "total_new": len(new_entries),
        "avg_delta": round(sum(all_deltas) / len(all_deltas), 1) if all_deltas else 0,
    }

    return {
        "movers": movers[:12],
        "risers": risers[:8],
        "fallers": fallers[:8],
        "new_entries": new_entries[:6],
        "summary": summary,
    }


def _build_competitor_watch(result, forecasts, eu_data=None):
    """Build competitor intelligence: what are competitors selling & where do we overlap/differ?

    Returns a dict with:
      brands        — per-brand summary (products scraped, top patterns/colors)
      overlap       — trends we share with competitors (red ocean)
      whitespace    — trends competitors have but we don't track (opportunities)
      our_strengths — trends strong in our data but weak/absent from competitors
    """
    fc_lookup = {f["term"].lower(): f for f in forecasts}
    comp_stats = scrape_status.get("competitor_stats", {})

    # Our top trends
    our_trends = set()
    our_trend_data = {}
    for cat_list in [result.get("colors", []), result.get("patterns", []),
                     result.get("styles", [])]:
        for t in cat_list[:10]:
            our_trends.add(t["term"].lower())
            our_trend_data[t["term"].lower()] = t

    # Analyze competitor listings from the database
    # Competitor listings were saved with source=brand_key
    from database import get_recent_listings
    comp_listings = {}
    comp_trend_counts = {}  # {term_lower: {brand: count}}

    for brand_key, info in comp_stats.items():
        if info.get("status") != "ok" or info.get("count", 0) == 0:
            continue
        listings = get_recent_listings(source=brand_key, limit=100)
        comp_listings[brand_key] = listings

        # Extract what trends each competitor carries
        brand_terms = {}
        for listing in listings:
            tags = listing.get("tags", [])
            if isinstance(tags, str):
                import json
                try:
                    tags = json.loads(tags)
                except (json.JSONDecodeError, TypeError):
                    tags = []
            title_lower = listing.get("title", "").lower()
            tag_lower = " ".join(t.lower() for t in tags)
            combined = title_lower + " " + tag_lower

            from config import PATTERN_TYPES, COLOR_TERMS, STYLE_TERMS
            for term_list, category in [
                (PATTERN_TYPES, "pattern"),
                (COLOR_TERMS, "color"),
                (STYLE_TERMS, "style"),
            ]:
                for term in term_list:
                    if term.lower() in combined:
                        brand_terms.setdefault(term.lower(), {
                            "term": term, "category": category, "count": 0,
                        })
                        brand_terms[term.lower()]["count"] += 1
                        comp_trend_counts.setdefault(term.lower(), {})
                        comp_trend_counts[term.lower()].setdefault(brand_key, 0)
                        comp_trend_counts[term.lower()][brand_key] += 1

        info["top_terms"] = sorted(
            brand_terms.values(),
            key=lambda x: x["count"],
            reverse=True,
        )[:8]

    # --- PER-BRAND SUMMARIES ---
    brands = []
    for brand_key, info in comp_stats.items():
        from config import COMPETITOR_BRANDS
        brand_cfg = COMPETITOR_BRANDS.get(brand_key, {})
        brands.append({
            "key": brand_key,
            "name": info.get("name", brand_key),
            "country": info.get("country", brand_cfg.get("country", "")),
            "tier": brand_cfg.get("tier", "unknown"),
            "note": brand_cfg.get("note", ""),
            "status": info.get("status", "unknown"),
            "product_count": info.get("count", 0),
            "top_terms": info.get("top_terms", []),
        })
    brands.sort(key=lambda b: b["product_count"], reverse=True)

    # --- OVERLAP: trends we share (red ocean — compete on quality/price) ---
    overlap = []
    for term_lower, brand_counts in comp_trend_counts.items():
        if term_lower in our_trends:
            our_data = our_trend_data.get(term_lower, {})
            fc = fc_lookup.get(term_lower, {})
            overlap.append({
                "term": term_lower,
                "category": our_data.get("category", ""),
                "our_score": our_data.get("score", 0),
                "competitor_brands": list(brand_counts.keys()),
                "competitor_count": len(brand_counts),
                "total_competitor_listings": sum(brand_counts.values()),
                "lifecycle": fc.get("lifecycle", "unknown"),
            })
    overlap.sort(key=lambda x: x["competitor_count"], reverse=True)

    # --- WHITESPACE: competitors have it, we don't track strongly ---
    whitespace = []
    for term_lower, brand_counts in comp_trend_counts.items():
        if term_lower not in our_trends and sum(brand_counts.values()) >= 2:
            fc = fc_lookup.get(term_lower, {})
            # Find the category from any entry
            cat = ""
            for info in comp_stats.values():
                for tt in info.get("top_terms", []):
                    if tt["term"].lower() == term_lower:
                        cat = tt.get("category", "")
                        break
                if cat:
                    break
            whitespace.append({
                "term": term_lower,
                "category": cat,
                "competitor_brands": list(brand_counts.keys()),
                "competitor_count": len(brand_counts),
                "total_listings": sum(brand_counts.values()),
                "lifecycle": fc.get("lifecycle", "unknown"),
            })
    whitespace.sort(key=lambda x: x["total_listings"], reverse=True)

    # --- OUR STRENGTHS: strong in our data, weak in competitors ---
    our_strengths = []
    for term_lower, our_data in our_trend_data.items():
        comp_count = len(comp_trend_counts.get(term_lower, {}))
        if comp_count == 0 and our_data.get("score", 0) >= 25:
            fc = fc_lookup.get(term_lower, {})
            our_strengths.append({
                "term": term_lower,
                "category": our_data.get("category", ""),
                "our_score": our_data.get("score", 0),
                "lifecycle": fc.get("lifecycle", "unknown"),
            })
    our_strengths.sort(key=lambda x: x["our_score"], reverse=True)

    return {
        "brands": brands,
        "overlap": overlap[:10],
        "whitespace": whitespace[:8],
        "our_strengths": our_strengths[:8],
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
