"""Phase 7 abuse tests: rate limiting, admin auth, quotas, audit log.

All tests run against an isolated temp DB (dependency_overrides), never
the dev database. The global rate limiter is reset before every test;
middleware tests swap ``app.security.middleware.settings`` for an
isolated Settings object with the limiter enabled.
"""

from __future__ import annotations

import os
import sqlite3
import stat
import time

import pytest
from fastapi.testclient import TestClient

import app.security.middleware as middleware
from app.ai.providers import LLMProvider, MockLLMProvider
from app.ai.quota import (
    QuotaExhausted,
    QuotaGuardedProvider,
    check_and_consume_quota,
    is_real_provider,
    quota_used_today,
)
from app.api import deps
from app.config import Settings
from app.db.database import connect, init_db
from app.db.seed import DEMO_STORE_ID, create_demo_store
from app.main import app
from app.security.admin import ensure_admin_key
from app.security.audit import hash_ip, recent_audits
from app.security.rate_limit import SlidingWindowLimiter, limiter

TEST_ADMIN_KEY = "phase7-test-admin-key"
ADMIN_HEADERS = {"X-Admin-Key": TEST_ADMIN_KEY}
WRONG_HEADERS = {"X-Admin-Key": "wrong-key"}


@pytest.fixture()
def isolated_db(tmp_path):
    db_path = tmp_path / "phase7.db"
    init_db(db_path)
    conn = connect(db_path)
    try:
        create_demo_store(conn)
    finally:
        conn.close()
    return db_path


@pytest.fixture()
def isolated_settings(isolated_db, monkeypatch):
    """Settings bound to the temp DB with the rate limiter enabled."""
    s = Settings()
    s.database_path = isolated_db
    s.demo_mode = True
    s.llm_provider = "mock"
    s.rate_limit_enabled = True
    s.rl_chat_per_minute = 1000
    s.rl_chat_per_day = 1000
    s.rl_read_per_minute = 1000
    s.rl_reset_per_hour = 1000
    s.audit_sample_rate = 1.0  # deterministic audit sampling in tests
    monkeypatch.setattr(middleware, "settings", s)
    return s


@pytest.fixture()
def isolated_client(isolated_db, isolated_settings):
    def _get_db():
        conn = connect(isolated_db, check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[deps.get_db] = _get_db
    app.dependency_overrides[deps.get_settings] = lambda: isolated_settings
    limiter.reset()
    try:
        with TestClient(app) as client:
            yield client, isolated_db, isolated_settings
    finally:
        limiter.reset()
        app.dependency_overrides.pop(deps.get_db, None)
        app.dependency_overrides.pop(deps.get_settings, None)


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


# -- unit: sliding window -------------------------------------------------


def test_sliding_window_allows_then_denies(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["t"])
    lim = SlidingWindowLimiter()
    for _ in range(3):
        allowed, _ = lim.hit("k", 3, 60.0)
        assert allowed
    allowed, retry_after = lim.hit("k", 3, 60.0)
    assert not allowed
    assert retry_after > 0
    # Window slides: after 61s the oldest hit expires.
    clock["t"] += 61.0
    allowed, _ = lim.hit("k", 3, 60.0)
    assert allowed


def test_sliding_window_keys_are_independent():
    lim = SlidingWindowLimiter()
    for _ in range(2):
        assert lim.hit("a", 2, 60.0)[0]
    assert not lim.hit("a", 2, 60.0)[0]
    assert lim.hit("b", 2, 60.0)[0]  # other key unaffected


# -- unit: quota -----------------------------------------------------------


class CountingStub(LLMProvider):
    """Deterministic stub provider: reuses the mock classification rules."""

    def __init__(self) -> None:
        self.calls = 0
        self._mock = MockLLMProvider()

    def classify(self, message: str) -> str:
        self.calls += 1
        return self._mock.classify(message)


def test_quota_counts_real_provider_only(isolated_db):
    conn = connect(isolated_db)
    try:
        assert is_real_provider(CountingStub())
        assert not is_real_provider(MockLLMProvider())
        assert check_and_consume_quota(conn, "stub", 2)
        assert check_and_consume_quota(conn, "stub", 2)
        assert not check_and_consume_quota(conn, "stub", 2)
        assert quota_used_today(conn, "stub") == 2
        assert quota_used_today(conn, "mock") == 0
    finally:
        conn.close()


def test_quota_guarded_provider_enforces_cap(isolated_db):
    conn = connect(isolated_db)
    stub = CountingStub()
    guarded = QuotaGuardedProvider(stub, conn, "stub", cap=2)
    guarded.classify("Hallo")
    guarded.classify("Hallo")
    with pytest.raises(QuotaExhausted):
        guarded.classify("Hallo")
    assert stub.calls == 2  # the third call never reached the provider
    conn.close()


def test_quota_is_per_day(isolated_db, monkeypatch):
    conn = connect(isolated_db)
    try:
        assert check_and_consume_quota(conn, "stub", 1)
        assert not check_and_consume_quota(conn, "stub", 1)
        # Next day the counter restarts.
        monkeypatch.setattr(
            "app.ai.quota.utc_today", lambda: "2999-01-01"
        )
        assert check_and_consume_quota(conn, "stub", 1)
    finally:
        conn.close()


# -- unit: admin key generation --------------------------------------------


def test_admin_key_generated_once_and_persisted(tmp_path, capsys):
    s = Settings()
    s.admin_api_key = None
    s.admin_key_file = tmp_path / ".admin_key"

    key = ensure_admin_key(s)
    assert len(key) >= 32
    out = capsys.readouterr().out
    assert key in out  # printed exactly once, at generation

    key2 = ensure_admin_key(s)
    assert key2 == key
    assert capsys.readouterr().out == ""  # never logged again

    stored = (tmp_path / ".admin_key").read_text(encoding="utf-8").strip()
    assert stored == key
    mode = stat.S_IMODE(os.stat(tmp_path / ".admin_key").st_mode)
    assert mode == 0o600

    # A fresh Settings picks the stored key up without printing.
    s2 = Settings()
    s2.admin_api_key = None
    s2.admin_key_file = tmp_path / ".admin_key"
    assert ensure_admin_key(s2) == key
    assert capsys.readouterr().out == ""


def test_ip_hash_is_one_way():
    hashed = hash_ip("203.0.113.7")
    assert hashed is not None
    assert len(hashed) == 16
    assert "203.0.113.7" not in hashed
    assert hash_ip("203.0.113.7") == hashed  # deterministic
    assert hash_ip(None) is None


# -- abuse: order enumeration -----------------------------------------------


def test_order_enumeration_yields_no_data(isolated_client):
    client, db_path, settings = isolated_client

    for i in range(20):
        order_ref = f"99{i:03d}"  # 99000..99019 — none exist in demo data
        resp = client.post(
            "/api/chat",
            json={"message": f"Wo bleibt meine Bestellung #{order_ref}?"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Honest clarification, no invented data, nothing to escalate on.
        assert data["order"] is None
        assert data["ticket_id"] is None
        assert "nicht gefunden" in data["answer"]

    # No row for any probed reference exists or was created.
    conn = connect(db_path)
    try:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM orders WHERE order_ref LIKE '99%'"
        ).fetchone()["n"]
        assert n == 0
        # No assistant message discloses order details (status, carrier,
        # tracking) for a probed reference — the only thing echoed back
        # is the customer's own input in the clarification text.
        details = conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE role = 'assistant'"
            " AND (content LIKE '%versendet%' OR content LIKE '%DHL%'"
            " OR content LIKE '%Sendungsnummer%')"
            " AND content LIKE '%99%'"
        ).fetchone()["n"]
        assert details == 0
    finally:
        conn.close()


def test_rapid_fire_chat_hits_429_then_recovers(isolated_client):
    client, db_path, settings = isolated_client
    settings.rl_chat_per_minute = 5

    statuses = [
        client.post("/api/chat", json={"message": "Hallo"}).status_code
        for _ in range(8)
    ]
    assert 429 in statuses
    assert statuses.count(200) == 5

    rejected = client.post("/api/chat", json={"message": "Hallo"})
    assert rejected.status_code == 429
    assert int(rejected.headers["Retry-After"]) >= 1
    assert "Zu viele Anfragen" in rejected.json()["message"]

    # A legitimate request works again once the window is cleared.
    limiter.reset()
    ok = client.post("/api/chat", json={"message": "Hallo"})
    assert ok.status_code == 200
    assert "willkommen" in ok.json()["answer"].lower()


def test_per_ip_daily_chat_cap(isolated_client):
    client, db_path, settings = isolated_client
    settings.rl_chat_per_day = 3
    codes = [
        client.post("/api/chat", json={"message": "Hallo"}).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]


def test_read_endpoints_rate_limited(isolated_client):
    client, db_path, settings = isolated_client
    settings.rl_read_per_minute = 4
    codes = [client.get("/api/dashboard/summary").status_code for _ in range(6)]
    assert codes.count(200) == 4
    assert codes.count(429) == 2


# -- input hardening --------------------------------------------------------


def test_oversized_message_rejected_400(isolated_client):
    client, _, _ = isolated_client
    resp = client.post("/api/chat", json={"message": "x" * 5000})
    assert resp.status_code == 400
    assert "zu lang" in resp.json()["detail"]


def test_empty_message_rejected_400_german(isolated_client):
    client, _, _ = isolated_client
    for bad in ["", "   "]:
        resp = client.post("/api/chat", json={"message": bad})
        assert resp.status_code == 400, bad
        assert "Nachricht" in resp.json()["detail"]


def test_oversized_body_rejected_413(isolated_client):
    client, _, settings = isolated_client
    big = "x" * (settings.max_body_bytes + 1)
    resp = client.post(
        "/api/chat",
        content=big,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 413


# -- admin auth on demo reset -------------------------------------------------


def test_demo_reset_requires_admin_key(isolated_client):
    client, db_path, settings = isolated_client

    no_key = client.post("/api/demo/reset")
    assert no_key.status_code == 401
    assert "Admin-Schlüssel" in no_key.json()["detail"]

    wrong_key = client.post("/api/demo/reset", headers=WRONG_HEADERS)
    assert wrong_key.status_code == 401

    ok = client.post("/api/demo/reset", headers=ADMIN_HEADERS)
    assert ok.status_code == 200
    assert ok.json() == {"status": "reset", "demo_store": DEMO_STORE_ID}

    # Data was actually restored.
    conn = connect(db_path)
    try:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM orders WHERE store_id = ?",
            (DEMO_STORE_ID,),
        ).fetchone()["n"]
        assert n == 4
        # Auth failures are audit-logged; raw IPs are not stored.
        failures = recent_audits(conn, "admin_auth_failure")
        assert len(failures) == 2
        assert failures[0]["actor_ip_hash"] is not None
        assert "." not in (failures[0]["actor_ip_hash"] or "")
        resets = recent_audits(conn, "demo_reset")
        assert len(resets) == 1
        assert resets[0]["store_id"] == DEMO_STORE_ID
    finally:
        conn.close()


def test_demo_reset_rate_limited(isolated_client):
    client, _, settings = isolated_client
    settings.rl_reset_per_hour = 2
    assert (
        client.post("/api/demo/reset", headers=ADMIN_HEADERS).status_code
        == 200
    )
    assert (
        client.post("/api/demo/reset", headers=ADMIN_HEADERS).status_code
        == 200
    )
    third = client.post("/api/demo/reset", headers=ADMIN_HEADERS)
    assert third.status_code == 429
    assert third.headers.get("Retry-After") is not None


# -- AI quota fallback ----------------------------------------------------------


def test_ai_quota_fallback_to_mock(isolated_client, monkeypatch):
    client, db_path, settings = isolated_client
    stub = CountingStub()
    monkeypatch.setattr(
        "app.api.chat.get_provider", lambda s: stub
    )
    settings.llm_provider = "stub-provider"
    settings.llm_daily_request_cap = 2

    first = client.post(
        "/api/chat", json={"message": "Wo bleibt meine Bestellung #10482?"}
    )
    assert first.status_code == 200
    assert first.json()["provider"] == "stub-provider"
    assert "quota_fallback" not in first.json()

    second = client.post(
        "/api/chat", json={"message": "Wo bleibt meine Bestellung #10482?"}
    )
    assert second.status_code == 200
    assert second.json()["provider"] == "stub-provider"

    # Cap exhausted: honest fallback to the mock, never a failure.
    third = client.post(
        "/api/chat", json={"message": "Wo bleibt meine Bestellung #10482?"}
    )
    assert third.status_code == 200
    body = third.json()
    assert body["provider"] == "mock"
    assert body["quota_fallback"] is True
    assert "Tageskontingent" in body["quota_note"]
    # The answer still uses real demo data (mock classifier → order found).
    assert body["order"] is not None
    assert body["order"]["order_ref"] == "10482"
    # The fallback is a real workflow event on the conversation timeline.
    keys = [e["key"] for e in body["events"]]
    assert "llm_quota_fallback" in keys

    assert stub.calls == 2  # only two real-provider calls were made
    conn = connect(db_path)
    try:
        assert quota_used_today(conn, "stub-provider") == 2
    finally:
        conn.close()


# -- audit log ------------------------------------------------------------------


def test_audit_log_covers_tickets_and_escalations(isolated_client):
    client, db_path, _ = isolated_client
    resp = client.post(
        "/api/chat",
        json={"message": "My package never arrived, I want my money back!"},
    )
    assert resp.status_code == 200
    assert resp.json()["escalated"] is True
    ticket_id = resp.json()["ticket_id"]
    assert ticket_id is not None

    conn = connect(db_path)
    try:
        created = recent_audits(conn, "ticket_created")
        assert len(created) == 1
        assert created[0]["actor_ip_hash"] is not None
        escalated = recent_audits(conn, "escalated")
        assert len(escalated) == 1
        assert escalated[0]["store_id"] == DEMO_STORE_ID
    finally:
        conn.close()


def test_audit_log_survives_demo_reset(isolated_client):
    client, db_path, _ = isolated_client
    client.post("/api/demo/reset", headers=ADMIN_HEADERS)
    conn = connect(db_path)
    try:
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_log"
        ).fetchone()["n"]
        assert total >= 1  # the reset's own audit row is still there
    finally:
        conn.close()
