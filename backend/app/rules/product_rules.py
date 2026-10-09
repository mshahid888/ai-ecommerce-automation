"""Product catalogue lookup and attribute answering (Phase 2).

Deterministic, store-scoped. Every answer is grounded in the store's
configured product rows (name, description, ``attributes_json``) — this
module never invents specifications. When a requested attribute is not in
the catalogue, the caller answers honestly ("information not available")
and offers human escalation.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

_TOKEN_RE = re.compile(r"[a-zäöüß0-9]+", re.IGNORECASE)

# Message keywords → attribute key in ``attributes_json``. Order matters:
# longer, more specific keywords are listed before their prefixes.
_ATTRIBUTE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("spuelmaschinengeeignet", ("spülmaschinengeeignet", "spülmaschine", "dishwasher-safe", "dishwasher")),
    ("volumen_ml", ("volumen", "fassungsvermögen", "volume", "capacity")),
    ("kapazitaet_mah", ("kapazität", "mah", "capacity")),
    ("isolierung", ("isoliert", "isolierung", "insulated", "insulation")),
    ("material", ("material",)),
    ("farbtemperaturen", ("farbtemperatur", "color temperature", "colour temperature")),
    ("dimmbar", ("dimmbar", "dimmable")),
    ("leistung_w", ("leistung", "watt", "power")),
    ("anschluss", ("anschluss", "connector", "port")),
    ("solarpanel", ("solarpanel", "solar", "solar panel")),
    ("mahlwerk", ("mahlwerk", "burr", "grinder")),
    ("einstellung", ("einstellung", "einstellbar", "adjustment", "adjustable")),
    ("farbe", ("farbe", "farb", "color", "colour", "colors", "colours")),
)

_UNIT_SUFFIXES = {
    "volumen_ml": "ml",
    "kapazitaet_mah": "mAh",
    "leistung_w": "W",
}

# Special stock display (not a plain unit suffix).
_STOCK_KEY = "bestand_stueck"

# German display labels for known attribute keys.
_ATTRIBUTE_LABELS = {
    "spuelmaschinengeeignet": "Dishwasher-safe",
    "material": "Material",
    "volumen_ml": "Volume",
    "kapazitaet_mah": "Capacity",
    "isolierung": "Insulation",
    "anschluss": "Connector",
    "solarpanel": "Solar panel",
    "mahlwerk": "Burr",
    "einstellung": "Adjustment",
    "dimmbar": "Dimmable",
    "farbtemperaturen": "Color temperatures",
    "leistung_w": "Power",
    "farbe": "Color",
    "bestand_stueck": "Availability",
}


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= 4]


def rank_products(
    conn: sqlite3.Connection, store_id: str, message: str
) -> list[dict[str, Any]]:
    """Return all matching products, best match first.

    Same deterministic token-overlap score as :func:`find_product`;
    rows with no overlap are excluded. The store adapters use this so
    the pipeline can pick the first (best) match through the
    ``StoreIntegration`` interface instead of querying the DB directly.
    """
    message_tokens = set(_tokens(message))
    if not message_tokens:
        return []
    rows = conn.execute(
        "SELECT * FROM products WHERE store_id = ?", (store_id,)
    ).fetchall()
    scored: list[tuple[int, sqlite3.Row]] = []
    for row in rows:
        haystack = set(_tokens(f"{row['name'] or ''} {row['description'] or ''}"))
        score = len(message_tokens & haystack)
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [dict(row) for _, row in scored]


def find_product(
    conn: sqlite3.Connection, store_id: str, message: str
) -> dict[str, Any] | None:
    """Return the best-matching product row for *message*, or None.

    Deterministic token-overlap match over product name + description.
    Returns None when nothing matches — the caller then asks the customer
    which product they mean instead of guessing.
    """
    matches = rank_products(conn, store_id, message)
    return matches[0] if matches else None


def product_attributes(product: dict[str, Any]) -> dict[str, Any]:
    """Parse a product's ``attributes_json`` into a dict (never raises)."""
    try:
        parsed = json.loads(product.get("attributes_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def detect_requested_attributes(message: str) -> list[str]:
    """Attribute keys the customer message asks about (may be empty)."""
    text = message.lower()
    return [
        key
        for key, keywords in _ATTRIBUTE_KEYWORDS
        if any(kw in text for kw in keywords)
    ]


def format_attribute_value(key: str, value: Any) -> str:
    """Render an attribute value in German demo-suitable text."""
    if key == _STOCK_KEY:
        try:
            units = int(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{units} units in stock" if units > 0 else "currently out of stock"
    if isinstance(value, bool):
        return "yes" if value else "no"
    unit = _UNIT_SUFFIXES.get(key)
    return f"{value} {unit}" if unit else str(value)


def stock_level(product: dict[str, Any]) -> int | None:
    """Return the product's demo stock level, or None when not configured."""
    attrs = product_attributes(product)
    try:
        return int(attrs[_STOCK_KEY])
    except (TypeError, ValueError, KeyError):
        return None


def attribute_label(key: str) -> str:
    return _ATTRIBUTE_LABELS.get(key, key)
