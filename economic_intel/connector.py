"""Visma e-conomic REST API connector.

Read-only connector for pulling invoices, customers, products, and payment
data from e-conomic.  Uses the proprietary two-token auth model:
  - X-AppSecretToken  (identifies the app)
  - X-AgreementGrantToken  (identifies the customer agreement)

Both tokens are long-lived (no expiry).  We only use GET requests —
this connector can NEVER create, modify, or delete anything in e-conomic.

Usage:
    eco = EconomicConnector(
        app_secret="your_app_secret",
        grant_token="your_grant_token",
    )
    invoices = eco.get_booked_invoices(days_back=365)
    customers = eco.get_customers()
"""

import logging
import time
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://restapi.e-conomic.com"


class EconomicConnector:
    """Read-only connector for the Visma e-conomic REST API."""

    def __init__(self, app_secret: str, grant_token: str, timeout: int = 30):
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "X-AppSecretToken": app_secret,
            "X-AgreementGrantToken": grant_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict = None) -> dict:
        """GET a single resource or the first page of a collection."""
        url = f"{BASE_URL}/{path.lstrip('/')}"
        resp = self._session.get(url, params=params or {}, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _get_paginated(self, path: str, params: dict = None,
                       max_pages: int = 100) -> list[dict]:
        """Fetch all pages of a paginated e-conomic collection.

        e-conomic uses cursor-based pagination via the 'pagination' key in the
        response, with a 'nextPage' URL for the next batch.
        """
        params = dict(params or {})
        params.setdefault("pagesize", 100)
        url = f"{BASE_URL}/{path.lstrip('/')}"
        all_items = []
        page = 0

        while url and page < max_pages:
            try:
                resp = self._session.get(url, params=params if page == 0 else {},
                                         timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()

                items = data.get("collection", [])
                all_items.extend(items)

                # Follow pagination
                pagination = data.get("pagination", {})
                url = pagination.get("nextPage")
                page += 1
                time.sleep(0.2)  # polite rate limiting
            except requests.RequestException as e:
                logger.warning("e-conomic API page %d failed: %s", page, e)
                break

        return all_items

    # ------------------------------------------------------------------
    # Invoices (booked = finalized/sent)
    # ------------------------------------------------------------------

    def get_booked_invoices(self, days_back: int = 365) -> list[dict]:
        """Fetch all booked (finalized) invoices from the last N days."""
        since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        logger.info("Fetching booked invoices since %s...", since)

        raw = self._get_paginated(
            "invoices/booked",
            params={"filter": f"date$gte:{since}", "sort": "-date"},
        )
        logger.info("Fetched %d booked invoices", len(raw))
        return [self._normalize_invoice(inv) for inv in raw]

    def get_booked_invoice_detail(self, invoice_number: int) -> dict:
        """Fetch full line-item detail for a single booked invoice."""
        data = self._get(f"invoices/booked/{invoice_number}")
        return self._normalize_invoice_detail(data)

    def get_draft_invoices(self) -> list[dict]:
        """Fetch current draft (not yet sent) invoices."""
        raw = self._get_paginated("invoices/drafts")
        logger.info("Fetched %d draft invoices", len(raw))
        return [self._normalize_invoice(inv) for inv in raw]

    def _normalize_invoice(self, raw: dict) -> dict:
        """Extract key fields from an invoice summary."""
        customer = raw.get("customer", {})
        return {
            "invoice_number": raw.get("bookedInvoiceNumber") or raw.get("draftInvoiceNumber"),
            "date": raw.get("date", ""),
            "due_date": raw.get("dueDate", ""),
            "currency": raw.get("currency", "DKK"),
            "net_amount": raw.get("netAmount", 0),
            "vat_amount": raw.get("vatAmount", 0),
            "gross_amount": raw.get("grossAmount", 0),
            "remainder": raw.get("remainder", 0),
            "is_paid": raw.get("remainder", 0) == 0 and raw.get("grossAmount", 0) > 0,
            "customer_number": customer.get("customerNumber"),
            "customer_name": customer.get("name", ""),
            "payment_terms": raw.get("paymentTerms", {}).get("name", ""),
            "pdf_link": raw.get("pdf", {}).get("download"),
        }

    def _normalize_invoice_detail(self, raw: dict) -> dict:
        """Full invoice with line items."""
        base = self._normalize_invoice(raw)
        lines = []
        for line in raw.get("lines", []):
            product = line.get("product", {})
            lines.append({
                "line_number": line.get("lineNumber", 0),
                "product_number": product.get("productNumber", ""),
                "product_name": line.get("description", ""),
                "quantity": line.get("quantity", 0),
                "unit_net_price": line.get("unitNetPrice", 0),
                "total_net_amount": line.get("totalNetAmount", 0),
                "discount_pct": line.get("discountPercentage", 0),
                "unit": line.get("unit", {}).get("name", ""),
            })
        base["lines"] = lines
        return base

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------

    def get_customers(self) -> list[dict]:
        """Fetch all customers."""
        logger.info("Fetching customers from e-conomic...")
        raw = self._get_paginated("customers")
        logger.info("Fetched %d customers", len(raw))
        return [self._normalize_customer(c) for c in raw]

    def _normalize_customer(self, raw: dict) -> dict:
        return {
            "customer_number": raw.get("customerNumber"),
            "name": raw.get("name", ""),
            "email": raw.get("email", ""),
            "phone": raw.get("telephoneAndFaxNumber", ""),
            "address": raw.get("address", ""),
            "city": raw.get("city", ""),
            "zip": raw.get("zip", ""),
            "country": raw.get("country", ""),
            "currency": raw.get("currency", "DKK"),
            "credit_limit": raw.get("creditLimit"),
            "balance": raw.get("balance", 0),
            "payment_terms": raw.get("paymentTerms", {}).get("name", ""),
            "customer_group": raw.get("customerGroup", {}).get("name", ""),
            "is_barred": raw.get("barred", False),
            "last_updated": raw.get("lastUpdated", ""),
        }

    # ------------------------------------------------------------------
    # Products (e-conomic product register)
    # ------------------------------------------------------------------

    def get_products(self) -> list[dict]:
        """Fetch all products from the e-conomic product register."""
        logger.info("Fetching products from e-conomic...")
        raw = self._get_paginated("products")
        logger.info("Fetched %d products", len(raw))
        return [self._normalize_product(p) for p in raw]

    def _normalize_product(self, raw: dict) -> dict:
        return {
            "product_number": raw.get("productNumber", ""),
            "name": raw.get("name", ""),
            "description": raw.get("description", ""),
            "sales_price": raw.get("salesPrice", 0),
            "cost_price": raw.get("costPrice", 0),
            "recommended_price": raw.get("recommendedPrice", 0),
            "barred": raw.get("barred", False),
            "product_group": raw.get("productGroup", {}).get("name", ""),
            "unit": raw.get("unit", {}).get("name", ""),
            "inventory_amount": raw.get("inventory", {}).get("amount"),
        }

    # ------------------------------------------------------------------
    # Accounts / Payment info
    # ------------------------------------------------------------------

    def get_entries(self, days_back: int = 365) -> list[dict]:
        """Fetch journal entries (payments, etc.) from the last N days."""
        since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        raw = self._get_paginated(
            "journals-experimental",
        )
        # Entries are nested under journals → vouchers → entries
        # For a simpler approach we use the accounts endpoint
        return raw

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    def test_connection(self) -> dict:
        """Quick health check — can we reach e-conomic?"""
        try:
            data = self._get("self")
            agreement = data.get("agreementNumber", "unknown")
            company = data.get("companyName", "unknown")
            return {
                "connected": True,
                "agreement_number": agreement,
                "company_name": company,
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
            }
