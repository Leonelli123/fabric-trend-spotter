"""Jersey Print Demand Forecaster.

Predicts how much of each jersey print design to reorder from the supplier,
factoring in:
  - Recent velocity (90-day window, not lifetime average)
  - Trend direction (accelerating designs get bigger orders)
  - Seasonal demand curves (jersey peaks spring-autumn)
  - Supplier lead time (Turkey = 4-5 weeks typically)
  - Safety stock buffer to prevent stockouts during lead time
  - Overstock risk scoring (decelerating = order less)
  - Minimum order quantity (MOQ) per design (Turkey: 50m minimum)

Output:
  - Per-design reorder recommendation with quantity, urgency, confidence
  - Supplier order summary (ready to copy/email to Turkey)
  - Stockout risk alerts (designs that will run out before delivery)
  - Overstock warnings (designs sitting too long)

Note: The forecaster uses WooCommerce stock_quantity (current inventory) and
customer order history to predict demand. It does NOT track inbound orders
(stock ordered from Turkey but not yet received). If you've already placed
an order, account for that when reviewing the suggestions.
"""

import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta

from woo_intel.analyzer import SEASONAL_FABRIC_PATTERNS, SEASONAL_COLOR_PATTERNS

logger = logging.getLogger(__name__)

# Jersey is in-season these months (primary demand window)
JERSEY_PEAK_MONTHS = {2, 3, 4, 5, 6, 7, 8, 9}  # Feb-Sep
JERSEY_HIGH_MONTHS = {4, 5, 6, 7, 8}  # Apr-Aug = peak peak

# Seasonal demand multipliers for jersey specifically
JERSEY_SEASONAL_FACTORS = {
    1: 0.6,   # Jan: post-holiday low
    2: 0.75,  # Feb: spring planning starts
    3: 0.9,   # Mar: spring orders pick up
    4: 1.15,  # Apr: peak spring
    5: 1.2,   # May: summer prep
    6: 1.2,   # Jun: summer peak
    7: 1.1,   # Jul: mid-summer, back-to-school starts
    8: 1.1,   # Aug: back-to-school
    9: 0.95,  # Sep: autumn transition
    10: 0.7,  # Oct: jersey demand drops
    11: 0.55, # Nov: holiday fabrics dominate
    12: 0.5,  # Dec: lowest jersey demand
}


class PrintForecaster:
    """Forecasts jersey print reorder quantities from sales data."""

    def __init__(self, analysis: dict, lead_time_weeks: int = 5,
                 moq_per_design: int = 50):
        """
        Args:
            analysis: Full inventory analysis from InventoryAnalyzer.run_full_analysis()
            lead_time_weeks: Supplier lead time in weeks (Turkey default: 5)
            moq_per_design: Minimum order quantity per design in meters (Turkey: 50)
        """
        self.analysis = analysis
        self.lead_time_weeks = lead_time_weeks
        self.moq = moq_per_design
        self._now = datetime.utcnow()
        self._current_month = self._now.month

    def forecast_all(self) -> dict:
        """Run complete print demand forecast."""
        velocity = self.analysis.get("velocity", [])

        # Filter to jersey products only
        jersey_products = self._filter_jersey_products(velocity)

        if not jersey_products:
            return self._empty_forecast()

        # Build per-design forecasts
        design_forecasts = []
        for product in jersey_products:
            forecast = self._forecast_single(product)
            design_forecasts.append(forecast)

        # Sort by urgency: stockout-risk first, then by demand
        design_forecasts.sort(
            key=lambda f: (
                -f["stockout_risk_score"],
                -f["forecast_demand_8w"],
            )
        )

        # Build summary groupings
        reorder_now = [f for f in design_forecasts if f["action"] == "REORDER_NOW"]
        reorder_soon = [f for f in design_forecasts if f["action"] == "REORDER_SOON"]
        hold = [f for f in design_forecasts if f["action"] in ("HOLD", "WELL_STOCKED")]
        reduce = [f for f in design_forecasts if f["action"] in ("OVERSTOCK", "PHASE_OUT")]

        # Aggregate reorder quantities for supplier order
        supplier_order = self._build_supplier_order(reorder_now + reorder_soon)

        # Build stockout timeline
        stockout_timeline = self._build_stockout_timeline(design_forecasts)

        # Design performance ranking
        design_ranking = self._rank_designs(jersey_products)

        # Seasonal outlook for jersey
        seasonal_outlook = self._get_seasonal_outlook()

        return {
            "generated_at": self._now.isoformat(),
            "total_jersey_products": len(jersey_products),
            "lead_time_weeks": self.lead_time_weeks,
            "moq_per_design": self.moq,
            "summary": {
                "reorder_now_count": len(reorder_now),
                "reorder_soon_count": len(reorder_soon),
                "well_stocked_count": len(hold),
                "overstock_count": len(reduce),
                "total_reorder_qty": sum(
                    f["suggested_reorder_qty"] for f in reorder_now + reorder_soon
                ),
                "total_reorder_value": round(sum(
                    f["suggested_reorder_qty"] * f["price"]
                    for f in reorder_now + reorder_soon
                ), 2),
                "stockout_risk_products": len([
                    f for f in design_forecasts if f["stockout_risk_score"] >= 70
                ]),
            },
            "design_forecasts": design_forecasts,
            "reorder_now": reorder_now,
            "reorder_soon": reorder_soon,
            "hold": hold,
            "reduce": reduce,
            "supplier_order": supplier_order,
            "stockout_timeline": stockout_timeline,
            "design_ranking": design_ranking,
            "seasonal_outlook": seasonal_outlook,
        }

    # ------------------------------------------------------------------
    # Jersey product filtering
    # ------------------------------------------------------------------

    def _filter_jersey_products(self, velocity: list[dict]) -> list[dict]:
        """Identify jersey print products from the velocity data.

        Uses multiple signals:
          1. jersey_or_woven attribute == "Jersey" (primary)
          2. fabric_type containing "jersey" (fallback)
          3. Category names containing "jersey" (fallback)
          4. Product name containing "jersey" (last resort)
        """
        jersey = []
        for v in velocity:
            is_jersey = False

            # Check jersey_or_woven attribute (most reliable)
            # This field comes from the WooCommerce product attribute
            # "jersey / fast" or "jersey/fast" or "type"
            jw = (v.get("jersey_or_woven", "") or "").lower()
            if "jersey" in jw:
                is_jersey = True

            # Check fabric_type
            if not is_jersey:
                fabric = (v.get("fabric_type", "") or "").lower()
                if "jersey" in fabric:
                    is_jersey = True

            # Check categories
            if not is_jersey:
                cats = v.get("categories", [])
                if any("jersey" in c.lower() for c in cats):
                    is_jersey = True

            # Check product name (last resort, less reliable)
            if not is_jersey:
                name = (v.get("name", "") or "").lower()
                if "jersey" in name:
                    is_jersey = True

            if is_jersey:
                jersey.append(v)

        logger.info("Found %d jersey products out of %d total", len(jersey), len(velocity))
        return jersey

    # ------------------------------------------------------------------
    # Per-design demand forecast
    # ------------------------------------------------------------------

    def _forecast_single(self, v: dict) -> dict:
        """Forecast demand and reorder quantity for a single design."""
        stock = v["stock_quantity"]
        qty_week = v["qty_per_week"]
        recent_rate = v.get("recent_rate", 0)
        direction = v["direction"]
        velocity_change = v.get("velocity_change", 0)
        recent_90d_qty = v.get("recent_90d_qty", 0)
        prev_90d_qty = v.get("prev_90d_qty", 0)
        has_recent = v.get("has_recent_sales", False)

        # Use RECENT velocity (90-day) as primary signal, not lifetime average
        # This is the key insight — recent demand matters more than history
        effective_rate = recent_rate if recent_rate > 0 else qty_week

        # Apply seasonal adjustment for forecast period
        seasonal_factor = self._get_forecast_seasonal_factor()

        # Apply trend adjustment based on direction
        trend_factor = self._get_trend_factor(direction, velocity_change)

        # Adjusted weekly demand forecast
        adjusted_rate = effective_rate * seasonal_factor * trend_factor

        # Forecast demand for next 8 weeks (standard order cycle)
        forecast_8w = round(adjusted_rate * 8)

        # Forecast demand during lead time (how much sells while waiting)
        demand_during_lead = round(adjusted_rate * self.lead_time_weeks)

        # Safety stock: extra buffer to prevent stockout
        # Higher for accelerating products, lower for decelerating
        safety_weeks = self._get_safety_weeks(direction, velocity_change)
        safety_stock = round(adjusted_rate * safety_weeks)

        # Weeks of stock remaining at current rate
        weeks_of_stock = stock / effective_rate if effective_rate > 0 else 999

        # Stockout risk: will we run out before supplier can deliver?
        will_stockout_before_delivery = (
            stock < demand_during_lead and effective_rate > 0
        )
        days_until_stockout = (
            round(stock / (effective_rate / 7)) if effective_rate > 0 else 999
        )
        stockout_risk_score = self._calc_stockout_risk(
            weeks_of_stock, direction, velocity_change, has_recent
        )

        # Suggested reorder quantity
        # = forecast demand + safety stock - current stock (but not negative)
        # Then round UP to the supplier's minimum order quantity (MOQ)
        ideal_stock_target = forecast_8w + safety_stock
        raw_reorder = max(ideal_stock_target - stock, 0)
        if raw_reorder > 0 and self.moq > 0:
            # Round up to nearest MOQ (e.g. 50m minimum per design)
            suggested_reorder = max(math.ceil(raw_reorder / self.moq) * self.moq, self.moq)
        else:
            suggested_reorder = 0

        # Action classification
        action, reason = self._classify_action(
            weeks_of_stock, direction, has_recent, stock,
            suggested_reorder, recent_90d_qty, adjusted_rate,
            seasonal_factor,
        )

        # Confidence level
        confidence = self._assess_confidence(v)

        return {
            "product_id": v["product_id"],
            "name": v["name"],
            "sku": v.get("sku", ""),
            "price": v["price"],
            "pattern": v.get("pattern", ""),
            "color": v.get("color", ""),
            "categories": v.get("categories", []),
            # Current state
            "current_stock": stock,
            "weeks_of_stock": round(weeks_of_stock, 1),
            "days_until_stockout": min(days_until_stockout, 999),
            # Velocity
            "current_weekly_rate": round(effective_rate, 2),
            "adjusted_weekly_rate": round(adjusted_rate, 2),
            "recent_90d_qty": recent_90d_qty,
            "prev_90d_qty": prev_90d_qty,
            "direction": direction,
            "velocity_change_pct": round(velocity_change * 100, 1),
            "total_sold": v["total_sold"],
            # Adjustments applied
            "seasonal_factor": round(seasonal_factor, 2),
            "trend_factor": round(trend_factor, 2),
            "safety_weeks": safety_weeks,
            # Forecast
            "forecast_demand_8w": forecast_8w,
            "demand_during_lead_time": demand_during_lead,
            "safety_stock": safety_stock,
            # Recommendation
            "suggested_reorder_qty": suggested_reorder,
            "stock_target": ideal_stock_target,
            "action": action,
            "reason": reason,
            # Risk
            "stockout_risk_score": stockout_risk_score,
            "will_stockout_before_delivery": will_stockout_before_delivery,
            "confidence": confidence,
        }

    def _get_forecast_seasonal_factor(self) -> float:
        """Get seasonal factor for the forecast period (next 8-12 weeks).

        Averages the seasonal factors across the forecast window,
        not just the current month.
        """
        factors = []
        for w in range(self.lead_time_weeks, self.lead_time_weeks + 8):
            future_date = self._now + timedelta(weeks=w)
            month = future_date.month
            factors.append(JERSEY_SEASONAL_FACTORS.get(month, 1.0))
        return sum(factors) / len(factors) if factors else 1.0

    def _get_trend_factor(self, direction: str, velocity_change: float) -> float:
        """Adjust forecast based on trend direction.

        Accelerating = order MORE (the trend will continue short-term)
        Decelerating = order LESS (don't get stuck with excess)
        Stable = order at face value
        """
        if direction == "accelerating":
            # Cap upside at 40% boost — don't over-order on hype
            return min(1.0 + abs(velocity_change) * 0.5, 1.4)
        elif direction == "decelerating":
            # Reduce by half the decline rate — cautious but not zero
            return max(1.0 - abs(velocity_change) * 0.3, 0.5)
        return 1.0

    def _get_safety_weeks(self, direction: str, velocity_change: float) -> float:
        """How many extra weeks of safety stock to hold.

        More safety for:
          - Accelerating products (demand may spike)
          - Products with high velocity variance
        Less safety for:
          - Decelerating products (excess risk)
          - Very stable products (predictable)
        """
        if direction == "accelerating":
            return 3.0  # 3 weeks buffer for fast movers
        elif direction == "stable":
            return 2.0  # 2 weeks standard buffer
        elif direction == "decelerating":
            return 1.0  # minimal buffer — don't overbuy
        return 1.5  # default for uncertain products

    def _calc_stockout_risk(self, weeks_of_stock: float, direction: str,
                            velocity_change: float, has_recent: bool) -> int:
        """Score stockout risk 0-100.

        100 = will definitely run out before next delivery
        0 = plenty of stock for months
        """
        if weeks_of_stock >= 999 or not has_recent:
            return 0  # no sales = no stockout risk

        score = 0

        # Base risk from stock level vs lead time
        if weeks_of_stock < self.lead_time_weeks:
            # Will run out before delivery arrives
            score += 80
        elif weeks_of_stock < self.lead_time_weeks + 2:
            # Cutting it close
            score += 60
        elif weeks_of_stock < self.lead_time_weeks + 4:
            score += 35
        elif weeks_of_stock < 8:
            score += 15

        # Amplify if accelerating (demand growing = more risk)
        if direction == "accelerating":
            score = min(score + 15, 100)
        elif direction == "decelerating":
            score = max(score - 10, 0)

        return min(score, 100)

    def _classify_action(self, weeks_of_stock, direction, has_recent,
                         stock, suggested_qty, recent_90d_qty,
                         adjusted_rate, seasonal_factor) -> tuple[str, str]:
        """Classify into action bucket with human-readable reason."""
        lead = self.lead_time_weeks

        if weeks_of_stock < lead and has_recent:
            return "REORDER_NOW", (
                f"Only {weeks_of_stock:.0f} weeks of stock — will run out before "
                f"delivery from Turkey (lead time: {lead} weeks). "
                f"Selling ~{adjusted_rate:.1f}/week. Order immediately."
            )

        if weeks_of_stock < lead + 3 and has_recent and direction != "decelerating":
            return "REORDER_SOON", (
                f"{weeks_of_stock:.0f} weeks left at current pace. "
                f"Place order within the next week to avoid gap. "
                f"{'Demand is growing — order generously.' if direction == 'accelerating' else 'Demand is steady.'}"
            )

        if not has_recent and stock > 0 and recent_90d_qty == 0:
            if stock > 20:
                return "OVERSTOCK", (
                    f"No sales in 90 days but {stock} units in stock. "
                    f"Do NOT reorder. Consider promotional push or discount."
                )
            return "PHASE_OUT", (
                f"No recent sales, {stock} left. "
                f"Discount to clear, do not reorder this design."
            )

        if direction == "decelerating" and weeks_of_stock > 12:
            return "OVERSTOCK", (
                f"Sales declining ({adjusted_rate:.1f}/week trend) and "
                f"{weeks_of_stock:.0f} weeks of stock. "
                f"Do NOT reorder — let stock sell through."
            )

        if weeks_of_stock > 12:
            return "WELL_STOCKED", (
                f"{weeks_of_stock:.0f} weeks of stock remaining. "
                f"No reorder needed yet. "
                f"{'Demand is growing — re-check in 2 weeks.' if direction == 'accelerating' else 'Monitor weekly.'}"
            )

        if suggested_qty > 0 and has_recent:
            return "REORDER_SOON", (
                f"{weeks_of_stock:.0f} weeks left. Forecast says order "
                f"{suggested_qty} units to cover next 8 weeks + safety buffer."
            )

        return "HOLD", (
            f"Current stock of {stock} is adequate. "
            f"Re-check next week."
        )

    def _assess_confidence(self, v: dict) -> str:
        """How confident are we in this forecast?"""
        sale_count = v.get("sale_count", 0)
        has_recent = v.get("has_recent_sales", False)

        if sale_count >= 20 and has_recent:
            return "high"
        elif sale_count >= 8 and has_recent:
            return "medium"
        elif sale_count >= 3:
            return "low"
        return "very_low"

    # ------------------------------------------------------------------
    # Supplier order builder
    # ------------------------------------------------------------------

    def _build_supplier_order(self, reorder_items: list[dict]) -> dict:
        """Build a summary order for the Turkish supplier.

        Groups by design/pattern and produces a ready-to-send order list.
        """
        if not reorder_items:
            return {
                "items": [],
                "total_units": 0,
                "total_estimated_cost": 0,
                "order_note": "No reorders needed at this time.",
            }

        items = []
        for f in reorder_items:
            items.append({
                "name": f["name"],
                "sku": f["sku"],
                "pattern": f["pattern"],
                "color": f["color"],
                "quantity": f["suggested_reorder_qty"],
                "urgency": f["action"],
                "current_stock": f["current_stock"],
                "weekly_demand": f["adjusted_weekly_rate"],
                "days_until_stockout": f["days_until_stockout"],
                "confidence": f["confidence"],
            })

        # Sort: urgent first, then by quantity descending
        items.sort(key=lambda i: (
            0 if i["urgency"] == "REORDER_NOW" else 1,
            -i["quantity"],
        ))

        total_units = sum(i["quantity"] for i in items)
        total_cost = sum(
            f["suggested_reorder_qty"] * f["price"] for f in reorder_items
        )

        urgent_count = len([i for i in items if i["urgency"] == "REORDER_NOW"])

        if urgent_count > 0:
            note = (
                f"{urgent_count} designs are URGENT — will run out before "
                f"delivery arrives. Place order today."
            )
        else:
            note = (
                f"{len(items)} designs need restocking within the next week. "
                f"Standard lead time order."
            )

        return {
            "items": items,
            "total_units": total_units,
            "total_estimated_cost": round(total_cost, 2),
            "item_count": len(items),
            "urgent_count": urgent_count,
            "order_note": note,
        }

    # ------------------------------------------------------------------
    # Stockout timeline
    # ------------------------------------------------------------------

    def _build_stockout_timeline(self, forecasts: list[dict]) -> list[dict]:
        """Which designs run out first? Timeline view."""
        timeline = []
        for f in forecasts:
            if f["current_stock"] <= 0 or not f.get("current_weekly_rate", 0):
                continue
            days = f["days_until_stockout"]
            if days > 180:
                continue  # skip products with 6+ months stock

            stockout_date = self._now + timedelta(days=days)
            delivery_date = self._now + timedelta(weeks=self.lead_time_weeks)

            timeline.append({
                "name": f["name"],
                "sku": f["sku"],
                "days_until_stockout": days,
                "stockout_date": stockout_date.strftime("%Y-%m-%d"),
                "delivery_possible_by": delivery_date.strftime("%Y-%m-%d"),
                "will_have_gap": stockout_date < delivery_date,
                "gap_days": max(
                    (delivery_date - stockout_date).days, 0
                ),
                "current_stock": f["current_stock"],
                "weekly_rate": f["current_weekly_rate"],
            })

        timeline.sort(key=lambda t: t["days_until_stockout"])
        return timeline

    # ------------------------------------------------------------------
    # Design ranking
    # ------------------------------------------------------------------

    def _rank_designs(self, jersey_products: list[dict]) -> list[dict]:
        """Rank jersey designs by overall performance score.

        Factors:
          - Revenue contribution (40%)
          - Velocity trend (30%)
          - Recent demand (30%)
        """
        if not jersey_products:
            return []

        max_rev = max(v["total_revenue"] for v in jersey_products) or 1
        max_recent = max(v.get("recent_90d_qty", 0) for v in jersey_products) or 1

        ranked = []
        for v in jersey_products:
            rev_score = (v["total_revenue"] / max_rev) * 40
            trend_score = 0
            if v["direction"] == "accelerating":
                trend_score = 30
            elif v["direction"] == "stable":
                trend_score = 20
            elif v["direction"] == "decelerating":
                trend_score = 5

            recent_score = (v.get("recent_90d_qty", 0) / max_recent) * 30

            total_score = rev_score + trend_score + recent_score

            ranked.append({
                "name": v["name"],
                "sku": v.get("sku", ""),
                "pattern": v.get("pattern", ""),
                "color": v.get("color", ""),
                "score": round(total_score, 1),
                "total_revenue": v["total_revenue"],
                "recent_90d_qty": v.get("recent_90d_qty", 0),
                "direction": v["direction"],
                "stock_quantity": v["stock_quantity"],
                "verdict": (
                    "Star Design" if total_score >= 70
                    else "Solid Performer" if total_score >= 40
                    else "Under-performer" if total_score >= 15
                    else "Consider Dropping"
                ),
            })

        ranked.sort(key=lambda r: r["score"], reverse=True)
        return ranked

    # ------------------------------------------------------------------
    # Seasonal outlook
    # ------------------------------------------------------------------

    def _get_seasonal_outlook(self) -> dict:
        """Jersey-specific seasonal outlook for planning."""
        month = self._current_month
        current_factor = JERSEY_SEASONAL_FACTORS.get(month, 1.0)

        # Look ahead 3 months
        outlook_months = []
        for i in range(4):
            m = ((month - 1 + i) % 12) + 1
            factor = JERSEY_SEASONAL_FACTORS.get(m, 1.0)
            month_name = [
                "", "January", "February", "March", "April", "May",
                "June", "July", "August", "September", "October",
                "November", "December",
            ][m]
            outlook_months.append({
                "month": m,
                "month_name": month_name,
                "demand_factor": factor,
                "demand_level": (
                    "Peak" if factor >= 1.1
                    else "High" if factor >= 0.9
                    else "Moderate" if factor >= 0.7
                    else "Low"
                ),
            })

        # Overall advice
        upcoming_avg = sum(o["demand_factor"] for o in outlook_months[1:]) / 3
        if upcoming_avg >= 1.0:
            advice = (
                "Jersey demand is RISING over the next 3 months. "
                "Order generously — better to have extra stock than miss sales. "
                "This is your selling season."
            )
        elif upcoming_avg >= 0.7:
            advice = (
                "Jersey demand is MODERATE. Order to cover actual sales "
                "with a small buffer. Don't over-invest in new designs right now."
            )
        else:
            advice = (
                "Jersey demand is DECLINING into off-season. "
                "Minimize orders — only restock proven best-sellers. "
                "Focus remaining budget on seasonal alternatives."
            )

        return {
            "current_month_factor": current_factor,
            "outlook_months": outlook_months,
            "upcoming_avg_factor": round(upcoming_avg, 2),
            "advice": advice,
            "is_jersey_season": month in JERSEY_PEAK_MONTHS,
            "is_peak_season": month in JERSEY_HIGH_MONTHS,
        }

    # ------------------------------------------------------------------
    # Empty result
    # ------------------------------------------------------------------

    def _empty_forecast(self) -> dict:
        return {
            "generated_at": self._now.isoformat(),
            "total_jersey_products": 0,
            "lead_time_weeks": self.lead_time_weeks,
            "moq_per_design": self.moq,
            "summary": {
                "reorder_now_count": 0,
                "reorder_soon_count": 0,
                "well_stocked_count": 0,
                "overstock_count": 0,
                "total_reorder_qty": 0,
                "total_reorder_value": 0,
                "stockout_risk_products": 0,
            },
            "design_forecasts": [],
            "reorder_now": [],
            "reorder_soon": [],
            "hold": [],
            "reduce": [],
            "supplier_order": {
                "items": [],
                "total_units": 0,
                "total_estimated_cost": 0,
                "order_note": (
                    "No jersey products found. Check that products have the "
                    "'jersey / fast' attribute or 'jersey' in their category."
                ),
            },
            "stockout_timeline": [],
            "design_ranking": [],
            "seasonal_outlook": self._get_seasonal_outlook(),
        }
