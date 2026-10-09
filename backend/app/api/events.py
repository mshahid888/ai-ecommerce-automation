"""GET /api/events — workflow timeline events, newest first (Phase 1)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from ..db.repositories import EventRepository
from ..services.pipeline import DEMO_STORE_ID
from .deps import get_db

router = APIRouter()


@router.get("/events")
def list_events(
    store_id: str = Query(default=DEMO_STORE_ID),
    limit: int = Query(default=50, le=200),
    db: sqlite3.Connection = Depends(get_db),
):
    return EventRepository(db).list(store_id, limit=limit)
