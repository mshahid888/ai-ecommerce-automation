"""Order lookup rules (stub).

Phase 1: ``lookup_order`` is a thin, documented pass-through. The real
lookup against the order repository (exact match, fuzzy handling of
whitespace/leading zeros, multi-order disambiguation) lands in Phase 4.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from ..db.repositories import OrderRepository


def lookup_order(
    conn: sqlite3.Connection, store_id: str, order_ref: str
) -> dict[str, Any] | None:
    """Return the order row for *order_ref* in *store_id*, or None.

    Phase 4 will implement real lookup logic here (normalization, fuzzy
    matching, disambiguation). Until then this performs a plain exact
    repository lookup — the chat pipeline never invents order data.
    """
    return OrderRepository(conn).find_by_ref(store_id, order_ref)
