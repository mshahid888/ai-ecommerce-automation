"""Order lookup rules (Phase 2).

Deterministic, store-scoped order lookup with light reference
normalization (whitespace, leading zeros). The pipeline never invents
order data: a reference that matches nothing returns None and the caller
asks for clarification instead of guessing.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from ..db.repositories import OrderRepository

_NON_DIGITS_RE = re.compile(r"\D+")


def normalize_order_ref(ref: str | None) -> str | None:
    """Normalize a customer-supplied order reference.

    Keeps digits only and strips leading zeros (``"010482"`` → ``"10482"``).
    Returns None when nothing usable remains.
    """
    if not ref:
        return None
    digits = _NON_DIGITS_RE.sub("", str(ref)).lstrip("0")
    return digits or None


def lookup_order(
    conn: sqlite3.Connection, store_id: str, order_ref: str | None
) -> dict[str, Any] | None:
    """Return the order row for *order_ref* in *store_id*, or None.

    Tries the raw reference first, then the normalized form. Never matches
    across stores — the repository always filters by ``store_id``.
    """
    if not order_ref:
        return None
    repo = OrderRepository(conn)
    direct = repo.find_by_ref(store_id, str(order_ref).strip())
    if direct is not None:
        return direct
    normalized = normalize_order_ref(order_ref)
    if normalized and normalized != str(order_ref).strip():
        return repo.find_by_ref(store_id, normalized)
    return None
