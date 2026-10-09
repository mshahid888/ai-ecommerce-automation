"""Phase 6 ops API: dashboard summary, conversation and ticket detail views.

All endpoints are read-only and strictly store-scoped: rows from another
store are invisible here. Numbers come straight from the database; the
summary marks itself as demo data.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db.repositories import (
    ConversationRepository,
    TicketRepository,
)
from ..services.dashboard import build_summary
from ..services.intent import intent_label_de
from ..services.pipeline import DEMO_STORE_ID
from .deps import get_db

router = APIRouter()


@router.get("/dashboard/summary")
def dashboard_summary(
    store_id: str = Query(default=DEMO_STORE_ID),
    db: sqlite3.Connection = Depends(get_db),
):
    return build_summary(db, store_id)


@router.get("/conversations")
def list_conversations(
    store_id: str = Query(default=DEMO_STORE_ID),
    limit: int = Query(default=50, le=200),
    db: sqlite3.Connection = Depends(get_db),
):
    conversations = ConversationRepository(db).list(store_id, limit=limit)
    return [
        {
            **c,
            "last_intent_label_de": intent_label_de(c["last_intent"]),
        }
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    store_id: str = Query(default=DEMO_STORE_ID),
    db: sqlite3.Connection = Depends(get_db),
):
    repo = ConversationRepository(db)
    conversation = repo.get(store_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    messages = repo.messages(store_id, conversation_id) or []
    events = repo.events(store_id, conversation_id) or []
    return {
        "id": conversation["id"],
        "started_at": conversation["created_at"],
        "message_count": len(messages),
        "messages": [
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "created_at": m["created_at"],
            }
            for m in messages
        ],
        "events": events,  # real workflow timeline, oldest first
    }


@router.get("/tickets")
def list_tickets(
    store_id: str = Query(default=DEMO_STORE_ID),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: sqlite3.Connection = Depends(get_db),
):
    tickets = TicketRepository(db).list(
        store_id, status=status, limit=limit
    )
    return [
        {
            **t,
            "intent_label_de": intent_label_de(t.get("intent")),
        }
        for t in tickets
    ]


@router.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: int,
    store_id: str = Query(default=DEMO_STORE_ID),
    db: sqlite3.Connection = Depends(get_db),
):
    ticket = TicketRepository(db).get(store_id, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")

    conversation_id = ticket.get("conversation_id")
    messages: list[dict] = []
    events: list[dict] = []
    if conversation_id:
        repo = ConversationRepository(db)
        messages = repo.messages(store_id, conversation_id) or []
        events = repo.events(store_id, conversation_id) or []

    return {
        **ticket,
        "intent_label_de": intent_label_de(ticket.get("intent")),
        "messages": [
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "created_at": m["created_at"],
            }
            for m in messages
        ],
        "events": events,
    }
