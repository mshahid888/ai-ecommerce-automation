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

    def list(
        self,
        store_id: str,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if status is not None:
            return self._query(
                "tickets",
                store_id,
                "AND status = ? ORDER BY id DESC LIMIT ?",
                (status, limit),
            )
        return self._query(
            "tickets", store_id, "ORDER BY id DESC LIMIT ?", (limit,)
        )


class ConversationRepository(BaseRepository):
    """Store-scoped conversations with their messages and event timeline.

    Every query verifies the conversation belongs to ``store_id`` first —
    a conversation from another store is treated as nonexistent.
    """

    def _belongs_to_store(
        self, store_id: str, conversation_id: int
    ) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND store_id = ?",
            (conversation_id, store_id),
        ).fetchone()
        return row is not None

    def list(
        self, store_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Recent conversations: id, started_at, message_count,
        last_intent (from the ``intent_classified`` event payload)."""
        rows = self.conn.execute(
            """SELECT c.id, c.created_at,
                      (SELECT COUNT(*) FROM messages m
                        WHERE m.conversation_id = c.id) AS message_count,
                      (SELECT e.payload_json FROM workflow_events e
                        WHERE e.conversation_id = c.id
                          AND e.event_key = 'intent_classified'
                          AND e.status = 'done'
                        ORDER BY e.id ASC LIMIT 1) AS intent_payload
               FROM conversations c
               WHERE c.store_id = ?
               ORDER BY c.id DESC LIMIT ?""",
            (store_id, limit),
        ).fetchall()
        result = []
        for row in rows:
            last_intent = None
            if row["intent_payload"]:
                try:
                    last_intent = json.loads(row["intent_payload"]).get("intent")
                except (json.JSONDecodeError, AttributeError):
                    last_intent = None
            result.append(
                {
                    "id": row["id"],
                    "started_at": row["created_at"],
                    "message_count": row["message_count"],
                    "last_intent": last_intent,
                }
            )
        return result

    def get(self, store_id: str, conversation_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM conversations WHERE id = ? AND store_id = ?",
            (conversation_id, store_id),
        ).fetchone()
        return _row_to_dict(row) if row else None

    def messages(
        self, store_id: str, conversation_id: int
    ) -> list[dict[str, Any]] | None:
        if not self._belongs_to_store(store_id, conversation_id):
            return None
        rows = self.conn.execute(
            """SELECT id, conversation_id, role, content, created_at
               FROM messages WHERE conversation_id = ?
               ORDER BY id ASC""",
            (conversation_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def events(
        self, store_id: str, conversation_id: int
    ) -> list[dict[str, Any]] | None:
        if not self._belongs_to_store(store_id, conversation_id):
            return None
        rows = self.conn.execute(
            """SELECT id, event_key, label_de, status, created_at
               FROM workflow_events
               WHERE conversation_id = ? AND store_id = ?
               ORDER BY id ASC""",
            (conversation_id, store_id),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


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
