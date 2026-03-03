"""Smart Intelligence Engine.

Cross-references WooCommerce inventory data with e-conomic financial data
to produce actionable intelligence that neither system can provide alone.

Core modules:
  1. CATEGORY TRENDS   — monthly revenue per category, growth direction, momentum
  2. DEAD CATEGORIES   — categories with zero or near-zero sales to consider dropping
  3. SMART REMOVE      — multi-signal scoring for products to cut from inventory
  4. SMART KEEP        — products worth keeping despite slow current sales
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from woo_intel.analyzer import SEASONAL_FABRIC_PATTERNS, NORDIC_SEASONAL_NOTES

logger = logging.getLogger(__name__)


class SmartAnalyzer:
    """Produces cross-system intelligence from WooCommerce + e-conomic data."""

    def __init__(self, woo_analysis: dict, eco_analysis: dict = None):
        self.woo = woo_analysis or {}
        self.eco = eco_analysis
        self._now = datetime.utcnow()
        self._current_month = self._now.month
        self._next_month = (self._current_month % 12) + 1

        # Pre-index velocity by product_id for fast lookup
        self._velocity_by_id = {
            v["product_id"]: v
            for v in self.woo.get("velocity", [])
        }

    def analyze(self) -> dict:
        """Run all smart intelligence modules."""
        logger.info("Running Smart Intelligence analysis...")

        category_trends = self.get_category_trends()
        dead_categories = self.get_dead_categories(category_trends)
        smart_remove = self.get_smart_remove(category_trends)
        smart_keep = self.get_smart_keep(category_trends)

        # Deduplicate: if a product is in both lists, keep it only in the
        # list where its score is higher, so the user gets clear direction.
        remove_by_id = {r["product_id"]: r for r in smart_remove}
        keep_by_id = {k["product_id"]: k for k in smart_keep}
        overlap_ids = set(remove_by_id.keys()) & set(keep_by_id.keys())
        for pid in overlap_ids:
            if remove_by_id[pid]["remove_score"] >= keep_by_id[pid]["keep_score"]:
                smart_keep = [k for k in smart_keep if k["product_id"] != pid]
            else:
                smart_remove = [r for r in smart_remove if r["product_id"] != pid]

        # Build executive summary
        summary = self._build_summary(
            category_trends, dead_categories, smart_remove, smart_keep,
        )

        result = {
            "generated_at": self._now.isoformat(),
            "summary": summary,
            "category_trends": category_trends,
            "dead_categories": dead_categories,
            "smart_remove": smart_remove,
            "smart_keep": smart_keep,
        }

        logger.info(
            "Smart Intelligence: %d category trends, %d dead categories, "
            "%d remove candidates, %d keep candidates",
            len(category_trends), len(dead_categories),
            len(smart_remove), len(smart_keep),
        )
        return result

    # ------------------------------------------------------------------
    # 1. Category Trends
    # ------------------------------------------------------------------

    def get_category_trends(self) -> list[dict]:
        """Monthly revenue per category with growth direction and momentum.

        Uses monthly_categories from InventoryAnalyzer and enriches with
        trend direction, growth rate, and seasonal context.
        """
        monthly_cats = self.woo.get("monthly_categories", {})
        cat_perf = {
            c["category"]: c
            for c in self.woo.get("categories", [])
        }

        results = []

        # Process categories that have monthly sales data
        seen = set()
        for cat_name, months in monthly_cats.items():
            if not months:
                continue
            seen.add(cat_name)

            perf = cat_perf.get(cat_name, {})
            total_rev = perf.get("total_revenue", 0)
            product_count = perf.get("product_count", 0)
            dead_ratio = perf.get("dead_ratio", 0)

            growth_pct, direction, momentum = self._compute_trend(months)

            monthly_series = [
                {"month": m["month"], "revenue": m["revenue"]}
                for m in months
            ]

            seasonal_note = self._category_seasonal_note(cat_name)

            results.append({
                "category": cat_name,
                "total_revenue": round(total_rev, 2),
                "product_count": product_count,
                "dead_ratio": dead_ratio,
                "active_products": perf.get("active_products", 0),
                "dead_products": perf.get("dead_products", 0),
                "growth_pct": round(growth_pct, 1),
                "direction": direction,
                "momentum": momentum,
                "monthly": monthly_series,
                "months_with_sales": len([m for m in months if m["revenue"] > 0]),
                "seasonal_note": seasonal_note,
            })

        # Include zero-sales categories (they have no monthly data)
        for cat_name, perf in cat_perf.items():
            if cat_name in seen:
                continue
            if perf.get("product_count", 0) == 0:
                continue
            results.append({
                "category": cat_name,
                "total_revenue": 0,
                "product_count": perf.get("product_count", 0),
                "dead_ratio": perf.get("dead_ratio", 1.0),
                "active_products": perf.get("active_products", 0),
                "dead_products": perf.get("dead_products", 0),
                "growth_pct": 0,
                "direction": "dead",
                "momentum": "flat",
                "monthly": [],
                "months_with_sales": 0,
                "seasonal_note": self._category_seasonal_note(cat_name),
            })

        results.sort(key=lambda r: r["total_revenue"], reverse=True)
        return results

    def _compute_trend(self, months: list[dict]) -> tuple[float, str, str]:
        """Compute growth %, direction, and momentum from monthly series.

        Returns (growth_pct, direction, momentum) where:
        - growth_pct: recent 3 months vs prior 3 months percentage change
        - direction: 'growing' | 'stable' | 'declining' | 'new' | 'dead'
        - momentum: 'accelerating' | 'steady' | 'decelerating' | 'flat'
        """
        if not months:
            return 0.0, "dead", "flat"

        revenues = [m["revenue"] for m in months]

        # Not enough history for trend analysis
        if len(revenues) < 2:
            if revenues[0] > 0:
                return 0.0, "new", "flat"
            return 0.0, "dead", "flat"

        # Split into halves for trend comparison
        mid = len(revenues) // 2
        recent = revenues[mid:]
        older = revenues[:mid]

        recent_avg = sum(recent) / len(recent) if recent else 0
        older_avg = sum(older) / len(older) if older else 0

        # Growth percentage
        if older_avg > 0:
            growth_pct = ((recent_avg - older_avg) / older_avg) * 100
        elif recent_avg > 0:
            growth_pct = 100.0  # went from 0 to something
        else:
            growth_pct = 0.0

        # Direction
        if sum(revenues) == 0:
            direction = "dead"
        elif growth_pct > 20:
            direction = "growing"
        elif growth_pct < -20:
            direction = "declining"
        else:
            direction = "stable"

        # Momentum: compare last month vs 2nd-to-last
        if len(revenues) >= 3:
            last = revenues[-1]
            second_last = revenues[-2]
            third_last = revenues[-3]
            if last > second_last > third_last:
                momentum = "accelerating"
            elif last < second_last < third_last:
                momentum = "decelerating"
            elif last > second_last:
                momentum = "steady"
            else:
                momentum = "steady"
        else:
            momentum = "flat"

        return growth_pct, direction, momentum

    def _category_seasonal_note(self, cat_name: str) -> str:
        """Check if a category name matches seasonal fabric patterns."""
        cat_lower = cat_name.lower()
        current = SEASONAL_FABRIC_PATTERNS.get(self._current_month, ([], [], ""))
        next_m = SEASONAL_FABRIC_PATTERNS.get(self._next_month, ([], [], ""))

        for high in current[0]:
            if high in cat_lower:
                return f"In-season now — {high} is high-demand this month"
        for low in current[1]:
            if low in cat_lower:
                # Check if next month is better
                for nh in next_m[0]:
                    if nh in cat_lower:
                        return f"Off-season now, but demand returns next month"
                return f"Off-season — {low} demand is low this month"
        return ""

    # ------------------------------------------------------------------
    # 2. Dead Categories
    # ------------------------------------------------------------------

    def get_dead_categories(self, category_trends: list[dict] = None) -> list[dict]:
        """Categories with zero or near-zero sales that should be reviewed.

        A category is "dead" if it meets ANY of:
        - Zero total revenue
        - Dead ratio > 60% (most products never sold)
        - Declining direction with revenue below category average
        """
        if category_trends is None:
            category_trends = self.get_category_trends()

        if not category_trends:
            return []

        # Average revenue per category for comparison
        all_revenues = [c["total_revenue"] for c in category_trends if c["total_revenue"] > 0]
        avg_rev = sum(all_revenues) / len(all_revenues) if all_revenues else 0

        dead = []
        for cat in category_trends:
            reasons = []
            severity = "info"

            if cat["total_revenue"] == 0:
                reasons.append("Zero revenue — no products in this category have ever sold")
                severity = "critical"
            elif cat["dead_ratio"] > 0.6:
                pct = int(cat["dead_ratio"] * 100)
                reasons.append(
                    f"{pct}% of products never sold — category is mostly dead weight"
                )
                severity = "critical" if cat["dead_ratio"] > 0.8 else "warning"
            elif cat["direction"] == "declining" and cat["total_revenue"] < avg_rev * 0.3:
                reasons.append(
                    f"Revenue declining and well below average "
                    f"({cat['total_revenue']:,.0f} vs avg {avg_rev:,.0f})"
                )
                severity = "warning"
            else:
                continue  # Not dead

            # Check seasonal context — don't flag seasonal dips as dead
            if cat["seasonal_note"] and "off-season" in cat["seasonal_note"].lower():
                severity = "seasonal"
                reasons.append(cat["seasonal_note"])

            # Capital tied up in this category
            capital = self._category_capital(cat["category"])

            dead.append({
                "category": cat["category"],
                "total_revenue": cat["total_revenue"],
                "product_count": cat["product_count"],
                "dead_ratio": cat["dead_ratio"],
                "active_products": cat["active_products"],
                "dead_products": cat["dead_products"],
                "direction": cat["direction"],
                "severity": severity,
                "reasons": reasons,
                "capital_tied": round(capital, 2),
                "recommendation": self._dead_category_action(cat, severity, capital),
            })

        # Sort: critical first, then by capital tied
        severity_order = {"critical": 0, "warning": 1, "seasonal": 2, "info": 3}
        dead.sort(key=lambda d: (severity_order.get(d["severity"], 9), -d["capital_tied"]))
        return dead

    def _category_capital(self, category_name: str) -> float:
        """Sum of price * stock_quantity for all products in a category."""
        total = 0
        for v in self.woo.get("velocity", []):
            if category_name in v.get("categories", []):
                total += v["price"] * v["stock_quantity"]
        return total

    def _dead_category_action(self, cat: dict, severity: str, capital: float) -> str:
        """Generate actionable recommendation for a dead category."""
        if severity == "seasonal":
            return (
                f"Hold — this is a seasonal dip. Keep products but don't reorder. "
                f"Promote when season returns."
            )
        if severity == "critical" and cat["total_revenue"] == 0:
            return (
                f"Remove all {cat['product_count']} products or run a deep clearance "
                f"(60-70% off) to recover the {capital:,.0f} tied up. "
                f"Stop ordering in this category entirely."
            )
        if severity == "critical":
            return (
                f"Run clearance sale on {cat['dead_products']} dead products. "
                f"Keep only the {cat['active_products']} that actually sell. "
                f"Don't reorder dead items."
            )
        return (
            f"Review this category — revenue is declining. "
            f"Consider reducing to only proven sellers and clearing the rest."
        )

    # ------------------------------------------------------------------
    # 3. Smart Remove
    # ------------------------------------------------------------------

    def get_smart_remove(self, category_trends: list[dict] = None) -> list[dict]:
        """Multi-signal scoring for products that should be removed.

        Each product gets a remove_score (0-100) based on weighted signals:
        - Staleness (25%):   days since last sale
        - Velocity (20%):    how slow it's selling
        - Capital drag (20%): money tied up relative to velocity
        - Category health (15%): is the category dying?
        - Seasonal fit (10%): does upcoming season favor this product?
        - History (10%):     has it EVER sold decently?

        Products with remove_score > 60 appear here (unless keep_score is higher).
        """
        if category_trends is None:
            category_trends = self.get_category_trends()

        # Pre-index category health
        cat_health = {}
        for ct in category_trends:
            cat_health[ct["category"]] = {
                "direction": ct["direction"],
                "dead_ratio": ct["dead_ratio"],
                "growth_pct": ct["growth_pct"],
            }

        velocity = self.woo.get("velocity", [])
        if not velocity:
            return []

        # Compute max values for normalization
        max_days = max((v["days_since_last_sale"] for v in velocity), default=1) or 1
        max_capital = max(
            (v["price"] * v["stock_quantity"] for v in velocity
             if v["stock_quantity"] > 0),
            default=1,
        ) or 1

        candidates = []
        for v in velocity:
            stock = v["stock_quantity"]
            if stock <= 0:
                continue  # Out of stock — nothing to remove

            # Signal 1: Staleness (0-100)
            staleness = min(v["days_since_last_sale"] / max_days, 1.0) * 100

            # Signal 2: Velocity — inverse (low velocity = high remove signal)
            if v["qty_per_week"] <= 0:
                velocity_signal = 100
            elif v["qty_per_week"] < 0.5:
                velocity_signal = 80
            elif v["qty_per_week"] < 1.0:
                velocity_signal = 50
            else:
                velocity_signal = max(0, 30 - v["qty_per_week"] * 5)

            # Signal 3: Capital drag — how much money is stuck
            capital = v["price"] * stock
            capital_signal = min(capital / max_capital, 1.0) * 100

            # Signal 4: Category health
            cat_signal = 0
            for cat in v.get("categories", []):
                ch = cat_health.get(cat, {})
                if ch.get("direction") == "declining":
                    cat_signal = max(cat_signal, 80)
                elif ch.get("dead_ratio", 0) > 0.5:
                    cat_signal = max(cat_signal, 70)
                elif ch.get("direction") == "stable":
                    cat_signal = max(cat_signal, 30)
                elif ch.get("direction") == "growing":
                    cat_signal = max(cat_signal, 0)

            # Signal 5: Seasonal fit (reduces remove score if season is coming)
            seasonal_signal = self._seasonal_remove_signal(v)

            # Signal 6: History — has it ever sold well?
            if v["total_sold"] == 0:
                history_signal = 100
            elif v["total_sold"] < 3:
                history_signal = 70
            elif v["total_sold"] < 10:
                history_signal = 40
            else:
                history_signal = max(0, 20 - v["total_sold"])

            # Weighted composite score
            remove_score = (
                0.25 * staleness +
                0.20 * velocity_signal +
                0.20 * capital_signal +
                0.15 * cat_signal +
                0.10 * seasonal_signal +
                0.10 * history_signal
            )

            if remove_score < 50:
                continue  # Not a removal candidate

            # Build reasoning
            reasons = self._remove_reasons(
                v, staleness, velocity_signal, capital_signal,
                cat_signal, seasonal_signal, history_signal, capital,
            )

            candidates.append({
                "product_id": v["product_id"],
                "name": v["name"],
                "sku": v.get("sku", ""),
                "price": v["price"],
                "stock_quantity": stock,
                "capital_tied": round(capital, 2),
                "categories": v.get("categories", []),
                "color": v.get("color", ""),
                "fabric_type": v.get("fabric_type", ""),
                "total_sold": v["total_sold"],
                "days_since_last_sale": v["days_since_last_sale"],
                "qty_per_week": v["qty_per_week"],
                "direction": v["direction"],
                "remove_score": round(remove_score, 1),
                "reasons": reasons,
                "action": self._remove_action(remove_score, v, capital),
                "signals": {
                    "staleness": round(staleness, 1),
                    "velocity": round(velocity_signal, 1),
                    "capital_drag": round(capital_signal, 1),
                    "category_health": round(cat_signal, 1),
                    "seasonal_fit": round(seasonal_signal, 1),
                    "history": round(history_signal, 1),
                },
            })

        candidates.sort(key=lambda c: -c["remove_score"])
        return candidates

    def _seasonal_remove_signal(self, v: dict) -> float:
        """0 = keep (good season ahead), 100 = remove (no seasonal hope)."""
        fabric = (v.get("fabric_type") or "").lower()
        if not fabric:
            return 50  # unknown — neutral

        next_high = SEASONAL_FABRIC_PATTERNS.get(self._next_month, ([], [], ""))[0]
        current_low = SEASONAL_FABRIC_PATTERNS.get(self._current_month, ([], [], ""))[1]

        # If upcoming season favors this fabric, reduce remove signal
        for h in next_high:
            if h in fabric:
                return 10  # season is coming — don't remove

        # If currently low-demand and next month isn't better
        for low in current_low:
            if low in fabric:
                return 70  # off-season, no relief coming

        return 50  # neutral

    def _remove_reasons(self, v, staleness, velocity_sig, capital_sig,
                        cat_sig, seasonal_sig, history_sig, capital) -> list[str]:
        """Human-readable reasons for removal, ordered by signal strength."""
        reasons = []
        signals = [
            (staleness, f"No sales in {v['days_since_last_sale']} days"),
            (velocity_sig, f"Very low velocity ({v['qty_per_week']:.2f}/week)"),
            (capital_sig, f"{capital:,.0f} of capital tied up"),
            (cat_sig, f"Category is {'declining' if cat_sig > 60 else 'underperforming'}"),
            (seasonal_sig, "No upcoming seasonal demand boost" if seasonal_sig > 60 else None),
            (history_sig, f"Only {v['total_sold']} units ever sold" if v['total_sold'] < 5 else None),
        ]
        for score, reason in sorted(signals, key=lambda s: -s[0]):
            if score >= 50 and reason:
                reasons.append(reason)
        return reasons[:4]

    def _remove_action(self, score: float, v: dict, capital: float) -> str:
        """Specific action recommendation based on remove score."""
        if score >= 80:
            if v["total_sold"] == 0:
                return (
                    f"Remove immediately. Never sold — deep discount (70% off) "
                    f"or donate to clear {capital:,.0f} in dead capital."
                )
            return (
                f"Clear out — discount 50-60% to recover what you can "
                f"of the {capital:,.0f} tied up. Do not reorder."
            )
        if score >= 65:
            return (
                f"Discount 30-40% for 2 weeks. If no sales, move to removal. "
                f"Capital at risk: {capital:,.0f}."
            )
        return (
            f"Put on watch list. Light discount (15-20%) to test demand. "
            f"Reassess in 30 days."
        )

    # ------------------------------------------------------------------
    # 4. Smart Keep
    # ------------------------------------------------------------------

    def get_smart_keep(self, category_trends: list[dict] = None) -> list[dict]:
        """Products worth keeping despite slow current sales.

        Identifies products that might LOOK dead but should be kept because:
        - Seasonal returner: sold well in its season historically
        - Growing category: the category is trending up
        - High margin: expensive product with decent history (if eco data)
        - Consistent performer: slow but steady, never zero months
        - Upcoming season: fabric type matches next month's demand

        Each product gets a keep_score (0-100). Products appear here only if
        they're currently slow (in dead_stock or low velocity) but have a
        keep_score > 50.
        """
        if category_trends is None:
            category_trends = self.get_category_trends()

        # Pre-index
        cat_health = {}
        for ct in category_trends:
            cat_health[ct["category"]] = {
                "direction": ct["direction"],
                "growth_pct": ct["growth_pct"],
                "momentum": ct["momentum"],
            }

        dead_ids = {d["product_id"] for d in self.woo.get("dead_stock", [])}
        velocity = self.woo.get("velocity", [])

        candidates = []
        for v in velocity:
            stock = v["stock_quantity"]
            if stock <= 0:
                continue

            # Only consider currently-slow products
            is_slow = (
                v["product_id"] in dead_ids or
                v["qty_per_week"] < 0.5 or
                v["days_since_last_sale"] > 45
            )
            if not is_slow:
                continue

            # Signal 1: Seasonal potential (0-100)
            seasonal_score = self._seasonal_keep_signal(v)

            # Signal 2: Category growth (0-100)
            cat_score = 0
            for cat in v.get("categories", []):
                ch = cat_health.get(cat, {})
                if ch.get("direction") == "growing":
                    cat_score = max(cat_score, 80)
                    if ch.get("momentum") == "accelerating":
                        cat_score = 100
                elif ch.get("direction") == "stable":
                    cat_score = max(cat_score, 40)

            # Signal 3: Historical performance (0-100)
            if v["total_sold"] >= 20:
                history_score = 90
            elif v["total_sold"] >= 10:
                history_score = 70
            elif v["total_sold"] >= 5:
                history_score = 50
            elif v["total_sold"] >= 2:
                history_score = 30
            else:
                history_score = 0

            # Signal 4: Price / margin signal (0-100)
            # High-priced items have more margin to protect
            price = v["price"]
            if price >= 200:
                margin_score = 80
            elif price >= 100:
                margin_score = 60
            elif price >= 50:
                margin_score = 40
            else:
                margin_score = 20

            # Signal 5: Trend relevance — does it match current fabric trends?
            trend_score = self._trend_relevance_score(v)

            # Weighted composite
            keep_score = (
                0.30 * seasonal_score +
                0.25 * cat_score +
                0.20 * history_score +
                0.15 * margin_score +
                0.10 * trend_score
            )

            if keep_score < 40:
                continue

            reasons = self._keep_reasons(
                v, seasonal_score, cat_score, history_score,
                margin_score, trend_score,
            )

            candidates.append({
                "product_id": v["product_id"],
                "name": v["name"],
                "sku": v.get("sku", ""),
                "price": v["price"],
                "stock_quantity": stock,
                "capital_tied": round(price * stock, 2),
                "categories": v.get("categories", []),
                "color": v.get("color", ""),
                "fabric_type": v.get("fabric_type", ""),
                "total_sold": v["total_sold"],
                "days_since_last_sale": v["days_since_last_sale"],
                "qty_per_week": v["qty_per_week"],
                "direction": v["direction"],
                "keep_score": round(keep_score, 1),
                "reasons": reasons,
                "strategy": self._keep_strategy(keep_score, v, seasonal_score, cat_score),
                "signals": {
                    "seasonal_potential": round(seasonal_score, 1),
                    "category_growth": round(cat_score, 1),
                    "historical_performance": round(history_score, 1),
                    "margin_signal": round(margin_score, 1),
                    "trend_relevance": round(trend_score, 1),
                },
            })

        candidates.sort(key=lambda c: -c["keep_score"])
        return candidates

    def _seasonal_keep_signal(self, v: dict) -> float:
        """0 = no seasonal hope, 100 = strong seasonal returner."""
        fabric = (v.get("fabric_type") or "").lower()

        # Check next 3 months for seasonal demand
        score = 0
        for offset in range(1, 4):
            future_month = ((self._current_month - 1 + offset) % 12) + 1
            seasonal = SEASONAL_FABRIC_PATTERNS.get(future_month, ([], [], ""))
            for high in seasonal[0]:
                if high in fabric:
                    # Sooner = higher score
                    score = max(score, 100 - (offset - 1) * 20)

        # Also check if it sold well historically (total_sold > 5 suggests
        # it's not a dud, just seasonal)
        if score > 0 and v["total_sold"] >= 5:
            score = min(score + 15, 100)

        return score

    def _trend_relevance_score(self, v: dict) -> float:
        """How well does this product match current trending attributes?"""
        # Use the attributes performance data to check if this product's
        # color/pattern/fabric is trending
        attrs = self.woo.get("attributes", {})
        score = 0

        color = (v.get("color") or "").lower()
        pattern = (v.get("pattern") or "").lower()
        fabric = (v.get("fabric_type") or "").lower()

        # Check if product's attributes are top performers
        for attr_list, attr_val in [
            (attrs.get("colors", []), color),
            (attrs.get("patterns", []), pattern),
            (attrs.get("fabrics", []), fabric),
        ]:
            if not attr_val:
                continue
            for i, attr in enumerate(attr_list[:5]):
                if attr["name"].lower() == attr_val:
                    # Top 5 attribute — boost score based on rank
                    score += (5 - i) * 15
                    if attr.get("dominant_direction") == "accelerating":
                        score += 10
                    break

        return min(score, 100)

    def _keep_reasons(self, v, seasonal, cat, history, margin, trend) -> list[str]:
        """Human-readable reasons to keep this product."""
        reasons = []
        signals = [
            (seasonal, "Seasonal demand coming" if seasonal > 60
             else "Some seasonal potential" if seasonal > 30 else None),
            (cat, "Category is growing" if cat > 60
             else "Category is stable" if cat > 30 else None),
            (history, f"Strong history — {v['total_sold']} units sold previously"
             if history > 60 else f"Some history — {v['total_sold']} units sold"
             if history > 30 else None),
            (margin, f"High-value item at {v['price']:,.0f}"
             if margin > 60 else None),
            (trend, "Matches trending attributes"
             if trend > 40 else None),
        ]
        for score, reason in sorted(signals, key=lambda s: -s[0]):
            if score >= 30 and reason:
                reasons.append(reason)
        return reasons[:4]

    def _keep_strategy(self, score: float, v: dict,
                       seasonal: float, cat: float) -> str:
        """What to do with a product you're keeping."""
        if seasonal > 70:
            return (
                f"Seasonal hold — keep {v['stock_quantity']} units. "
                f"Promote when season turns. Do NOT discount."
            )
        if cat > 70:
            return (
                f"Category is growing — give this product a marketing push. "
                f"Feature in collection pages and newsletters."
            )
        if score >= 70:
            return (
                f"Strong keep — this product has multiple positive signals. "
                f"Maintain stock, light promotion to revive velocity."
            )
        return (
            f"Tentative keep — hold for 30 more days. "
            f"If no improvement, move to discount."
        )

    # ------------------------------------------------------------------
    # Executive Summary
    # ------------------------------------------------------------------

    def _build_summary(self, category_trends, dead_categories,
                       smart_remove, smart_keep) -> dict:
        """Top-level intelligence summary."""
        summary = self.woo.get("summary", {})

        # Category health
        growing = [c for c in category_trends if c["direction"] == "growing"]
        declining = [c for c in category_trends if c["direction"] == "declining"]
        stable = [c for c in category_trends if c["direction"] == "stable"]

        # Capital at risk in remove candidates
        remove_capital = sum(r["capital_tied"] for r in smart_remove)
        keep_capital = sum(k["capital_tied"] for k in smart_keep)

        # High-confidence removal (score > 75)
        strong_removes = [r for r in smart_remove if r["remove_score"] >= 75]
        strong_remove_capital = sum(r["capital_tied"] for r in strong_removes)

        # Top actions
        top_actions = []
        if strong_removes:
            top_actions.append({
                "urgency": "today",
                "title": f"Remove {len(strong_removes)} products to free {strong_remove_capital:,.0f}",
                "detail": (
                    f"These products score 75+ on removal signals. "
                    f"Deep discount or pull from store."
                ),
            })
        if dead_categories:
            critical_dead = [d for d in dead_categories if d["severity"] == "critical"]
            if critical_dead:
                top_actions.append({
                    "urgency": "this_week",
                    "title": f"{len(critical_dead)} categories need clearance or removal",
                    "detail": ", ".join(d["category"] for d in critical_dead[:5]),
                })
        if growing:
            top_actions.append({
                "urgency": "opportunity",
                "title": f"{len(growing)} categories growing — invest here",
                "detail": ", ".join(c["category"] for c in growing[:5]),
            })

        return {
            "total_categories": len(category_trends),
            "growing_categories": len(growing),
            "declining_categories": len(declining),
            "stable_categories": len(stable),
            "dead_categories": len(dead_categories),
            "remove_candidates": len(smart_remove),
            "remove_capital_at_risk": round(remove_capital, 2),
            "strong_remove_count": len(strong_removes),
            "strong_remove_capital": round(strong_remove_capital, 2),
            "keep_candidates": len(smart_keep),
            "keep_capital_protected": round(keep_capital, 2),
            "top_actions": top_actions,
        }
