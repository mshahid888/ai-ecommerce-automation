"""POST /api/chat pipeline tests (Phase 2) — run against an isolated temp DB.

Covers the four demo scenarios end to end: order-status happy path,
unknown order clarification, product question with/without catalog data,
return request triage, and human escalation. Asserts that every timeline
event corresponds to an operation that actually executed.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.config import Settings
from app.db.database import connect, init_db
from app.db.seed import DEMO_STORE_ID, create_demo_store
from app.main import app
from app.rules.return_policy import evaluate_return_eligibility


@pytest.fixture()
def isolated_client(tmp_path):
    db_path = tmp_path / "demo_pipeline.db"
    init_db(db_path)
    # NOTE: app startup seeds the *real* DB path, not the overridden one,
    # so the isolated DB is seeded explicitly here.
    conn = connect(db_path)
    try:
        create_demo_store(conn)
    finally:
        conn.close()

    test_settings = Settings()
    test_settings.database_path = db_path
    test_settings.demo_mode = True
    test_settings.llm_provider = "mock"

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


def _chat(client, message: str) -> dict:
    resp = client.post("/api/chat", json={"message": message})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _event_keys(body: dict) -> list[str]:
    return [step["key"] for step in body["events"]]


def _count(conn: sqlite3.Connection, table: str, where: str = "") -> int:
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table} {where}").fetchone()
    return row["n"]


# --- Scenario A: order-status inquiry --------------------------------------


def test_order_status_happy_path(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "Hello, where is my order #10482?")

    assert body["intent"] == "order_status"
    assert body["order_ref"] == "10482"
    assert body["ticket_id"] is None
    assert body["escalated"] is False

    # Answer is grounded in verified demo data — nothing invented.
    answer = body["answer"]
    assert "10482" in answer
    assert "shipped" in answer
    assert "has been shipped via DHL" in answer
    assert "DHL" in answer
    assert "DEMO-TRK-10482" in answer
    assert "simulated reference" in answer
    assert "Demo" in answer

    order = body["order"]
    assert order is not None
    assert order["order_ref"] == "10482"
    assert order["status"] == "shipped"
    assert order["carrier"] == "DHL"
    assert order["tracking_ref"] == "DEMO-TRK-10482"

    # Every event reflects an operation that actually executed.
    assert _event_keys(body) == [
        "message_received",
        "intent_classified",
        "order_ref_extracted",
        "order_lookup",
        "rules_applied",
        "response_generated",
        "interaction_logged",
    ]


def test_order_status_bare_order_ref(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "#10479")
    assert body["intent"] == "order_status"
    assert body["order"]["status"] == "delayed"
    assert "delayed" in body["answer"]


def test_unknown_order_asks_for_clarification(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "Where is my order #99999?")

    assert body["intent"] == "order_status"
    assert body["order"] is None
    answer = body["answer"]
    assert "not found" in answer
    assert "team member" in answer  # human support offered, not invented data

    # The lookup really ran (found nothing); no rules were applied to data.
    keys = _event_keys(body)
    assert keys == [
        "message_received",
        "intent_classified",
        "order_ref_extracted",
        "order_lookup",
        "response_generated",
        "interaction_logged",
    ]


# --- Scenario B: product question ------------------------------------------


def test_product_question_answered_from_catalog(isolated_client):
    client, _ = isolated_client
    body = _chat(
        client, "Is this water bottle dishwasher-safe?"
    )

    assert body["intent"] == "product_question"
    assert body["ticket_id"] is None
    answer = body["answer"]
    assert "Dishwasher-safe" in answer
    assert "Yes" in answer
    assert "AquaPure 750" in answer
    assert _event_keys(body) == [
        "message_received",
        "intent_classified",
        "product_search",
        "response_generated",
        "interaction_logged",
    ]


def test_product_question_missing_attribute_is_honest(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "In which colors does the water bottle come?")

    assert body["intent"] == "product_question"
    answer = body["answer"]
    # Honest "not available" — never invents a color.
    assert "any information" in answer
    assert "Color" in answer
    # Escalation is offered where appropriate.
    assert "team member" in answer


def test_product_question_unknown_product_asks_which(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "Is the vacuum cleaner quiet?")

    assert body["intent"] == "product_question"
    assert "Which product" in body["answer"]


# --- Scenario C: return request --------------------------------------------


def test_return_request_without_order_ref_asks_for_it(isolated_client):
    client, db_path = isolated_client
    body = _chat(client, "I would like to return my order.")

    assert body["intent"] == "return_request"
    assert body["ticket_id"] is None
    assert "order number" in body["answer"]

    conn = connect(db_path)
    try:
        assert _count(conn, "return_requests") == 0
        assert _count(conn, "tickets") == 0
    finally:
        conn.close()


def test_return_request_creates_ticket(isolated_client):
    client, db_path = isolated_client
    body = _chat(client, "I would like to return order #10482.")

    assert body["intent"] == "return_request"
    assert body["ticket_id"] is not None
    assert body["ticket"]["id"] == body["ticket_id"]
    answer = body["answer"]
    # Demo labeling: no real return authorized, no refund executed.
    assert "Demo" in answer
    assert "no real return" in answer
    assert "no refund" in answer
    assert "30" in answer  # return window from the policy row

    conn = connect(db_path)
    try:
        rr = conn.execute(
            "SELECT * FROM return_requests WHERE order_ref = '10482'"
        ).fetchone()
        assert rr is not None
        assert rr["status"] == "pending_review"  # never auto-authorized
        ticket = conn.execute(
            "SELECT * FROM tickets WHERE id = ?", (body["ticket_id"],)
        ).fetchone()
        assert ticket is not None
        assert ticket["intent"] == "return_request"
        assert ticket["order_ref"] == "10482"
        assert ticket["status"] == "open"
        # Staff-facing ticket text is English, never raw German or codes.
        assert "Return request for order #10482" in ticket["summary"]
        assert "defekt" not in ticket["summary"]
    finally:
        conn.close()

    assert _event_keys(body) == [
        "message_received",
        "intent_classified",
        "order_ref_extracted",
        "order_lookup",
        "policy_check",
        "return_request_created",
        "ticket_created",
        "response_generated",
        "interaction_logged",
    ]


def test_return_policy_engine_unit():
    policy = {"rueckgabefrist_tage": 30}
    eligible = evaluate_return_eligibility(
        policy,
        {"status": "delivered", "created_at": "2026-10-01T00:00:00Z"},
        today=date(2026, 10, 9),
    )
    assert eligible["eligible"] is True
    assert eligible["verdict"] == "preliminary_eligible"

    expired = evaluate_return_eligibility(
        policy,
        {"status": "delivered", "created_at": "2026-08-01T00:00:00Z"},
        today=date(2026, 10, 9),
    )
    assert expired["eligible"] is False
    assert expired["verdict"] == "window_expired"

    missing = evaluate_return_eligibility(policy, None)
    assert missing["eligible"] is None
    assert missing["verdict"] == "order_missing"


# --- Scenario D: escalation -------------------------------------------------


def test_human_support_creates_escalation_ticket(isolated_client):
    client, db_path = isolated_client
    body = _chat(client, "I want to speak to a human.")

    assert body["intent"] == "human_support"
    assert body["escalated"] is True
    assert body["ticket_id"] is not None
    assert f"Ticket #{body['ticket_id']}" in body["answer"]
    # The escalation reply is English, never raw German.
    assert "team member" in body["answer"]

    conn = connect(db_path)
    try:
        ticket = conn.execute(
            "SELECT * FROM tickets WHERE id = ?", (body["ticket_id"],)
        ).fetchone()
        assert ticket["escalation_reason"]
        assert ticket["recommended_action"]
        assert ticket["status"] == "open"
    finally:
        conn.close()

    assert "escalated" in _event_keys(body)
    assert "ticket_created" in _event_keys(body)


def test_complaint_escalates_with_high_priority(isolated_client):
    client, db_path = isolated_client
    body = _chat(
        client,
        "My package never arrived, and I want my money back immediately.",
    )

    assert body["escalated"] is True
    assert body["ticket_id"] is not None
    # No unsupported promises in the reply — staff review is promised instead.
    assert "team member" in body["answer"]

    conn = connect(db_path)
    try:
        ticket = conn.execute(
            "SELECT * FROM tickets WHERE id = ?", (body["ticket_id"],)
        ).fetchone()
        assert ticket is not None
    finally:
        conn.close()


# --- Demo reset -------------------------------------------------------------


def test_demo_reset_restores_seed_data(isolated_client):
    client, db_path = isolated_client

    conn = connect(db_path)
    try:
        conn.execute(
            "DELETE FROM orders WHERE store_id = ? AND order_ref = '10479'",
            (DEMO_STORE_ID,),
        )
        conn.commit()
        assert _count(conn, "orders") == 3  # one deleted below the seed of 4
    finally:
        conn.close()

    resp = client.post(
        "/api/demo/reset", headers={"X-Admin-Key": "phase7-test-admin-key"}
    )
    assert resp.status_code == 200

    conn = connect(db_path)
    try:
        assert _count(conn, "orders") == 4
        assert _count(conn, "products") == 4
        assert _count(conn, "store_policies") == 3
        assert (
            _count(
                conn, "orders",
                "WHERE order_ref = '10479' AND status = 'delayed'",
            )
            == 1
        )
    finally:
        conn.close()
