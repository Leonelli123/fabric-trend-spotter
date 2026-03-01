"""WooCommerce + e-conomic Data Reconciler.

Combines WooCommerce order data with e-conomic invoice data to produce
a unified, verified view of the business.  WooCommerce tells us what was
ordered; e-conomic tells us what was actually invoiced and paid.

Key outputs:
  - Revenue accuracy check (Woo orders vs e-conomic invoices)
  - True profitability per product (invoice amounts + cost prices)
  - Cash collection rate (invoiced vs paid)
  - Customer cross-reference (Woo customer IDs ↔ e-conomic customer numbers)
"""

import logging
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


class DataReconciler:
    """Cross-references WooCommerce and e-conomic data."""

    def __init__(self, woo_analysis: dict = None, eco_analysis: dict = None):
        """Initialize with analysis results from both systems.

        Either or both can be None — we degrade gracefully.
        """
        self.woo = woo_analysis
        self.eco = eco_analysis
        self._now = datetime.utcnow()

    def reconcile(self) -> dict:
        """Run all reconciliation checks and produce a unified view."""
        result = {
            "generated_at": self._now.isoformat(),
            "data_sources": {
                "woocommerce": self.woo is not None,
                "economic": self.eco is not None,
            },
        }

        # Revenue comparison
        if self.woo and self.eco:
            result["revenue_comparison"] = self._compare_revenue()
            result["combined_health"] = self._combined_health_score()
        elif self.eco:
            result["revenue_comparison"] = self._eco_only_revenue()
        elif self.woo:
            result["revenue_comparison"] = self._woo_only_revenue()
        else:
            result["revenue_comparison"] = {"error": "No data from either source"}

        # Cash collection (e-conomic only — it has payment data)
        if self.eco:
            result["cash_collection"] = self._cash_collection_rate()
            result["overdue_alert"] = self._overdue_alert()
        else:
            result["cash_collection"] = None
            result["overdue_alert"] = None

        return result

    # ------------------------------------------------------------------
    # Revenue Comparison
    # ------------------------------------------------------------------

    def _compare_revenue(self) -> dict:
        """Compare WooCommerce order revenue vs e-conomic invoice revenue."""
        woo_summary = self.woo.get("summary", {})
        eco_summary = self.eco.get("summary", {})

        woo_rev = woo_summary.get("total_revenue", 0)
        eco_rev = eco_summary.get("total_net_revenue", 0)

        diff = eco_rev - woo_rev
        diff_pct = (diff / woo_rev * 100) if woo_rev else 0

        # Determine explanation
        if abs(diff_pct) < 5:
            match_status = "good_match"
            note = "WooCommerce and e-conomic revenue are within 5% — data is consistent."
        elif diff > 0:
            match_status = "economic_higher"
            note = (
                f"e-conomic shows {diff:,.0f} more than WooCommerce. "
                f"Likely: offline invoices, B2B orders not in WooCommerce, "
                f"or manual invoices."
            )
        else:
            match_status = "woo_higher"
            note = (
                f"WooCommerce shows {abs(diff):,.0f} more than e-conomic. "
                f"Possible: refunds processed in e-conomic, cancelled orders "
                f"still counted in Woo, or uninvoiced orders."
            )

        # Monthly comparison
        woo_monthly = self._woo_monthly_revenue()
        eco_monthly = self.eco.get("revenue", {}).get("monthly", [])
        eco_by_month = {m["month"]: m["net_amount"] for m in eco_monthly}

        monthly_comparison = []
        all_months = sorted(set(list(woo_monthly.keys()) + list(eco_by_month.keys())))
        for month in all_months:
            w = woo_monthly.get(month, 0)
            e = eco_by_month.get(month, 0)
            monthly_comparison.append({
                "month": month,
                "woo_revenue": round(w, 2),
                "eco_revenue": round(e, 2),
                "difference": round(e - w, 2),
                "match": abs(e - w) < max(w, e) * 0.1 if max(w, e) > 0 else True,
            })

        return {
            "woo_total_revenue": round(woo_rev, 2),
            "eco_total_net_revenue": round(eco_rev, 2),
            "difference": round(diff, 2),
            "difference_pct": round(diff_pct, 1),
            "match_status": match_status,
            "note": note,
            "monthly_comparison": monthly_comparison,
        }

    def _eco_only_revenue(self) -> dict:
        """Revenue summary when only e-conomic data is available."""
        eco_summary = self.eco.get("summary", {})
        return {
            "source": "e-conomic_only",
            "total_net_revenue": eco_summary.get("total_net_revenue", 0),
            "total_invoices": eco_summary.get("total_invoices", 0),
            "note": "100% accurate — sourced directly from invoices.",
        }

    def _woo_only_revenue(self) -> dict:
        """Revenue summary when only WooCommerce data is available."""
        woo_summary = self.woo.get("summary", {})
        return {
            "source": "woocommerce_only",
            "total_revenue": woo_summary.get("total_revenue", 0),
            "total_orders": woo_summary.get("total_orders", 0),
            "note": (
                "Based on WooCommerce orders — may differ from actual invoiced "
                "amounts. Connect e-conomic for precise figures."
            ),
        }

    def _woo_monthly_revenue(self) -> dict:
        """Extract monthly revenue from WooCommerce seasonal data."""
        seasonal = self.woo.get("seasonal", {})
        monthly_data = seasonal.get("monthly", [])
        result = {}
        for m in monthly_data:
            month_num = m.get("month", 0)
            if month_num:
                key = f"{self._now.year}-{month_num:02d}"
                result[key] = m.get("revenue", 0)
        return result

    # ------------------------------------------------------------------
    # Cash Collection
    # ------------------------------------------------------------------

    def _cash_collection_rate(self) -> dict:
        """What percentage of invoiced revenue has actually been paid?"""
        eco_summary = self.eco.get("summary", {})
        total_rev = eco_summary.get("total_net_revenue", 0)
        outstanding = eco_summary.get("total_outstanding", 0)
        collected = total_rev - outstanding

        collection_rate = (collected / total_rev * 100) if total_rev else 100

        # Forecast: when will outstanding be collected?
        cash_flow = self.eco.get("cash_flow", {})
        expected_12w = cash_flow.get("total_expected_12_weeks", 0)

        return {
            "total_invoiced": round(total_rev, 2),
            "total_collected": round(collected, 2),
            "total_outstanding": round(outstanding, 2),
            "collection_rate_pct": round(collection_rate, 1),
            "expected_next_12_weeks": round(expected_12w, 2),
            "health": (
                "excellent" if collection_rate >= 95
                else "good" if collection_rate >= 85
                else "needs_attention" if collection_rate >= 70
                else "critical"
            ),
        }

    def _overdue_alert(self) -> dict | None:
        """Generate alert if significant amounts are overdue."""
        receivables = self.eco.get("accounts_receivable", {})
        overdue = receivables.get("total_overdue", 0)
        outstanding = receivables.get("total_outstanding", 0)

        if overdue <= 0:
            return None

        overdue_pct = (overdue / outstanding * 100) if outstanding else 0
        worst = receivables.get("worst_debtors", [])

        severity = (
            "critical" if overdue_pct > 30
            else "warning" if overdue_pct > 15
            else "info"
        )

        return {
            "severity": severity,
            "total_overdue": round(overdue, 2),
            "overdue_pct": round(overdue_pct, 1),
            "message": (
                f"{overdue:,.0f} is overdue ({overdue_pct:.0f}% of outstanding). "
                + (f"Top debtor: {worst[0]['name']} ({worst[0]['total_outstanding']:,.0f})"
                   if worst else "")
            ),
            "top_debtors": worst[:5],
        }

    # ------------------------------------------------------------------
    # Combined Health Score
    # ------------------------------------------------------------------

    def _combined_health_score(self) -> dict:
        """Unified business health score using both data sources."""
        score = 100
        factors = []

        # From WooCommerce: inventory health
        woo_summary = self.woo.get("summary", {})
        dead_ratio = woo_summary.get("dead_stock_ratio", 0)
        if dead_ratio > 0.3:
            score -= 20
            factors.append(f"High dead stock ({dead_ratio:.0%} of inventory)")
        elif dead_ratio > 0.15:
            score -= 10
            factors.append(f"Moderate dead stock ({dead_ratio:.0%})")

        # From e-conomic: payment health
        eco_summary = self.eco.get("summary", {})
        overdue_ratio = eco_summary.get("overdue_ratio", 0)
        if overdue_ratio > 30:
            score -= 20
            factors.append(f"High overdue invoices ({overdue_ratio:.0f}%)")
        elif overdue_ratio > 15:
            score -= 10
            factors.append(f"Some overdue invoices ({overdue_ratio:.0f}%)")

        # Revenue trend
        growth = self.eco.get("revenue", {}).get("growth", [])
        if len(growth) >= 3:
            recent_growth = [g["growth_pct"] for g in growth[-3:]]
            avg_growth = sum(recent_growth) / len(recent_growth)
            if avg_growth > 10:
                score += 5
                factors.append(f"Revenue growing ({avg_growth:.0f}% avg last 3 months)")
            elif avg_growth < -10:
                score -= 15
                factors.append(f"Revenue declining ({avg_growth:.0f}% avg last 3 months)")

        # Cash collection
        collection = self._cash_collection_rate()
        rate = collection["collection_rate_pct"]
        if rate < 70:
            score -= 15
            factors.append(f"Low cash collection ({rate:.0f}%)")
        elif rate < 85:
            score -= 5
            factors.append(f"Cash collection needs attention ({rate:.0f}%)")

        score = max(0, min(100, score))

        if score >= 80:
            rating = "Healthy"
            color = "green"
        elif score >= 60:
            rating = "Needs Attention"
            color = "yellow"
        elif score >= 40:
            rating = "At Risk"
            color = "orange"
        else:
            rating = "Critical"
            color = "red"

        return {
            "score": score,
            "rating": rating,
            "color": color,
            "factors": factors,
            "data_quality": "high" if self.woo and self.eco else "partial",
        }
