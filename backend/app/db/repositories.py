"""Tiny store-scoped repository layer.

Rule: ``store_id`` is ALWAYS required and enforced in every WHERE clause.
Code that reads or writes tenant data goes through these repositories, so
a missing store filter is a bug in exactly one place.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


class BaseRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _query(
        self, table: str, store_id: str, extra: str = "", params: Iterable[Any] = ()
    ) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            f"SELECT * FROM {table} WHERE store_id = ? {extra}",
            (store_id, *params),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


class StoreRepository(BaseRepository):
    def get(self, store_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM stores WHERE id = ?", (store_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None

    def create(self, store_id: str, name: str, is_demo: bool = False) -> dict:
        self.conn.execute(
            "INSERT OR REPLACE INTO stores (id, name, is_demo) VALUES (?, ?, ?)",
            (store_id, name, 1 if is_demo else 0),
        )
        return self.get(store_id) or {}

    def delete_demo(self) -> int:
        cur = self.conn.execute("DELETE FROM stores WHERE is_demo = 1")
        return cur.rowcount


class OrderRepository(BaseRepository):
    def find_by_ref(
        self, store_id: str, order_ref: str
    ) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM orders WHERE store_id = ? AND order_ref = ?",
            (store_id, order_ref),
        ).fetchone()
        return _row_to_dict(row) if row else None

    def list(self, store_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self._query("orders", store_id, "ORDER BY id DESC LIMIT ?", (limit,))

    def insert(self, store_id: str, **fields: Any) -> dict[str, Any]:
        fields = dict(fields)
        fields["store_id"] = store_id
        cols = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        self.conn.execute(
            f"INSERT INTO orders ({cols}) VALUES ({placeholders})",
            tuple(fields.values()),
        )
        return self.find_by_ref(store_id, fields["order_ref"]) or {}


class ProductRepository(BaseRepository):
    def list(self, store_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self._query(
            "products", store_id, "ORDER BY id DESC LIMIT ?", (limit,)
        )


class CustomerRepository(BaseRepository):
    def insert(self, store_id: str, **fields: Any) -> dict[str, Any]:
        fields = dict(fields)
        fields["store_id"] = store_id
        cols = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        cur = self.conn.execute(
            f"INSERT INTO customers ({cols}) VALUES ({placeholders})",
            tuple(fields.values()),
        )
        row = self.conn.execute(
            "SELECT * FROM customers WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _row_to_dict(row) if row else {}


class TicketRepository(BaseRepository):
    def create(self, store_id: str, **fields: Any) -> dict[str, Any]:
        fields = dict(fields)
        fields["store_id"] = store_id
        cols = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        cur = self.conn.execute(
            f"INSERT INTO tickets ({cols}) VALUES ({placeholders})",
            tuple(fields.values()),
        )
        row = self.conn.execute(
            "SELECT * FROM tickets WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _row_to_dict(row) if row else {}

    def get(self, store_id: str, ticket_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM tickets WHERE id = ? AND store_id = ?",
            (ticket_id, store_id),
        ).fetchone()
        return _row_to_dict(row) if row else None

    def list(self, store_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self._query(
            "tickets", store_id, "ORDER BY id DESC LIMIT ?", (limit,)
        )


class EventRepository(BaseRepository):
    def log_event(
        self,
        store_id: str,
        conversation_id: int | None,
        event_key: str,
        label_de: str,
        payload: dict[str, Any] | None = None,
        status: str = "done",
    ) -> dict[str, Any]:
        cur = self.conn.execute(
            """INSERT INTO workflow_events
               (store_id, conversation_id, event_key, label_de, payload_json, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                store_id,
                conversation_id,
                event_key,
                label_de,
                json.dumps(payload or {}),
                status,
            ),
        )
        row = self.conn.execute(
            "SELECT * FROM workflow_events WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _row_to_dict(row) if row else {}

    def list(
        self, store_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        return self._query(
            "workflow_events",
            store_id,
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
