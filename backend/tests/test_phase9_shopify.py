"""Phase 9 tests: StoreIntegration interface, Shopify adapters, webhooks.

- Interface parity: demo vs simulated adapters return identical canonical
  payloads (order #10482, product AquaPure 750, fulfillment, order list).
- Webhooks: valid locally-computed HMAC → 200 + audit row; bad HMAC →
  401; duplicate webhook id → 200 "duplicate" without double-processing.
- Real ShopifyAdapter: helpful error when env vars are missing; no real
  network calls in tests (``_http_get_json`` is monkeypatched).
- Chat pipeline: identical English replies under STORE_BACKEND=demo and
  shopify_simulated.

All tests run against an isolated temp DB (dependency_overrides).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import sqlite3
import urllib.error

import pytest

from app.api import deps
from app.config import Settings
from app.db.database import connect, init_db
from app.db.seed import DEMO_STORE_ID, create_demo_store
from app.integrations import (
    DemoStoreAdapter,
    IntegrationConfigError,
    IntegrationError,
    ShopifyAdapter,
    SimulatedShopifyAdapter,
    get_store_integration,
    verify_webhook_hmac,
)
from app.security.audit import recent_audits


# --- fixtures -----------------------------------------------------------


@pytest.fixture()
def isolated_db(tmp_path):
    db_path = tmp_path / "phase9.db"
    init_db(db_path)
    conn = connect(db_path)
    try:
        create_demo_store(conn)
    finally:
        conn.close()
    return db_path


@pytest.fixture()
def isolated_conn(isolated_db):
    conn = connect(isolated_db)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture()
def test_settings(isolated_db):
    s = Settings()
    s.database_path = isolated_db
    s.demo_mode = True
    s.llm_provider = "mock"
    return s


@pytest.fixture()
def isolated_client(isolated_db, test_settings):
    from fastapi.testclient import TestClient

    from app.main import app

    def _get_db():
        conn = connect(isolated_db, check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[deps.get_db] = _get_db
    app.dependency_overrides[deps.get_settings] = lambda: test_settings
    try:
        with TestClient(app) as client:
            yield client, test_settings
    finally:
        app.dependency_overrides.pop(deps.get_db, None)
        app.dependency_overrides.pop(deps.get_settings, None)


def _demo(isolated_conn):
    return DemoStoreAdapter(isolated_conn, DEMO_STORE_ID)


def _simulated(isolated_conn):
    return SimulatedShopifyAdapter(isolated_conn, DEMO_STORE_ID)


def _canonical(payload: dict | None) -> dict | None:
    """Strip Shopify-simulation metadata so canonical fields compare equal."""
    if payload is None:
        return None
    return {
        k: v
        for k, v in payload.items()
        if not (k == "simulated" or k.startswith("shopify_"))
    }


# --- interface parity ----------------------------------------------------


def test_parity_get_order_10482(isolated_conn):
    demo_order = _canonical(_demo(isolated_conn).get_order("10482"))
    sim_order = _canonical(_simulated(isolated_conn).get_order("10482"))
    assert demo_order is not None and sim_order is not None
    assert demo_order == sim_order
    assert demo_order["order_ref"] == "10482"
    assert demo_order["status"] == "shipped"
    assert demo_order["carrier"] == "DHL"
    assert demo_order["tracking_ref"] == "DEMO-TRK-10482"
    assert demo_order["eta_date"] == "2026-10-14"
    assert demo_order["total_cents"] == 3499


def test_parity_order_ref_normalization(isolated_conn):
    # Raw-then-normalized lookup behavior preserved through the interface.
    for ref in ("10482", "010482", " #10482 "):
        assert _canonical(_demo(isolated_conn).get_order(ref))["order_ref"] == "10482"
        assert _canonical(_simulated(isolated_conn).get_order(ref))["order_ref"] == "10482"
    assert _demo(isolated_conn).get_order("99999") is None
    assert _simulated(isolated_conn).get_order("99999") is None


def test_parity_get_product_aquapure(isolated_conn):
    demo_product = _canonical(_demo(isolated_conn).get_product("MS-AP750"))
    sim_product = _canonical(_simulated(isolated_conn).get_product("MS-AP750"))
    assert demo_product is not None and sim_product is not None
    assert demo_product == sim_product
    assert demo_product["name"] == "AquaPure 750"
    # Lookup by numeric id also works.
    by_id = _demo(isolated_conn).get_product(str(demo_product["id"]))
    assert by_id is not None and by_id["sku"] == "MS-AP750"
    assert _demo(isolated_conn).get_product("NO-SUCH-SKU") is None


def test_parity_search_products(isolated_conn):
    demo_matches = _demo(isolated_conn).search_products(
        "Is the water bottle dishwasher-safe?"
    )
    sim_matches = _simulated(isolated_conn).search_products(
        "Is the water bottle dishwasher-safe?"
    )
    assert demo_matches and sim_matches
    assert demo_matches[0]["name"] == "AquaPure 750"
    assert sim_matches[0]["name"] == "AquaPure 750"
    assert [_canonical(m) for m in demo_matches] == [
        _canonical(m) for m in sim_matches
    ]


def test_parity_get_fulfillment(isolated_conn):
    demo_f = _canonical(_demo(isolated_conn).get_fulfillment("10482"))
    sim_f = _canonical(_simulated(isolated_conn).get_fulfillment("10482"))
    assert demo_f is not None and sim_f is not None
    assert demo_f == sim_f
    assert demo_f["carrier"] == "DHL"
    assert demo_f["tracking_ref"] == "DEMO-TRK-10482"
    # Order 10483 (processing) has no carrier/tracking → None on both.
    assert _demo(isolated_conn).get_fulfillment("10483") is None
    assert _simulated(isolated_conn).get_fulfillment("10483") is None


def test_parity_list_orders(isolated_conn):
    demo_orders = [_canonical(o) for o in _demo(isolated_conn).list_orders(10)]
    sim_orders = [_canonical(o) for o in _simulated(isolated_conn).list_orders(10)]
    assert [o["order_ref"] for o in demo_orders] == [
        "10479",
        "10471",
        "10483",
        "10482",
    ]
    assert demo_orders == sim_orders
    assert len(_demo(isolated_conn).list_orders(2)) == 2


def test_simulated_marks_simulated(isolated_conn):
    order = _simulated(isolated_conn).get_order("10482")
    assert order["simulated"] is True
    assert order["shopify_id"] == "gid://shopify/Order/10482"
    assert order["shopify_name"] == "#10482"
    product = _simulated(isolated_conn).get_product("MS-AP750")
    assert product["simulated"] is True
    assert product["shopify_id"].startswith("gid://shopify/Product/")
    fulfillment = _simulated(isolated_conn).get_fulfillment("10482")
    assert fulfillment["simulated"] is True
    assert fulfillment["shopify_id"].startswith("gid://shopify/FulfillmentOrder/")


def test_adapters_are_store_scoped(isolated_conn):
    demo = DemoStoreAdapter(isolated_conn, "other-store")
    simulated = SimulatedShopifyAdapter(isolated_conn, "other-store")
    assert demo.get_order("10482") is None
    assert simulated.get_order("10482") is None
    assert demo.list_orders() == []
    assert simulated.list_orders() == []
    assert demo.search_products("water bottle") == []
    assert simulated.search_products("water bottle") == []
    assert demo.get_product("MS-AP750") is None
    assert demo.get_fulfillment("10482") is None


def test_factory_selects_backend(isolated_conn, test_settings):
    test_settings.store_backend = "demo"
    assert get_store_integration(
        test_settings, isolated_conn, DEMO_STORE_ID
    ).backend_name == "demo"
    test_settings.store_backend = "shopify_simulated"
    assert get_store_integration(
        test_settings, isolated_conn, DEMO_STORE_ID
    ).backend_name == "shopify_simulated"
    test_settings.store_backend = "bogus"
    assert get_store_integration(
        test_settings, isolated_conn, DEMO_STORE_ID
    ).backend_name == "demo"


# --- webhooks ------------------------------------------------------------


_WEBHOOK_SECRET = "phase9-test-webhook-secret"


def _sign(body: bytes, secret: str = _WEBHOOK_SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


_WEBHOOK_HEADERS = {
    "X-Shopify-Topic": "orders/create",
    "X-Shopify-Shop-Domain": "muster-shop.myshopify.com",
    "Content-Type": "application/json",
}


def _webhook_client(isolated_client, secret: str | None):
    client, settings = isolated_client
    settings.shopify_webhook_secret = secret
    return client, settings


def test_webhook_unconfigured_returns_503(isolated_client):
    client, _ = _webhook_client(isolated_client, None)
    resp = client.post("/api/integrations/shopify/webhooks", content=b"{}")
    assert resp.status_code == 503
    assert resp.json()["error"] == "shopify_not_configured"
    assert resp.json()["simulated"] is True


def test_verify_webhook_hmac_unit():
    body = b'{"id": 1}'
    good = _sign(body)
    assert verify_webhook_hmac(body, good, _WEBHOOK_SECRET) is True
    assert verify_webhook_hmac(body, "bogus", _WEBHOOK_SECRET) is False
    assert verify_webhook_hmac(body, None, _WEBHOOK_SECRET) is False
    assert verify_webhook_hmac(body, good, None) is False
    # Tampered body fails even with the right header for the old body.
    assert verify_webhook_hmac(b'{"id": 2}', good, _WEBHOOK_SECRET) is False


def test_webhook_valid_hmac_200_and_audit(isolated_client, isolated_db):
    client, _ = _webhook_client(isolated_client, _WEBHOOK_SECRET)
    body = b'{"id": 820982911946154508, "name": "#10482"}'
    headers = {
        **_WEBHOOK_HEADERS,
        "X-Shopify-Hmac-Sha256": _sign(body),
        "X-Shopify-Webhook-Id": "phase9-test-id-1",
    }
    resp = client.post("/api/integrations/shopify/webhooks", content=body, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "received"
    assert resp.json()["simulated"] is True

    conn = connect(isolated_db)
    try:
        rows = recent_audits(conn, "shopify_webhook_received")
        assert len(rows) == 1
        assert rows[0]["store_id"] is None
        event = conn.execute(
            "SELECT * FROM shopify_webhook_events WHERE webhook_id = ?",
            ("phase9-test-id-1",),
        ).fetchone()
        assert event is not None
        assert event["topic"] == "orders/create"
    finally:
        conn.close()


def test_webhook_bad_hmac_401(isolated_client, isolated_db):
    client, _ = _webhook_client(isolated_client, _WEBHOOK_SECRET)
    body = b'{"id": 1}'
    headers = {
        **_WEBHOOK_HEADERS,
        "X-Shopify-Hmac-Sha256": "invalid-signature",
        "X-Shopify-Webhook-Id": "phase9-test-id-bad",
    }
    resp = client.post("/api/integrations/shopify/webhooks", content=body, headers=headers)
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_webhook_signature"
    conn = connect(isolated_db)
    try:
        assert len(recent_audits(conn, "shopify_webhook_rejected")) == 1
        assert len(recent_audits(conn, "shopify_webhook_received")) == 0
    finally:
        conn.close()


def test_webhook_duplicate_id_not_reprocessed(isolated_client, isolated_db):
    client, _ = _webhook_client(isolated_client, _WEBHOOK_SECRET)
    body = b'{"id": 2}'
    headers = {
        **_WEBHOOK_HEADERS,
        "X-Shopify-Hmac-Sha256": _sign(body),
        "X-Shopify-Webhook-Id": "phase9-test-id-dupe",
    }
    first = client.post("/api/integrations/shopify/webhooks", content=body, headers=headers)
    second = client.post("/api/integrations/shopify/webhooks", content=body, headers=headers)
    assert first.status_code == 200 and first.json()["status"] == "received"
    assert second.status_code == 200 and second.json()["status"] == "duplicate"
    conn = connect(isolated_db)
    try:
        # No double-processing: exactly one "received" audit row.
        assert len(recent_audits(conn, "shopify_webhook_received")) == 1
    finally:
        conn.close()


def test_webhook_missing_id_400(isolated_client):
    client, _ = _webhook_client(isolated_client, _WEBHOOK_SECRET)
    body = b"{}"
    headers = {**_WEBHOOK_HEADERS, "X-Shopify-Hmac-Sha256": _sign(body)}
    resp = client.post("/api/integrations/shopify/webhooks", content=body, headers=headers)
    assert resp.status_code == 400


# --- real ShopifyAdapter skeleton -----------------------------------------


def _shopify_settings(monkeypatch, **overrides):
    monkeypatch.delenv("SHOPIFY_SHOP_DOMAIN", raising=False)
    monkeypatch.delenv("SHOPIFY_ADMIN_API_TOKEN", raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_real_adapter_missing_env_raises(monkeypatch):
    settings = _shopify_settings(monkeypatch)
    with pytest.raises(IntegrationConfigError) as excinfo:
        ShopifyAdapter(settings, DEMO_STORE_ID)
    message = str(excinfo.value)
    assert "SHOPIFY_SHOP_DOMAIN" in message
    assert "SHOPIFY_ADMIN_API_TOKEN" in message
    assert "docs/SHOPIFY.md" in message


def test_real_adapter_bad_domain_raises(monkeypatch):
    settings = _shopify_settings(
        monkeypatch,
        SHOPIFY_SHOP_DOMAIN="example.com",
        SHOPIFY_ADMIN_API_TOKEN="shpat_fake",
    )
    with pytest.raises(IntegrationConfigError) as excinfo:
        ShopifyAdapter(settings, DEMO_STORE_ID)
    assert "myshopify.com" in str(excinfo.value)


def test_real_adapter_mapping_no_network(monkeypatch):
    import app.integrations.shopify as shopify_mod

    settings = _shopify_settings(
        monkeypatch,
        SHOPIFY_SHOP_DOMAIN="https://muster-shop.myshopify.com/",
        SHOPIFY_ADMIN_API_TOKEN="shpat_fake",
    )
    adapter = ShopifyAdapter(settings, DEMO_STORE_ID)
    assert adapter.shop_domain == "muster-shop.myshopify.com"
    assert adapter.backend_name == "shopify"

    calls: list[str] = []

    def fake_http_get_json(url, headers, timeout):
        calls.append(url)
        assert timeout == 10
        # The token must travel ONLY in the header, never in the URL.
        assert "shpat_fake" not in url
        assert headers["X-Shopify-Access-Token"] == "shpat_fake"
        if "/orders.json" in url:
            return 200, {
                "orders": [
                    {
                        "id": 5500000001,
                        "name": "#10482",
                        "cancelled": False,
                        "fulfillment_status": "fulfilled",
                        "total_price": "34.99",
                        "currency": "EUR",
                    }
                ]
            }
        if "/fulfillments.json" in url:
            return 200, {
                "fulfillments": [
                    {
                        "id": 6600000001,
                        "tracking_number": "1ZFAKE999",
                        "tracking_company": "DHL",
                    }
                ]
            }
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(shopify_mod, "_http_get_json", fake_http_get_json)
    order = adapter.get_order("10482")
    assert order is not None
    assert order["order_ref"] == "10482"
    assert order["status"] == "shipped"
    assert order["total_cents"] == 3499
    assert order["currency"] == "EUR"
    assert order["shopify_id"] == "gid://shopify/Order/5500000001"
    assert order["eta_date"] is None  # Shopify has no ETA field (honest)
    assert calls, "the adapter must go through the HTTP layer (mocked)"

    fulfillment = adapter.get_fulfillment("10482")
    assert fulfillment is not None
    assert fulfillment["carrier"] == "DHL"
    assert fulfillment["tracking_ref"] == "1ZFAKE999"


def test_real_adapter_403_mentions_scopes(monkeypatch):
    import app.integrations.shopify as shopify_mod

    settings = _shopify_settings(
        monkeypatch,
        SHOPIFY_SHOP_DOMAIN="muster-shop.myshopify.com",
        SHOPIFY_ADMIN_API_TOKEN="shpat_fake",
    )
    adapter = ShopifyAdapter(settings, DEMO_STORE_ID)

    def fake_403(url, headers, timeout):
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(shopify_mod, "_http_get_json", fake_403)
    with pytest.raises(IntegrationError) as excinfo:
        adapter.get_order("10482")
    assert "read_orders" in str(excinfo.value)


def test_real_adapter_product_mapping_no_network(monkeypatch):
    import app.integrations.shopify as shopify_mod

    settings = _shopify_settings(
        monkeypatch,
        SHOPIFY_SHOP_DOMAIN="muster-shop.myshopify.com",
        SHOPIFY_ADMIN_API_TOKEN="shpat_fake",
    )
    adapter = ShopifyAdapter(settings, DEMO_STORE_ID)

    def fake_http_get_json(url, headers, timeout):
        if "/products/123.json" in url:
            return 200, {
                "product": {
                    "id": 123,
                    "title": "AquaPure 750",
                    "body_html": "<p>Stainless steel <strong>water bottle</strong>.</p>",
                    "variants": [{"sku": "MS-AP750", "price": "19.99"}],
                }
            }
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(shopify_mod, "_http_get_json", fake_http_get_json)
    product = adapter.get_product("123")
    assert product is not None
    assert product["sku"] == "MS-AP750"
    assert product["name"] == "AquaPure 750"
    assert product["description"] == "Stainless steel water bottle."
    assert product["shopify_id"] == "gid://shopify/Product/123"


# --- chat pipeline parity across backends ---------------------------------


def _chat(client, message: str) -> dict:
    resp = client.post("/api/chat", json={"message": message})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_chat_identical_under_both_backends(isolated_client):
    client, settings = isolated_client
    messages = [
        "Hello, where is my order #10482?",
        "Is the AquaPure 750 water bottle dishwasher-safe?",
        "I would like to return order #10471.",
    ]
    replies = {}
    for backend in ("demo", "shopify_simulated"):
        settings.store_backend = backend
        # Ticket IDs increment across runs (separate conversations), so
        # normalize them before comparing: the backend choice must not
        # change anything else about the reply.
        replies[backend] = [
            re.sub(r"Ticket #\d+", "Ticket #N", _chat(client, m)["reply_de"])
            for m in messages
        ]
    assert replies["demo"] == replies["shopify_simulated"]
    # Sanity: the order-status reply really uses the demo order data.
    assert "DHL" in replies["demo"][0]
    assert "DEMO-TRK-10482" in replies["demo"][0]
