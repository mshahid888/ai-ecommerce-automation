"""GET /api/tickets — ticket list and detail (read-only in Phase 1)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db.repositories import TicketRepository
from ..services.pipeline import DEMO_STORE_ID
from .deps import get_db

router = APIRouter()


@router.get("/tickets")
def list_tickets(
    store_id: str = Query(default=DEMO_STORE_ID),
    limit: int = Query(default=50, le=200),
    db: sqlite3.Connection = Depends(get_db),
):
    return TicketRepository(db).list(store_id, limit=limit)


@router.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: int,
    store_id: str = Query(default=DEMO_STORE_ID),
    db: sqlite3.Connection = Depends(get_db),
):
    ticket = TicketRepository(db).get(store_id, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return ticket
