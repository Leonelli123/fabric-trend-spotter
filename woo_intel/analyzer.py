"""Inventory Intelligence Analyzer.

Takes WooCommerce products + orders and produces actionable metrics:
  - Sales velocity per product (units/week, revenue/week, trend direction)
  - Dead stock detection (days since last sale, capital tied up)
  - Winner identification (top sellers, rising stars, reorder alerts)
  - Color, pattern, and fabric performance breakdown
  - Category performance comparison
  - Seasonal patterns from historical data
  - Customer geography breakdown (B2B vs B2C, country mix)
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Fabric industry seasonal knowledge
SEASONAL_FABRIC_PATTERNS = {
    # month -> (high-demand categories, low-demand categories, notes)
    1:  (["fleece", "flannel", "wool", "knit", "minky"],
         ["lawn", "voile", "chiffon"],
         "Post-holiday sewing projects, warm fabrics for winter"),
    2:  (["cotton", "jersey", "valentine"],
         ["heavy wool", "flannel"],
         "Spring planning begins, Valentine's prints, early quilting"),
    3:  (["cotton", "linen", "lawn", "floral", "pastel"],
         ["fleece", "flannel"],
         "Spring fabrics, Easter prints, garden/botanical themes"),
    4:  (["cotton", "linen", "lawn", "jersey", "floral"],
         ["wool", "fleece", "velvet"],
         "Peak spring — floral prints, light fabrics, outdoor themes"),
    5:  (["cotton", "linen", "lawn", "voile", "tropical"],
         ["wool", "flannel", "fleece"],
         "Summer prep, tropical prints, graduation/wedding fabrics"),
    6:  (["cotton", "linen", "jersey", "tropical", "bold"],
         ["wool", "fleece", "flannel"],
         "Summer peak — bright colors, vacation prints, lightweight"),
    7:  (["cotton", "linen", "jersey", "back-to-school"],
         ["wool", "fleece"],
         "Mid-summer sales, early back-to-school prep"),
    8:  (["cotton", "jersey", "back-to-school", "autumn"],
         ["tropical", "vacation"],
         "Back-to-school rush, autumn preview collections"),
    9:  (["cotton", "jersey", "flannel", "autumn", "rust", "mustard"],
         ["tropical", "neon", "vacation"],
         "Autumn collections, Halloween prep, warm tones return"),
    10: (["flannel", "fleece", "halloween", "autumn", "knit"],
         ["lawn", "voile", "chiffon"],
         "Halloween peak, cozy fabrics, holiday sewing begins"),
    11: (["fleece", "flannel", "christmas", "holiday", "velvet", "minky"],
         ["lawn", "voile", "tropical"],
         "Holiday fabric rush — Christmas prints, gift-making"),
    12: (["fleece", "flannel", "christmas", "minky", "gift"],
         ["linen", "lawn"],
         "Last holiday push, end-of-year clearance opportunity"),
}

# Nordic/EU-specific seasonal adjustments
NORDIC_SEASONAL_NOTES = {
    1:  "Scandinavia: hygge season peak, dark prints, warm knits dominant",
    3:  "Nordic spring = still cold. Don't rush to lightweight fabrics yet",
    5:  "Scandinavian midsummer prep — light linens, blue/yellow themes",
    6:  "EU summer: outdoor living fabrics, Mediterranean colors trend",
    8:  "Back-to-school earlier in DK/DE than US. Stock jersey/knit early",
    10: "Nordic autumn: 'mys' culture drives cozy fabric demand",
    11: "Christmas markets begin early in DE/DK — holiday fabrics by Nov 1",
    12: "Scandinavia: January sale culture means discount timing matters",
}

# Color seasonality — which colors peak in which months
# month -> (high-demand colors, low-demand colors)
SEASONAL_COLOR_PATTERNS = {
    1:  (["dark", "navy", "charcoal", "black", "burgundy", "forest", "mørk"],
         ["pastel", "neon", "coral", "mint", "lyserød"]),
    2:  (["red", "pink", "rose", "rød", "lyserød", "bordeaux"],
         ["neon", "tropical"]),
    3:  (["pastel", "mint", "baby blue", "soft pink", "lavender", "sage", "lys"],
         ["dark", "burgundy", "mørk"]),
    4:  (["pastel", "floral", "mint", "coral", "yellow", "lys", "gul", "rosa"],
         ["dark", "charcoal", "mørk", "sort"]),
    5:  (["bright", "coral", "turquoise", "yellow", "white", "gul", "hvid", "turkis"],
         ["dark", "burgundy", "mørk"]),
    6:  (["bright", "bold", "coral", "turquoise", "tropical", "orange", "turkis"],
         ["dark", "muted", "charcoal", "mørk"]),
    7:  (["bright", "bold", "blue", "turquoise", "white", "blå", "hvid"],
         ["dark", "muted", "mørk"]),
    8:  (["earth", "rust", "mustard", "olive", "warm", "rust", "sennep"],
         ["pastel", "neon"]),
    9:  (["rust", "mustard", "burgundy", "olive", "earth", "terracotta", "sennep", "bordeaux"],
         ["pastel", "mint", "baby blue"]),
    10: (["dark", "orange", "rust", "burgundy", "forest", "mørk", "bordeaux"],
         ["pastel", "coral", "tropical"]),
    11: (["red", "green", "gold", "navy", "forest", "rød", "grøn", "guld"],
         ["pastel", "neon", "tropical"]),
    12: (["red", "green", "gold", "silver", "navy", "rød", "grøn", "sølv"],
         ["pastel", "tropical", "neon"]),
}


class InventoryAnalyzer:
    """Crunches product + order data into actionable intelligence."""

    def __init__(self, products: list[dict], orders: list[dict]):
        self.products = {p["id"]: p for p in products}
        self.orders = orders
        self._product_list = products
        self._now = datetime.utcnow()

        # Pre-compute order line items indexed by product_id
        self._sales_by_product = defaultdict(list)
        for order in orders:
            order_date = _parse_date(order["date_created"])
            if not order_date:
                continue
            for item in order.get("items", []):
                pid = item.get("product_id")
                if pid:
                    self._sales_by_product[pid].append({
                        "date": order_date,
                        "quantity": item["quantity"],
                        "revenue": item["total"],
                        "order_id": order["id"],
                        "country": order.get("billing_country", ""),
                        "is_b2b": order.get("is_b2b", False),
                    })

    # ------------------------------------------------------------------
    # Sales Velocity
    # ------------------------------------------------------------------

    def get_sales_velocity(self) -> list[dict]:
        """Per-product sales velocity with trend direction."""
        results = []
        for pid, product in self.products.items():
            sales = sorted(self._sales_by_product.get(pid, []),
                           key=lambda s: s["date"])
            if not sales:
                results.append(self._zero_velocity(product))
                continue

            total_qty = sum(s["quantity"] for s in sales)
            total_rev = sum(s["revenue"] for s in sales)
            first_sale = sales[0]["date"]
            last_sale = sales[-1]["date"]
            days_since_last = (self._now - last_sale).days
            active_days = max((last_sale - first_sale).days, 1)

            # Weekly velocity
            weeks = max(active_days / 7, 1)
            qty_per_week = total_qty / weeks
            rev_per_week = total_rev / weeks

            # Recent vs older velocity (trend direction)
            midpoint = first_sale + timedelta(days=active_days // 2)
            recent = [s for s in sales if s["date"] >= midpoint]
            older = [s for s in sales if s["date"] < midpoint]
            recent_weeks = max((self._now - midpoint).days / 7, 1)
            older_weeks = max((midpoint - first_sale).days / 7, 1)

            recent_rate = sum(s["quantity"] for s in recent) / recent_weeks
            older_rate = sum(s["quantity"] for s in older) / older_weeks if older else 0

            if older_rate > 0:
                velocity_change = (recent_rate - older_rate) / older_rate
            else:
                velocity_change = 1.0 if recent_rate > 0 else 0.0

            if velocity_change > 0.15:
                direction = "accelerating"
            elif velocity_change < -0.15:
                direction = "decelerating"
            else:
                direction = "stable"

            results.append({
                "product_id": pid,
                "name": product["name"],
                "sku": product.get("sku", ""),
                "price": product["price"],
                "stock_quantity": product["stock_quantity"],
                "categories": product["categories"],
                "color": product.get("color", ""),
                "pattern": product.get("pattern", ""),
                "fabric_type": product.get("fabric_type", ""),
                "total_sold": total_qty,
                "total_revenue": round(total_rev, 2),
                "qty_per_week": round(qty_per_week, 2),
                "rev_per_week": round(rev_per_week, 2),
                "days_since_last_sale": days_since_last,
                "first_sale": first_sale.isoformat(),
                "last_sale": last_sale.isoformat(),
                "sale_count": len(sales),
                "direction": direction,
                "velocity_change": round(velocity_change, 3),
                "recent_rate": round(recent_rate, 2),
                "older_rate": round(older_rate, 2),
            })

        return sorted(results, key=lambda r: r["rev_per_week"], reverse=True)

    def _zero_velocity(self, product: dict) -> dict:
        """Product with zero sales."""
        created = _parse_date(product.get("date_created", ""))
        days_listed = (self._now - created).days if created else 0
        return {
            "product_id": product["id"],
            "name": product["name"],
            "sku": product.get("sku", ""),
            "price": product["price"],
            "stock_quantity": product["stock_quantity"],
            "categories": product["categories"],
            "color": product.get("color", ""),
            "pattern": product.get("pattern", ""),
            "fabric_type": product.get("fabric_type", ""),
            "total_sold": 0,
            "total_revenue": 0.0,
            "qty_per_week": 0.0,
            "rev_per_week": 0.0,
            "days_since_last_sale": days_listed,
            "first_sale": None,
            "last_sale": None,
            "sale_count": 0,
            "direction": "no_sales",
            "velocity_change": 0.0,
            "recent_rate": 0.0,
            "older_rate": 0.0,
        }

    # ------------------------------------------------------------------
    # Dead Stock Detection
    # ------------------------------------------------------------------

    def get_dead_stock(self, stale_days: int = 60) -> list[dict]:
        """Products that haven't sold in N days with capital tied up."""
        velocity = self.get_sales_velocity()
        dead = []
        for v in velocity:
            if v["days_since_last_sale"] < stale_days and v["sale_count"] > 0:
                continue
            if v["stock_quantity"] <= 0:
                continue

            capital_tied = v["price"] * v["stock_quantity"]
            product = self.products.get(v["product_id"], {})

            # Classify severity
            if v["sale_count"] == 0:
                severity = "critical"
                reason = "Never sold — consider removing or deep discount"
            elif v["days_since_last_sale"] > 180:
                severity = "critical"
                reason = f"No sales in {v['days_since_last_sale']} days"
            elif v["days_since_last_sale"] > 90:
                severity = "warning"
                reason = f"No sales in {v['days_since_last_sale']} days"
            else:
                severity = "watch"
                reason = f"Slowing — {v['days_since_last_sale']} days since last sale"

            # Seasonal check: is this fabric simply out of season?
            current_month = self._now.month
            seasonal = SEASONAL_FABRIC_PATTERNS.get(current_month, ([], [], ""))
            low_demand = seasonal[1]
            fabric = (v.get("fabric_type", "") or "").lower()
            is_seasonal_dip = any(ld in fabric for ld in low_demand)

            if is_seasonal_dip and severity != "critical":
                severity = "seasonal"
                reason += " (likely seasonal — demand expected to return)"

            dead.append({
                **v,
                "capital_tied": round(capital_tied, 2),
                "severity": severity,
                "reason": reason,
                "is_seasonal_dip": is_seasonal_dip,
                "on_sale": product.get("on_sale", False),
                "images": product.get("images", [])[:1],
            })

        return sorted(dead, key=lambda d: d["capital_tied"], reverse=True)

    # ------------------------------------------------------------------
    # Winner Detection
    # ------------------------------------------------------------------

    def get_winners(self, top_n: int = 20) -> dict:
        """Identify top sellers, rising stars, and reorder alerts."""
        velocity = self.get_sales_velocity()
        active = [v for v in velocity if v["sale_count"] > 0]

        # Top sellers by revenue
        top_by_revenue = active[:top_n]

        # Rising stars: accelerating velocity, at least 3 sales
        rising_stars = [
            v for v in active
            if v["direction"] == "accelerating" and v["sale_count"] >= 3
        ]
        rising_stars.sort(key=lambda v: v["velocity_change"], reverse=True)

        # Reorder alerts: high velocity + low stock
        reorder_alerts = []
        for v in active:
            if v["qty_per_week"] <= 0 or v["stock_quantity"] <= 0:
                continue
            weeks_of_stock = v["stock_quantity"] / v["qty_per_week"]
            if weeks_of_stock < 4:  # less than 4 weeks of stock
                reorder_alerts.append({
                    **v,
                    "weeks_of_stock": round(weeks_of_stock, 1),
                    "urgency": "critical" if weeks_of_stock < 2 else "soon",
                    "suggested_reorder": max(
                        round(v["qty_per_week"] * 8), 1  # 8 weeks of stock
                    ),
                })
        reorder_alerts.sort(key=lambda r: r["weeks_of_stock"])

        # Consistent performers: stable velocity, good margin
        consistent = [
            v for v in active
            if v["direction"] == "stable" and v["qty_per_week"] >= 1
        ]

        return {
            "top_by_revenue": top_by_revenue[:top_n],
            "rising_stars": rising_stars[:10],
            "reorder_alerts": reorder_alerts,
            "consistent_performers": consistent[:15],
            "summary": {
                "total_active_products": len(active),
                "total_zero_sales": len(velocity) - len(active),
                "accelerating_count": len([
                    v for v in active if v["direction"] == "accelerating"
                ]),
                "decelerating_count": len([
                    v for v in active if v["direction"] == "decelerating"
                ]),
            },
        }

    # ------------------------------------------------------------------
    # Color / Pattern / Fabric Analysis
    # ------------------------------------------------------------------

    def get_attribute_performance(self) -> dict:
        """Which colors, patterns, and fabrics are selling best/worst?"""
        velocity = self.get_sales_velocity()

        color_perf = defaultdict(lambda: {
            "total_rev": 0, "total_qty": 0, "products": 0, "items": [],
        })
        pattern_perf = defaultdict(lambda: {
            "total_rev": 0, "total_qty": 0, "products": 0, "items": [],
        })
        fabric_perf = defaultdict(lambda: {
            "total_rev": 0, "total_qty": 0, "products": 0, "items": [],
        })

        for v in velocity:
            color = (v.get("color") or "").strip().lower()
            pattern = (v.get("pattern") or "").strip().lower()
            fabric = (v.get("fabric_type") or "").strip().lower()

            if color:
                color_perf[color]["total_rev"] += v["total_revenue"]
                color_perf[color]["total_qty"] += v["total_sold"]
                color_perf[color]["products"] += 1
                color_perf[color]["items"].append(v)
            if pattern:
                pattern_perf[pattern]["total_rev"] += v["total_revenue"]
                pattern_perf[pattern]["total_qty"] += v["total_sold"]
                pattern_perf[pattern]["products"] += 1
                pattern_perf[pattern]["items"].append(v)
            if fabric:
                fabric_perf[fabric]["total_rev"] += v["total_revenue"]
                fabric_perf[fabric]["total_qty"] += v["total_sold"]
                fabric_perf[fabric]["products"] += 1
                fabric_perf[fabric]["items"].append(v)

        def _summarize(perf: dict) -> list:
            result = []
            for name, data in perf.items():
                avg_velocity = (
                    sum(i["qty_per_week"] for i in data["items"]) / len(data["items"])
                    if data["items"] else 0
                )
                directions = [i["direction"] for i in data["items"]]
                dominant_direction = max(set(directions), key=directions.count)
                result.append({
                    "name": name,
                    "total_revenue": round(data["total_rev"], 2),
                    "total_quantity": data["total_qty"],
                    "product_count": data["products"],
                    "avg_velocity_per_week": round(avg_velocity, 2),
                    "dominant_direction": dominant_direction,
                    "rev_per_product": round(
                        data["total_rev"] / data["products"], 2
                    ) if data["products"] else 0,
                })
            return sorted(result, key=lambda r: r["total_revenue"], reverse=True)

        return {
            "colors": _summarize(color_perf),
            "patterns": _summarize(pattern_perf),
            "fabrics": _summarize(fabric_perf),
        }

    # ------------------------------------------------------------------
    # Category Performance
    # ------------------------------------------------------------------

    def get_category_performance(self) -> list[dict]:
        """Revenue and velocity per product category."""
        velocity = self.get_sales_velocity()
        cat_data = defaultdict(lambda: {
            "total_rev": 0, "total_qty": 0, "products": 0, "items": [],
        })

        for v in velocity:
            for cat in v.get("categories", []):
                cat_data[cat]["total_rev"] += v["total_revenue"]
                cat_data[cat]["total_qty"] += v["total_sold"]
                cat_data[cat]["products"] += 1
                cat_data[cat]["items"].append(v)

        results = []
        for name, data in cat_data.items():
            active = [i for i in data["items"] if i["sale_count"] > 0]
            dead = [i for i in data["items"] if i["sale_count"] == 0]
            results.append({
                "category": name,
                "total_revenue": round(data["total_rev"], 2),
                "total_sold": data["total_qty"],
                "product_count": data["products"],
                "active_products": len(active),
                "dead_products": len(dead),
                "dead_ratio": round(len(dead) / data["products"], 2)
                if data["products"] else 0,
                "avg_rev_per_product": round(
                    data["total_rev"] / data["products"], 2
                ) if data["products"] else 0,
            })

        return sorted(results, key=lambda r: r["total_revenue"], reverse=True)

    # ------------------------------------------------------------------
    # Seasonal Analysis
    # ------------------------------------------------------------------

    def get_seasonal_insights(self) -> dict:
        """Analyze historical sales patterns by month to identify seasonality."""
        monthly = defaultdict(lambda: {"revenue": 0, "quantity": 0, "orders": 0})

        for order in self.orders:
            date = _parse_date(order["date_created"])
            if not date:
                continue
            key = date.month
            monthly[key]["revenue"] += order["total"]
            monthly[key]["quantity"] += order["item_count"]
            monthly[key]["orders"] += 1

        # Build monthly summary
        months = []
        for m in range(1, 13):
            data = monthly.get(m, {"revenue": 0, "quantity": 0, "orders": 0})
            seasonal = SEASONAL_FABRIC_PATTERNS.get(m, ([], [], ""))
            nordic_note = NORDIC_SEASONAL_NOTES.get(m, "")
            months.append({
                "month": m,
                "month_name": [
                    "", "January", "February", "March", "April", "May",
                    "June", "July", "August", "September", "October",
                    "November", "December",
                ][m],
                "revenue": round(data["revenue"], 2),
                "quantity": data["quantity"],
                "orders": data["orders"],
                "high_demand_fabrics": seasonal[0],
                "low_demand_fabrics": seasonal[1],
                "industry_note": seasonal[2],
                "nordic_note": nordic_note,
            })

        # Identify peak and low months
        if any(m["revenue"] > 0 for m in months):
            peak = max(months, key=lambda m: m["revenue"])
            low = min(
                (m for m in months if m["revenue"] > 0),
                key=lambda m: m["revenue"],
                default=months[0],
            )
        else:
            peak = low = months[0]

        current_month = self._now.month
        upcoming = SEASONAL_FABRIC_PATTERNS.get(
            (current_month % 12) + 1, ([], [], "")
        )

        return {
            "monthly": months,
            "peak_month": peak,
            "low_month": low,
            "current_season": SEASONAL_FABRIC_PATTERNS.get(
                current_month, ([], [], "")
            ),
            "next_month_prep": {
                "high_demand": upcoming[0],
                "low_demand": upcoming[1],
                "note": upcoming[2],
                "nordic_note": NORDIC_SEASONAL_NOTES.get(
                    (current_month % 12) + 1, ""
                ),
            },
        }

    # ------------------------------------------------------------------
    # Geography / Channel Analysis
    # ------------------------------------------------------------------

    def get_geography_breakdown(self) -> dict:
        """Revenue by country and B2B vs B2C split."""
        country_rev = defaultdict(float)
        country_orders = defaultdict(int)
        b2b_rev = 0.0
        b2c_rev = 0.0
        b2b_orders = 0
        b2c_orders = 0

        for order in self.orders:
            country = order.get("billing_country", "Unknown")
            country_rev[country] += order["total"]
            country_orders[country] += 1
            if order.get("is_b2b"):
                b2b_rev += order["total"]
                b2b_orders += 1
            else:
                b2c_rev += order["total"]
                b2c_orders += 1

        countries = []
        for code, rev in sorted(country_rev.items(), key=lambda x: -x[1]):
            countries.append({
                "country": code,
                "revenue": round(rev, 2),
                "orders": country_orders[code],
                "avg_order_value": round(rev / country_orders[code], 2)
                if country_orders[code] else 0,
            })

        return {
            "countries": countries,
            "b2b": {
                "revenue": round(b2b_rev, 2),
                "orders": b2b_orders,
                "avg_order_value": round(b2b_rev / b2b_orders, 2)
                if b2b_orders else 0,
            },
            "b2c": {
                "revenue": round(b2c_rev, 2),
                "orders": b2c_orders,
                "avg_order_value": round(b2c_rev / b2c_orders, 2)
                if b2c_orders else 0,
            },
        }

    # ------------------------------------------------------------------
    # Monthly Category Data (for Smart Intelligence)
    # ------------------------------------------------------------------

    def get_monthly_category_data(self) -> dict:
        """Monthly revenue and quantity breakdown per category.

        Returns {category_name: [{month, revenue, quantity, order_count}, ...]}
        sorted chronologically.  Used by SmartAnalyzer for category trends.
        """
        # {category -> {month_key -> {revenue, quantity, order_ids}}}
        monthly = defaultdict(lambda: defaultdict(lambda: {
            "revenue": 0, "quantity": 0, "order_ids": set(),
        }))

        for pid, sales in self._sales_by_product.items():
            product = self.products.get(pid, {})
            categories = product.get("categories", [])
            for sale in sales:
                month_key = sale["date"].strftime("%Y-%m")
                for cat in categories:
                    monthly[cat][month_key]["revenue"] += sale["revenue"]
                    monthly[cat][month_key]["quantity"] += sale["quantity"]
                    monthly[cat][month_key]["order_ids"].add(sale["order_id"])

        result = {}
        for cat, months in monthly.items():
            result[cat] = [
                {
                    "month": mk,
                    "revenue": round(months[mk]["revenue"], 2),
                    "quantity": months[mk]["quantity"],
                    "order_count": len(months[mk]["order_ids"]),
                }
                for mk in sorted(months.keys())
            ]
        return result

    # ------------------------------------------------------------------
    # Full analysis (all modules combined)
    # ------------------------------------------------------------------

    def run_full_analysis(self) -> dict:
        """Run all analysis modules and return combined results."""
        logger.info("Running full inventory analysis on %d products, %d orders...",
                     len(self.products), len(self.orders))

        velocity = self.get_sales_velocity()
        dead_stock = self.get_dead_stock()
        winners = self.get_winners()
        attributes = self.get_attribute_performance()
        categories = self.get_category_performance()
        seasonal = self.get_seasonal_insights()
        geography = self.get_geography_breakdown()
        monthly_categories = self.get_monthly_category_data()

        total_revenue = sum(o["total"] for o in self.orders)
        total_inventory_value = sum(
            p["price"] * p["stock_quantity"]
            for p in self._product_list
            if p["price"] and p["stock_quantity"]
        )
        dead_capital = sum(d["capital_tied"] for d in dead_stock)

        return {
            "generated_at": self._now.isoformat(),
            "summary": {
                "total_products": len(self.products),
                "total_orders": len(self.orders),
                "total_revenue": round(total_revenue, 2),
                "total_inventory_value": round(total_inventory_value, 2),
                "dead_stock_capital": round(dead_capital, 2),
                "dead_stock_ratio": round(
                    dead_capital / total_inventory_value, 3
                ) if total_inventory_value else 0,
                "active_products": winners["summary"]["total_active_products"],
                "zero_sales_products": winners["summary"]["total_zero_sales"],
            },
            "velocity": velocity,
            "dead_stock": dead_stock,
            "winners": winners,
            "attributes": attributes,
            "categories": categories,
            "seasonal": seasonal,
            "geography": geography,
            "monthly_categories": monthly_categories,
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_date(val) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            return datetime.strptime(val[:19], fmt[:len(val[:19])+2])
        except (ValueError, IndexError):
            continue
    return None
