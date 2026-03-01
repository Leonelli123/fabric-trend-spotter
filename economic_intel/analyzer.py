"""e-conomic Financial Analyzer.

Takes invoice and customer data from e-conomic and produces precise financial
intelligence — this is the "source of truth" for money since every invoice
is the actual document sent to the customer.

Modules:
  - Revenue breakdown (monthly, by customer, by product)
  - Accounts receivable aging (who owes what, how overdue)
  - Customer profitability (revenue, payment behavior, lifetime value)
  - Product-level profitability (if cost prices are tracked)
  - Payment term analysis (cash flow timing)
  - B2B vs B2C split (from customer groups)
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FinancialAnalyzer:
    """Crunches e-conomic invoice data into financial intelligence."""

    def __init__(self, invoices: list[dict], customers: list[dict],
                 products: list[dict] = None):
        self.invoices = invoices
        self.customers = {c["customer_number"]: c for c in customers}
        self.products = {p["product_number"]: p for p in (products or [])}
        self._now = datetime.utcnow()

    # ------------------------------------------------------------------
    # Revenue Breakdown
    # ------------------------------------------------------------------

    def get_revenue_summary(self) -> dict:
        """Total revenue, monthly breakdown, and growth metrics."""
        monthly = defaultdict(lambda: {
            "net_amount": 0, "vat_amount": 0, "gross_amount": 0,
            "invoice_count": 0,
        })

        total_net = 0
        total_gross = 0
        total_invoices = 0

        for inv in self.invoices:
            date = _parse_date(inv["date"])
            if not date:
                continue
            key = date.strftime("%Y-%m")
            monthly[key]["net_amount"] += inv["net_amount"]
            monthly[key]["vat_amount"] += inv["vat_amount"]
            monthly[key]["gross_amount"] += inv["gross_amount"]
            monthly[key]["invoice_count"] += 1
            total_net += inv["net_amount"]
            total_gross += inv["gross_amount"]
            total_invoices += 1

        # Sort months chronologically
        sorted_months = []
        for month_key in sorted(monthly.keys()):
            data = monthly[month_key]
            sorted_months.append({
                "month": month_key,
                "net_amount": round(data["net_amount"], 2),
                "vat_amount": round(data["vat_amount"], 2),
                "gross_amount": round(data["gross_amount"], 2),
                "invoice_count": data["invoice_count"],
            })

        # Month-over-month growth
        growth = []
        for i in range(1, len(sorted_months)):
            prev = sorted_months[i - 1]["net_amount"]
            curr = sorted_months[i]["net_amount"]
            pct = ((curr - prev) / prev * 100) if prev > 0 else 0
            growth.append({
                "month": sorted_months[i]["month"],
                "growth_pct": round(pct, 1),
                "change": round(curr - prev, 2),
            })

        # Average monthly revenue
        avg_monthly = total_net / len(monthly) if monthly else 0

        return {
            "total_net_revenue": round(total_net, 2),
            "total_gross_revenue": round(total_gross, 2),
            "total_invoices": total_invoices,
            "avg_monthly_net": round(avg_monthly, 2),
            "avg_invoice_value": round(total_net / total_invoices, 2) if total_invoices else 0,
            "monthly": sorted_months,
            "growth": growth,
        }

    # ------------------------------------------------------------------
    # Accounts Receivable / Outstanding
    # ------------------------------------------------------------------

    def get_accounts_receivable(self) -> dict:
        """Who owes money and how overdue is it?"""
        outstanding = []
        total_outstanding = 0
        overdue_total = 0

        aging_buckets = {
            "current": [],     # not yet due
            "1_30_days": [],   # 1-30 days overdue
            "31_60_days": [],  # 31-60 days overdue
            "61_90_days": [],  # 61-90 days overdue
            "over_90_days": [],  # 90+ days overdue
        }

        for inv in self.invoices:
            remainder = inv.get("remainder", 0)
            if remainder <= 0:
                continue

            due_date = _parse_date(inv.get("due_date", ""))
            days_overdue = (self._now - due_date).days if due_date else 0

            entry = {
                "invoice_number": inv["invoice_number"],
                "customer_name": inv["customer_name"],
                "customer_number": inv["customer_number"],
                "gross_amount": inv["gross_amount"],
                "remainder": remainder,
                "due_date": inv.get("due_date", ""),
                "days_overdue": max(days_overdue, 0),
                "date": inv["date"],
            }

            outstanding.append(entry)
            total_outstanding += remainder

            if days_overdue <= 0:
                aging_buckets["current"].append(entry)
            elif days_overdue <= 30:
                aging_buckets["1_30_days"].append(entry)
                overdue_total += remainder
            elif days_overdue <= 60:
                aging_buckets["31_60_days"].append(entry)
                overdue_total += remainder
            elif days_overdue <= 90:
                aging_buckets["61_90_days"].append(entry)
                overdue_total += remainder
            else:
                aging_buckets["over_90_days"].append(entry)
                overdue_total += remainder

        # Summarize buckets
        bucket_summary = {}
        for bucket, items in aging_buckets.items():
            bucket_summary[bucket] = {
                "count": len(items),
                "total": round(sum(i["remainder"] for i in items), 2),
                "invoices": sorted(items, key=lambda x: -x["remainder"])[:10],
            }

        return {
            "total_outstanding": round(total_outstanding, 2),
            "total_overdue": round(overdue_total, 2),
            "invoice_count": len(outstanding),
            "aging": bucket_summary,
            "worst_debtors": self._get_worst_debtors(outstanding),
        }

    def _get_worst_debtors(self, outstanding: list) -> list[dict]:
        """Customers with the most money outstanding."""
        by_customer = defaultdict(lambda: {"total": 0, "invoices": 0, "name": ""})
        for item in outstanding:
            cnum = item["customer_number"]
            by_customer[cnum]["total"] += item["remainder"]
            by_customer[cnum]["invoices"] += 1
            by_customer[cnum]["name"] = item["customer_name"]

        return sorted(
            [
                {"customer_number": k, "name": v["name"],
                 "total_outstanding": round(v["total"], 2),
                 "outstanding_invoices": v["invoices"]}
                for k, v in by_customer.items()
            ],
            key=lambda x: -x["total_outstanding"],
        )[:15]

    # ------------------------------------------------------------------
    # Customer Profitability
    # ------------------------------------------------------------------

    def get_customer_profitability(self) -> list[dict]:
        """Revenue per customer with payment behavior analysis."""
        customer_data = defaultdict(lambda: {
            "net_revenue": 0, "gross_revenue": 0, "invoice_count": 0,
            "first_invoice": None, "last_invoice": None,
            "outstanding": 0, "overdue_count": 0,
            "payment_dates": [],
        })

        for inv in self.invoices:
            cnum = inv["customer_number"]
            if not cnum:
                continue
            cd = customer_data[cnum]
            cd["net_revenue"] += inv["net_amount"]
            cd["gross_revenue"] += inv["gross_amount"]
            cd["invoice_count"] += 1

            inv_date = _parse_date(inv["date"])
            if inv_date:
                if cd["first_invoice"] is None or inv_date < cd["first_invoice"]:
                    cd["first_invoice"] = inv_date
                if cd["last_invoice"] is None or inv_date > cd["last_invoice"]:
                    cd["last_invoice"] = inv_date

            remainder = inv.get("remainder", 0)
            if remainder > 0:
                cd["outstanding"] += remainder
                due = _parse_date(inv.get("due_date", ""))
                if due and self._now > due:
                    cd["overdue_count"] += 1

        results = []
        for cnum, data in customer_data.items():
            customer_info = self.customers.get(cnum, {})

            # Customer lifetime in months
            months_active = 0
            if data["first_invoice"] and data["last_invoice"]:
                delta = data["last_invoice"] - data["first_invoice"]
                months_active = max(delta.days / 30, 1)

            monthly_avg = data["net_revenue"] / months_active if months_active > 0 else 0

            # Payment reliability score (0-100)
            total_inv = data["invoice_count"]
            reliability = 100
            if total_inv > 0:
                overdue_ratio = data["overdue_count"] / total_inv
                reliability = max(0, round(100 - (overdue_ratio * 100)))

            results.append({
                "customer_number": cnum,
                "name": customer_info.get("name", f"Customer #{cnum}"),
                "customer_group": customer_info.get("customer_group", ""),
                "country": customer_info.get("country", ""),
                "net_revenue": round(data["net_revenue"], 2),
                "gross_revenue": round(data["gross_revenue"], 2),
                "invoice_count": total_inv,
                "avg_invoice_value": round(data["net_revenue"] / total_inv, 2) if total_inv else 0,
                "monthly_avg_revenue": round(monthly_avg, 2),
                "months_active": round(months_active, 0),
                "outstanding": round(data["outstanding"], 2),
                "overdue_invoices": data["overdue_count"],
                "payment_reliability": reliability,
                "first_invoice": data["first_invoice"].isoformat() if data["first_invoice"] else None,
                "last_invoice": data["last_invoice"].isoformat() if data["last_invoice"] else None,
            })

        return sorted(results, key=lambda r: -r["net_revenue"])

    # ------------------------------------------------------------------
    # Product Revenue (from invoice lines)
    # ------------------------------------------------------------------

    def get_product_revenue(self, invoice_details: list[dict]) -> list[dict]:
        """Revenue and margin per product (requires detailed invoice data).

        Pass in invoices fetched with get_booked_invoice_detail() which
        contain line-item data.
        """
        product_data = defaultdict(lambda: {
            "revenue": 0, "quantity": 0, "invoice_count": 0,
            "name": "", "product_number": "",
        })

        for inv in invoice_details:
            for line in inv.get("lines", []):
                pnum = line.get("product_number", "")
                if not pnum:
                    continue
                pd = product_data[pnum]
                pd["revenue"] += line.get("total_net_amount", 0)
                pd["quantity"] += line.get("quantity", 0)
                pd["invoice_count"] += 1
                pd["name"] = line.get("product_name", pd["name"])
                pd["product_number"] = pnum

        results = []
        for pnum, data in product_data.items():
            product_info = self.products.get(pnum, {})
            cost_price = product_info.get("cost_price", 0)
            margin = 0
            if data["revenue"] > 0 and cost_price > 0:
                total_cost = cost_price * data["quantity"]
                margin = round((data["revenue"] - total_cost) / data["revenue"] * 100, 1)

            results.append({
                "product_number": pnum,
                "name": data["name"],
                "total_revenue": round(data["revenue"], 2),
                "total_quantity": data["quantity"],
                "invoice_count": data["invoice_count"],
                "avg_unit_price": round(data["revenue"] / data["quantity"], 2) if data["quantity"] else 0,
                "cost_price": cost_price,
                "margin_pct": margin,
                "product_group": product_info.get("product_group", ""),
            })

        return sorted(results, key=lambda r: -r["total_revenue"])

    # ------------------------------------------------------------------
    # Cash Flow Timing
    # ------------------------------------------------------------------

    def get_cash_flow_timing(self) -> dict:
        """Analyze payment terms and predict cash inflow timing."""
        terms_data = defaultdict(lambda: {
            "count": 0, "total_net": 0, "outstanding": 0,
        })

        # Weekly expected inflows based on due dates
        weekly_inflows = defaultdict(float)

        for inv in self.invoices:
            term = inv.get("payment_terms", "Unknown")
            terms_data[term]["count"] += 1
            terms_data[term]["total_net"] += inv["net_amount"]

            remainder = inv.get("remainder", 0)
            if remainder > 0:
                terms_data[term]["outstanding"] += remainder
                due = _parse_date(inv.get("due_date", ""))
                if due:
                    # Bucket into week
                    days_until = (due - self._now).days
                    week = max(0, days_until // 7)
                    if week <= 12:
                        weekly_inflows[week] += remainder

        terms_summary = []
        for name, data in terms_data.items():
            terms_summary.append({
                "payment_term": name,
                "invoice_count": data["count"],
                "total_net_revenue": round(data["total_net"], 2),
                "outstanding": round(data["outstanding"], 2),
            })
        terms_summary.sort(key=lambda t: -t["total_net_revenue"])

        # Build weekly forecast
        inflow_forecast = []
        for week in range(13):
            inflow_forecast.append({
                "week": week,
                "label": "This week" if week == 0 else f"Week +{week}",
                "expected_inflow": round(weekly_inflows.get(week, 0), 2),
            })

        total_expected = sum(w["expected_inflow"] for w in inflow_forecast)

        return {
            "payment_terms": terms_summary,
            "weekly_inflow_forecast": inflow_forecast,
            "total_expected_12_weeks": round(total_expected, 2),
        }

    # ------------------------------------------------------------------
    # Full Analysis
    # ------------------------------------------------------------------

    def run_full_analysis(self, invoice_details: list[dict] = None) -> dict:
        """Run all financial analysis modules."""
        logger.info("Running financial analysis on %d invoices, %d customers...",
                     len(self.invoices), len(self.customers))

        revenue = self.get_revenue_summary()
        receivables = self.get_accounts_receivable()
        customers = self.get_customer_profitability()
        cash_flow = self.get_cash_flow_timing()

        product_revenue = None
        if invoice_details:
            product_revenue = self.get_product_revenue(invoice_details)

        # Top-level health metrics
        total_rev = revenue["total_net_revenue"]
        outstanding = receivables["total_outstanding"]
        overdue = receivables["total_overdue"]

        return {
            "generated_at": self._now.isoformat(),
            "summary": {
                "total_net_revenue": total_rev,
                "total_invoices": revenue["total_invoices"],
                "avg_monthly_revenue": revenue["avg_monthly_net"],
                "total_outstanding": outstanding,
                "total_overdue": overdue,
                "overdue_ratio": round(overdue / outstanding * 100, 1) if outstanding else 0,
                "total_customers": len(self.customers),
                "active_customers": len([c for c in customers if c["invoice_count"] > 0]),
            },
            "revenue": revenue,
            "accounts_receivable": receivables,
            "customer_profitability": customers,
            "product_revenue": product_revenue,
            "cash_flow": cash_flow,
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_date(val) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            return datetime.strptime(val[:19], fmt[:len(val[:19]) + 2])
        except (ValueError, IndexError):
            continue
    return None
