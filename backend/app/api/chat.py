"""POST /api/chat — the conversational entry point (Phase 2).

Full pipeline: validate → classify → extract → deterministic lookup/rules →
German reply grounded only in verified demo data → persist
conversation + messages + workflow events.

Response contract (JSON):
  {conversation_id, intent, confidence, order_ref, reply_de, answer,
   order, timeline, events, ticket_id, ticket, provider, escalated}
``answer``/``events``/``ticket`` are the canonical names; ``reply_de``,
``timeline``, ``ticket_id`` stay for backward compatibility.

Never invents order/product data; unknown references → German
clarification or human escalation. Provider failures surface as
``ai_provider_unavailable`` with an honest German fallback reply.
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


def _result_to_response(result) -> dict:
    timeline = result.timeline
    ticket = {"id": result.ticket_id} if result.ticket_id is not None else None
    return {
        "conversation_id": result.conversation_id,
        "intent": result.intent,
        "confidence": result.confidence,
        "order_ref": result.order_ref,
        "reply_de": result.reply_de,
        "answer": result.reply_de,
        "order": result.order,
        "timeline": timeline,
        "events": timeline,
        "ticket_id": result.ticket_id,
        "ticket": ticket,
        "provider": result.provider,
        "escalated": result.escalated,
    }


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
    except LLMError:
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

    return _result_to_response(result)
