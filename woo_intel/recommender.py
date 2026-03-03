"""Action Recommender — turns analysis into buy/hold/discount/cut decisions.

This is the "what should I actually DO?" module.  It takes the full analysis
from InventoryAnalyzer and produces prioritized recommendations with reasoning.

Recommendation types:
  - REORDER_NOW     — high velocity, low stock → buy aggressively
  - REORDER_SOON    — moderate velocity, stock running low
  - DISCOUNT_NOW    — dead stock, capital tied up → free the cash
  - DISCOUNT_LIGHT  — slowing but not dead → gentle markdown
  - HOLD            — stable performer, stock is fine
  - WATCH           — new or uncertain, needs more data
  - REMOVE          — never sold, zero potential, cut your losses
  - SEASONAL_HOLD   — slow now but season coming → keep and wait
  - PROMOTE         — good product, needs visibility/marketing push
"""

import logging
from datetime import datetime

from woo_intel.analyzer import (
    SEASONAL_FABRIC_PATTERNS,
    SEASONAL_COLOR_PATTERNS,
    NORDIC_SEASONAL_NOTES,
)

logger = logging.getLogger(__name__)


class ActionRecommender:
    """Generates prioritized recommendations from inventory analysis."""

    def __init__(self, analysis: dict):
        self.analysis = analysis
        self._now = datetime.utcnow()
        self._current_month = self._now.month
        self._next_month = (self._current_month % 12) + 1
        self._seasonal = SEASONAL_FABRIC_PATTERNS.get(
            self._current_month, ([], [], "")
        )
        self._next_seasonal = SEASONAL_FABRIC_PATTERNS.get(
            self._next_month, ([], [], "")
        )

    def generate_all(self) -> dict:
        """Generate all recommendation categories."""
        velocity = self.analysis.get("velocity", [])
        dead_stock = self.analysis.get("dead_stock", [])
        winners = self.analysis.get("winners", {})
        attributes = self.analysis.get("attributes", {})
        seasonal = self.analysis.get("seasonal", {})
        summary = self.analysis.get("summary", {})

        # Build per-product recommendations
        product_recs = self._classify_products(velocity, dead_stock, winners)

        # Build strategic recommendations
        strategic = self._build_strategic_recs(
            summary, attributes, seasonal, winners, dead_stock
        )

        # Build discount strategy
        discount_plan = self._build_discount_plan(dead_stock, velocity)

        # Build buying plan
        buying_plan = self._build_buying_plan(winners, attributes, seasonal)

        # Build marketing recommendations
        marketing = self._build_marketing_recs(winners, attributes, velocity)

        # Cash recovery plan
        cash_recovery = self._build_cash_recovery(dead_stock, summary)

        return {
            "generated_at": self._now.isoformat(),
            "product_recommendations": product_recs,
            "strategic": strategic,
            "discount_plan": discount_plan,
            "buying_plan": buying_plan,
            "marketing": marketing,
            "cash_recovery": cash_recovery,
            "priorities": self._build_priority_list(
                product_recs, strategic, cash_recovery
            ),
        }

    # ------------------------------------------------------------------
    # Per-product classification
    # ------------------------------------------------------------------

    def _classify_products(self, velocity, dead_stock, winners) -> list[dict]:
        """Assign an action to every product."""
        dead_ids = {d["product_id"] for d in dead_stock}
        reorder_ids = {
            r["product_id"] for r in winners.get("reorder_alerts", [])
        }
        rising_ids = {
            r["product_id"] for r in winners.get("rising_stars", [])
        }
        recs = []

        for v in velocity:
            pid = v["product_id"]
            rec = self._classify_single(v, pid in dead_ids, pid in reorder_ids,
                                         pid in rising_ids)
            recs.append(rec)

        # Sort: urgent actions first
        priority_order = {
            "REORDER_NOW": 0, "DISCOUNT_NOW": 1, "REMOVE": 2,
            "REORDER_SOON": 3, "PROMOTE": 4, "DISCOUNT_LIGHT": 5,
            "SEASONAL_HOLD": 6, "WATCH": 7, "HOLD": 8,
        }
        recs.sort(key=lambda r: priority_order.get(r["action"], 99))
        return recs

    def _classify_single(self, v: dict, is_dead: bool, needs_reorder: bool,
                          is_rising: bool) -> dict:
        """Classify a single product into an action bucket."""
        pid = v["product_id"]
        stock = v["stock_quantity"]
        qty_week = v["qty_per_week"]
        direction = v["direction"]
        days_since = v["days_since_last_sale"]
        total_sold = v["total_sold"]
        fabric = (v.get("fabric_type") or "").lower()
        color = (v.get("color") or "").lower()
        name = v["name"]

        # Check if upcoming season favors this fabric OR color
        next_high = self._next_seasonal[0]
        is_upcoming_fabric = any(h in fabric for h in next_high) if fabric else False
        next_high_colors = SEASONAL_COLOR_PATTERNS.get(self._next_month, ([], []))[0]
        is_upcoming_color = any(
            hc in color or color in hc for hc in next_high_colors
        ) if color else False
        is_upcoming_season = is_upcoming_fabric or is_upcoming_color

        current_low = self._seasonal[1]
        is_off_season_fabric = any(h in fabric for h in current_low) if fabric else False
        current_low_colors = SEASONAL_COLOR_PATTERNS.get(self._current_month, ([], []))[1]
        is_off_season_color = any(
            lc in color or color in lc for lc in current_low_colors
        ) if color else False
        is_off_season = is_off_season_fabric or is_off_season_color

        # Decision tree
        if needs_reorder and direction in ("accelerating", "stable"):
            weeks_left = stock / qty_week if qty_week > 0 else 999
            action = "REORDER_NOW"
            reason = (
                f"Selling {qty_week:.1f}/week, only {weeks_left:.0f} weeks of "
                f"stock left. Buy aggressively — this is a proven winner."
            )
        elif is_rising and stock > 0:
            action = "REORDER_SOON"
            reason = (
                f"Rising star — velocity up {v['velocity_change']:.0%}. "
                f"Watch next 2 weeks and reorder if trend continues."
            )
        elif total_sold == 0 and stock > 0:
            if is_upcoming_season:
                action = "SEASONAL_HOLD"
                reason = (
                    f"Never sold, but {fabric} demand rises next month. "
                    f"Hold until season, then discount if still no sales."
                )
            else:
                created_days = days_since  # days_since_last_sale = days since created
                if created_days > 120:
                    action = "REMOVE"
                    reason = (
                        f"Listed for {created_days} days with zero sales. "
                        f"Remove or deep discount (70%+ off) to recover any value."
                    )
                elif created_days > 60:
                    action = "DISCOUNT_NOW"
                    reason = (
                        f"No sales in {created_days} days. "
                        f"Discount 30-50% to test price sensitivity."
                    )
                else:
                    action = "WATCH"
                    reason = f"New listing ({created_days} days). Give it time."

        elif is_dead and stock > 0:
            if is_off_season and is_upcoming_season:
                action = "SEASONAL_HOLD"
                reason = (
                    f"Currently off-season for {fabric}. "
                    f"Demand expected to return. Hold and promote when season turns."
                )
            elif is_off_season:
                action = "DISCOUNT_LIGHT"
                reason = (
                    f"Off-season slow period. Light discount (15-25%) to "
                    f"maintain visibility without destroying margin."
                )
            elif days_since > 120:
                action = "DISCOUNT_NOW"
                reason = (
                    f"No sales in {days_since} days. "
                    f"Discount 30-50% to free up {v['price'] * stock:.0f} in capital."
                )
            else:
                action = "DISCOUNT_LIGHT"
                reason = (
                    f"Slowing down — {days_since} days since last sale. "
                    f"Try 15-25% discount or bundle with winners."
                )

        elif direction == "decelerating" and stock > 0:
            action = "WATCH"
            reason = (
                f"Sales slowing ({v['velocity_change']:.0%} change). "
                f"Don't reorder. Let current stock sell through."
            )

        elif direction == "accelerating" and stock > 5:
            action = "PROMOTE"
            reason = (
                f"Sales accelerating! Push this in marketing — "
                f"feature in email, social, homepage."
            )

        elif direction == "stable" and qty_week >= 0.5:
            action = "HOLD"
            reason = (
                f"Steady performer at {qty_week:.1f}/week. "
                f"Keep stocked, no action needed."
            )

        else:
            action = "WATCH"
            reason = "Moderate activity. Monitor and reassess next week."

        return {
            "product_id": pid,
            "name": name,
            "sku": v.get("sku", ""),
            "action": action,
            "reason": reason,
            "price": v["price"],
            "stock_quantity": stock,
            "qty_per_week": qty_week,
            "total_sold": total_sold,
            "days_since_last_sale": days_since,
            "direction": direction,
            "categories": v.get("categories", []),
            "color": v.get("color", ""),
            "pattern": v.get("pattern", ""),
            "fabric_type": v.get("fabric_type", ""),
        }

    # ------------------------------------------------------------------
    # Strategic Recommendations
    # ------------------------------------------------------------------

    def _build_strategic_recs(self, summary, attributes, seasonal,
                               winners, dead_stock) -> list[dict]:
        """High-level business strategy recommendations."""
        recs = []
        total_inv = summary.get("total_inventory_value", 0)
        dead_capital = summary.get("dead_stock_capital", 0)
        dead_ratio = summary.get("dead_stock_ratio", 0)

        # Dead stock alarm
        if dead_ratio > 0.3:
            recs.append({
                "priority": "critical",
                "title": "Dead Stock Emergency",
                "detail": (
                    f"{dead_ratio:.0%} of your inventory value "
                    f"({dead_capital:,.0f}) is tied up in dead stock. "
                    f"Run a clearance event to recover cash."
                ),
                "action": (
                    "Create a 'Warehouse Sale' collection with all dead stock "
                    "at 40-60% off. Promote via email + social. "
                    "Goal: recover at least 50% of dead capital this month."
                ),
            })
        elif dead_ratio > 0.15:
            recs.append({
                "priority": "warning",
                "title": "Dead Stock Cleanup Needed",
                "detail": (
                    f"{dead_ratio:.0%} of inventory is slow-moving "
                    f"({dead_capital:,.0f} tied up). "
                    f"Time for a focused markdown strategy."
                ),
                "action": "Discount dead stock 25-40%. Bundle slow movers with winners.",
            })

        # Winning color/pattern insight
        colors = attributes.get("colors", [])
        if colors:
            top_color = colors[0]
            worst_colors = [c for c in colors if c["total_revenue"] == 0]
            recs.append({
                "priority": "insight",
                "title": f"Best-selling color: {top_color['name']}",
                "detail": (
                    f"'{top_color['name']}' generated {top_color['total_revenue']:,.0f} "
                    f"across {top_color['product_count']} products. "
                ),
                "action": (
                    f"Stock more {top_color['name']} variants. "
                    + (f"Consider dropping: {', '.join(c['name'] for c in worst_colors[:3])}"
                       if worst_colors else "All colors selling.")
                ),
            })

        patterns = attributes.get("patterns", [])
        if patterns:
            top_pattern = patterns[0]
            recs.append({
                "priority": "insight",
                "title": f"Best-selling pattern: {top_pattern['name']}",
                "detail": (
                    f"'{top_pattern['name']}' is your strongest pattern at "
                    f"{top_pattern['total_revenue']:,.0f} revenue."
                ),
                "action": f"Design new colorways in '{top_pattern['name']}' style.",
            })

        # Reorder urgency
        reorder_alerts = winners.get("reorder_alerts", [])
        critical_reorders = [r for r in reorder_alerts if r.get("urgency") == "critical"]
        if critical_reorders:
            names = [r["name"][:30] for r in critical_reorders[:3]]
            recs.append({
                "priority": "critical",
                "title": f"{len(critical_reorders)} products critically low on stock",
                "detail": f"Running out within 2 weeks: {', '.join(names)}",
                "action": "Place reorder TODAY for these SKUs.",
            })

        # Seasonal prep
        next_high = self._next_seasonal[0]
        next_note = self._next_seasonal[2]
        if next_high:
            recs.append({
                "priority": "planning",
                "title": f"Next month prep: {', '.join(next_high[:4])}",
                "detail": next_note,
                "action": (
                    f"Ensure you have stock in: {', '.join(next_high)}. "
                    f"Start marketing these categories now."
                ),
            })

        # Nordic market note
        nordic = NORDIC_SEASONAL_NOTES.get(self._current_month, "")
        if nordic:
            recs.append({
                "priority": "planning",
                "title": "Nordic Market Note",
                "detail": nordic,
                "action": "Adjust marketing and stock for Nordic seasonal preferences.",
            })

        return recs

    # ------------------------------------------------------------------
    # Discount Plan
    # ------------------------------------------------------------------

    def _build_discount_plan(self, dead_stock, velocity) -> dict:
        """Specific discount recommendations with amounts."""
        tiers = {
            "deep_discount": [],   # 50-70% off — never sold or 180+ days
            "medium_discount": [], # 25-40% off — stale 90-180 days
            "light_discount": [],  # 10-20% off — slowing
            "bundle_candidates": [],  # bundle with winners instead of discounting
        }

        for d in dead_stock:
            capital = d["capital_tied"]
            if capital <= 0:
                continue

            if d["severity"] == "critical" and d["sale_count"] == 0:
                tiers["deep_discount"].append({
                    "name": d["name"],
                    "sku": d.get("sku", ""),
                    "current_price": d["price"],
                    "suggested_discount": "50-70%",
                    "suggested_price": round(d["price"] * 0.4, 2),
                    "capital_at_stake": capital,
                    "reason": "Never sold — recover any value possible",
                })
            elif d["severity"] == "critical":
                tiers["medium_discount"].append({
                    "name": d["name"],
                    "sku": d.get("sku", ""),
                    "current_price": d["price"],
                    "suggested_discount": "30-40%",
                    "suggested_price": round(d["price"] * 0.65, 2),
                    "capital_at_stake": capital,
                    "reason": f"No sales in {d['days_since_last_sale']} days",
                })
            elif d["severity"] == "warning":
                tiers["light_discount"].append({
                    "name": d["name"],
                    "sku": d.get("sku", ""),
                    "current_price": d["price"],
                    "suggested_discount": "15-25%",
                    "suggested_price": round(d["price"] * 0.8, 2),
                    "capital_at_stake": capital,
                    "reason": f"Slow — {d['days_since_last_sale']} days since sale",
                })
            elif d["severity"] == "seasonal":
                tiers["bundle_candidates"].append({
                    "name": d["name"],
                    "sku": d.get("sku", ""),
                    "current_price": d["price"],
                    "capital_at_stake": capital,
                    "reason": "Seasonal dip — bundle don't discount",
                })

        total_recoverable = sum(
            item["capital_at_stake"]
            for tier in tiers.values()
            for item in tier
        )

        return {
            **tiers,
            "total_recoverable_capital": round(total_recoverable, 2),
            "summary": (
                f"{len(tiers['deep_discount'])} products need deep discounts, "
                f"{len(tiers['medium_discount'])} medium, "
                f"{len(tiers['light_discount'])} light. "
                f"Total capital to recover: {total_recoverable:,.0f}"
            ),
        }

    # ------------------------------------------------------------------
    # Buying Plan
    # ------------------------------------------------------------------

    def _build_buying_plan(self, winners, attributes, seasonal) -> dict:
        """What to buy and how aggressively."""
        reorder = winners.get("reorder_alerts", [])
        rising = winners.get("rising_stars", [])
        top = winners.get("top_by_revenue", [])

        # Reorders with quantities
        reorder_list = []
        for r in reorder:
            reorder_list.append({
                "name": r["name"],
                "sku": r.get("sku", ""),
                "current_stock": r["stock_quantity"],
                "weeks_left": r.get("weeks_of_stock", 0),
                "suggested_quantity": r.get("suggested_reorder", 0),
                "weekly_velocity": r["qty_per_week"],
                "urgency": r.get("urgency", "soon"),
            })

        # What to buy MORE of (based on attribute winners)
        buy_more = []
        for attr_type, items in attributes.items():
            if not items:
                continue
            top_item = items[0]
            if top_item["dominant_direction"] in ("accelerating", "stable"):
                buy_more.append({
                    "type": attr_type.rstrip("s"),  # "color" not "colors"
                    "name": top_item["name"],
                    "revenue": top_item["total_revenue"],
                    "direction": top_item["dominant_direction"],
                    "reason": f"Top {attr_type.rstrip('s')} by revenue, demand is {top_item['dominant_direction']}",
                })

        # What NOT to buy
        avoid = []
        for attr_type, items in attributes.items():
            for item in items:
                if (item["total_revenue"] == 0 and item["product_count"] >= 2):
                    avoid.append({
                        "type": attr_type.rstrip("s"),
                        "name": item["name"],
                        "products_listed": item["product_count"],
                        "reason": f"Zero revenue across {item['product_count']} products",
                    })

        return {
            "reorder_now": reorder_list,
            "buy_more_of": buy_more,
            "avoid_buying": avoid,
            "seasonal_prep": {
                "stock_up": self._next_seasonal[0],
                "reduce": self._next_seasonal[1],
                "note": self._next_seasonal[2],
            },
        }

    # ------------------------------------------------------------------
    # Marketing Recommendations
    # ------------------------------------------------------------------

    def _build_marketing_recs(self, winners, attributes, velocity) -> list[dict]:
        """What to feature in marketing campaigns."""
        recs = []

        # Feature rising stars
        for star in winners.get("rising_stars", [])[:5]:
            recs.append({
                "type": "feature_product",
                "name": star["name"],
                "reason": (
                    f"Sales up {star['velocity_change']:.0%} — "
                    f"ride the momentum with a campaign"
                ),
                "suggested_action": "Feature in email, social post, homepage banner",
            })

        # Promote top performers to new audiences
        for top in winners.get("top_by_revenue", [])[:3]:
            recs.append({
                "type": "scale_winner",
                "name": top["name"],
                "reason": (
                    f"Top seller at {top['rev_per_week']:.0f}/week — "
                    f"expand reach to new markets"
                ),
                "suggested_action": (
                    "List on additional channels (Etsy if not already), "
                    "run targeted ads, create a Pinterest pin"
                ),
            })

        # Color campaign
        colors = attributes.get("colors", [])
        if colors and colors[0]["total_revenue"] > 0:
            recs.append({
                "type": "color_campaign",
                "name": colors[0]["name"],
                "reason": f"Best-selling color with {colors[0]['total_revenue']:,.0f} revenue",
                "suggested_action": (
                    f"Create a '{colors[0]['name']}' collection page, "
                    f"feature in newsletter"
                ),
            })

        return recs

    # ------------------------------------------------------------------
    # Cash Recovery
    # ------------------------------------------------------------------

    def _build_cash_recovery(self, dead_stock, summary) -> dict:
        """How to recover cash from dead inventory."""
        dead_capital = summary.get("dead_stock_capital", 0)
        total_inv = summary.get("total_inventory_value", 0)

        strategies = []

        # Clearance sale
        never_sold = [d for d in dead_stock if d["sale_count"] == 0]
        if never_sold:
            capital = sum(d["capital_tied"] for d in never_sold)
            strategies.append({
                "strategy": "Clearance: Never-sold items",
                "products": len(never_sold),
                "capital_locked": round(capital, 2),
                "expected_recovery": round(capital * 0.35, 2),
                "action": (
                    f"Bundle {len(never_sold)} never-sold items in a "
                    f"'Mystery Box' or 'Surprise Bundle' at 60% off. "
                    f"Recover ~{capital * 0.35:,.0f}."
                ),
            })

        # Stale but previously sold
        stale_sellers = [
            d for d in dead_stock
            if d["sale_count"] > 0 and d["days_since_last_sale"] > 90
        ]
        if stale_sellers:
            capital = sum(d["capital_tied"] for d in stale_sellers)
            strategies.append({
                "strategy": "Markdown: Stale ex-sellers",
                "products": len(stale_sellers),
                "capital_locked": round(capital, 2),
                "expected_recovery": round(capital * 0.55, 2),
                "action": (
                    f"Markdown {len(stale_sellers)} stale products by 30-40%. "
                    f"These sold before — price is the barrier. "
                    f"Expected recovery: ~{capital * 0.55:,.0f}."
                ),
            })

        # Seasonal holds
        seasonal_holds = [d for d in dead_stock if d.get("is_seasonal_dip")]
        if seasonal_holds:
            capital = sum(d["capital_tied"] for d in seasonal_holds)
            strategies.append({
                "strategy": "Seasonal Hold (no action needed)",
                "products": len(seasonal_holds),
                "capital_locked": round(capital, 2),
                "expected_recovery": round(capital * 0.85, 2),
                "action": (
                    f"Hold {len(seasonal_holds)} seasonal items. "
                    f"Demand expected to return. Don't discount these."
                ),
            })

        total_expected = sum(s["expected_recovery"] for s in strategies)

        return {
            "dead_capital": round(dead_capital, 2),
            "total_inventory": round(total_inv, 2),
            "dead_ratio_pct": round(
                (dead_capital / total_inv * 100) if total_inv else 0, 1
            ),
            "strategies": strategies,
            "total_expected_recovery": round(total_expected, 2),
            "net_loss_estimate": round(dead_capital - total_expected, 2),
        }

    # ------------------------------------------------------------------
    # Priority List
    # ------------------------------------------------------------------

    def _build_priority_list(self, product_recs, strategic, cash_recovery) -> list[dict]:
        """Top 10 things to do THIS WEEK, ranked by impact."""
        priorities = []

        # From strategic recs
        for s in strategic:
            if s["priority"] == "critical":
                priorities.append({
                    "rank": 0,
                    "urgency": "today",
                    "title": s["title"],
                    "action": s["action"],
                    "impact": "high",
                })
            elif s["priority"] == "warning":
                priorities.append({
                    "rank": 1,
                    "urgency": "this_week",
                    "title": s["title"],
                    "action": s["action"],
                    "impact": "medium",
                })

        # Reorder urgencies
        reorders = [r for r in product_recs if r["action"] == "REORDER_NOW"]
        if reorders:
            priorities.append({
                "rank": 0,
                "urgency": "today",
                "title": f"Reorder {len(reorders)} products running out",
                "action": (
                    "Place orders for: "
                    + ", ".join(r["name"][:25] for r in reorders[:5])
                ),
                "impact": "high",
            })

        # Cash recovery
        if cash_recovery.get("dead_ratio_pct", 0) > 20:
            priorities.append({
                "rank": 0,
                "urgency": "this_week",
                "title": (
                    f"Recover {cash_recovery['total_expected_recovery']:,.0f} "
                    f"from dead stock"
                ),
                "action": (
                    "Launch clearance sale on dead inventory. "
                    "See discount plan for details."
                ),
                "impact": "high",
            })

        # Sort by rank then urgency
        priorities.sort(key=lambda p: (p["rank"], p["urgency"] != "today"))
        return priorities[:10]
