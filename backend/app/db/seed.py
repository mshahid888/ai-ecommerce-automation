"""Demo data seeding.

``create_demo_store`` wipes and re-seeds ONLY rows belonging to the demo
store (``demo-muster-shop``, ``is_demo=1``). Real (non-demo) rows are never
touched, so ``POST /api/demo/reset`` is safe against tenant data.
"""

from __future__ import annotations

import json
import sqlite3

DEMO_STORE_ID = "demo-muster-shop"

_PRODUCTS = [
    {
        "sku": "MS-AF750",
        "name": "AquaFlasche 750ml",
        "description": (
            "Isolierte Trinkflasche aus Edelstahl, 750 ml, hält 24h kalt / 12h warm."
        ),
        "attributes_json": json.dumps(
            {
                "spuelmaschinengeeignet": True,
                "material": "Edelstahl",
                "volumen_ml": 750,
            }
        ),
    },
    {
        "sku": "MS-SB30",
        "name": "Solarbank 30000mAh",
        "description": (
            "Powerbank mit Solarpanel, 30000 mAh, USB-C Schnellladung."
        ),
        "attributes_json": json.dumps(
            {
                "kapazitaet_mah": 30000,
                "anschluss": "USB-C",
                "solarpanel": True,
            }
        ),
    },
    {
        "sku": "MS-KM100",
        "name": "Kaffeemühle manuell",
        "description": (
            "Manuelle Kaffeemühle mit Keramikmahlwerk, stufenlos einstellbar."
        ),
        "attributes_json": json.dumps(
            {
                "mahlwerk": "Keramik",
                "einstellung": "stufenlos",
                "material": "Edelstahl/Holz",
            }
        ),
    },
    {
        "sku": "MS-LD200",
        "name": "LED-Schreibtischlampe",
        "description": (
            "Dimmbare LED-Schreibtischlampe mit 3 Farbtemperaturen."
        ),
        "attributes_json": json.dumps(
            {
                "dimmbar": True,
                "farbtemperaturen": 3,
                "leistung_w": 12,
            }
        ),
    },
]

_CUSTOMERS = [
    {"name": "Max Mustermann", "email": "max.mustermann@example.de"},
    {"name": "Erika Musterfrau", "email": "erika.musterfrau@example.de"},
]

_ORDERS = [
    {
        "order_ref": "10482",
        "customer": "Max Mustermann",
        "status": "shipped",
        "carrier": "DHL",
        "tracking_ref": "DEMO-TRK-0048217",
        "eta_date": "2026-10-14",
        "total_cents": 3499,
        "currency": "EUR",
    },
    {
        "order_ref": "10483",
        "customer": "Erika Musterfrau",
        "status": "processing",
        "carrier": None,
        "tracking_ref": None,
        "eta_date": "2026-10-16",
        "total_cents": 5999,
        "currency": "EUR",
    },
    {
        "order_ref": "10471",
        "customer": "Max Mustermann",
        "status": "delivered",
        "carrier": "DHL",
        "tracking_ref": "DEMO-TRK-0047110",
        "eta_date": "2026-10-02",
        "total_cents": 1299,
        "currency": "EUR",
    },
]

_RETURNS_POLICY = {
    "widerrufsfrist_tage": 14,
    "ruecksendeadresse": "Muster-Shop GmbH, Retouren, Musterstraße 1, 37073 Göttingen",
    "ausnahmen": ["versiegelte Hygieneartikel"],
    "status": "stub_phase_5",
}


def _wipe_demo_rows(conn: sqlite3.Connection) -> None:
    conn.execute(
        "DELETE FROM workflow_events WHERE store_id = ?", (DEMO_STORE_ID,)
    )
    conn.execute("DELETE FROM tickets WHERE store_id = ?", (DEMO_STORE_ID,))
    conn.execute(
        "DELETE FROM return_requests WHERE store_id = ?", (DEMO_STORE_ID,)
    )
    conn.execute("DELETE FROM orders WHERE store_id = ?", (DEMO_STORE_ID,))
    conn.execute("DELETE FROM products WHERE store_id = ?", (DEMO_STORE_ID,))
    conn.execute("DELETE FROM customers WHERE store_id = ?", (DEMO_STORE_ID,))
    conn.execute("DELETE FROM conversations WHERE store_id = ?", (DEMO_STORE_ID,))
    conn.execute(
        "DELETE FROM store_policies WHERE store_id = ?", (DEMO_STORE_ID,)
    )
    conn.execute(
        "DELETE FROM integration_credentials WHERE store_id = ?", (DEMO_STORE_ID,)
    )
    conn.execute("DELETE FROM stores WHERE id = ?", (DEMO_STORE_ID,))


def create_demo_store(conn: sqlite3.Connection) -> str:
    """Wipe and re-seed the demo store. Idempotent; demo-only rows only."""
    _wipe_demo_rows(conn)
    conn.execute(
        "INSERT INTO stores (id, name, slug, is_demo) VALUES (?, ?, ?, 1)",
        (DEMO_STORE_ID, "Muster-Shop GmbH", "demo-muster-shop"),
    )

    customer_ids: dict[str, int] = {}
    for customer in _CUSTOMERS:
        cur = conn.execute(
            "INSERT INTO customers (store_id, name, email, is_demo) "
            "VALUES (?, ?, ?, 1)",
            (DEMO_STORE_ID, customer["name"], customer["email"]),
        )
        customer_ids[customer["name"]] = cur.lastrowid  # type: ignore[assignment]

    for product in _PRODUCTS:
        conn.execute(
            "INSERT INTO products "
            "(store_id, sku, name, description, attributes_json, is_demo) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (
                DEMO_STORE_ID,
                product["sku"],
                product["name"],
                product["description"],
                product["attributes_json"],
            ),
        )

    for order in _ORDERS:
        conn.execute(
            "INSERT INTO orders (store_id, order_ref, customer_id, status, "
            "carrier, tracking_ref, eta_date, total_cents, currency, is_demo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (
                DEMO_STORE_ID,
                order["order_ref"],
                customer_ids[order["customer"]],
                order["status"],
                order["carrier"],
                order["tracking_ref"],
                order["eta_date"],
                order["total_cents"],
                order["currency"],
            ),
        )

    conn.execute(
        "INSERT INTO store_policies (store_id, policy_key, policy_json) "
        "VALUES (?, 'returns', ?)",
        (DEMO_STORE_ID, json.dumps(_RETURNS_POLICY)),
    )
    conn.commit()
    return DEMO_STORE_ID
