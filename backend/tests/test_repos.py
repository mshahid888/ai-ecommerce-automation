"""Repository store-isolation tests: rows are invisible across store_id."""

import pytest

from app.db.database import connect, init_db
from app.db.repositories import EventRepository, OrderRepository, TicketRepository


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "iso.db"
    init_db(path)
    conn = connect(path)
    conn.execute(
        "INSERT INTO stores (id, name, is_demo) VALUES "
        "('store-a', 'Store A', 0), ('store-b', 'Store B', 0)"
    )
    conn.commit()
    yield conn
    conn.close()


def test_order_invisible_across_stores(db):
    orders = OrderRepository(db)
    orders.insert("store-a", order_ref="90001", status="processing")
    db.commit()
    assert orders.find_by_ref("store-a", "90001") is not None
    assert orders.find_by_ref("store-b", "90001") is None
    assert orders.list("store-b") == []
    assert len(orders.list("store-a")) == 1


def test_ticket_invisible_across_stores(db):
    tickets = TicketRepository(db)
    created = tickets.create("store-a", intent="complaint", summary="x")
    db.commit()
    assert tickets.get("store-a", created["id"]) is not None
    assert tickets.get("store-b", created["id"]) is None
    assert tickets.list("store-b") == []


def test_events_invisible_across_stores(db):
    events = EventRepository(db)
    events.log_event("store-a", None, "message_received", "Nachricht empfangen")
    db.commit()
    assert len(events.list("store-a")) == 1
    assert events.list("store-b") == []
