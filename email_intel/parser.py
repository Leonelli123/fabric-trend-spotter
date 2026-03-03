"""Order Email Parser — extracts design names and quantities from supplier emails.

Parses freeform English order emails sent to the Turkish supplier.
Looks for patterns like:
  - "200m Design Name"
  - "Design Name - 150 meters"
  - "Design Name: 100m"
  - "Design Name  200"
  - Tabular formats (Design | Qty | ...)

Also extracts order metadata: date, subject, whether it's a reorder or new order.
"""

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# Patterns to match quantities in various formats
# Group 1: quantity, Group 2: unit (optional), rest: design context
QTY_PATTERNS = [
    # "200m Design Name" or "200 m Design Name" or "200 meters Design Name"
    re.compile(
        r"(\d+)\s*(?:m(?:eters?)?|metre?s?)\s+[–\-]?\s*(.+)",
        re.IGNORECASE,
    ),
    # "Design Name - 200m" or "Design Name: 200 m"
    re.compile(
        r"(.+?)\s*[:\-–]\s*(\d+)\s*(?:m(?:eters?)?|metre?s?)\b",
        re.IGNORECASE,
    ),
    # "Design Name  200m" or "Design Name  200 meters" (2+ spaces, then qty+unit)
    re.compile(
        r"(.+?)\s{2,}(\d+)\s*(?:m(?:eters?)?|metre?s?)\s*$",
        re.IGNORECASE,
    ),
    # "Design Name  200" (number at end of line, no unit, 2+ spaces)
    re.compile(
        r"(.+?)\s{2,}(\d+)\s*$",
        re.IGNORECASE,
    ),
    # "Design Name (200m)" or "Design Name [200m]"
    re.compile(
        r"(.+?)\s*[\(\[]\s*(\d+)\s*(?:m(?:eters?)?|metre?s?)?\s*[\)\]]",
        re.IGNORECASE,
    ),
    # "Design Name x200" or "Design Name x 200" (quantity prefix)
    re.compile(
        r"(.+?)\s+x\s*(\d+)\s*(?:m(?:eters?)?|metre?s?)?\s*$",
        re.IGNORECASE,
    ),
]

# Words that indicate this line is NOT a design (headers, signatures, etc.)
NOISE_WORDS = {
    "hi", "hello", "dear", "regards", "best", "thanks", "thank", "please",
    "order", "total", "subject", "from", "to", "date", "sent", "kind",
    "sincerely", "cheers", "attached", "invoice", "payment", "price",
    "delivery", "shipping", "address", "phone", "email", "note", "notes",
    "summary", "qty", "quantity", "design", "name", "sku", "ref",
}

# Minimum quantity to consider valid (avoid parsing phone numbers etc.)
MIN_QTY = 10
MAX_QTY = 10000


def parse_order_email(email: dict, product_names: list[str] = None) -> dict:
    """Parse a single email and extract order line items.

    Args:
        email: Dict with 'subject', 'body_text', 'date', 'id'.
        product_names: Optional list of known product names from WooCommerce
                       to help match fuzzy design names.

    Returns:
        Dict with:
          - email_id, subject, date
          - items: [{design, quantity, confidence, matched_product}]
          - is_order: bool (does this look like an order email?)
          - raw_text: the email body
    """
    subject = email.get("subject", "")
    body = email.get("body_text", "") or email.get("body_preview", "")
    date = email.get("date", "")

    # Check if this looks like an order email
    is_order = _is_order_email(subject, body)

    # Extract line items
    items = []
    if is_order:
        items = _extract_items_from_body(body, product_names)

    # Try to detect if this is a reorder vs new order
    is_reorder = bool(re.search(
        r"\b(re[\-\s]?order|restock|additional|more of|repeat)\b",
        subject + " " + body[:200],
        re.IGNORECASE,
    ))

    return {
        "email_id": email.get("id", ""),
        "subject": subject,
        "date": date,
        "items": items,
        "total_quantity": sum(i["quantity"] for i in items),
        "is_order": is_order,
        "is_reorder": is_reorder,
        "item_count": len(items),
        "raw_text": body[:2000],  # Cap for display
    }


def parse_multiple_emails(emails: list[dict],
                          product_names: list[str] = None) -> list[dict]:
    """Parse a list of emails and return order data for each.

    Filters to only emails that look like orders.
    """
    results = []
    for email in emails:
        parsed = parse_order_email(email, product_names)
        results.append(parsed)

    # Sort: most likely orders first, then by date
    results.sort(key=lambda r: (not r["is_order"], r["date"]), reverse=True)
    return results


def _is_order_email(subject: str, body: str) -> bool:
    """Heuristic: does this email look like a supplier order?"""
    text = (subject + " " + body[:500]).lower()

    # Strong signals
    order_signals = [
        r"\border\b",
        r"\breorder\b",
        r"\bquantit(?:y|ies)\b",
        r"\bmeters?\b",
        r"\bmetre?s?\b",
        r"\b\d+\s*m\b",
        r"\bdesigns?\b",
        r"\bprints?\b",
        r"\bfabric\b",
        r"\bjersey\b",
        r"\bplease\s+(?:send|prepare|produce)\b",
        r"\bstock\b",
        r"\brestock\b",
    ]
    signal_count = sum(1 for p in order_signals if re.search(p, text))

    # If subject contains "order" or "reorder", strong signal
    if re.search(r"\b(?:re)?order\b", subject.lower()):
        signal_count += 3

    # If there are numbers followed by 'm' or 'meters' in the body
    qty_matches = re.findall(r"\b\d{2,4}\s*m(?:eters?)?\b", text)
    if len(qty_matches) >= 2:
        signal_count += 2

    return signal_count >= 3


def _extract_items_from_body(body: str, product_names: list[str] = None) -> list[dict]:
    """Extract design + quantity pairs from the email body."""
    items = []
    seen_designs = set()

    # Build product name lookup for fuzzy matching
    name_lookup = {}
    if product_names:
        for name in product_names:
            # Create simplified keys for matching
            key = _simplify_name(name)
            if key:
                name_lookup[key] = name

    lines = body.split("\n")
    for line in lines:
        line = line.strip()
        if not line or len(line) < 5 or len(line) > 200:
            continue

        # Skip obvious non-data lines
        first_word = line.split()[0].lower().rstrip(",:;")
        if first_word in NOISE_WORDS:
            continue

        # Try each pattern
        for pattern in QTY_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue

            groups = match.groups()
            if len(groups) < 2:
                continue

            # Figure out which group is the quantity and which is the design
            qty_str, design = _identify_qty_and_design(groups)
            if not qty_str or not design:
                continue

            try:
                qty = int(qty_str)
            except ValueError:
                continue

            if qty < MIN_QTY or qty > MAX_QTY:
                continue

            # Clean up design name
            design = _clean_design_name(design)
            if not design or len(design) < 3:
                continue

            # Deduplicate
            design_key = _simplify_name(design)
            if design_key in seen_designs:
                continue
            seen_designs.add(design_key)

            # Try to match to a known WooCommerce product
            matched_product = _fuzzy_match_product(design, name_lookup)
            confidence = "high" if matched_product else "medium"

            items.append({
                "design": design,
                "quantity": qty,
                "confidence": confidence,
                "matched_product": matched_product,
                "raw_line": line.strip(),
            })
            break  # Found a match for this line, move to next

    return items


def _identify_qty_and_design(groups: tuple) -> tuple[str, str]:
    """Determine which matched group is the quantity and which is the design."""
    # If first group is a number, it's the quantity
    if groups[0].strip().isdigit():
        return groups[0].strip(), groups[1].strip() if len(groups) > 1 else ""
    # If second group is a number, it's the quantity
    if len(groups) > 1 and groups[1].strip().isdigit():
        return groups[1].strip(), groups[0].strip()
    # Ambiguous — try both
    for g in groups:
        g = g.strip()
        if g.isdigit() and MIN_QTY <= int(g) <= MAX_QTY:
            other = [x.strip() for x in groups if x.strip() != g]
            return g, other[0] if other else ""
    return "", ""


def _clean_design_name(name: str) -> str:
    """Clean up a parsed design name."""
    # Remove leading/trailing punctuation and whitespace
    name = re.sub(r"^[\s\-–:,.\|]+", "", name)
    name = re.sub(r"[\s\-–:,.\|]+$", "", name)
    # Remove common noise prefixes
    name = re.sub(r"^(?:design|print|fabric|jersey)\s*[:\-–]\s*",
                  "", name, flags=re.IGNORECASE)
    # Remove quantity-like suffixes that leaked in
    name = re.sub(r"\s*\d+\s*(?:m|meters?|metre?s?)?\s*$", "", name,
                  flags=re.IGNORECASE)
    return name.strip()


def _simplify_name(name: str) -> str:
    """Create a simplified key for fuzzy matching."""
    name = name.lower()
    # Remove common prefixes
    name = re.sub(r"^(?:cotton\s+)?(?:jersey\s+)?(?:print\s+)?(?:[-–]\s*)?",
                  "", name)
    # Remove non-alphanumeric
    name = re.sub(r"[^a-z0-9\s]", "", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _fuzzy_match_product(design: str, name_lookup: dict) -> str | None:
    """Try to match a parsed design name to a known WooCommerce product.

    Uses simplified name matching — not perfect but catches most cases.
    """
    if not name_lookup:
        return None

    design_key = _simplify_name(design)
    if not design_key:
        return None

    # Exact match on simplified name
    if design_key in name_lookup:
        return name_lookup[design_key]

    # Partial match: does the design key appear IN a product name or vice versa?
    best_match = None
    best_overlap = 0
    design_words = set(design_key.split())

    for key, full_name in name_lookup.items():
        product_words = set(key.split())
        overlap = len(design_words & product_words)
        # Need at least 2 matching words for confidence
        if overlap >= 2 and overlap > best_overlap:
            best_overlap = overlap
            best_match = full_name

    return best_match
