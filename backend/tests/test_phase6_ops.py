"""Phase 6 ops API tests — run against an isolated temp DB.

Every assertion targets real database counts: dashboard summary,
ticket list/detail with linked messages+events, conversations list/detail,
and strict store isolation on the new endpoints. No invented data.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.config import Settings
from app.db.database import connect, init_db
from app.db.repositories import StoreRepository, TicketRepository
from app.db.seed import DEMO_STORE_ID, create_demo_store
from app.main import app


@pytest.fixture()
def isolated_client(tmp_path):
    db_path = tmp_path / "demo_phase6.db"
    init_db(db_path)
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


def _seed_traffic(client: TestClient) -> dict:
    """3 chats: order_status + greeting (no tickets), complaint (ticket)."""
    out = {}
    out["order"] = client.post(
        "/api/chat", json={"message": "Hello, where is my order #10482?"}
    ).json()
    out["greeting"] = client.post(
        "/api/chat", json={"message": "Good morning"}
    ).json()
    out["complaint"] = client.post(
        "/api/chat",
        json={"message": "My package never arrived, and I want my money back immediately."},
    ).json()
    assert out["order"]["intent"] == "order_status"
    assert out["greeting"]["intent"] == "greeting"
    assert out["complaint"]["intent"] == "complaint"
    assert out["complaint"]["ticket_id"] is not None
    return out


def test_dashboard_summary_real_counts(isolated_client):
    client, _ = isolated_client
    ticket_id = _seed_traffic(client)["complaint"]["ticket_id"]

    body = client.get("/api/dashboard/summary").json()

    assert body["store_id"] == DEMO_STORE_ID
    assert body["demo_data"] is True
    assert body["conversations_count"] == 3
    assert body["messages_count"] == 6  # user + assistant per chat
    assert body["tickets_total"] == 1
    assert body["tickets_open"] == 1
    assert body["escalations_count"] == 1  # one real escalated event

    breakdown = {b["intent"]: b for b in body["intents_breakdown"]}
    assert set(breakdown) == {"order_status", "greeting", "complaint"}
    assert all(b["count"] == 1 for b in breakdown.values())
    # Dashboard intent labels are English (via the ops API).
    assert breakdown["complaint"]["label_de"] == "Complaint"
    assert breakdown["order_status"]["label_de"] == "Order status"
    assert breakdown["greeting"]["label_de"] == "Greeting"

    events = body["recent_events"]
    assert 0 < len(events) <= 15
    labels = {e["label_de"] for e in events}
    assert "Intent detected" in labels
    assert "Support ticket created" in labels
    assert all(e["created_at"] for e in events)
    # ticket-created event payload references the real ticket id
    assert any(
        e["event_key"] == "ticket_created"
        for e in events
        if e["conversation_id"]
    ), "ticket_created events carry the real conversation id"


def test_ticket_list_and_status_filter(isolated_client):
    client, _ = isolated_client
    ticket_id = _seed_traffic(client)["complaint"]["ticket_id"]

    all_tickets = client.get("/api/tickets").json()
    assert len(all_tickets) == 1
    t = all_tickets[0]
    assert t["id"] == ticket_id
    assert t["intent"] == "complaint"
    assert t["intent_label_de"] == "Complaint"
    assert t["status"] == "open"
    assert t["escalation_reason"] == "always_human"
    assert t["created_at"]

    open_tickets = client.get("/api/tickets?status=open").json()
    assert len(open_tickets) == 1
    closed_tickets = client.get("/api/tickets?status=closed").json()
    assert closed_tickets == []


def test_ticket_detail_links_messages_and_events(isolated_client):
    client, _ = isolated_client
    traffic = _seed_traffic(client)
    ticket_id = traffic["complaint"]["ticket_id"]

    detail = client.get(f"/api/tickets/{ticket_id}").json()
    assert detail["id"] == ticket_id
    assert detail["intent"] == "complaint"
    assert detail["recommended_action"] == "Team member replies to the customer"

    messages = detail["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert "never arrived" in messages[0]["content"]
    assert messages[1]["role"] == "assistant"

    keys = [e["event_key"] for e in detail["events"]]
    assert "message_received" in keys
    assert "intent_classified" in keys
    assert "ticket_created" in keys
    assert "escalated" in keys
    assert all(e["label_de"] and e["created_at"] for e in detail["events"])

    r = client.get("/api/tickets/999999")
    assert r.status_code == 404


def test_conversations_list_and_detail(isolated_client):
    client, _ = isolated_client
    traffic = _seed_traffic(client)
    conv_id = traffic["order"]["conversation_id"]

    listing = client.get("/api/conversations").json()
    assert len(listing) == 3
    by_id = {c["id"]: c for c in listing}
    assert by_id[conv_id]["message_count"] == 2
    assert by_id[conv_id]["last_intent"] == "order_status"
    assert by_id[conv_id]["last_intent_label_de"] == "Order status"
    assert all(c["started_at"] for c in listing)

    detail = client.get(f"/api/conversations/{conv_id}").json()
    assert detail["id"] == conv_id
    assert detail["message_count"] == 2
    assert len(detail["messages"]) == 2
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    keys = [e["event_key"] for e in detail["events"]]
    assert "message_received" in keys
    assert "intent_classified" in keys
    assert "ticket_created" not in keys  # order_status creates no ticket

    r = client.get("/api/conversations/999999")
    assert r.status_code == 404


def test_ops_store_isolation(isolated_client):
    client, db_path = isolated_client
    traffic = _seed_traffic(client)
    demo_ticket = traffic["complaint"]["ticket_id"]
    demo_conv = traffic["order"]["conversation_id"]

    # Second store with its own ticket, inserted directly (not via chat).
    conn = connect(db_path)
    try:
        StoreRepository(conn).create("store-b", "Store B")
        other = TicketRepository(conn).create(
            "store-b", intent="complaint", summary="other store", status="open"
        )
        conn.commit()
    finally:
        conn.close()

    # Demo-store views see only demo rows.
    demo_tickets = client.get("/api/tickets").json()
    assert [t["id"] for t in demo_tickets] == [demo_ticket]

    other_tickets = client.get("/api/tickets?store_id=store-b").json()
    assert [t["id"] for t in other_tickets] == [other["id"]]

    demo_convs = client.get("/api/conversations").json()
    assert len(demo_convs) == 3
    other_convs = client.get("/api/conversations?store_id=store-b").json()
    assert other_convs == []

    # Cross-store detail access → 404, never a leak.
    assert client.get(f"/api/tickets/{demo_ticket}?store_id=store-b").status_code == 404
    assert client.get(f"/api/conversations/{demo_conv}?store_id=store-b").status_code == 404
    assert client.get(f"/api/tickets/{other['id']}").status_code == 404

    # Summary counts are per-store.
    other_summary = client.get("/api/dashboard/summary?store_id=store-b").json()
    assert other_summary["tickets_total"] == 1
    assert other_summary["conversations_count"] == 0
    assert other_summary["messages_count"] == 0
    assert other_summary["escalations_count"] == 0
    assert other_summary["intents_breakdown"] == []
    assert other_summary["recent_events"] == []

    demo_summary = client.get("/api/dashboard/summary").json()
    assert demo_summary["tickets_total"] == 1
    assert demo_summary["conversations_count"] == 3
