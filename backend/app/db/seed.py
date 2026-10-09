"""Demo data seeding (Phase 2).

``create_demo_store`` wipes and re-seeds ONLY rows belonging to the demo
store (``demo-muster-shop``, ``is_demo=1``). Real (non-demo) rows are never
touched, so ``POST /api/demo/reset`` is safe against tenant data.

All demo content is fictional and clearly labeled: store "Muster-Shop GmbH",
tracking references prefixed ``DEMO-TRK-``, fictional customers, fictional
delivery dates.
"""

from __future__ import annotations

import json
import sqlite3

DEMO_STORE_ID = "demo-muster-shop"

_PRODUCTS = [
    {
        "sku": "MS-AP750",
        "name": "AquaPure 750",
        "description": (
            "Stainless steel water bottle, 750 mL, double-walled insulated — "
            "keeps drinks cold for 24 hours and warm for 12 hours."
        ),
        "attributes_json": json.dumps(
            {
                "spuelmaschinengeeignet": True,
                "material": "stainless steel",
                "volumen_ml": 750,
                "isolierung": "double-walled",
                "bestand_stueck": 42,
            }
        ),
    },
    {
        "sku": "MS-SB30",
        "name": "SolarBank 30000mAh",
        "description": (
            "Power bank with solar panel, 30000 mAh capacity, USB-C fast charging."
        ),
        "attributes_json": json.dumps(
            {
                "kapazitaet_mah": 30000,
                "anschluss": "USB-C",
                "solarpanel": True,
                "bestand_stueck": 15,
            }
        ),
    },
    {
        "sku": "MS-KM100",
        "name": "Manual Coffee Grinder",
        "description": (
            "Manual coffee grinder with ceramic burr, stepless adjustment."
        ),
        "attributes_json": json.dumps(
            {
                "mahlwerk": "Ceramic",
                "einstellung": "stepless",
                "material": "stainless steel/wood",
                "bestand_stueck": 0,
            }
        ),
    },
    {
        "sku": "MS-LD200",
        "name": "LED Desk Lamp",
        "description": (
            "Dimmable LED desk lamp with 3 color temperatures."
        ),
        "attributes_json": json.dumps(
            {
                "dimmbar": True,
                "farbtemperaturen": 3,
                "leistung_w": 12,
                "bestand_stueck": 28,
            }
        ),
    },
]

_CUSTOMERS = [
    {"name": "John Doe", "email": "john.doe@example.com"},
    {"name": "Jane Doe", "email": "jane.doe@example.com"},
]

# Fictional orders for the four demo scenarios. created_at is explicit so
# the deterministic return-policy engine can compute the return window.
_ORDERS = [
    {
        "order_ref": "10482",
        "customer": "John Doe",
        "status": "shipped",
        "carrier": "DHL",
        "tracking_ref": "DEMO-TRK-10482",
        "eta_date": "2026-10-14",
        "total_cents": 3499,
        "currency": "EUR",
        "created_at": "2026-10-06T09:12:00Z",
    },
    {
        "order_ref": "10483",
        "customer": "Jane Doe",
        "status": "processing",
        "carrier": None,
        "tracking_ref": None,
        "eta_date": "2026-10-16",
        "total_cents": 5999,
        "currency": "EUR",
        "created_at": "2026-10-08T14:03:00Z",
    },
    {
        "order_ref": "10471",
        "customer": "John Doe",
        "status": "delivered",
        "carrier": "DHL",
        "tracking_ref": "DEMO-TRK-10471",
        "eta_date": "2026-10-02",
        "total_cents": 1299,
        "currency": "EUR",
        "created_at": "2026-09-20T11:47:00Z",
    },
    {
        "order_ref": "10479",
        "customer": "Jane Doe",
        "status": "delayed",
        "carrier": "DHL",
        "tracking_ref": "DEMO-TRK-10479",
        "eta_date": "2026-10-09",
        "total_cents": 2499,
        "currency": "EUR",
        "created_at": "2026-09-25T16:20:00Z",
    },
]

# Store policies are explicit configuration rows — never hardcoded in prompts
# or business logic. The return-policy engine reads these deterministically.
_POLICIES = {
    "returns": {
        "rueckgabefrist_tage": 30,
        "widerrufsfrist_tage": 14,
        "bedingungen": [
            "Item unused and in original packaging",
            "Provide your order number",
        ],
        "ausnahmen": [
            "sealed hygiene items after opening",
        ],
        "ruecksendeadresse": (
            "Demo Shop GmbH, Returns, Sample Street 1, 37073 Göttingen"
        ),
        "hinweis": (
            "This is a demo policy. In demo mode, no real returns are "
            "authorized and no refunds are issued."
        ),
        "status": "active",
    },
    "shipping": {
        "versandkosten_eur": 4.99,
        "versandkostenfrei_ab_eur": 50.0,
        "lieferzeit_werktage": "2-4",
        "versandpartner": ["DHL", "Hermes"],
        "tracking_hinweis": (
            "Demo environment: tracking numbers are fictional; "
            "no live tracking available."
        ),
        "status": "active",
    },
    "payments": {
        "zahlungsarten": [
            "PayPal",
            "Credit card (Visa/Mastercard)",
            "Purchase on account",
            "Prepayment by bank transfer",
        ],
        "hinweis": (
            "Payment processing is handled by the shop's payment provider; "
            "no real payments are processed in demo mode."
        ),
        "status": "active",
    },
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
        (DEMO_STORE_ID, "Demo Shop GmbH", "demo-muster-shop"),
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
            "carrier, tracking_ref, eta_date, total_cents, currency, "
            "created_at, is_demo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
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
                order["created_at"],
            ),
        )

    for policy_key, policy in _POLICIES.items():
        conn.execute(
            "INSERT INTO store_policies (store_id, policy_key, policy_json) "
            "VALUES (?, ?, ?)",
            (DEMO_STORE_ID, policy_key, json.dumps(policy)),
        )
    conn.commit()
    return DEMO_STORE_ID
