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
    ("spuelmaschinengeeignet", ("spülmaschinengeeignet", "spülmaschine")),
    ("volumen_ml", ("volumen", "fassungsvermögen")),
    ("kapazitaet_mah", ("kapazität", "mah")),
    ("isolierung", ("isoliert", "isolierung")),
    ("material", ("material",)),
    ("farbtemperaturen", ("farbtemperatur",)),
    ("dimmbar", ("dimmbar",)),
    ("leistung_w", ("leistung", "watt")),
    ("anschluss", ("anschluss",)),
    ("solarpanel", ("solarpanel", "solar")),
    ("mahlwerk", ("mahlwerk",)),
    ("einstellung", ("einstellung", "einstellbar")),
    ("farbe", ("farbe", "farb")),
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
    "spuelmaschinengeeignet": "spülmaschinengeeignet",
    "material": "Material",
    "volumen_ml": "Volumen",
    "kapazitaet_mah": "Kapazität",
    "isolierung": "Isolierung",
    "anschluss": "Anschluss",
    "solarpanel": "Solarpanel",
    "mahlwerk": "Mahlwerk",
    "einstellung": "Einstellung",
    "dimmbar": "dimmbar",
    "farbtemperaturen": "Farbtemperaturen",
    "leistung_w": "Leistung",
    "farbe": "Farbe",
    "bestand_stueck": "Verfügbarkeit",
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
        return f"{units} Stück auf Lager" if units > 0 else "derzeit nicht auf Lager"
    if isinstance(value, bool):
        return "ja" if value else "nein"
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
