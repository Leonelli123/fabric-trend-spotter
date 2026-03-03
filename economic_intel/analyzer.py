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
    # Customer Actions (actionable intelligence)
    # ------------------------------------------------------------------

    def get_customer_actions(self) -> dict:
        """Classify every customer into actionable buckets.

        Returns a dict of action lists:
          - rising_stars: growing fast, invest in them
          - nurture: high-value loyal customers to protect
          - churn_risk: were active, gone quiet — win them back
          - chase_payment: owe money, pay late
          - new_potential: recently appeared, show promise
          - revenue_concentration: dependency risk analysis
          - expense_guidance: overall spending/collection recommendations
        """
        customers = self.get_customer_profitability()
        if not customers:
            return self._empty_actions()

        # ── Build per-customer monthly revenue series ──
        customer_monthly = defaultdict(lambda: defaultdict(float))
        customer_invoice_dates = defaultdict(list)
        for inv in self.invoices:
            cnum = inv["customer_number"]
            if not cnum:
                continue
            date = _parse_date(inv["date"])
            if not date:
                continue
            key = date.strftime("%Y-%m")
            customer_monthly[cnum][key] += inv["net_amount"]
            customer_invoice_dates[cnum].append(date)

        # Recent vs older split: last 3 months vs previous 3 months
        three_months_ago = self._now - timedelta(days=90)
        six_months_ago = self._now - timedelta(days=180)

        total_revenue = sum(c["net_revenue"] for c in customers) or 1

        rising_stars = []
        nurture = []
        churn_risk = []
        chase_payment = []
        new_potential = []

        for c in customers:
            cnum = c["customer_number"]
            dates = sorted(customer_invoice_dates.get(cnum, []))
            if not dates:
                continue

            # Revenue in recent 3mo vs previous 3mo
            recent_rev = sum(
                amt for month, amt in customer_monthly[cnum].items()
                if _parse_date(month + "-01") and _parse_date(month + "-01") >= three_months_ago
            )
            older_rev = sum(
                amt for month, amt in customer_monthly[cnum].items()
                if _parse_date(month + "-01")
                and six_months_ago <= _parse_date(month + "-01") < three_months_ago
            )

            last_invoice = _parse_date(c["last_invoice"]) if c["last_invoice"] else None
            first_invoice = _parse_date(c["first_invoice"]) if c["first_invoice"] else None
            days_since_last = (self._now - last_invoice).days if last_invoice else 999
            revenue_share = c["net_revenue"] / total_revenue * 100

            # ── CHASE PAYMENT: owes money and pays late ──
            if c["outstanding"] > 0 and c["payment_reliability"] < 70:
                severity = "critical" if c["overdue_invoices"] >= 3 or c["outstanding"] > 10000 else "warning"
                chase_payment.append({
                    **c,
                    "action": "CHASE_PAYMENT",
                    "severity": severity,
                    "reason": (
                        f"Owes {c['outstanding']:,.0f} with {c['overdue_invoices']} overdue invoices. "
                        f"Reliability score: {c['payment_reliability']}/100. "
                        f"{'Demand prepayment or tighten terms.' if severity == 'critical' else 'Send reminder and follow up.'}"
                    ),
                    "revenue_share_pct": round(revenue_share, 1),
                })
            elif c["outstanding"] > 0 and c["overdue_invoices"] > 0:
                chase_payment.append({
                    **c,
                    "action": "CHASE_PAYMENT",
                    "severity": "info",
                    "reason": (
                        f"Owes {c['outstanding']:,.0f} — {c['overdue_invoices']} overdue. "
                        f"Reliability {c['payment_reliability']}/100. Gentle reminder."
                    ),
                    "revenue_share_pct": round(revenue_share, 1),
                })

            # ── RISING STAR: revenue growing significantly ──
            if (older_rev > 0 and recent_rev > older_rev * 1.3
                    and c["invoice_count"] >= 3 and recent_rev > 0):
                growth_pct = (recent_rev - older_rev) / older_rev * 100
                rising_stars.append({
                    **c,
                    "action": "RISING_STAR",
                    "recent_revenue": round(recent_rev, 2),
                    "previous_revenue": round(older_rev, 2),
                    "growth_pct": round(growth_pct, 1),
                    "reason": (
                        f"Revenue up {growth_pct:.0f}% in the last 3 months "
                        f"({recent_rev:,.0f} vs {older_rev:,.0f} previous quarter). "
                        f"Invest in this relationship — offer volume discounts or priority service."
                    ),
                    "revenue_share_pct": round(revenue_share, 1),
                })
            # New customer showing promise
            elif (first_invoice and (self._now - first_invoice).days < 120
                  and c["invoice_count"] >= 2 and c["net_revenue"] > 0):
                new_potential.append({
                    **c,
                    "action": "NEW_POTENTIAL",
                    "recent_revenue": round(recent_rev, 2),
                    "reason": (
                        f"New customer ({(self._now - first_invoice).days} days), "
                        f"already {c['invoice_count']} orders for {c['net_revenue']:,.0f}. "
                        f"Welcome outreach — personal contact, introduction to full range."
                    ),
                    "revenue_share_pct": round(revenue_share, 1),
                })

            # ── NURTURE: high-value, loyal, consistent ──
            if (c["net_revenue"] > total_revenue * 0.03
                    and c["payment_reliability"] >= 80
                    and c["invoice_count"] >= 4
                    and days_since_last < 90):
                nurture.append({
                    **c,
                    "action": "NURTURE",
                    "reason": (
                        f"Top customer — {revenue_share:.1f}% of your revenue, "
                        f"{c['invoice_count']} orders, reliability {c['payment_reliability']}/100. "
                        f"Protect this relationship. Consider loyalty pricing or early access to new stock."
                    ),
                    "revenue_share_pct": round(revenue_share, 1),
                })

            # ── CHURN RISK: was active, gone quiet ──
            if (c["invoice_count"] >= 2
                    and days_since_last > 90
                    and c["net_revenue"] > total_revenue * 0.01):
                urgency = "critical" if days_since_last > 180 else "warning"
                churn_risk.append({
                    **c,
                    "action": "CHURN_RISK",
                    "severity": urgency,
                    "days_since_last": days_since_last,
                    "reason": (
                        f"No orders in {days_since_last} days but previously spent "
                        f"{c['net_revenue']:,.0f} across {c['invoice_count']} orders. "
                        f"{'Urgent win-back campaign — call directly.' if urgency == 'critical' else 'Send a personal check-in. Offer a returning-customer incentive.'}"
                    ),
                    "revenue_share_pct": round(revenue_share, 1),
                })

        # ── REVENUE CONCENTRATION RISK ──
        sorted_by_rev = sorted(customers, key=lambda c: -c["net_revenue"])
        top5_rev = sum(c["net_revenue"] for c in sorted_by_rev[:5])
        top5_pct = top5_rev / total_revenue * 100 if total_revenue else 0
        top10_rev = sum(c["net_revenue"] for c in sorted_by_rev[:10])
        top10_pct = top10_rev / total_revenue * 100 if total_revenue else 0

        concentration_risk = "low"
        concentration_advice = "Revenue is well distributed across customers."
        if top5_pct > 60:
            concentration_risk = "critical"
            concentration_advice = (
                f"Your top 5 customers make up {top5_pct:.0f}% of all revenue. "
                f"Losing even one would be devastating. Actively diversify — "
                f"invest in acquiring new B2B accounts."
            )
        elif top5_pct > 40:
            concentration_risk = "warning"
            concentration_advice = (
                f"Top 5 customers = {top5_pct:.0f}% of revenue. "
                f"Moderate concentration. Focus on growing your mid-tier accounts."
            )

        concentration = {
            "risk_level": concentration_risk,
            "advice": concentration_advice,
            "top5_revenue": round(top5_rev, 2),
            "top5_pct": round(top5_pct, 1),
            "top10_revenue": round(top10_rev, 2),
            "top10_pct": round(top10_pct, 1),
            "top_customers": [
                {
                    "name": c["name"],
                    "customer_number": c["customer_number"],
                    "net_revenue": c["net_revenue"],
                    "share_pct": round(c["net_revenue"] / total_revenue * 100, 1),
                }
                for c in sorted_by_rev[:10]
            ],
        }

        # ── EXPENSE / COLLECTION GUIDANCE ──
        receivables = self.get_accounts_receivable()
        total_overdue = receivables["total_overdue"]
        total_outstanding = receivables["total_outstanding"]
        overdue_pct = (total_overdue / total_outstanding * 100) if total_outstanding else 0

        guidance = []
        if overdue_pct > 30:
            guidance.append({
                "priority": "critical",
                "area": "Collections",
                "action": (
                    f"{overdue_pct:.0f}% of outstanding invoices are overdue. "
                    f"This is bleeding cash. Pause new orders for worst offenders "
                    f"and escalate collection on 90+ day invoices."
                ),
            })
        elif overdue_pct > 15:
            guidance.append({
                "priority": "warning",
                "area": "Collections",
                "action": (
                    f"{overdue_pct:.0f}% overdue rate is above healthy levels. "
                    f"Set up automated reminders at 7, 14, and 30 days. "
                    f"Personally call anyone over 60 days."
                ),
            })

        # Revenue trend advice
        revenue = self.get_revenue_summary()
        growth_data = revenue.get("growth", [])
        if len(growth_data) >= 3:
            recent_growth = [g["growth_pct"] for g in growth_data[-3:]]
            avg_growth = sum(recent_growth) / len(recent_growth)
            if avg_growth < -5:
                guidance.append({
                    "priority": "critical",
                    "area": "Revenue Decline",
                    "action": (
                        f"Revenue trending down {avg_growth:.1f}% avg over last 3 months. "
                        f"Investigate: are you losing customers, or are existing ones ordering less? "
                        f"Check churn risk list above for leads."
                    ),
                })
            elif avg_growth < 0:
                guidance.append({
                    "priority": "warning",
                    "area": "Revenue Flat/Declining",
                    "action": (
                        f"Revenue slightly declining ({avg_growth:.1f}% avg last 3 months). "
                        f"Focus on upselling to existing nurture customers and "
                        f"converting new potential accounts."
                    ),
                })

        # Payment terms advice
        cash_flow = self.get_cash_flow_timing()
        terms = cash_flow.get("payment_terms", [])
        long_terms = [t for t in terms if "60" in str(t["payment_term"]) or "90" in str(t["payment_term"])]
        if long_terms:
            long_outstanding = sum(t["outstanding"] for t in long_terms)
            if long_outstanding > 0:
                guidance.append({
                    "priority": "info",
                    "area": "Payment Terms",
                    "action": (
                        f"You have {long_outstanding:,.0f} outstanding on long payment terms (60-90 days). "
                        f"Consider offering 2% early-payment discount to accelerate cash flow."
                    ),
                })

        if not guidance:
            guidance.append({
                "priority": "good",
                "area": "Overall",
                "action": "Collections and cash flow look healthy. Keep monitoring monthly.",
            })

        return {
            "rising_stars": sorted(rising_stars, key=lambda x: -x.get("growth_pct", 0)),
            "nurture": sorted(nurture, key=lambda x: -x["net_revenue"]),
            "churn_risk": sorted(churn_risk, key=lambda x: -x["net_revenue"]),
            "chase_payment": sorted(chase_payment, key=lambda x: -x["outstanding"]),
            "new_potential": sorted(new_potential, key=lambda x: -x["net_revenue"]),
            "revenue_concentration": concentration,
            "expense_guidance": guidance,
            "summary": {
                "rising_star_count": len(rising_stars),
                "nurture_count": len(nurture),
                "churn_risk_count": len(churn_risk),
                "chase_payment_count": len(chase_payment),
                "new_potential_count": len(new_potential),
                "concentration_risk": concentration_risk,
            },
        }

    def _empty_actions(self) -> dict:
        return {
            "rising_stars": [], "nurture": [], "churn_risk": [],
            "chase_payment": [], "new_potential": [],
            "revenue_concentration": {
                "risk_level": "unknown", "advice": "Not enough data.",
                "top5_revenue": 0, "top5_pct": 0, "top10_revenue": 0,
                "top10_pct": 0, "top_customers": [],
            },
            "expense_guidance": [],
            "summary": {
                "rising_star_count": 0, "nurture_count": 0,
                "churn_risk_count": 0, "chase_payment_count": 0,
                "new_potential_count": 0, "concentration_risk": "unknown",
            },
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
        customer_actions = self.get_customer_actions()

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
            "customer_actions": customer_actions,
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
