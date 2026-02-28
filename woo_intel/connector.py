"""WooCommerce REST API connector.

Pulls products, orders, categories, and customer data from one or more
WooCommerce stores.  Handles pagination, caching, and rate limits.

Usage:
    woo = WooConnector(url="https://jydskstoflager.dk",
                       key="ck_xxx", secret="cs_xxx")
    products = woo.get_all_products()
    orders   = woo.get_orders(days_back=365)
"""

import logging
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class WooConnector:
    """Thin wrapper around the WooCommerce REST API v3."""

    API_VERSION = "wc/v3"

    def __init__(self, url: str, key: str, secret: str, timeout: int = 30):
        self.base_url = url.rstrip("/")
        self.auth = HTTPBasicAuth(key, secret)
        self.timeout = timeout
        self._session = requests.Session()
        self._session.auth = self.auth
        self._session.headers.update({
            "User-Agent": "FabricTrendSpotter/1.0",
            "Accept": "application/json",
        })

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _endpoint(self, path: str) -> str:
        return f"{self.base_url}/wp-json/{self.API_VERSION}/{path}"

    def _get(self, path: str, params: dict = None) -> list | dict:
        url = self._endpoint(path)
        resp = self._session.get(url, params=params or {}, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _get_paginated(self, path: str, params: dict = None,
                       max_pages: int = 50) -> list:
        """Fetch all pages of a paginated WooCommerce endpoint."""
        params = dict(params or {})
        params.setdefault("per_page", 100)
        all_items = []
        page = 1
        while page <= max_pages:
            params["page"] = page
            try:
                resp = self._session.get(
                    self._endpoint(path), params=params, timeout=self.timeout
                )
                resp.raise_for_status()
                items = resp.json()
                if not items:
                    break
                all_items.extend(items)
                total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
                if page >= total_pages:
                    break
                page += 1
                time.sleep(0.3)  # polite rate limiting
            except requests.RequestException as e:
                logger.warning("WooCommerce API page %d failed: %s", page, e)
                break
        return all_items

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    def get_all_products(self, status: str = "publish") -> list[dict]:
        """Fetch all published products with full metadata."""
        logger.info("Fetching all products from %s...", self.base_url)
        products = self._get_paginated("products", {"status": status})
        logger.info("Fetched %d products", len(products))
        return [self._normalize_product(p) for p in products]

    def _normalize_product(self, raw: dict) -> dict:
        """Extract the fields we care about from a WooCommerce product."""
        categories = [c["name"] for c in raw.get("categories", [])]
        tags = [t["name"] for t in raw.get("tags", [])]
        images = [img["src"] for img in raw.get("images", [])]
        attrs = {}
        for a in raw.get("attributes", []):
            attrs[a["name"].lower()] = a.get("options", [])

        return {
            "id": raw["id"],
            "name": raw.get("name", ""),
            "slug": raw.get("slug", ""),
            "sku": raw.get("sku", ""),
            "status": raw.get("status", ""),
            "price": _safe_float(raw.get("price")),
            "regular_price": _safe_float(raw.get("regular_price")),
            "sale_price": _safe_float(raw.get("sale_price")),
            "on_sale": raw.get("on_sale", False),
            "stock_quantity": raw.get("stock_quantity") or 0,
            "stock_status": raw.get("stock_status", ""),
            "manage_stock": raw.get("manage_stock", False),
            "categories": categories,
            "tags": tags,
            "images": images,
            "attributes": attrs,
            "date_created": raw.get("date_created", ""),
            "date_modified": raw.get("date_modified", ""),
            "total_sales": raw.get("total_sales", 0),
            "average_rating": raw.get("average_rating", "0"),
            "rating_count": raw.get("rating_count", 0),
            "permalink": raw.get("permalink", ""),
            # Fabric-specific extraction (supports DK/DE/EN attribute names)
            "color": _extract_attribute(attrs, [
                "farve", "vare farve", "color", "colour", "farbe",
            ]),
            "pattern": _extract_attribute(attrs, [
                "mønster", "pattern", "print", "muster", "design",
            ]),
            "fabric_type": _extract_attribute(attrs, [
                "materialer", "materiale", "material", "fabric", "stof", "stoff",
            ]),
            "jersey_or_woven": _extract_attribute(attrs, [
                "jersey / fast", "jersey/fast", "type",
            ]),
            "properties": _extract_attribute(attrs, [
                "egenskaber", "properties", "eigenschaften",
            ]),
            "certification": _extract_attribute(attrs, [
                "certifikat", "certification", "zertifikat",
            ]),
            "weight_gsm": _extract_attribute(attrs, [
                "weight", "gsm", "vægt", "gewicht", "gram",
            ]),
            "width_cm": _extract_attribute(attrs, [
                "width", "bredde", "breite",
            ]),
            "length_options": _extract_attribute(attrs, [
                "længde", "length", "länge",
            ]),
        }

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def get_orders(self, days_back: int = 365, status: str = None) -> list[dict]:
        """Fetch orders from the last N days."""
        after = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        params = {"after": after, "orderby": "date", "order": "desc"}
        if status:
            params["status"] = status
        else:
            params["status"] = "completed,processing,refunded"

        logger.info("Fetching orders since %s from %s...", after[:10], self.base_url)
        raw_orders = self._get_paginated("orders", params)
        logger.info("Fetched %d orders", len(raw_orders))
        return [self._normalize_order(o) for o in raw_orders]

    def _normalize_order(self, raw: dict) -> dict:
        """Extract the fields we care about from a WooCommerce order."""
        items = []
        for li in raw.get("line_items", []):
            items.append({
                "product_id": li.get("product_id"),
                "name": li.get("name", ""),
                "sku": li.get("sku", ""),
                "quantity": li.get("quantity", 0),
                "subtotal": _safe_float(li.get("subtotal")),
                "total": _safe_float(li.get("total")),
                "price": _safe_float(li.get("price")),
            })

        billing = raw.get("billing", {})
        shipping = raw.get("shipping", {})

        return {
            "id": raw["id"],
            "status": raw.get("status", ""),
            "date_created": raw.get("date_created", ""),
            "date_completed": raw.get("date_completed"),
            "total": _safe_float(raw.get("total")),
            "discount_total": _safe_float(raw.get("discount_total")),
            "shipping_total": _safe_float(raw.get("shipping_total")),
            "currency": raw.get("currency", "DKK"),
            "payment_method": raw.get("payment_method", ""),
            "customer_id": raw.get("customer_id", 0),
            "billing_country": billing.get("country", ""),
            "shipping_country": shipping.get("country", ""),
            "items": items,
            "item_count": sum(i["quantity"] for i in items),
            "is_b2b": _detect_b2b(raw),
        }

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    def get_categories(self) -> list[dict]:
        """Fetch all product categories."""
        return self._get_paginated("products/categories")

    # ------------------------------------------------------------------
    # Store summary (quick health check)
    # ------------------------------------------------------------------

    def get_store_summary(self) -> dict:
        """Quick health check — product count, recent order count, totals."""
        try:
            products = self._get("reports/products/totals")
            orders = self._get("reports/orders/totals")
            return {
                "connected": True,
                "url": self.base_url,
                "product_totals": products,
                "order_totals": orders,
            }
        except Exception as e:
            return {"connected": False, "url": self.base_url, "error": str(e)}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _safe_float(val) -> float:
    try:
        return float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0


def _extract_attribute(attrs: dict, keys: list) -> str:
    """Try multiple attribute names (handles DK/DE/EN variations)."""
    for k in keys:
        if k in attrs and attrs[k]:
            val = attrs[k]
            return val[0] if isinstance(val, list) else str(val)
    return ""


def _detect_b2b(order: dict) -> bool:
    """Heuristic: B2B orders often have a company name or VAT number."""
    billing = order.get("billing", {})
    if billing.get("company"):
        return True
    for meta in order.get("meta_data", []):
        key = meta.get("key", "").lower()
        if any(term in key for term in ["vat", "cvr", "company", "ust", "btw"]):
            return True
    return False
