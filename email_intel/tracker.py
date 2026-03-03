"""Pending Order Tracker — manages inbound supplier orders.

Tracks orders that have been placed with the Turkish supplier but haven't
arrived yet. Feeds this data into the Print Forecaster so it can subtract
"stock in transit" from its reorder suggestions.

Data flow:
  1. Email parser extracts orders from sent emails
  2. User confirms/edits the parsed quantities (via UI)
  3. Tracker stores confirmed pending orders
  4. Print Forecaster queries tracker for inbound stock per design
  5. Orders are auto-archived when their expected delivery date passes

Storage: In-memory dict (survives within process, lost on restart).
For persistence, the confirmed orders are also written to a JSON file.
"""

import json
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Where to persist pending orders between restarts
PENDING_ORDERS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "pending_orders.json"
)


class PendingOrderTracker:
    """Manages pending supplier orders."""

    def __init__(self, lead_time_weeks: int = 5):
        self.lead_time_weeks = lead_time_weeks
        self._orders = {}  # order_id -> order dict
        self._load_from_disk()

    # ------------------------------------------------------------------
    # Add / update / remove orders
    # ------------------------------------------------------------------

    def add_order_from_email(self, parsed_email: dict,
                             confirmed_items: list[dict] = None) -> str:
        """Add a pending order from a parsed email.

        Args:
            parsed_email: Output from OrderEmailParser.parse_order_email()
            confirmed_items: Optional user-confirmed items (overrides parsed).
                             Each: {design, quantity, matched_product}

        Returns:
            Order ID.
        """
        email_id = parsed_email.get("email_id", "")
        order_id = f"email_{email_id[:20]}" if email_id else f"manual_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        items = confirmed_items or parsed_email.get("items", [])
        order_date = parsed_email.get("date", datetime.utcnow().isoformat())

        # Calculate expected delivery
        if isinstance(order_date, str):
            try:
                dt = datetime.fromisoformat(order_date.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                dt = datetime.utcnow()
        else:
            dt = order_date

        expected_delivery = dt + timedelta(weeks=self.lead_time_weeks)

        self._orders[order_id] = {
            "order_id": order_id,
            "email_id": email_id,
            "subject": parsed_email.get("subject", ""),
            "order_date": dt.isoformat(),
            "expected_delivery": expected_delivery.isoformat(),
            "items": [
                {
                    "design": item.get("design", ""),
                    "quantity": item.get("quantity", 0),
                    "matched_product": item.get("matched_product"),
                }
                for item in items
            ],
            "total_quantity": sum(i.get("quantity", 0) for i in items),
            "status": "in_transit",
            "confirmed": confirmed_items is not None,
            "created_at": datetime.utcnow().isoformat(),
        }

        self._save_to_disk()
        logger.info("Added pending order %s: %d items, %d total qty",
                     order_id, len(items),
                     self._orders[order_id]["total_quantity"])
        return order_id

    def add_manual_order(self, items: list[dict],
                         order_date: str = None,
                         note: str = "") -> str:
        """Add a pending order manually (not from email).

        Args:
            items: [{design: str, quantity: int, matched_product: str|None}]
            order_date: ISO date string (default: now)
            note: Optional note

        Returns:
            Order ID.
        """
        return self.add_order_from_email({
            "email_id": "",
            "subject": note or "Manual order",
            "date": order_date or datetime.utcnow().isoformat(),
            "items": items,
        }, confirmed_items=items)

    def update_order_items(self, order_id: str,
                           items: list[dict]) -> bool:
        """Update the items for an existing order (user correction)."""
        if order_id not in self._orders:
            return False
        self._orders[order_id]["items"] = [
            {
                "design": item.get("design", ""),
                "quantity": item.get("quantity", 0),
                "matched_product": item.get("matched_product"),
            }
            for item in items
        ]
        self._orders[order_id]["total_quantity"] = sum(
            i.get("quantity", 0) for i in items
        )
        self._orders[order_id]["confirmed"] = True
        self._save_to_disk()
        return True

    def mark_received(self, order_id: str) -> bool:
        """Mark an order as received (stock arrived)."""
        if order_id not in self._orders:
            return False
        self._orders[order_id]["status"] = "received"
        self._orders[order_id]["received_at"] = datetime.utcnow().isoformat()
        self._save_to_disk()
        return True

    def delete_order(self, order_id: str) -> bool:
        """Remove an order entirely."""
        if order_id in self._orders:
            del self._orders[order_id]
            self._save_to_disk()
            return True
        return False

    # ------------------------------------------------------------------
    # Query pending orders
    # ------------------------------------------------------------------

    def get_all_pending(self) -> list[dict]:
        """Get all pending (in-transit) orders, sorted by expected delivery."""
        self._auto_archive_old()
        pending = [
            o for o in self._orders.values()
            if o["status"] == "in_transit"
        ]
        pending.sort(key=lambda o: o["expected_delivery"])
        return pending

    def get_inbound_stock(self) -> dict[str, int]:
        """Get total inbound stock per product name.

        Returns: {product_name: total_inbound_quantity}
        Used by PrintForecaster to subtract from reorder suggestions.
        """
        self._auto_archive_old()
        inbound = {}
        for order in self._orders.values():
            if order["status"] != "in_transit":
                continue
            for item in order["items"]:
                # Use matched_product name if available, otherwise the design name
                key = item.get("matched_product") or item.get("design", "")
                if key:
                    inbound[key] = inbound.get(key, 0) + item.get("quantity", 0)
        return inbound

    def get_inbound_for_product(self, product_name: str) -> int:
        """Get inbound quantity for a specific product."""
        inbound = self.get_inbound_stock()
        # Direct match
        if product_name in inbound:
            return inbound[product_name]
        # Case-insensitive partial match
        product_lower = product_name.lower()
        for key, qty in inbound.items():
            if key.lower() in product_lower or product_lower in key.lower():
                return qty
        return 0

    def get_summary(self) -> dict:
        """Summary of all pending orders."""
        pending = self.get_all_pending()
        received = [o for o in self._orders.values() if o["status"] == "received"]
        now = datetime.utcnow()

        arriving_soon = []
        for o in pending:
            try:
                delivery = datetime.fromisoformat(o["expected_delivery"])
                days_left = (delivery - now).days
                if days_left <= 14:
                    arriving_soon.append({
                        **o,
                        "days_until_delivery": max(days_left, 0),
                    })
            except (ValueError, TypeError):
                pass

        return {
            "pending_count": len(pending),
            "total_pending_qty": sum(o["total_quantity"] for o in pending),
            "received_count": len(received),
            "arriving_soon": arriving_soon,
            "orders": pending,
        }

    # ------------------------------------------------------------------
    # Auto-archive
    # ------------------------------------------------------------------

    def _auto_archive_old(self):
        """Auto-mark orders as received if past delivery date + 7 day buffer."""
        now = datetime.utcnow()
        changed = False
        for order in self._orders.values():
            if order["status"] != "in_transit":
                continue
            try:
                delivery = datetime.fromisoformat(order["expected_delivery"])
                if now > delivery + timedelta(days=7):
                    order["status"] = "received"
                    order["auto_archived"] = True
                    changed = True
            except (ValueError, TypeError):
                pass
        if changed:
            self._save_to_disk()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_to_disk(self):
        """Save pending orders to JSON file."""
        try:
            os.makedirs(os.path.dirname(PENDING_ORDERS_FILE), exist_ok=True)
            with open(PENDING_ORDERS_FILE, "w") as f:
                json.dump(self._orders, f, indent=2, default=str)
        except Exception as e:
            logger.warning("Could not save pending orders: %s", e)

    def _load_from_disk(self):
        """Load pending orders from JSON file."""
        try:
            if os.path.exists(PENDING_ORDERS_FILE):
                with open(PENDING_ORDERS_FILE, "r") as f:
                    self._orders = json.load(f)
                logger.info("Loaded %d pending orders from disk",
                            len(self._orders))
        except Exception as e:
            logger.warning("Could not load pending orders: %s", e)
            self._orders = {}
