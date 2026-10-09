"""POST /api/chat — the conversational entry point (Phase 1 skeleton).

Honest skeleton: validates, runs the pipeline stub, logs real events.
Never invents order data; provider failures surface as
``ai_provider_unavailable`` with a German fallback reply.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ..ai.providers import LLMError, get_provider
from ..config import Settings
from ..db.repositories import EventRepository
from ..services.pipeline import (
    DEMO_STORE_ID,
    EVENT_INTENT_CLASSIFIED,
    EVENT_MESSAGE_RECEIVED,
    run_pipeline,
)
from ..validators import body_within_cap, validate_message_payload
from .deps import get_db, get_settings

router = APIRouter()


@router.post("/chat")
async def chat(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    raw_body = await request.body()
    if not body_within_cap(raw_body, settings):
        return JSONResponse(
            status_code=413,
            content={"error": "payload_too_large", "reply_de": ""},
        )
    try:
        payload = await request.json()
    except Exception:
        payload = None
    ok, error = validate_message_payload(payload, settings)
    if not ok:
        raise HTTPException(status_code=422, detail=error)

    message: str = payload["message"].strip()
    store_id: str = payload.get("store_id") or DEMO_STORE_ID

    try:
        provider = get_provider(settings)
    except LLMError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": "ai_provider_unavailable",
                "reply_de": (
                    "Der KI-Dienst ist derzeit nicht erreichbar. "
                    "Bitte versuche es später erneut oder wende dich "
                    "an unser Team."
                ),
            },
        )

    try:
        result = run_pipeline(message, store_id, db, provider, settings)
    except LLMError:
        # Log the failure as a real event, then answer honestly.
        convo = db.execute(
            "INSERT INTO conversations (store_id, session_key) VALUES (?, ?)",
            (store_id, None),
        )
        conversation_id = convo.lastrowid
        EventRepository(db).log_event(
            store_id,
            conversation_id,
            EVENT_MESSAGE_RECEIVED,
            "Nachricht empfangen",
            {"length": len(message)},
        )
        EventRepository(db).log_event(
            store_id,
            conversation_id,
            EVENT_INTENT_CLASSIFIED,
            "Absichtserkennung fehlgeschlagen",
            {},
            status="failed",
        )
        db.commit()
        return JSONResponse(
            status_code=502,
            content={
                "error": "ai_provider_unavailable",
                "reply_de": (
                    "Der KI-Dienst ist derzeit nicht erreichbar. "
                    "Bitte versuche es später erneut oder wende dich "
                    "an unser Team."
                ),
            },
        )

    return {
        "conversation_id": result.conversation_id,
        "intent": result.intent,
        "confidence": result.confidence,
        "order_ref": result.order_ref,
        "reply_de": result.reply_de,
        "timeline": result.timeline,
        "ticket_id": result.ticket_id,
        "provider": result.provider,
    }
