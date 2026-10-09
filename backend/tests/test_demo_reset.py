"""POST /api/demo/reset tests — run against an isolated temp DB.

The temp database is injected via ``app.dependency_overrides`` for
``get_db``/``get_settings``, so the real dev database is never clobbered.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.config import Settings
from app.db.database import connect, init_db
from app.db.seed import DEMO_STORE_ID
from app.main import app


@pytest.fixture()
def isolated_client(tmp_path):
    db_path = tmp_path / "demo_reset.db"
    init_db(db_path)

    test_settings = Settings()
    test_settings.database_path = db_path
    test_settings.demo_mode = True

    def _get_db():
        conn = connect(db_path, check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[deps.get_db] = _get_db
    app.dependency_overrides[deps.get_settings] = lambda: test_settings
    try:
        with TestClient(app) as client:
            yield client, db_path
    finally:
        app.dependency_overrides.pop(deps.get_db, None)
        app.dependency_overrides.pop(deps.get_settings, None)


def _count(conn: sqlite3.Connection, table: str, where: str = "") -> int:
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table} {where}").fetchone()
    return row["n"]


def test_reset_seeds_demo_store(isolated_client):
    client, db_path = isolated_client
    resp = client.post("/api/demo/reset")
    assert resp.status_code == 200
    assert resp.json() == {"status": "reset", "demo_store": DEMO_STORE_ID}

    conn = connect(db_path)
    try:
        assert _count(conn, "stores") == 1
        assert _count(conn, "products") == 4
        assert _count(conn, "customers") == 2
        assert _count(conn, "orders") == 3
        order = conn.execute(
            "SELECT * FROM orders WHERE order_ref = '10482'"
        ).fetchone()
        assert order["status"] == "shipped"
        assert order["tracking_ref"] == "DEMO-TRK-0048217"
        policies = conn.execute(
            "SELECT * FROM store_policies WHERE store_id = ?", (DEMO_STORE_ID,)
        ).fetchall()
        assert len(policies) == 1
    finally:
        conn.close()


def test_reset_removes_demo_tickets_but_keeps_non_demo(isolated_client):
    client, db_path = isolated_client
    client.post("/api/demo/reset")

    # A non-demo tenant row must survive resets.
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO stores (id, name, is_demo) VALUES ('tenant-1', 'Tenant 1', 0)"
        )
        conn.execute(
            "INSERT INTO orders (store_id, order_ref, status, is_demo) "
            "VALUES ('tenant-1', 'T-1', 'processing', 0)"
        )
        conn.commit()
    finally:
        conn.close()

    # Chat once to produce a demo ticket (complaint -> escalated).
    resp = client.post(
        "/api/chat",
        json={"message": "This is terrible, I want to complain!"},
    )
    assert resp.status_code == 200
    assert resp.json()["ticket_id"] is not None
    tickets_before = client.get("/api/tickets").json()
    assert len(tickets_before) >= 1

    resp = client.post("/api/demo/reset")
    assert resp.status_code == 200
    assert client.get("/api/tickets").json() == []

    conn = connect(db_path)
    try:
        assert _count(conn, "stores", "WHERE id = 'tenant-1'") == 1
        assert _count(conn, "orders", "WHERE store_id = 'tenant-1'") == 1
        assert _count(conn, "orders") == 4  # 3 demo + 1 tenant
    finally:
        conn.close()


def test_reset_forbidden_when_demo_mode_off(isolated_client, tmp_path):
    client, db_path = isolated_client
    app.dependency_overrides[deps.get_settings] = lambda: _off_settings(db_path)
    resp = client.post("/api/demo/reset")
    assert resp.status_code == 403


def _off_settings(db_path):
    s = Settings()
    s.database_path = db_path
    s.demo_mode = False
    return s


def test_reset_is_idempotent(isolated_client):
    client, db_path = isolated_client
    client.post("/api/demo/reset")
    resp = client.post("/api/demo/reset")
    assert resp.status_code == 200
    conn = connect(db_path)
    try:
        # Exactly one seeded set of demo rows — no duplicates.
        assert _count(conn, "stores", f"WHERE id = '{DEMO_STORE_ID}'") == 1
        assert _count(conn, "orders", f"WHERE store_id = '{DEMO_STORE_ID}'") == 3
        assert _count(conn, "products", f"WHERE store_id = '{DEMO_STORE_ID}'") == 4
    finally:
        conn.close()
