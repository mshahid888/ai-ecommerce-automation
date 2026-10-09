"""Simulated Shopify adapter (Phase 9).

``SimulatedShopifyAdapter`` serves the SAME demo data as
``DemoStoreAdapter`` but wraps every payload in Shopify-shaped metadata:
``shopify_id`` fields like ``gid://shopify/Order/10482`` and a
``simulated: True`` marker. It proves the pipeline works against the
``StoreIntegration`` interface, not against the demo store directly —
switching backends is one env var (``STORE_BACKEND=shopify_simulated``)
with zero behavior change.

Canonical fields are byte-identical to the demo adapter; only the extra
``shopify_*`` / ``simulated`` keys differ. Nothing here touches a real
Shopify store.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from .base import StoreIntegration
from .demo import DemoStoreAdapter


def _shopify_order_id(order_ref: str | None) -> str:
    return f"gid://shopify/Order/{order_ref or 'unknown'}"


def _decorate_order(order: dict[str, Any] | None) -> dict[str, Any] | None:
    if order is None:
        return None
    decorated = dict(order)
    decorated["shopify_id"] = _shopify_order_id(order.get("order_ref"))
    decorated["shopify_name"] = f"#{order.get('order_ref')}"
    decorated["simulated"] = True
    return decorated


def _decorate_product(product: dict[str, Any] | None) -> dict[str, Any] | None:
    if product is None:
        return None
    decorated = dict(product)
    decorated["shopify_id"] = f"gid://shopify/Product/{product.get('id')}"
    decorated["shopify_handle"] = str(product.get("sku") or "").lower()
    decorated["simulated"] = True
    return decorated


def _decorate_fulfillment(
    fulfillment: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if fulfillment is None:
        return None
    decorated = dict(fulfillment)
    decorated["shopify_id"] = (
        f"gid://shopify/FulfillmentOrder/{fulfillment.get('order_ref')}"
    )
    decorated["simulated"] = True
    return decorated


class SimulatedShopifyAdapter(StoreIntegration):
    """Demo data dressed as Shopify API responses (SIMULATED)."""

    def __init__(self, conn: sqlite3.Connection, store_id: str) -> None:
        super().__init__(store_id)
        # Delegation (not duplication): canonical fields are guaranteed
        # identical to the demo adapter by construction.
        self._inner = DemoStoreAdapter(conn, store_id)

    @property
    def backend_name(self) -> str:
        return "shopify_simulated"

    def get_product(self, sku_or_id: str) -> dict[str, Any] | None:
        return _decorate_product(self._inner.get_product(sku_or_id))

    def search_products(self, query: str) -> list[dict[str, Any]]:
        return [
            decorated
            for product in self._inner.search_products(query)
            if (decorated := _decorate_product(product)) is not None
        ]

    def get_order(self, order_ref: str | None) -> dict[str, Any] | None:
        return _decorate_order(self._inner.get_order(order_ref))

    def list_orders(self, limit: int = 50) -> list[dict[str, Any]]:
        return [
            decorated
            for order in self._inner.list_orders(limit)
            if (decorated := _decorate_order(order)) is not None
        ]

    def get_fulfillment(self, order_ref: str | None) -> dict[str, Any] | None:
        return _decorate_fulfillment(self._inner.get_fulfillment(order_ref))
