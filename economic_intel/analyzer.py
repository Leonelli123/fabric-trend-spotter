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
    # Customer Actions (actionable intelligence — the AI advisor)
    # ------------------------------------------------------------------

    def get_customer_actions(self) -> dict:
        """AI business advisor: tells you exactly what to do with each customer.

        Returns:
          - ai_briefing: top priority actions ranked by business impact
          - invest: customers to spend MORE on (rising, loyal, high-potential)
          - stop_spending: customers draining money (low value, bad payers)
          - chase_payment: owes money, ranked by urgency
          - churn_risk: were active, gone quiet — with win-back vs write-off advice
          - revenue_concentration: dependency risk
          - expense_guidance: where to cut costs, where to invest
        """
        customers = self.get_customer_profitability()
        if not customers:
            return self._empty_actions()

        # ── Build per-customer monthly revenue series ──
        customer_monthly = defaultdict(lambda: defaultdict(float))
        customer_invoice_dates = defaultdict(list)
        customer_invoice_amounts = defaultdict(list)
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
            customer_invoice_amounts[cnum].append(inv["net_amount"])

        three_months_ago = self._now - timedelta(days=90)
        six_months_ago = self._now - timedelta(days=180)
        total_revenue = sum(c["net_revenue"] for c in customers) or 1
        avg_revenue_per_customer = total_revenue / max(len(customers), 1)

        # Pre-compute per-customer metrics
        enriched = []
        for c in customers:
            cnum = c["customer_number"]
            dates = sorted(customer_invoice_dates.get(cnum, []))
            if not dates:
                continue

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
            days_as_customer = (self._now - first_invoice).days if first_invoice else 0
            revenue_share = c["net_revenue"] / total_revenue * 100
            amounts = customer_invoice_amounts.get(cnum, [])
            avg_order = sum(amounts) / len(amounts) if amounts else 0

            growth_pct = 0.0
            if older_rev > 0:
                growth_pct = (recent_rev - older_rev) / older_rev * 100
            elif recent_rev > 0:
                growth_pct = 100.0

            enriched.append({
                **c,
                "recent_rev": round(recent_rev, 2),
                "older_rev": round(older_rev, 2),
                "growth_pct": round(growth_pct, 1),
                "days_since_last": days_since_last,
                "days_as_customer": days_as_customer,
                "revenue_share_pct": round(revenue_share, 1),
                "avg_order_value": round(avg_order, 2),
            })

        # ══════════════════════════════════════════════════════
        # INVEST — customers worth spending more money/time on
        # ══════════════════════════════════════════════════════
        invest = []
        for c in enriched:
            verdict = None

            # Rising star: growing fast
            if (c["older_rev"] > 0 and c["growth_pct"] > 30
                    and c["invoice_count"] >= 3 and c["recent_rev"] > 0):
                projected_annual = c["recent_rev"] * 4
                verdict = {
                    "sub_type": "rising_star",
                    "priority": "high",
                    "recommendation": (
                        f"Revenue up {c['growth_pct']:.0f}% this quarter "
                        f"({c['recent_rev']:,.0f} vs {c['older_rev']:,.0f}). "
                        f"At this rate, projected annual value: {projected_annual:,.0f}. "
                        f"Offer volume discount or dedicated account contact to lock in growth."
                    ),
                    "projected_value": round(projected_annual, 2),
                }

            # Loyal high-value: big spender, reliable, recent
            elif (c["net_revenue"] > total_revenue * 0.03
                    and c["payment_reliability"] >= 80
                    and c["invoice_count"] >= 4
                    and c["days_since_last"] < 90):
                verdict = {
                    "sub_type": "loyal_vip",
                    "priority": "high",
                    "recommendation": (
                        f"VIP — {c['revenue_share_pct']}% of total revenue, "
                        f"{c['invoice_count']} orders, always pays (reliability {c['payment_reliability']}/100). "
                        f"Protect at all costs: loyalty pricing, early access to new collections, "
                        f"personal check-in quarterly."
                    ),
                    "projected_value": round(c["monthly_avg_revenue"] * 12, 2),
                }

            # New & promising: fresh customer, already repeat ordering
            elif (c["days_as_customer"] < 120 and c["invoice_count"] >= 2
                  and c["net_revenue"] > 0 and c["payment_reliability"] >= 60):
                run_rate = c["net_revenue"] / max(c["days_as_customer"], 1) * 365
                verdict = {
                    "sub_type": "new_promising",
                    "priority": "medium",
                    "recommendation": (
                        f"New customer ({c['days_as_customer']} days), already "
                        f"{c['invoice_count']} orders for {c['net_revenue']:,.0f}. "
                        f"Annualized run-rate: {run_rate:,.0f}. "
                        f"Personal welcome call, introduce full product range, "
                        f"offer first-year loyalty incentive."
                    ),
                    "projected_value": round(run_rate, 2),
                }

            # Sleeping giant: big historical spender but slowing down
            elif (c["net_revenue"] > total_revenue * 0.02
                    and 60 < c["days_since_last"] <= 150
                    and c["invoice_count"] >= 3):
                verdict = {
                    "sub_type": "sleeping_giant",
                    "priority": "high",
                    "recommendation": (
                        f"Was a big spender ({c['net_revenue']:,.0f} total, "
                        f"{c['revenue_share_pct']}% of revenue) but hasn't ordered "
                        f"in {c['days_since_last']} days. Still winnable — call "
                        f"this week. Offer a \"welcome back\" deal or ask what's changed."
                    ),
                    "projected_value": round(c["monthly_avg_revenue"] * 12, 2),
                }

            if verdict:
                invest.append({**c, **verdict})

        invest.sort(key=lambda x: (-1 if x["priority"] == "high" else 0,
                                    -x.get("projected_value", 0)))

        # ══════════════════════════════════════════════════════
        # STOP SPENDING — customers draining money
        # ══════════════════════════════════════════════════════
        stop_spending = []
        for c in enriched:
            reasons = []
            severity = "info"

            # Tiny spender + bad payer = not worth it
            if (c["net_revenue"] < avg_revenue_per_customer * 0.2
                    and c["payment_reliability"] < 60
                    and c["invoice_count"] >= 2):
                reasons.append(
                    f"Low value ({c['net_revenue']:,.0f} total across "
                    f"{c['invoice_count']} orders) AND unreliable payer "
                    f"(score {c['payment_reliability']}/100)"
                )
                severity = "warning"

            # Owes more than they've ever been worth
            if c["outstanding"] > 0 and c["outstanding"] > c["net_revenue"] * 0.5:
                reasons.append(
                    f"Currently owes {c['outstanding']:,.0f} — that's "
                    f"{c['outstanding'] / max(c['net_revenue'], 1) * 100:.0f}% of "
                    f"their total lifetime revenue"
                )
                severity = "critical"

            # Declining + small = not worth chasing
            if (c["growth_pct"] < -30 and c["net_revenue"] < avg_revenue_per_customer * 0.5
                    and c["invoice_count"] >= 3):
                reasons.append(
                    f"Spending declining {c['growth_pct']:.0f}% and below-average value"
                )

            # Very old, one-time tiny order = dead weight
            if (c["invoice_count"] == 1
                    and c["days_since_last"] > 180
                    and c["net_revenue"] < avg_revenue_per_customer * 0.3):
                reasons.append(
                    f"Single order of {c['net_revenue']:,.0f} over "
                    f"{c['days_since_last']} days ago — never came back"
                )

            if reasons:
                if c["outstanding"] > 0:
                    action = (
                        f"Stop extending credit. Collect the {c['outstanding']:,.0f} "
                        f"owed, then require prepayment for any future orders."
                    )
                elif len(reasons) >= 2 or severity == "critical":
                    action = (
                        f"Stop investing time and marketing spend on this customer. "
                        f"Don't chase, don't discount — let them self-serve or move on."
                    )
                else:
                    action = (
                        f"Deprioritize — no special treatment, discounts, or outreach. "
                        f"Serve if they order, but don't spend energy chasing."
                    )

                stop_spending.append({
                    **c,
                    "severity": severity,
                    "problems": reasons,
                    "recommendation": ". ".join(reasons) + ". " + action,
                    "money_at_risk": round(c["outstanding"], 2),
                })

        stop_spending.sort(key=lambda x: (
            0 if x["severity"] == "critical" else 1 if x["severity"] == "warning" else 2,
            -x["money_at_risk"],
        ))

        # ══════════════════════════════════════════════════════
        # CHASE PAYMENT — who owes money, ranked by urgency
        # ══════════════════════════════════════════════════════
        chase_payment = []
        for c in enriched:
            if c["outstanding"] <= 0:
                continue
            if c["overdue_invoices"] <= 0 and c["payment_reliability"] >= 80:
                continue  # Not yet due and reliable — don't nag

            if c["overdue_invoices"] >= 3 or c["outstanding"] > 15000:
                severity = "critical"
                action = (
                    f"URGENT: Owes {c['outstanding']:,.0f} with "
                    f"{c['overdue_invoices']} overdue invoices. "
                    f"Call today. If no response within 48h, send formal "
                    f"demand letter and pause all new orders."
                )
            elif c["payment_reliability"] < 50:
                severity = "critical"
                action = (
                    f"Chronic late payer (reliability {c['payment_reliability']}/100) "
                    f"owes {c['outstanding']:,.0f}. Switch to prepayment terms "
                    f"for all future orders. Chase current balance now."
                )
            elif c["overdue_invoices"] >= 1:
                severity = "warning"
                action = (
                    f"Owes {c['outstanding']:,.0f} — {c['overdue_invoices']} invoice(s) "
                    f"overdue. Send reminder email today. "
                    f"Follow up by phone if unpaid within 7 days."
                )
            else:
                severity = "info"
                action = (
                    f"Outstanding {c['outstanding']:,.0f} (not yet overdue). "
                    f"Reliability: {c['payment_reliability']}/100. Monitor."
                )

            chase_payment.append({
                **c,
                "severity": severity,
                "recommendation": action,
            })

        chase_payment.sort(key=lambda x: (
            0 if x["severity"] == "critical" else 1 if x["severity"] == "warning" else 2,
            -x["outstanding"],
        ))

        # ══════════════════════════════════════════════════════
        # CHURN RISK — with win-back vs write-off recommendation
        # ══════════════════════════════════════════════════════
        churn_risk = []
        for c in enriched:
            if c["days_since_last"] < 90 or c["invoice_count"] < 2:
                continue
            if c["net_revenue"] < total_revenue * 0.005:
                continue  # Too small to worry about

            was_valuable = c["net_revenue"] > avg_revenue_per_customer
            long_gone = c["days_since_last"] > 180

            if was_valuable and not long_gone:
                severity = "critical"
                action = (
                    f"CALL THIS WEEK. Spent {c['net_revenue']:,.0f} across "
                    f"{c['invoice_count']} orders but silent for {c['days_since_last']} "
                    f"days. They were {c['revenue_share_pct']}% of your revenue. "
                    f"Personal outreach — ask what's changed. Offer a returning customer "
                    f"incentive worth up to {c['monthly_avg_revenue'] * 0.5:,.0f}."
                )
            elif was_valuable and long_gone:
                severity = "warning"
                action = (
                    f"Big former customer ({c['net_revenue']:,.0f} lifetime) gone "
                    f"{c['days_since_last']} days. Win-back is still worth trying — "
                    f"send a personal email with new collection preview. "
                    f"If no response after 2 attempts, mark as lost and stop spending."
                )
            elif not was_valuable and long_gone:
                severity = "info"
                action = (
                    f"Small customer ({c['net_revenue']:,.0f}), gone {c['days_since_last']} "
                    f"days. Write off — don't spend resources chasing. "
                    f"Include in bulk re-engagement email at most."
                )
            else:
                severity = "info"
                action = (
                    f"No orders in {c['days_since_last']} days (spent {c['net_revenue']:,.0f} "
                    f"previously). Add to automated win-back email sequence."
                )

            churn_risk.append({
                **c,
                "severity": severity,
                "recommendation": action,
            })

        churn_risk.sort(key=lambda x: (
            0 if x["severity"] == "critical" else 1 if x["severity"] == "warning" else 2,
            -x["net_revenue"],
        ))

        # ══════════════════════════════════════════════════════
        # REVENUE CONCENTRATION RISK
        # ══════════════════════════════════════════════════════
        sorted_by_rev = sorted(enriched, key=lambda c: -c["net_revenue"])
        top5_rev = sum(c["net_revenue"] for c in sorted_by_rev[:5])
        top5_pct = top5_rev / total_revenue * 100 if total_revenue else 0
        top10_rev = sum(c["net_revenue"] for c in sorted_by_rev[:10])
        top10_pct = top10_rev / total_revenue * 100 if total_revenue else 0

        if top5_pct > 60:
            concentration_risk = "critical"
            concentration_advice = (
                f"DANGEROUS: Top 5 customers = {top5_pct:.0f}% of all revenue. "
                f"Losing one could cripple the business. Actively diversify — "
                f"invest in acquiring new B2B accounts and growing mid-tier customers."
            )
        elif top5_pct > 40:
            concentration_risk = "warning"
            concentration_advice = (
                f"Top 5 = {top5_pct:.0f}% of revenue. Moderate risk. "
                f"Focus on growing customers ranked 6-20 to reduce dependency."
            )
        else:
            concentration_risk = "low"
            concentration_advice = (
                f"Revenue is well distributed (top 5 = {top5_pct:.0f}%). "
                f"Healthy diversification."
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

        # ══════════════════════════════════════════════════════
        # EXPENSE GUIDANCE — where to cut, where to spend
        # ══════════════════════════════════════════════════════
        receivables = self.get_accounts_receivable()
        total_overdue = receivables["total_overdue"]
        total_outstanding = receivables["total_outstanding"]
        overdue_pct = (total_overdue / total_outstanding * 100) if total_outstanding else 0

        guidance = []

        # Collection pressure
        if overdue_pct > 30:
            guidance.append({
                "priority": "critical",
                "area": "Collections",
                "action": (
                    f"CUT THE BLEEDING: {overdue_pct:.0f}% of outstanding invoices are "
                    f"overdue ({total_overdue:,.0f} of {total_outstanding:,.0f}). "
                    f"Pause new orders for worst offenders. Escalate 90+ day invoices "
                    f"to formal collection. This is money you've already earned — go get it."
                ),
            })
        elif overdue_pct > 15:
            guidance.append({
                "priority": "warning",
                "area": "Collections",
                "action": (
                    f"{overdue_pct:.0f}% overdue rate ({total_overdue:,.0f}). "
                    f"Set up automated reminders at 7, 14, 30 days. "
                    f"Call anyone over 60 days personally."
                ),
            })

        # Revenue trend
        revenue = self.get_revenue_summary()
        growth_data = revenue.get("growth", [])
        if len(growth_data) >= 3:
            recent_growth = [g["growth_pct"] for g in growth_data[-3:]]
            avg_growth = sum(recent_growth) / len(recent_growth)
            if avg_growth < -5:
                # Calculate how much lost
                monthly_data = revenue.get("monthly", [])
                if len(monthly_data) >= 4:
                    peak = max(m.get("net_amount", 0) for m in monthly_data[-6:])
                    current = monthly_data[-1].get("net_amount", 0) if monthly_data else 0
                    lost_monthly = peak - current
                else:
                    lost_monthly = 0
                guidance.append({
                    "priority": "critical",
                    "area": "Revenue Decline",
                    "action": (
                        f"INVEST IN SALES: Revenue down {avg_growth:.1f}% avg "
                        f"over last 3 months"
                        + (f" (losing ~{lost_monthly:,.0f}/month vs recent peak). " if lost_monthly > 0 else ". ")
                        + f"Check churn risk list — your lost customers ARE your "
                        f"growth opportunity. Winning one back is cheaper than "
                        f"finding a new one."
                    ),
                })
            elif avg_growth < 0:
                guidance.append({
                    "priority": "warning",
                    "area": "Revenue Softening",
                    "action": (
                        f"Revenue drifting down ({avg_growth:.1f}% avg). "
                        f"Upsell to VIP/nurture customers — they already trust you. "
                        f"Introduce them to product lines they haven't tried."
                    ),
                })
            elif avg_growth > 10:
                guidance.append({
                    "priority": "good",
                    "area": "Revenue Growth",
                    "action": (
                        f"Strong growth ({avg_growth:.1f}% avg last 3 months). "
                        f"Now is the time to invest — add stock for bestsellers, "
                        f"lock in your rising stars with volume deals."
                    ),
                })

        # Payment terms
        cash_flow = self.get_cash_flow_timing()
        terms = cash_flow.get("payment_terms", [])
        long_terms = [t for t in terms
                      if any(x in str(t.get("payment_term", "")) for x in ("60", "90"))]
        if long_terms:
            long_outstanding = sum(t["outstanding"] for t in long_terms)
            if long_outstanding > 0:
                guidance.append({
                    "priority": "info",
                    "area": "Cash Flow",
                    "action": (
                        f"SPEED UP CASH: {long_outstanding:,.0f} tied up in "
                        f"60-90 day payment terms. Offer 2% early-payment discount "
                        f"— you'll recover the money faster than any marketing spend."
                    ),
                })

        # Stop spending advice based on stop_spending list
        total_at_risk = sum(c["money_at_risk"] for c in stop_spending)
        if stop_spending and total_at_risk > 0:
            guidance.append({
                "priority": "warning",
                "area": "Cut Losses",
                "action": (
                    f"STOP SPENDING on {len(stop_spending)} unprofitable customers "
                    f"({total_at_risk:,.0f} at risk). "
                    f"Redirect that energy to your invest list — every hour spent "
                    f"on a dead-end customer is an hour stolen from a rising star."
                ),
            })

        # Invest advice
        invest_projected = sum(c.get("projected_value", 0) for c in invest[:5])
        if invest and invest_projected > 0:
            guidance.append({
                "priority": "good",
                "area": "Invest",
                "action": (
                    f"DOUBLE DOWN on your top {min(len(invest), 5)} invest targets — "
                    f"projected combined annual value: {invest_projected:,.0f}. "
                    f"Personal outreach, volume incentives, and priority service "
                    f"will compound your returns."
                ),
            })

        if not guidance:
            guidance.append({
                "priority": "good",
                "area": "Overall",
                "action": (
                    "Business looks healthy. Keep monitoring weekly. "
                    "Focus on growing mid-tier customers to reduce concentration risk."
                ),
            })

        # ══════════════════════════════════════════════════════
        # AI BRIEFING — the 5 most important things right now
        # ══════════════════════════════════════════════════════
        briefing = self._build_ai_briefing(
            invest, stop_spending, chase_payment, churn_risk,
            concentration, guidance, total_revenue, total_overdue,
        )

        return {
            "ai_briefing": briefing,
            "invest": invest[:15],
            "stop_spending": stop_spending[:15],
            "chase_payment": chase_payment[:15],
            "churn_risk": churn_risk[:15],
            "revenue_concentration": concentration,
            "expense_guidance": guidance,
            "summary": {
                "invest_count": len(invest),
                "stop_spending_count": len(stop_spending),
                "chase_payment_count": len(chase_payment),
                "churn_risk_count": len(churn_risk),
                "concentration_risk": concentration_risk,
                "total_at_risk": round(total_at_risk, 2),
                "total_projected_invest": round(invest_projected, 2),
                "total_overdue": round(total_overdue, 2),
            },
        }

    def _build_ai_briefing(self, invest, stop_spending, chase_payment,
                           churn_risk, concentration, guidance,
                           total_revenue, total_overdue) -> list[dict]:
        """Build the top-priority action list — the morning briefing."""
        items = []

        # 1. Critical payments to chase
        critical_chase = [c for c in chase_payment if c["severity"] == "critical"]
        if critical_chase:
            total_critical = sum(c["outstanding"] for c in critical_chase)
            names = ", ".join(c["name"] for c in critical_chase[:3])
            items.append({
                "priority": 1,
                "icon": "money",
                "severity": "critical",
                "title": f"Collect {total_critical:,.0f} in critical overdue payments",
                "detail": (
                    f"{len(critical_chase)} customer(s) with urgent overdue invoices: "
                    f"{names}. Call today — every day you wait reduces your "
                    f"chance of collecting."
                ),
            })

        # 2. Critical churn risk (valuable customers going quiet)
        critical_churn = [c for c in churn_risk if c["severity"] == "critical"]
        if critical_churn:
            lost_value = sum(c["net_revenue"] for c in critical_churn)
            names = ", ".join(c["name"] for c in critical_churn[:3])
            items.append({
                "priority": 2,
                "icon": "alert",
                "severity": "critical",
                "title": f"Win back {lost_value:,.0f} in at-risk customer revenue",
                "detail": (
                    f"{len(critical_churn)} valuable customer(s) going quiet: {names}. "
                    f"Personal outreach this week — they represent "
                    f"{lost_value / total_revenue * 100:.1f}% of your revenue."
                ),
            })

        # 3. Invest in rising stars
        high_invest = [c for c in invest if c["priority"] == "high"]
        if high_invest:
            upside = sum(c.get("projected_value", 0) for c in high_invest[:5])
            names = ", ".join(c["name"] for c in high_invest[:3])
            items.append({
                "priority": 3,
                "icon": "invest",
                "severity": "good",
                "title": f"Invest in {len(high_invest)} high-potential customers",
                "detail": (
                    f"Your best growth opportunities: {names}. "
                    f"Projected annual value: {upside:,.0f}. "
                    f"Volume discounts, personal contact, priority service."
                ),
            })

        # 4. Stop spending on drains
        critical_stops = [c for c in stop_spending if c["severity"] in ("critical", "warning")]
        if critical_stops:
            wasted = sum(c["money_at_risk"] for c in critical_stops)
            items.append({
                "priority": 4,
                "icon": "cut",
                "severity": "warning",
                "title": f"Stop spending on {len(critical_stops)} unprofitable customers",
                "detail": (
                    f"These customers are draining resources with {wasted:,.0f} at risk. "
                    f"Require prepayment or deprioritize. Redirect effort to invest list."
                ),
            })

        # 5. Concentration warning
        if concentration["risk_level"] == "critical":
            items.append({
                "priority": 5,
                "icon": "warning",
                "severity": "warning",
                "title": "Revenue dangerously concentrated",
                "detail": concentration["advice"],
            })

        # 6. Top guidance item
        crit_guidance = [g for g in guidance if g["priority"] == "critical"]
        for g in crit_guidance:
            if not any(g["area"].lower() in (i.get("title", "").lower()) for i in items):
                items.append({
                    "priority": 6,
                    "icon": "guidance",
                    "severity": "critical",
                    "title": g["area"],
                    "detail": g["action"],
                })

        # If nothing urgent, add a positive note
        if not items:
            items.append({
                "priority": 1,
                "icon": "good",
                "severity": "good",
                "title": "Business is in good shape",
                "detail": (
                    "No critical actions needed. Focus on growing mid-tier customers "
                    "and maintaining your VIP relationships."
                ),
            })

        items.sort(key=lambda x: x["priority"])
        return items[:6]

    def _empty_actions(self) -> dict:
        return {
            "ai_briefing": [{
                "priority": 1, "icon": "info", "severity": "info",
                "title": "Not enough data yet",
                "detail": "Load financial data to generate actionable intelligence.",
            }],
            "invest": [], "stop_spending": [], "churn_risk": [],
            "chase_payment": [],
            "revenue_concentration": {
                "risk_level": "unknown", "advice": "Not enough data.",
                "top5_revenue": 0, "top5_pct": 0, "top10_revenue": 0,
                "top10_pct": 0, "top_customers": [],
            },
            "expense_guidance": [],
            "summary": {
                "invest_count": 0, "stop_spending_count": 0,
                "chase_payment_count": 0, "churn_risk_count": 0,
                "concentration_risk": "unknown", "total_at_risk": 0,
                "total_projected_invest": 0, "total_overdue": 0,
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
