"""Ops dashboard aggregates (Phase 6).

Every number here is a REAL ``COUNT(*)`` against the database — nothing is
invented, estimated, or sampled. Labeled as demo data at the API layer;
the frontend shows exactly what these functions return.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..services.intent import INTENT_LABELS_DE, VALID_INTENTS


def _count(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0]) if row else 0


def intents_breakdown(
    conn: sqlite3.Connection, store_id: str
) -> list[dict[str, Any]]:
    """Count classifications per intent from ``intent_classified`` events.

    Only ``status='done'`` events with a valid intent in the payload count —
    failed classifications carry no intent and are excluded rather than
    guessed.
    """
    rows = conn.execute(
        """SELECT payload_json FROM workflow_events
           WHERE store_id = ? AND event_key = 'intent_classified'
             AND status = 'done'""",
        (store_id,),
    ).fetchall()
    counts: dict[str, int] = {}
    for row in rows:
        try:
            intent = json.loads(row[0] or "{}").get("intent")
        except (json.JSONDecodeError, AttributeError):
            continue
        if intent in VALID_INTENTS:
            counts[intent] = counts.get(intent, 0) + 1
    return [
        {
            "intent": intent,
            "label_de": INTENT_LABELS_DE[intent],
            "count": counts[intent],
        }
        for intent in sorted(counts, key=lambda i: (-counts[i], i))
    ]


def build_summary(conn: sqlite3.Connection, store_id: str) -> dict[str, Any]:
    """Real database counts for the operations dashboard."""
    return {
        "store_id": store_id,
        "conversations_count": _count(
            conn,
            "SELECT COUNT(*) FROM conversations WHERE store_id = ?",
            (store_id,),
        ),
        "messages_count": _count(
            conn,
            """SELECT COUNT(*) FROM messages m
               JOIN conversations c ON c.id = m.conversation_id
               WHERE c.store_id = ?""",
            (store_id,),
        ),
        "tickets_open": _count(
            conn,
            "SELECT COUNT(*) FROM tickets WHERE store_id = ? AND status = 'open'",
            (store_id,),
        ),
        "tickets_total": _count(
            conn,
            "SELECT COUNT(*) FROM tickets WHERE store_id = ?",
            (store_id,),
        ),
        "escalations_count": _count(
            conn,
            """SELECT COUNT(*) FROM workflow_events
               WHERE store_id = ? AND event_key = 'escalated'
                 AND status = 'done'""",
            (store_id,),
        ),
        "intents_breakdown": intents_breakdown(conn, store_id),
        "recent_events": [
            {
                "id": row["id"],
                "event_key": row["event_key"],
                "label_de": row["label_de"],
                "status": row["status"],
                "conversation_id": row["conversation_id"],
                "created_at": row["created_at"],
            }
            for row in conn.execute(
                """SELECT id, event_key, label_de, status, conversation_id,
                          created_at
                   FROM workflow_events
                   WHERE store_id = ?
                   ORDER BY id DESC LIMIT 15""",
                (store_id,),
            ).fetchall()
        ],
        "demo_data": True,
    }
