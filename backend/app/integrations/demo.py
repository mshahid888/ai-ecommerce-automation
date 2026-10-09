"""Demo store adapter (Phase 9).

``DemoStoreAdapter`` is a thin ``StoreIntegration`` wrapper around the
existing SQLite demo-store queries. It adds NO new behavior: order lookup
keeps the raw-then-normalized reference logic from
``rules/order_rules.py``, product search keeps the token-overlap ranking
from ``rules/product_rules.py``. The pipeline gets the same data it
always did — now through the interface instead of direct DB calls.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from ..db.repositories import OrderRepository, ProductRepository
from ..rules import product_rules
from ..rules.order_rules import lookup_order
from .base import StoreIntegration


class DemoStoreAdapter(StoreIntegration):
    """Serves the SQLite demo store through the ``StoreIntegration``
    contract."""

    def __init__(self, conn: sqlite3.Connection, store_id: str) -> None:
        super().__init__(store_id)
        self.conn = conn
        self._orders = OrderRepository(conn)
        self._products = ProductRepository(conn)

    @property
    def backend_name(self) -> str:
        return "demo"

    def get_product(self, sku_or_id: str) -> dict[str, Any] | None:
        key = (sku_or_id or "").strip()
        if not key:
            return None
        row = self.conn.execute(
            "SELECT * FROM products WHERE store_id = ? AND sku = ?",
            (self.store_id, key),
        ).fetchone()
        if row is None and key.isdigit():
            row = self.conn.execute(
                "SELECT * FROM products WHERE store_id = ? AND id = ?",
                (self.store_id, int(key)),
            ).fetchone()
        return dict(row) if row is not None else None

    def search_products(self, query: str) -> list[dict[str, Any]]:
        # Best match first — the pipeline takes matches[0], which is
        # exactly what product_rules.find_product() returned before.
        return product_rules.rank_products(self.conn, self.store_id, query or "")

    def get_order(self, order_ref: str | None) -> dict[str, Any] | None:
        # lookup_order() tries the raw reference first, then the
        # normalized form — behavior unchanged from before Phase 9.
        return lookup_order(self.conn, self.store_id, order_ref)

    def list_orders(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._orders.list(self.store_id, limit=max(1, int(limit)))

    def get_fulfillment(self, order_ref: str | None) -> dict[str, Any] | None:
        order = self.get_order(order_ref)
        if order is None:
            return None
        carrier = order.get("carrier")
        tracking_ref = order.get("tracking_ref")
        eta_date = order.get("eta_date")
        if not carrier and not tracking_ref:
            # Nothing to report — the caller treats this as "no
            # tracking information available yet".
            return None
        return {
            "order_ref": order.get("order_ref"),
            "carrier": carrier,
            "tracking_ref": tracking_ref,
            "eta_date": eta_date,
        }
