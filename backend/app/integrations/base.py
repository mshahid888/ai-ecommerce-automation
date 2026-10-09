"""Store backend contract (Phase 9).

``StoreIntegration`` is the ONLY way the chat pipeline reads product and
order data. Every store backend — the SQLite demo store, a simulated
Shopify layer, or a real Shopify Admin API connection — implements this
interface, so the pipeline works against the contract, never against a
specific database or API.

Canonical payload shapes (plain dicts, all store-scoped):

Order::

    {
        "order_ref": "10482",        # merchant-facing reference (no "#")
        "status": "shipped",         # processing | shipped | delivered | delayed | cancelled
        "carrier": "DHL",
        "tracking_ref": "DEMO-TRK-10482",
        "eta_date": "2026-10-14",    # ISO date or None
        "total_cents": 3499,
        "currency": "EUR",
    }

Product::

    {
        "id": 1,
        "sku": "MS-AP750",
        "name": "AquaPure 750",
        "description": "Trinkflasche aus Edelstahl, ...",
        "attributes_json": '{"spuelmaschinengeeignet": true, ...}',
    }

Fulfillment (``None`` when the order has no tracking information yet)::

    {
        "order_ref": "10482",
        "carrier": "DHL",
        "tracking_ref": "DEMO-TRK-10482",
        "eta_date": "2026-10-14",
    }

Adapters may attach EXTRA keys (e.g. ``shopify_id`` on the simulated
adapter) — the pipeline reads only the canonical keys above.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IntegrationError(Exception):
    """A store backend failed (network, permissions, bad payload)."""


class IntegrationConfigError(IntegrationError):
    """The backend is not configured (missing env vars, etc.)."""


class StoreIntegration(ABC):
    """Contract every store backend must satisfy. All methods are
    store-scoped: implementations must never return another store's data.
    """

    def __init__(self, store_id: str) -> None:
        self.store_id = store_id

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Human-readable backend identifier for logs and the timeline."""

    @abstractmethod
    def get_product(self, sku_or_id: str) -> dict[str, Any] | None:
        """Return the canonical product dict for *sku_or_id*, or None."""

    @abstractmethod
    def search_products(self, query: str) -> list[dict[str, Any]]:
        """Return canonical product dicts matching *query*, best first."""

    @abstractmethod
    def get_order(self, order_ref: str | None) -> dict[str, Any] | None:
        """Return the canonical order dict for *order_ref*, or None."""

    @abstractmethod
    def list_orders(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the newest canonical order dicts, at most *limit*."""

    @abstractmethod
    def get_fulfillment(self, order_ref: str | None) -> dict[str, Any] | None:
        """Return the canonical fulfillment dict for *order_ref*, or None
        when no tracking/carrier information is available."""
