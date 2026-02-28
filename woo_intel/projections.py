"""Revenue Projections & Cash Flow Monitor.

Projects future revenue based on current velocity, seasonal patterns,
and trend direction.  Monitors cash flow health and inventory turnover.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RevenueProjector:
    """Forecasts revenue and monitors cash flow."""

    def __init__(self, analysis: dict, orders: list[dict] = None):
        self.analysis = analysis
        self.orders = orders or []
        self._now = datetime.utcnow()
        self.summary = analysis.get("summary", {})

    def project_revenue(self, weeks_ahead: int = 12) -> dict:
        """Project revenue for next N weeks based on current velocity."""
        velocity = self.analysis.get("velocity", [])
        seasonal = self.analysis.get("seasonal", {})

        # Calculate current weekly run rate from velocity data
        active = [v for v in velocity if v["qty_per_week"] > 0]
        if not active:
            return self._empty_projection(weeks_ahead)

        current_weekly_rev = sum(v["rev_per_week"] for v in active)

        # Build weekly projections with seasonal adjustment
        weekly = []
        monthly_seasonal = self._get_monthly_factors(seasonal)

        for w in range(1, weeks_ahead + 1):
            target_date = self._now + timedelta(weeks=w)
            month = target_date.month
            factor = monthly_seasonal.get(month, 1.0)

            # Adjust for trend direction
            accelerating = len([v for v in active if v["direction"] == "accelerating"])
            decelerating = len([v for v in active if v["direction"] == "decelerating"])
            trend_factor = 1.0
            if accelerating > decelerating:
                trend_factor = 1.0 + (0.02 * w)  # compounding growth
            elif decelerating > accelerating:
                trend_factor = max(1.0 - (0.01 * w), 0.7)

            projected = current_weekly_rev * factor * trend_factor
            weekly.append({
                "week": w,
                "date": target_date.strftime("%Y-%m-%d"),
                "month": target_date.strftime("%B"),
                "projected_revenue": round(projected, 2),
                "seasonal_factor": round(factor, 2),
                "trend_factor": round(trend_factor, 3),
            })

        # Aggregate to monthly
        monthly_proj = defaultdict(float)
        for w in weekly:
            monthly_proj[w["month"]] += w["projected_revenue"]

        total_projected = sum(w["projected_revenue"] for w in weekly)

        # Confidence based on data quality
        order_count = len(self.orders)
        if order_count > 200:
            confidence = "high"
        elif order_count > 50:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "current_weekly_revenue": round(current_weekly_rev, 2),
            "projected_total": round(total_projected, 2),
            "weeks_ahead": weeks_ahead,
            "weekly": weekly,
            "monthly": {
                k: round(v, 2) for k, v in monthly_proj.items()
            },
            "confidence": confidence,
            "note": (
                f"Based on {len(active)} active products, "
                f"{order_count} historical orders, "
                f"and seasonal patterns."
            ),
        }

    def get_cash_flow_health(self) -> dict:
        """Assess overall cash flow health of the inventory."""
        summary = self.summary
        total_inv = summary.get("total_inventory_value", 0)
        dead_capital = summary.get("dead_stock_capital", 0)
        total_rev = summary.get("total_revenue", 0)
        total_orders = summary.get("total_orders", 0)

        # Inventory turnover ratio (annual revenue / average inventory)
        turnover = total_rev / total_inv if total_inv else 0

        # Gross margin estimate (fabric typically 40-60% markup)
        est_cogs_ratio = 0.45  # assume 45% cost of goods
        est_gross_profit = total_rev * (1 - est_cogs_ratio)

        # Days of inventory remaining (current stock / daily sell rate)
        velocity = self.analysis.get("velocity", [])
        daily_units = sum(v["qty_per_week"] for v in velocity if v["qty_per_week"] > 0) / 7
        total_stock = sum(v["stock_quantity"] for v in velocity if v["stock_quantity"] > 0)
        days_of_inventory = total_stock / daily_units if daily_units > 0 else 999

        # Working capital efficiency
        working_capital_ratio = dead_capital / total_inv if total_inv else 0

        # Health score (0-100)
        health = 100
        if working_capital_ratio > 0.4:
            health -= 30
        elif working_capital_ratio > 0.2:
            health -= 15
        if turnover < 2:
            health -= 20
        elif turnover < 4:
            health -= 10
        if days_of_inventory > 180:
            health -= 15
        elif days_of_inventory > 90:
            health -= 5
        if total_orders < 20:
            health -= 10  # not enough data

        health = max(0, min(100, health))

        if health >= 80:
            rating = "Healthy"
            color = "green"
        elif health >= 60:
            rating = "Needs Attention"
            color = "yellow"
        elif health >= 40:
            rating = "At Risk"
            color = "orange"
        else:
            rating = "Critical"
            color = "red"

        return {
            "health_score": health,
            "rating": rating,
            "color": color,
            "metrics": {
                "inventory_turnover": round(turnover, 2),
                "turnover_note": self._turnover_note(turnover),
                "days_of_inventory": round(days_of_inventory, 0),
                "working_capital_tied_pct": round(working_capital_ratio * 100, 1),
                "dead_capital": round(dead_capital, 2),
                "total_inventory_value": round(total_inv, 2),
                "est_gross_profit": round(est_gross_profit, 2),
                "avg_order_value": round(
                    total_rev / total_orders, 2
                ) if total_orders else 0,
            },
            "recommendations": self._cash_flow_recs(
                health, working_capital_ratio, turnover, days_of_inventory
            ),
        }

    def get_inventory_turnover_by_category(self) -> list[dict]:
        """Inventory turnover rate per product category."""
        categories = self.analysis.get("categories", [])
        results = []
        for cat in categories:
            if cat["product_count"] == 0:
                continue
            turnover = (
                cat["total_revenue"] / (cat["avg_rev_per_product"] * cat["product_count"])
                if cat["avg_rev_per_product"] and cat["product_count"]
                else 0
            )
            results.append({
                "category": cat["category"],
                "turnover": round(turnover, 2),
                "revenue": cat["total_revenue"],
                "products": cat["product_count"],
                "dead_ratio": cat["dead_ratio"],
                "health": (
                    "good" if cat["dead_ratio"] < 0.2
                    else "warning" if cat["dead_ratio"] < 0.4
                    else "poor"
                ),
            })
        return sorted(results, key=lambda r: r["turnover"], reverse=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _empty_projection(self, weeks: int) -> dict:
        return {
            "current_weekly_revenue": 0,
            "projected_total": 0,
            "weeks_ahead": weeks,
            "weekly": [],
            "monthly": {},
            "confidence": "none",
            "note": "No active sales data to project from.",
        }

    def _get_monthly_factors(self, seasonal: dict) -> dict:
        """Compute relative seasonal factors from historical data."""
        monthly = seasonal.get("monthly", [])
        if not monthly:
            return {m: 1.0 for m in range(1, 13)}

        revenues = [m["revenue"] for m in monthly]
        avg_rev = sum(revenues) / len(revenues) if revenues else 1
        if avg_rev == 0:
            return {m: 1.0 for m in range(1, 13)}

        return {
            m["month"]: round(m["revenue"] / avg_rev, 2) if m["revenue"] else 0.8
            for m in monthly
        }

    def _turnover_note(self, turnover: float) -> str:
        if turnover >= 8:
            return "Excellent — inventory moves fast"
        elif turnover >= 4:
            return "Good — healthy turnover for fabric retail"
        elif turnover >= 2:
            return "Below average — consider reducing slow stock"
        else:
            return "Low — too much capital locked in inventory"

    def _cash_flow_recs(self, health, wc_ratio, turnover, days_inv) -> list[str]:
        recs = []
        if wc_ratio > 0.3:
            recs.append(
                "Urgent: Run a clearance sale to free up dead stock capital"
            )
        if turnover < 2:
            recs.append(
                "Reduce SKU count — focus on fewer, proven products"
            )
        if days_inv > 120:
            recs.append(
                "Over-stocked: reduce reorder quantities by 30% until "
                "inventory normalizes"
            )
        if health >= 70:
            recs.append(
                "Cash flow is healthy — you can invest in new designs"
            )
        return recs
