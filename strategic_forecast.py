"""Strategic Forecasting Engine.

Combines WooCommerce inventory data + e-conomic financial data + external
market intelligence to produce actionable forecasts:

  1. MARKET CONTEXT     — Danish economy, fabric trends, AI narrative
  2. CASH RUNWAY        — "How many weeks can you operate?"
  3. INVENTORY ROI      — "Which SKUs earn their shelf space?"
  4. DEMAND FORECAST    — "What will sell next month/quarter?"
  5. MARGIN EROSION     — "Where are you losing money without realizing?"
  6. CUSTOMER LIFECYCLE — "Who's about to churn? Who should you invest in?"
  7. BUYING SIGNALS     — "What should you buy aggressively vs. let die?"
  8. RISK ALERTS        — "What could hurt you in the next 90 days?"
  9. 90-DAY ACTION PLAN — "Exactly what to do, in what order, this week/month/quarter"
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ======================================================================
# External Market Intelligence (updated periodically)
# ======================================================================

# Source: OECD, Nordea, European Commission, Danmarks Statistik, Trading Economics
DANISH_ECONOMY = {
    "gdp_growth_2025": 2.9,
    "gdp_growth_2026": 2.2,
    "inflation_2025": 1.9,
    "inflation_2026": 1.1,
    "core_inflation_2026": 1.7,
    "real_wage_growth_2026": 2.4,
    "unemployment_pct": 2.9,
    "interest_rate_dk": 1.6,
    "consumer_confidence_index": -17.3,  # Dec 2025 (long-term avg +1.31)
    "retail_sales_yoy": 4.7,  # Nov 2025
    "clothing_retail_yoy": 4.4,  # Nov 2025
    "household_savings_rate": 15.0,
    "ecommerce_growth_rate": 6.3,
    "b2b_ecommerce_cagr": 21.2,
    "tax_cuts_2026": True,
    "summary": (
        "Danish GDP grew 2.9% in 2025, moderating to 2.2% in 2026. Consumer "
        "confidence is negative (-17.3) but improving, while retail sales "
        "are actually growing +4.7% YoY. Clothing retail up +4.4%. "
        "Real wages growing +2.4% (3.5% nominal minus 1.1% inflation). "
        "Tax cuts in 2026 boost disposable income. Record employment at 2.9% "
        "unemployment. Danish households saving 15% — pent-up spending potential."
    ),
    "risk_factors": [
        "Consumer confidence deeply negative (-17.3) despite strong fundamentals",
        "Food price inflation (+6.5%) squeezing household budgets",
        "Temu becoming 3rd largest Danish webshop — aggressive price competition",
        "Global trade uncertainty and potential tariff impacts",
    ],
    "positive_factors": [
        "Retail sales growing +4.7% despite low confidence (consumers spending anyway)",
        "Tax cuts effective 2026 lift disposable income",
        "Record-low unemployment at 2.9%, wages growing +3.5%",
        "High savings rate (15%) = pent-up demand if confidence returns",
        "Lowest interest rates since Nov 2022 (1.6%) reduce business costs",
    ],
}

# Monthly demand index for Danish fabric retail (100 = average month)
# Source: seasonal analysis + Nordic market patterns
NORDIC_DEMAND_INDEX = {
    1: 120,   # Jan: New Year projects, dark winter = indoor crafting peak
    2: 125,   # Feb: Valentine's, peak search for quilting/fabric
    3: 130,   # Mar: National Quilting Month, spring fabric launches
    4: 110,   # Apr: Easter sewing, spring collections
    5: 105,   # May: Wedding season, spring apparel
    6: 80,    # Jun: Summer begins, outdoor focus, demand drops
    7: 70,    # Jul: Peak summer / vacation trough
    8: 85,    # Aug: Back-to-school prep begins
    9: 100,   # Sep: Fall crafting starts, autumn fabrics arrive
    10: 115,  # Oct: Halloween, fall shop hops, holiday prep begins
    11: 125,  # Nov: Pre-Christmas peak, Black Friday, gift sewing
    12: 115,  # Dec: Holiday finishing, drops late month
}

# Source: Première Vision, Fiberseal, Pantone, AllAboutFabrics, WGSN, Accio
FABRIC_TRENDS_2026 = {
    "trending_fabrics": [
        {"name": "bouclé", "strength": "very_high", "note": "Top trend from 2025 into 2026, expanding to home décor"},
        {"name": "linen", "strength": "very_high", "note": "No longer seasonal — year-round sustainability darling"},
        {"name": "organic cotton", "strength": "high", "note": "Top for quilting, apparel, home. Water-washed poplin trending"},
        {"name": "velvet", "strength": "high", "note": "Deeper colors, matte finishes, improved durability"},
        {"name": "canvas", "strength": "high", "note": "Moving from utility to fashion — softer, lighter, unexpected colors"},
        {"name": "jacquard", "strength": "high", "note": "Oversized florals, geometric repeats, metallic threads"},
        {"name": "textured knits", "strength": "high", "note": "Slub, nubby textures — 'plain jersey won't cut it' in 2026"},
        {"name": "recycled fabrics", "strength": "rising", "note": "Sustainable fabrics market growing 12% CAGR"},
        {"name": "hemp", "strength": "rising", "note": "Durable, breathable, sustainable — bags to casual wear"},
    ],
    "pantone_2025": {"name": "Mocha Mousse", "hex": "#A47764", "note": "Warm earth tones, chocolate/cocoa hues"},
    "pantone_2026": {"name": "Cloud Dancer", "hex": "#F0EDE5", "note": "Clean whites, natural tones, quiet luxury"},
    "trending_themes": [
        "Sustainability: natural, recycled, organic, bio-based (12% CAGR market growth)",
        "Texture over print: bouclé, velvet, jacquard — touch is the new luxury",
        "Bold prints & maximalism: moving away from all-neutral spaces",
        "DIY & Gen Z sewing: 71% of new sewers learned via YouTube/Instagram",
        "Anti-fast-fashion: upcycling, thrift, handmade — sewing as mindfulness",
    ],
    "color_directions": {
        "spring_summer": "Cloud Dancer white, warm pastels, sage green, sky blue, ecru",
        "fall_winter": "Deep jewel tones (emerald, burgundy, sapphire), warm earth tones",
        "year_round": "Quiet luxury neutrals, terracotta, olive, cream, Mocha Mousse brown",
    },
    "sustainable_market_cagr": 12.0,
    "eu_sewing_machine_cagr": 5.67,
}


class StrategicForecaster:
    """Merges WooCommerce + e-conomic data into strategic forecasts."""

    def __init__(self, woo_analysis: dict = None, woo_recommendations: dict = None,
                 woo_projections: dict = None, eco_analysis: dict = None,
                 eco_reconciliation: dict = None):
        self.woo = woo_analysis or {}
        self.woo_recs = woo_recommendations or {}
        self.woo_proj = woo_projections or {}
        self.eco = eco_analysis or {}
        self.recon = eco_reconciliation or {}
        self._now = datetime.utcnow()
        self._month = self._now.month

    def generate_full_forecast(self) -> dict:
        """Run all forecasting modules and return combined strategic output."""
        return {
            "generated_at": self._now.isoformat(),
            "market_context": self._market_context(),
            "cash_runway": self._cash_runway(),
            "inventory_roi": self._inventory_roi_ranking(),
            "demand_forecast": self._demand_forecast(),
            "margin_analysis": self._margin_erosion_check(),
            "customer_lifecycle": self._customer_lifecycle(),
            "buying_signals": self._buying_signals(),
            "risk_alerts": self._risk_alerts(),
            "action_plan_90_day": self._build_90_day_plan(),
        }

    # ------------------------------------------------------------------
    # 0. MARKET CONTEXT — Economy, trends, AI narrative
    # ------------------------------------------------------------------

    def _market_context(self) -> dict:
        """Generate market intelligence combining Danish economy + fabric trends
        + actual business data into a natural language AI narrative."""
        economy = DANISH_ECONOMY
        trends = FABRIC_TRENDS_2026
        demand_idx = NORDIC_DEMAND_INDEX.get(self._month, 100)

        # Trend alignment: check our inventory against trending fabrics
        alignment = self._trend_alignment()

        # Build AI narrative
        narrative = self._build_ai_narrative(economy, trends, alignment, demand_idx)

        # Current season
        season_map = {1: "winter", 2: "winter", 3: "spring", 4: "spring",
                      5: "spring", 6: "summer", 7: "summer", 8: "summer",
                      9: "fall", 10: "fall", 11: "fall", 12: "winter"}
        current_season = season_map.get(self._month, "unknown")

        return {
            "ai_narrative": narrative.get("text", "") if isinstance(narrative, dict) else narrative,
            "ai_digest": narrative if isinstance(narrative, dict) else {"headline": "", "summary": str(narrative), "insights": [], "actions": []},
            "danish_economy": {
                "gdp_growth": economy["gdp_growth_2026"],
                "inflation": economy["inflation_2026"],
                "consumer_confidence": economy["consumer_confidence_index"],
                "retail_sales_growth": economy["retail_sales_yoy"],
                "clothing_retail_growth": economy["clothing_retail_yoy"],
                "unemployment": economy["unemployment_pct"],
                "real_wage_growth": economy["real_wage_growth_2026"],
                "outlook": "cautious_recovery",
                "summary": economy["summary"],
                "risk_factors": economy["risk_factors"],
                "positive_factors": economy["positive_factors"],
            },
            "fabric_trends": {
                "trending_fabrics": trends["trending_fabrics"],
                "pantone_2026": trends["pantone_2026"],
                "trending_themes": trends["trending_themes"],
                "color_direction": trends["color_directions"].get(
                    "spring_summer" if self._month in (3, 4, 5, 6, 7, 8)
                    else "fall_winter", trends["color_directions"]["year_round"]
                ),
                "sustainable_market_growth": f"{trends['sustainable_market_cagr']}% CAGR",
            },
            "demand_index": {
                "current_month": demand_idx,
                "current_season": current_season,
                "interpretation": (
                    "High demand period" if demand_idx >= 115
                    else "Above average" if demand_idx >= 105
                    else "Average" if demand_idx >= 95
                    else "Below average — reduce orders" if demand_idx >= 80
                    else "Low season — minimize inventory spend"
                ),
                "monthly_indexes": NORDIC_DEMAND_INDEX,
            },
            "trend_alignment": alignment,
        }

    def _trend_alignment(self) -> dict:
        """Check how well current inventory aligns with 2026 fabric trends."""
        velocity = self.woo.get("velocity", [])
        attributes = self.woo.get("attributes", {})
        fabrics = attributes.get("fabrics", [])
        colors = attributes.get("colors", [])

        trending_names = {t["name"].lower() for t in FABRIC_TRENDS_2026["trending_fabrics"]}

        # Check fabric inventory against trends
        aligned = []
        misaligned = []
        opportunities = []

        for f in fabrics:
            fname = f.get("name", "").lower()
            rev = f.get("total_revenue", 0)
            count = f.get("product_count", 0)

            # Check if any trending fabric name appears in this fabric name
            is_trending = any(t in fname for t in trending_names)

            if is_trending and rev > 0:
                aligned.append({
                    "fabric": f["name"], "revenue": rev,
                    "products": count, "status": "aligned",
                })
            elif is_trending and rev == 0:
                misaligned.append({
                    "fabric": f["name"], "products": count,
                    "issue": "Trending fabric but no sales — check pricing/visibility",
                })
            elif not is_trending and rev == 0 and count >= 2:
                misaligned.append({
                    "fabric": f["name"], "products": count,
                    "issue": "Not trending and no sales — consider clearing",
                })

        # Check for missing trending fabrics we don't stock
        stocked_fabric_names = {f.get("name", "").lower() for f in fabrics}
        for trend in FABRIC_TRENDS_2026["trending_fabrics"]:
            tname = trend["name"].lower()
            if not any(tname in sf for sf in stocked_fabric_names):
                if trend["strength"] in ("very_high", "high"):
                    opportunities.append({
                        "fabric": trend["name"],
                        "strength": trend["strength"],
                        "note": trend["note"],
                        "action": f"Consider adding {trend['name']} to your collection",
                    })

        # Color trend alignment
        pantone_2026 = FABRIC_TRENDS_2026["pantone_2026"]["name"].lower()
        color_insights = []
        white_natural = [c for c in colors if any(
            w in c.get("name", "").lower()
            for w in ["white", "hvid", "cream", "ecru", "natural", "natur"]
        )]
        if white_natural:
            rev = sum(c.get("total_revenue", 0) for c in white_natural)
            color_insights.append(
                f"Pantone 2026 is Cloud Dancer (white). "
                f"Your white/natural fabrics generated {rev:,.0f} — "
                f"{'promote these heavily' if rev > 0 else 'stock and promote these'}"
            )

        total_fabric_products = sum(f.get("product_count", 0) for f in fabrics)
        aligned_products = sum(a.get("products", 0) for a in aligned)
        score = round((aligned_products / total_fabric_products * 100)
                       if total_fabric_products > 0 else 0)

        return {
            "score": min(score, 100),
            "aligned": aligned[:10],
            "misaligned": misaligned[:10],
            "opportunities": opportunities[:5],
            "color_insights": color_insights,
            "total_products": total_fabric_products,
            "aligned_count": aligned_products,
        }

    def _build_ai_narrative(self, economy, trends, alignment, demand_idx):
        """Generate a structured AI digest with headline, insights, and actions.

        Inspired by ThoughtSpot's morning digest and Fathom's structured insights.
        Returns a dict with: headline, summary, insights (categorized), actions.
        """
        woo_summary = self.woo.get("summary", {})
        eco_summary = self.eco.get("summary", {})

        month_names = {1: "January", 2: "February", 3: "March", 4: "April",
                       5: "May", 6: "June", 7: "July", 8: "August",
                       9: "September", 10: "October", 11: "November", 12: "December"}
        quarter = (self._month - 1) // 3 + 1
        month_name = month_names[self._month]

        # --- Headline ---
        dead_ratio = woo_summary.get("dead_stock_ratio", 0)
        score = alignment.get("score", 0)
        opps = alignment.get("opportunities", [])

        if demand_idx >= 115:
            headline = f"{month_name}: High-demand period — push marketing and stock best-sellers"
        elif demand_idx <= 80:
            headline = f"{month_name}: Low season — focus on clearance and planning ahead"
        elif dead_ratio > 0.25:
            headline = f"{month_name}: Clear dead stock urgently — {dead_ratio:.0%} of capital is stuck"
        elif score < 30:
            headline = f"{month_name}: Trend gap detected — inventory misaligned with 2026 trends"
        else:
            headline = f"{month_name}: Steady quarter — optimize margins and prepare for next season"

        # --- Summary (1-2 sentences) ---
        conf = economy["consumer_confidence_index"]
        retail = economy["retail_sales_yoy"]
        summary = (
            f"Danish retail is growing +{retail}% despite negative confidence ({conf}). "
            f"Demand index for {month_name} is {demand_idx}/100. "
            f"Trend alignment: {score}%."
        )

        # --- Categorized Insights ---
        insights = []

        # Market insight
        if demand_idx >= 115:
            insights.append({
                "category": "market", "severity": "opportunity",
                "text": f"Peak demand period (index {demand_idx}). Increase ad spend and email campaigns on best-sellers.",
            })
        elif demand_idx >= 95:
            insights.append({
                "category": "market", "severity": "info",
                "text": f"Average demand period (index {demand_idx}). Maintain steady operations.",
            })
        elif demand_idx <= 80:
            insights.append({
                "category": "market", "severity": "warning",
                "text": f"Low season (index {demand_idx}). Reduce purchasing, focus on clearance and next-season prep.",
            })

        # Economy insight
        insights.append({
            "category": "economy", "severity": "info",
            "text": (
                f"Danes spending despite low confidence ({conf}). "
                f"Real wages +{economy['real_wage_growth_2026']}%, tax cuts effective 2026. "
                f"Bullish for Q{quarter}."
            ),
        })

        # Dead stock insight
        dead_cap = woo_summary.get("dead_stock_capital", 0)
        if dead_ratio > 0.25:
            insights.append({
                "category": "inventory", "severity": "critical",
                "text": f"{dead_ratio:.0%} of inventory ({dead_cap:,.0f} DKK) is dead stock. Every month loses ~3% of that value.",
            })
        elif dead_ratio > 0.15:
            insights.append({
                "category": "inventory", "severity": "warning",
                "text": f"Dead stock at {dead_ratio:.0%} — clear underperformers to free capital for trending fabrics.",
            })
        elif dead_ratio > 0:
            insights.append({
                "category": "inventory", "severity": "good",
                "text": f"Dead stock ratio at {dead_ratio:.0%} — healthy level. Keep monitoring.",
            })

        # Trend alignment insight
        if score >= 60:
            insights.append({
                "category": "trends", "severity": "good",
                "text": f"Strong trend alignment ({score}%). Your inventory matches 2026 fabric trends well. Push marketing on trending items.",
            })
        elif score >= 30:
            gap_text = f" Consider adding {', '.join(o['fabric'] for o in opps[:2])}." if opps else ""
            insights.append({
                "category": "trends", "severity": "warning",
                "text": f"Moderate trend alignment ({score}%).{gap_text}",
            })
        else:
            gap_text = f" Missing: {', '.join(o['fabric'] for o in opps[:3])}." if opps else ""
            insights.append({
                "category": "trends", "severity": "critical",
                "text": f"Low trend alignment ({score}%) — risk of missing 2026 shift to textured, sustainable fabrics.{gap_text}",
            })

        # Revenue insight
        monthly_rev = eco_summary.get("avg_monthly_revenue", 0)
        total_rev = woo_summary.get("total_revenue", 0)
        if monthly_rev:
            insights.append({
                "category": "revenue", "severity": "info",
                "text": f"Current run rate: {monthly_rev:,.0f} DKK/month. Tax cuts + wage growth support improvement through 2026.",
            })

        # --- Clear Actions ---
        actions = []
        if demand_idx >= 115:
            actions.append({"priority": "high", "action": "Increase marketing spend on best-sellers this month"})
        if dead_ratio > 0.15:
            recovery = dead_cap * 0.4
            actions.append({"priority": "high", "action": f"Run clearance on dead stock to recover ~{recovery:,.0f} DKK"})
        if score < 50 and opps:
            actions.append({"priority": "medium", "action": f"Source trending fabrics: {', '.join(o['fabric'] for o in opps[:2])}"})
        if demand_idx <= 80:
            actions.append({"priority": "medium", "action": "Reduce new inventory orders — save budget for next high-demand period"})

        next_month = (self._month % 12) + 1
        next_demand = NORDIC_DEMAND_INDEX.get(next_month, 100)
        if next_demand >= 115 and demand_idx < 115:
            actions.append({"priority": "medium", "action": f"Prepare for {month_names[next_month]} peak (demand index: {next_demand})"})

        # Always add a planning action
        if not actions:
            actions.append({"priority": "low", "action": "Review inventory ROI and phase out lowest-performing SKUs"})

        return {
            "headline": headline,
            "summary": summary,
            "insights": insights,
            "actions": actions,
            "text": summary,  # backward-compatible flat text
        }

    # ------------------------------------------------------------------
    # 1. CASH RUNWAY — How many weeks can you operate?
    # ------------------------------------------------------------------

    def _cash_runway(self) -> dict:
        """Estimate how long the business can sustain current operations."""
        eco_summary = self.eco.get("summary", {})
        eco_cashflow = self.eco.get("cash_flow", {})
        woo_summary = self.woo.get("summary", {})

        # Monthly revenue from e-conomic (most accurate)
        monthly_rev = self.eco.get("revenue", {}).get("monthly", [])
        if monthly_rev:
            recent_months = monthly_rev[-3:] if len(monthly_rev) >= 3 else monthly_rev
            avg_monthly_revenue = sum(m["net_amount"] for m in recent_months) / len(recent_months)
        else:
            avg_monthly_revenue = eco_summary.get("total_net_revenue", 0) / 12

        weekly_revenue = avg_monthly_revenue / 4.33

        # Outstanding cash expected
        outstanding = eco_summary.get("total_outstanding", 0)
        overdue = self.eco.get("accounts_receivable", {}).get("total_overdue", 0)
        expected_12w = eco_cashflow.get("total_expected_12_weeks", 0)

        # Inventory that can be liquidated
        dead_capital = woo_summary.get("dead_stock_capital", 0)
        total_inv_value = woo_summary.get("total_inventory_value", 0)

        # Weekly inflow forecast from e-conomic
        weekly_inflow = eco_cashflow.get("weekly_inflow_forecast", [])

        # Estimate burn rate (rough: 70% of revenue goes to costs in fabric retail)
        est_weekly_burn = weekly_revenue * 0.70

        # Cash buffer: expected inflows vs burn
        inflow_4w = sum(w["expected_inflow"] for w in weekly_inflow[:4]) if weekly_inflow else 0
        inflow_12w = expected_12w

        # Runway calculation
        if est_weekly_burn > 0:
            weeks_from_inflows = inflow_12w / est_weekly_burn
            weeks_from_revenue = avg_monthly_revenue * 3 / est_weekly_burn  # 3 months
        else:
            weeks_from_inflows = 52
            weeks_from_revenue = 52

        # Actionable cash recovery potential
        cash_recovery_potential = dead_capital * 0.40  # assume 40% recovery on dead stock

        return {
            "avg_weekly_revenue": round(weekly_revenue, 0),
            "avg_monthly_revenue": round(avg_monthly_revenue, 0),
            "est_weekly_costs": round(est_weekly_burn, 0),
            "est_weekly_profit": round(weekly_revenue - est_weekly_burn, 0),
            "outstanding_receivables": round(outstanding, 0),
            "overdue_receivables": round(overdue, 0),
            "expected_inflow_4_weeks": round(inflow_4w, 0),
            "expected_inflow_12_weeks": round(inflow_12w, 0),
            "dead_stock_recovery_potential": round(cash_recovery_potential, 0),
            "assessment": self._runway_assessment(
                weekly_revenue, est_weekly_burn, overdue, outstanding, dead_capital
            ),
        }

    def _runway_assessment(self, weekly_rev, weekly_burn, overdue, outstanding, dead_capital):
        """Plain-language assessment of cash position."""
        weekly_profit = weekly_rev - weekly_burn
        months_of_overdue = overdue / weekly_rev if weekly_rev > 0 else 0

        insights = []
        if weekly_profit > 0:
            insights.append(
                f"You're profitable at ~{weekly_profit:,.0f}/week net. "
                f"That's ~{weekly_profit * 4.33:,.0f}/month after estimated costs."
            )
        else:
            insights.append(
                f"WARNING: Estimated weekly costs ({weekly_burn:,.0f}) exceed "
                f"revenue ({weekly_rev:,.0f}). Review expenses immediately."
            )

        if overdue > weekly_rev * 4:
            insights.append(
                f"CRITICAL: {overdue:,.0f} overdue is more than a month's revenue. "
                f"This is your #1 priority — chase these invoices TODAY."
            )
        elif overdue > weekly_rev * 2:
            insights.append(
                f"WARNING: {overdue:,.0f} overdue = ~{months_of_overdue:.1f} weeks of revenue "
                f"stuck in unpaid invoices. Prioritize collections."
            )

        if dead_capital > weekly_rev * 4:
            recovery = dead_capital * 0.4
            insights.append(
                f"You have {dead_capital:,.0f} locked in dead inventory. "
                f"A clearance sale could free ~{recovery:,.0f} — that's "
                f"{recovery / weekly_rev:.0f} weeks of revenue."
            )

        return insights

    # ------------------------------------------------------------------
    # 2. INVENTORY ROI — Which SKUs earn their shelf space?
    # ------------------------------------------------------------------

    def _inventory_roi_ranking(self) -> dict:
        """Rank products by return on inventory investment."""
        velocity = self.woo.get("velocity", [])
        if not velocity:
            return {"products": [], "summary": "No WooCommerce data available."}

        ranked = []
        for v in velocity:
            stock = v["stock_quantity"]
            price = v["price"]
            rev_per_week = v["rev_per_week"]
            capital_invested = stock * price if stock > 0 and price > 0 else 0

            if capital_invested > 0:
                # Annualized ROI: (yearly revenue / capital invested)
                annual_rev = rev_per_week * 52
                roi = annual_rev / capital_invested
                weeks_to_payback = capital_invested / rev_per_week if rev_per_week > 0 else 999
            elif rev_per_week > 0:
                roi = 999  # selling with no stock investment = infinite ROI
                weeks_to_payback = 0
            else:
                roi = 0
                weeks_to_payback = 999

            ranked.append({
                "name": v["name"],
                "sku": v.get("sku", ""),
                "stock": stock,
                "capital_invested": round(capital_invested, 0),
                "rev_per_week": round(rev_per_week, 2),
                "annual_roi_pct": round(roi * 100, 0),
                "weeks_to_payback": round(weeks_to_payback, 1),
                "direction": v["direction"],
                "verdict": self._roi_verdict(roi, v["direction"], weeks_to_payback),
            })

        ranked.sort(key=lambda r: r["annual_roi_pct"], reverse=True)

        # Summary stats
        profitable = [r for r in ranked if r["annual_roi_pct"] > 100]
        losers = [r for r in ranked if r["annual_roi_pct"] == 0 and r["capital_invested"] > 0]
        total_dead_capital = sum(r["capital_invested"] for r in losers)

        return {
            "top_performers": ranked[:15],
            "worst_performers": sorted(
                [r for r in ranked if r["capital_invested"] > 0],
                key=lambda r: r["annual_roi_pct"]
            )[:15],
            "summary": {
                "total_products_analyzed": len(ranked),
                "profitable_products": len(profitable),
                "zero_roi_products": len(losers),
                "capital_in_zero_roi": round(total_dead_capital, 0),
                "insight": (
                    f"{len(profitable)} products earn their shelf space. "
                    f"{len(losers)} products have zero ROI with "
                    f"{total_dead_capital:,.0f} capital locked up."
                ),
            },
        }

    def _roi_verdict(self, roi, direction, weeks_to_payback):
        if roi > 5 and direction == "accelerating":
            return "STAR — Aggressive buy, maximize stock"
        elif roi > 3:
            return "STRONG — Keep well-stocked"
        elif roi > 1:
            return "OK — Maintain current levels"
        elif roi > 0:
            return "WEAK — Don't reorder, let stock sell through"
        else:
            return "DEAD — Discount or remove"

    # ------------------------------------------------------------------
    # 3. DEMAND FORECAST — What will sell next month/quarter?
    # ------------------------------------------------------------------

    def _demand_forecast(self) -> dict:
        """Forecast demand for next 30/60/90 days using velocity + seasonality."""
        velocity = self.woo.get("velocity", [])
        seasonal = self.woo.get("seasonal", {})
        monthly_data = seasonal.get("monthly", [])

        if not velocity:
            return {"forecast": [], "note": "No WooCommerce data."}

        # Get seasonal factors
        revenue_by_month = {}
        for m in monthly_data:
            if m.get("revenue", 0) > 0:
                revenue_by_month[m["month"]] = m["revenue"]

        avg_monthly = (
            sum(revenue_by_month.values()) / len(revenue_by_month)
            if revenue_by_month else 1
        )
        seasonal_factors = {
            m: rev / avg_monthly for m, rev in revenue_by_month.items()
        } if avg_monthly > 0 else {}

        # Forecast by category
        categories = self.woo.get("categories", [])
        cat_forecasts = []
        for cat in categories[:20]:
            current_rev = cat.get("total_revenue", 0)
            active = cat.get("active_products", 0)
            dead = cat.get("dead_products", 0)

            # Estimate monthly rate from annual
            monthly_rate = current_rev / 12 if current_rev > 0 else 0

            # Apply seasonal factor for next 3 months
            forecast_30 = 0
            forecast_60 = 0
            forecast_90 = 0
            for offset in range(1, 4):
                target_month = ((self._month - 1 + offset) % 12) + 1
                factor = seasonal_factors.get(target_month, 1.0)
                month_forecast = monthly_rate * factor
                if offset == 1:
                    forecast_30 = month_forecast
                elif offset == 2:
                    forecast_60 = month_forecast
                else:
                    forecast_90 = month_forecast

            cat_forecasts.append({
                "category": cat["category"],
                "current_monthly_rate": round(monthly_rate, 0),
                "forecast_30_days": round(forecast_30, 0),
                "forecast_60_days": round(forecast_60, 0),
                "forecast_90_days": round(forecast_90, 0),
                "active_products": active,
                "dead_products": dead,
                "trend": (
                    "growing" if forecast_30 > monthly_rate * 1.1
                    else "declining" if forecast_30 < monthly_rate * 0.9
                    else "stable"
                ),
            })

        cat_forecasts.sort(key=lambda c: c["forecast_30_days"], reverse=True)

        # Attribute demand forecast (which colors/patterns will trend?)
        attributes = self.woo.get("attributes", {})
        color_forecast = self._forecast_attributes(attributes.get("colors", []))
        pattern_forecast = self._forecast_attributes(attributes.get("patterns", []))
        fabric_forecast = self._forecast_attributes(attributes.get("fabrics", []))

        # Next month's expected total with Nordic demand index adjustment
        next_month = ((self._month - 1 + 1) % 12) + 1
        next_factor = seasonal_factors.get(next_month, 1.0)
        current_weekly = sum(v["rev_per_week"] for v in velocity if v["rev_per_week"] > 0)
        next_month_total = current_weekly * 4.33 * next_factor

        # Apply economic confidence adjustment
        # Retail is growing +4.7% despite negative confidence — slight positive
        econ_modifier = 1.0 + (DANISH_ECONOMY.get("retail_sales_yoy", 0) / 100 * 0.3)
        next_month_total *= econ_modifier

        # Nordic demand index for this month
        demand_idx = NORDIC_DEMAND_INDEX.get(next_month, 100)

        # Confidence band: wider when less historical data or more volatile
        data_months = len(revenue_by_month)
        if data_months >= 9:
            confidence = "high"
            band_pct = 0.12  # +/- 12%
        elif data_months >= 5:
            confidence = "medium"
            band_pct = 0.22  # +/- 22%
        else:
            confidence = "low"
            band_pct = 0.35  # +/- 35%

        return {
            "next_month_projected_revenue": round(next_month_total, 0),
            "confidence_band": {
                "level": confidence,
                "low": round(next_month_total * (1 - band_pct), 0),
                "mid": round(next_month_total, 0),
                "high": round(next_month_total * (1 + band_pct), 0),
                "band_pct": band_pct,
                "data_months": data_months,
            },
            "seasonal_factor": round(next_factor, 2),
            "economic_modifier": round(econ_modifier, 3),
            "demand_index": demand_idx,
            "category_forecasts": cat_forecasts,
            "trending_up": {
                "colors": [c for c in color_forecast if c["signal"] == "BUY MORE"],
                "patterns": [p for p in pattern_forecast if p["signal"] == "BUY MORE"],
                "fabrics": [f for f in fabric_forecast if f["signal"] == "BUY MORE"],
            },
            "trending_down": {
                "colors": [c for c in color_forecast if c["signal"] in ("REDUCE", "STOP BUYING")],
                "patterns": [p for p in pattern_forecast if p["signal"] in ("REDUCE", "STOP BUYING")],
                "fabrics": [f for f in fabric_forecast if f["signal"] in ("REDUCE", "STOP BUYING")],
            },
        }

    def _forecast_attributes(self, items: list) -> list:
        """Convert attribute performance into buy/hold/cut signals."""
        signals = []
        for item in items:
            rev = item.get("total_revenue", 0)
            direction = item.get("dominant_direction", "no_sales")
            count = item.get("product_count", 0)
            velocity = item.get("avg_velocity_per_week", 0)

            if direction == "accelerating" and rev > 0:
                signal = "BUY MORE"
                reason = f"Accelerating demand, {rev:,.0f} revenue, {velocity:.1f}/week"
            elif direction == "stable" and velocity > 0.5:
                signal = "MAINTAIN"
                reason = f"Steady demand at {velocity:.1f}/week"
            elif direction == "decelerating" and rev > 0:
                signal = "REDUCE"
                reason = f"Demand falling — don't reorder, sell through existing stock"
            elif rev == 0 and count >= 2:
                signal = "STOP BUYING"
                reason = f"Zero revenue across {count} products — your customers don't want this"
            else:
                signal = "WATCH"
                reason = "Insufficient data"

            signals.append({
                "name": item["name"],
                "signal": signal,
                "reason": reason,
                "revenue": rev,
                "velocity": velocity,
                "products": count,
            })
        return signals

    # ------------------------------------------------------------------
    # 4. MARGIN EROSION — Where are you losing money?
    # ------------------------------------------------------------------

    def _margin_erosion_check(self) -> dict:
        """Identify where margins are being eroded."""
        findings = []

        # Check: overdue invoices are free loans to customers
        ar = self.eco.get("accounts_receivable", {})
        overdue = ar.get("total_overdue", 0)
        if overdue > 0:
            # Cost of capital: ~5% annual rate for a small business
            annual_cost = overdue * 0.05
            findings.append({
                "type": "overdue_cost_of_capital",
                "severity": "warning" if overdue < 200000 else "critical",
                "title": "Overdue invoices = free loans to customers",
                "amount": round(overdue, 0),
                "annual_cost": round(annual_cost, 0),
                "detail": (
                    f"You have {overdue:,.0f} in overdue invoices. At a 5% cost of capital, "
                    f"these unpaid invoices cost you ~{annual_cost:,.0f}/year in lost opportunity. "
                    f"Every day they're unpaid, you're effectively lending money at 0% interest."
                ),
                "action": "Implement payment reminders at 7, 14, 30 days. Add late fees to terms.",
            })

        # Check: dead stock depreciation
        woo_summary = self.woo.get("summary", {})
        dead_capital = woo_summary.get("dead_stock_capital", 0)
        if dead_capital > 0:
            # Fabric depreciates: trends change, colors go out of style
            monthly_depreciation = dead_capital * 0.03  # ~3% per month for fashion
            findings.append({
                "type": "dead_stock_depreciation",
                "severity": "warning" if dead_capital < 50000 else "critical",
                "title": "Dead stock loses value every month",
                "amount": round(dead_capital, 0),
                "monthly_loss": round(monthly_depreciation, 0),
                "detail": (
                    f"Your {dead_capital:,.0f} in dead stock is depreciating at ~3%/month "
                    f"as trends change. That's ~{monthly_depreciation:,.0f}/month vanishing. "
                    f"In 6 months, this inventory will be worth ~{dead_capital * 0.83:,.0f} — "
                    f"a loss of {dead_capital * 0.17:,.0f}."
                ),
                "action": "Run clearance NOW. A 40% discount today beats a 70% discount in 6 months.",
            })

        # Check: customers with high revenue but poor payment behavior
        customer_prof = self.eco.get("customer_profitability", [])
        bad_payers = [
            c for c in customer_prof[:30]
            if c.get("payment_reliability", 100) < 80
            and c.get("total_net_revenue", 0) > 10000
        ]
        if bad_payers:
            total_risk = sum(c.get("total_outstanding", 0) for c in bad_payers)
            findings.append({
                "type": "unreliable_big_customers",
                "severity": "warning",
                "title": f"{len(bad_payers)} big customers pay unreliably",
                "amount": round(total_risk, 0),
                "detail": (
                    f"You have {len(bad_payers)} customers with >10K revenue but <80% "
                    f"payment reliability. Total exposure: {total_risk:,.0f}. "
                    f"These customers generate revenue on paper but consume cash flow."
                ),
                "customers": [
                    {
                        "name": c.get("name", "Unknown"),
                        "revenue": c.get("total_net_revenue", 0),
                        "outstanding": c.get("total_outstanding", 0),
                        "reliability": c.get("payment_reliability", 0),
                    }
                    for c in bad_payers[:5]
                ],
                "action": "Switch to prepayment or cash-on-delivery for these customers.",
            })

        # Check: discount erosion from WooCommerce
        discount_plan = self.woo_recs.get("discount_plan", {})
        total_to_discount = discount_plan.get("total_recoverable_capital", 0)
        if total_to_discount > 0:
            findings.append({
                "type": "discount_opportunity",
                "severity": "info",
                "title": "Capital recoverable through strategic discounting",
                "amount": round(total_to_discount, 0),
                "detail": (
                    f"Strategic discounting on slow/dead inventory could recover "
                    f"~{total_to_discount * 0.5:,.0f} of the {total_to_discount:,.0f} "
                    f"currently locked in non-performing stock."
                ),
                "action": "See discount plan for tier-by-tier recommendations.",
            })

        total_annual_erosion = sum(
            f.get("annual_cost", f.get("monthly_loss", 0) * 12)
            for f in findings
        )

        return {
            "findings": findings,
            "total_annual_margin_erosion": round(total_annual_erosion, 0),
            "summary": (
                f"Identified {len(findings)} margin leaks costing ~{total_annual_erosion:,.0f}/year. "
                f"Fixing these directly improves your bottom line."
            ),
        }

    # ------------------------------------------------------------------
    # 5. CUSTOMER LIFECYCLE — Who's churning? Who to invest in?
    # ------------------------------------------------------------------

    def _customer_lifecycle(self) -> dict:
        """Analyze customer health and predict churn."""
        customers = self.eco.get("customer_profitability", [])
        if not customers:
            return {"segments": {}, "note": "No customer data."}

        # Segment customers
        champions = []      # High revenue, reliable, recent
        at_risk = []        # High revenue but declining/overdue
        nurture = []        # Low revenue but growing
        churn_risk = []     # Haven't ordered recently
        vip_potential = []  # Good revenue, room to grow

        for c in customers:
            rev = c.get("total_net_revenue", 0)
            reliability = c.get("payment_reliability", 0)
            outstanding = c.get("total_outstanding", 0)
            invoice_count = c.get("invoice_count", 0)

            if rev > 50000 and reliability >= 90:
                champions.append({
                    "name": c.get("name", "Unknown"),
                    "revenue": round(rev, 0),
                    "reliability": reliability,
                    "invoices": invoice_count,
                    "recommendation": "VIP treatment — volume discounts, early access to new prints",
                })
            elif rev > 20000 and reliability < 80:
                at_risk.append({
                    "name": c.get("name", "Unknown"),
                    "revenue": round(rev, 0),
                    "reliability": reliability,
                    "outstanding": round(outstanding, 0),
                    "recommendation": "Require prepayment. High revenue but unreliable — protect yourself.",
                })
            elif rev > 10000 and reliability >= 85:
                vip_potential.append({
                    "name": c.get("name", "Unknown"),
                    "revenue": round(rev, 0),
                    "reliability": reliability,
                    "recommendation": "Upsell opportunity — offer bulk pricing to increase order size",
                })
            elif invoice_count <= 2 and rev < 5000:
                nurture.append({
                    "name": c.get("name", "Unknown"),
                    "revenue": round(rev, 0),
                    "invoices": invoice_count,
                    "recommendation": "Send a follow-up offer. First-time buyers need a nudge to return.",
                })

        return {
            "champions": champions[:10],
            "at_risk_high_value": at_risk[:10],
            "vip_potential": vip_potential[:10],
            "nurture": nurture[:10],
            "summary": {
                "champion_count": len(champions),
                "at_risk_count": len(at_risk),
                "at_risk_exposure": round(sum(c["outstanding"] for c in at_risk), 0),
                "vip_potential_count": len(vip_potential),
                "nurture_count": len(nurture),
                "insight": (
                    f"{len(champions)} champion customers (protect these at all costs). "
                    f"{len(at_risk)} high-value but risky customers "
                    f"({sum(c['outstanding'] for c in at_risk):,.0f} exposure). "
                    f"{len(vip_potential)} ready to grow into VIPs."
                ),
            },
        }

    # ------------------------------------------------------------------
    # 6. BUYING SIGNALS — What to buy/not buy
    # ------------------------------------------------------------------

    def _buying_signals(self) -> dict:
        """Clear buy/hold/cut signals combining all data."""
        buying_plan = self.woo_recs.get("buying_plan", {})
        velocity = self.woo.get("velocity", [])
        attributes = self.woo.get("attributes", {})

        aggressive_buy = []
        cautious_buy = []
        do_not_buy = []
        liquidate = []

        for v in velocity:
            stock = v["stock_quantity"]
            weekly = v["qty_per_week"]
            direction = v["direction"]
            rev = v["total_revenue"]
            days_since = v["days_since_last_sale"]

            if direction == "accelerating" and weekly > 1 and stock < weekly * 4:
                aggressive_buy.append({
                    "name": v["name"],
                    "sku": v.get("sku", ""),
                    "current_stock": stock,
                    "weekly_velocity": round(weekly, 1),
                    "weeks_left": round(stock / weekly, 1) if weekly > 0 else 999,
                    "suggested_order": max(round(weekly * 12), 1),  # 12 weeks supply
                    "reason": f"Accelerating at {weekly:.1f}/week, only {stock} left",
                    "urgency": "THIS WEEK",
                })
            elif direction == "stable" and weekly > 0.5 and stock < weekly * 6:
                cautious_buy.append({
                    "name": v["name"],
                    "sku": v.get("sku", ""),
                    "current_stock": stock,
                    "weekly_velocity": round(weekly, 1),
                    "suggested_order": max(round(weekly * 8), 1),  # 8 weeks supply
                    "reason": f"Steady seller at {weekly:.1f}/week",
                    "urgency": "NEXT 2 WEEKS",
                })
            elif v["total_sold"] == 0 and stock > 0 and days_since > 90:
                liquidate.append({
                    "name": v["name"],
                    "sku": v.get("sku", ""),
                    "stock": stock,
                    "capital_locked": round(stock * v["price"], 0),
                    "days_listed": days_since,
                    "reason": f"Zero sales in {days_since} days, {stock * v['price']:,.0f} locked",
                    "action": "DEEP DISCOUNT (50-70%) or REMOVE",
                })
            elif direction == "decelerating" or (days_since > 60 and v["total_sold"] > 0):
                do_not_buy.append({
                    "name": v["name"],
                    "sku": v.get("sku", ""),
                    "stock": stock,
                    "reason": (
                        f"{'Decelerating' if direction == 'decelerating' else 'Stale'} — "
                        f"sell through existing stock, don't reorder"
                    ),
                })

        return {
            "aggressive_buy": aggressive_buy[:20],
            "cautious_buy": cautious_buy[:20],
            "do_not_reorder": do_not_buy[:20],
            "liquidate_now": liquidate[:20],
            "attribute_signals": {
                "buy_more_colors": [
                    c["name"] for c in (attributes.get("colors", []))
                    if c.get("dominant_direction") == "accelerating"
                ][:5],
                "buy_more_patterns": [
                    p["name"] for p in (attributes.get("patterns", []))
                    if p.get("dominant_direction") == "accelerating"
                ][:5],
                "avoid_colors": [
                    c["name"] for c in (attributes.get("colors", []))
                    if c.get("total_revenue", 0) == 0 and c.get("product_count", 0) >= 2
                ][:5],
                "avoid_patterns": [
                    p["name"] for p in (attributes.get("patterns", []))
                    if p.get("total_revenue", 0) == 0 and p.get("product_count", 0) >= 2
                ][:5],
            },
            "summary": (
                f"BUY AGGRESSIVELY: {len(aggressive_buy)} products. "
                f"CAUTIOUS BUY: {len(cautious_buy)}. "
                f"STOP BUYING: {len(do_not_buy)}. "
                f"LIQUIDATE: {len(liquidate)}."
            ),
        }

    # ------------------------------------------------------------------
    # 7. RISK ALERTS — What could hurt you in 90 days?
    # ------------------------------------------------------------------

    def _risk_alerts(self) -> list:
        """Proactive warnings about risks in the next 90 days."""
        alerts = []

        # Risk: stockout on winners
        velocity = self.woo.get("velocity", [])
        winners_at_risk = [
            v for v in velocity
            if v["qty_per_week"] > 1 and v["stock_quantity"] > 0
            and v["stock_quantity"] / v["qty_per_week"] < 3
        ]
        if winners_at_risk:
            lost_weekly_rev = sum(v["rev_per_week"] for v in winners_at_risk)
            alerts.append({
                "risk": "STOCKOUT ON TOP SELLERS",
                "severity": "critical",
                "timeframe": "1-3 weeks",
                "impact": f"Could lose {lost_weekly_rev:,.0f}/week in revenue",
                "detail": (
                    f"{len(winners_at_risk)} top-selling products will run out within 3 weeks. "
                    f"Combined they generate {lost_weekly_rev:,.0f}/week."
                ),
                "products": [v["name"] for v in winners_at_risk[:5]],
                "action": "Order these TODAY. Every day of stockout = lost revenue that never comes back.",
            })

        # Risk: customer concentration
        customers = self.eco.get("customer_profitability", [])
        total_rev = self.eco.get("summary", {}).get("total_net_revenue", 0)
        if customers and total_rev > 0:
            top3_rev = sum(c.get("total_net_revenue", 0) for c in customers[:3])
            concentration = top3_rev / total_rev
            if concentration > 0.3:
                alerts.append({
                    "risk": "CUSTOMER CONCENTRATION",
                    "severity": "warning",
                    "timeframe": "ongoing",
                    "impact": f"Top 3 customers = {concentration:.0%} of revenue",
                    "detail": (
                        f"If any of your top 3 customers ({', '.join(c.get('name', '?') for c in customers[:3])}) "
                        f"stops ordering, you lose {concentration:.0%} of revenue. "
                        f"Diversify your customer base."
                    ),
                    "action": "Invest in acquiring new B2B customers. Consider Etsy/Amazon channels.",
                })

        # Risk: seasonal downturn approaching
        seasonal_alerts = {
            5: "Summer dip approaching (July). Reduce inventory orders in June.",
            6: "July is historically your worst month (-49%). Tighten cash now.",
            10: "Holiday season ending. December/January will drop. Don't overstock.",
            11: "Year-end slowdown. Reduce reorders, focus on clearance.",
        }
        if self._month in seasonal_alerts:
            alerts.append({
                "risk": "SEASONAL DOWNTURN AHEAD",
                "severity": "warning",
                "timeframe": "next 30-60 days",
                "impact": "Revenue could drop 30-50%",
                "detail": seasonal_alerts[self._month],
                "action": "Cut reorder quantities by 30%. Front-load marketing to current month.",
            })

        # Risk: overdue concentration
        ar = self.eco.get("accounts_receivable", {})
        worst_debtors = ar.get("worst_debtors", [])
        over_90 = [d for d in worst_debtors if d.get("avg_days_overdue", 0) > 90]
        if over_90:
            total_over_90 = sum(d.get("total_outstanding", 0) for d in over_90)
            alerts.append({
                "risk": "BAD DEBT RISK",
                "severity": "critical" if total_over_90 > 100000 else "warning",
                "timeframe": "now",
                "impact": f"{total_over_90:,.0f} may become uncollectable",
                "detail": (
                    f"{len(over_90)} customers owe {total_over_90:,.0f} at 90+ days overdue. "
                    f"After 90 days, collection probability drops significantly."
                ),
                "action": "Send final demand letters. Consider debt collection for amounts over 10K.",
            })

        # Risk: dead stock growing
        dead_ratio = self.woo.get("summary", {}).get("dead_stock_ratio", 0)
        if dead_ratio > 0.25:
            alerts.append({
                "risk": "INVENTORY OBSOLESCENCE",
                "severity": "warning",
                "timeframe": "next 90 days",
                "impact": f"{dead_ratio:.0%} of inventory value is dead",
                "detail": (
                    f"Over a quarter of your inventory isn't selling. "
                    f"This will get worse, not better. Fabric trends move fast."
                ),
                "action": "Launch 'warehouse sale' this week. Target 50% recovery on dead stock.",
            })

        # Risk: economic headwinds
        conf = DANISH_ECONOMY.get("consumer_confidence_index", 0)
        if conf < -15:
            alerts.append({
                "risk": "LOW CONSUMER CONFIDENCE",
                "severity": "info",
                "timeframe": "ongoing",
                "impact": f"Danish consumer confidence at {conf} (long-term avg: +1.3)",
                "detail": (
                    "Consumer confidence is deeply negative, though retail sales "
                    "are still growing +4.7%. Danes are spending but cautious. "
                    "Focus on value propositions and avoid aggressive price increases."
                ),
                "action": (
                    "Emphasize quality and sustainability in marketing. "
                    "Consider bundle deals to increase perceived value."
                ),
            })

        # Risk: trend misalignment
        velocity = self.woo.get("velocity", [])
        fabrics = self.woo.get("attributes", {}).get("fabrics", [])
        if fabrics:
            trending_names = {t["name"].lower() for t in FABRIC_TRENDS_2026["trending_fabrics"]}
            total_rev = sum(f.get("total_revenue", 0) for f in fabrics)
            trending_rev = sum(
                f.get("total_revenue", 0) for f in fabrics
                if any(t in f.get("name", "").lower() for t in trending_names)
            )
            if total_rev > 0 and trending_rev / total_rev < 0.3:
                alerts.append({
                    "risk": "TREND MISALIGNMENT",
                    "severity": "warning",
                    "timeframe": "next 3-6 months",
                    "impact": f"Only {trending_rev/total_rev:.0%} of revenue from trending fabrics",
                    "detail": (
                        "2026 fabric trends emphasize texture (bouclé, velvet, jacquard), "
                        "sustainability (linen, organic cotton, hemp), and bold prints. "
                        "Your inventory may be falling behind market direction."
                    ),
                    "action": (
                        "Shift purchasing toward trending fabrics. "
                        "Consider adding bouclé and textured knits to your collection."
                    ),
                })

        alerts.sort(key=lambda a: {"critical": 0, "warning": 1, "info": 2}.get(a.get("severity"), 2))
        return alerts

    # ------------------------------------------------------------------
    # 8. 90-DAY ACTION PLAN
    # ------------------------------------------------------------------

    def _build_90_day_plan(self) -> dict:
        """Concrete, prioritized actions for this week, this month, this quarter."""
        this_week = []
        this_month = []
        this_quarter = []

        # --- THIS WEEK ---

        # Reorder urgent products
        velocity = self.woo.get("velocity", [])
        urgent_reorders = [
            v for v in velocity
            if v["qty_per_week"] > 0 and v["stock_quantity"] > 0
            and v["stock_quantity"] / v["qty_per_week"] < 2
        ]
        if urgent_reorders:
            this_week.append({
                "action": "Place reorders for critically low stock",
                "detail": f"{len(urgent_reorders)} products will sell out within 2 weeks",
                "products": [
                    f"{v['name']} (stock: {v['stock_quantity']}, sells {v['qty_per_week']:.1f}/week)"
                    for v in urgent_reorders[:5]
                ],
                "impact": "Prevents revenue loss from stockouts",
            })

        # Chase overdue invoices
        ar = self.eco.get("accounts_receivable", {})
        overdue = ar.get("total_overdue", 0)
        if overdue > 10000:
            worst = ar.get("worst_debtors", [])
            this_week.append({
                "action": f"Chase {overdue:,.0f} in overdue invoices",
                "detail": "Send payment reminders and final demands",
                "contacts": [
                    f"{d['name']}: {d['total_outstanding']:,.0f}"
                    for d in worst[:5]
                ],
                "impact": f"Recover up to {overdue:,.0f} in cash",
            })

        # --- THIS MONTH ---

        # Dead stock clearance
        dead_capital = self.woo.get("summary", {}).get("dead_stock_capital", 0)
        if dead_capital > 5000:
            this_month.append({
                "action": "Launch dead stock clearance sale",
                "detail": (
                    f"Create a 'Warehouse Sale' collection with all dead stock at 40-60% off. "
                    f"Target: recover {dead_capital * 0.4:,.0f} of the {dead_capital:,.0f} locked up."
                ),
                "impact": f"Free up to {dead_capital * 0.4:,.0f} in working capital",
            })

        # Customer outreach
        customers = self.eco.get("customer_profitability", [])
        high_value = [c for c in customers[:20] if c.get("payment_reliability", 0) >= 90]
        if high_value:
            this_month.append({
                "action": f"VIP outreach to top {len(high_value)} reliable customers",
                "detail": (
                    "Send personalized email with early access to new collections, "
                    "volume discount offers, or fabric sample packs."
                ),
                "impact": "Increase repeat orders from your most profitable customers",
            })

        # Payment terms review
        bad_payers = [
            c for c in customers[:30]
            if c.get("payment_reliability", 100) < 75
            and c.get("total_outstanding", 0) > 5000
        ]
        if bad_payers:
            this_month.append({
                "action": f"Switch {len(bad_payers)} customers to prepayment terms",
                "detail": (
                    "These customers have <75% payment reliability. "
                    "Change their terms to 'Netto kontant' (cash on delivery) or prepayment."
                ),
                "customers": [c.get("name", "?") for c in bad_payers[:5]],
                "impact": "Reduce future bad debt risk",
            })

        # --- THIS QUARTER ---

        # Inventory optimization
        this_quarter.append({
            "action": "Reduce total SKU count by removing zero-performers",
            "detail": (
                "Products that have never sold after 120+ days should be removed from the store. "
                "Fewer SKUs = less capital tied up + cleaner store for customers."
            ),
            "impact": "Lower holding costs, cleaner product catalog",
        })

        # Seasonal preparation
        season_prep = {
            1: "Stock spring fabrics (cotton, linen, floral). Order by late February.",
            2: "Spring collection launch. Heavy marketing on new arrivals.",
            3: "Summer prep — order lightweight, tropical prints. Plan summer sale for July.",
            4: "Peak spring sales. Double down on marketing. Stock up on bestsellers.",
            5: "Summer preview + prep for the July dip. Start clearance on spring leftovers.",
            6: "Final push before summer dip. Heavy promotion this month.",
            7: "Lowest month — focus on planning, not spending. Prep autumn collection.",
            8: "Autumn rebound begins! Launch autumn collection, heavy marketing.",
            9: "Peak season approaching. Stock up for October peak.",
            10: "Best month historically. Maximize sales. Start holiday collection tease.",
            11: "Holiday rush. Christmas fabrics, gift bundles. Black Friday sale.",
            12: "Wind down + January sale prep. Clear remaining holiday stock.",
        }
        if self._month in season_prep:
            this_quarter.append({
                "action": "Seasonal strategy",
                "detail": season_prep[self._month],
                "impact": "Align inventory and marketing with proven seasonal patterns",
            })

        # Revenue diversification
        geo = self.woo.get("geography", {})
        countries = geo.get("countries", [])
        if countries and len(countries) < 5:
            this_quarter.append({
                "action": "Expand to new markets",
                "detail": (
                    f"You currently sell to {len(countries)} countries. "
                    f"Nordic neighbors (SE, NO, FI) and DE are natural expansion markets "
                    f"for Danish fabric retailers."
                ),
                "impact": "Reduce dependence on single-market revenue",
            })

        return {
            "this_week": this_week,
            "this_month": this_month,
            "this_quarter": this_quarter,
            "summary": (
                f"{len(this_week)} urgent actions this week, "
                f"{len(this_month)} this month, "
                f"{len(this_quarter)} this quarter."
            ),
        }
