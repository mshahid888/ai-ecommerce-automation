"""POST /api/chat — the conversational entry point (Phase 2).

Full pipeline: validate → classify → extract → deterministic lookup/rules →
German reply grounded only in verified demo data → persist
conversation + messages + workflow events.

Response contract (JSON):
  {conversation_id, intent, confidence, order_ref, reply_de, answer,
   order, timeline, events, ticket_id, ticket, provider, escalated,
   quota_fallback, quota_note}
``answer``/``events``/``ticket`` are the canonical names; ``reply_de``,
``timeline``, ``ticket_id`` stay for backward compatibility.

Never invents order/product data; unknown references → German
clarification or human escalation. Provider failures surface as
``ai_provider_unavailable`` with an honest German fallback reply.

Phase 7: real-provider calls are wrapped in a daily quota guard
(``LLM_DAILY_REQUEST_CAP``). When the cap is exhausted the request is
retried with the deterministic mock provider; the response carries
``quota_fallback: true`` and an honest German note instead of failing.
Validation errors return 400 with German messages.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ..ai.providers import LLMError, MockLLMProvider, get_provider
from ..ai.quota import (
    QUOTA_FALLBACK_NOTE_DE,
    check_and_consume_quota,
    is_real_provider,
)
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


def _result_to_response(result, quota_fallback: bool = False) -> dict:
    timeline = result.timeline
    ticket = {"id": result.ticket_id} if result.ticket_id is not None else None
    response = {
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
    if quota_fallback:
        response["quota_fallback"] = True
        response["quota_note"] = QUOTA_FALLBACK_NOTE_DE
    return response


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


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
        # Phase 7: German, customer-facing validation errors (400).
        raise HTTPException(status_code=400, detail=error)

    message: str = payload["message"].strip()
    store_id: str = payload.get("store_id") or DEMO_STORE_ID
    actor_ip = _client_ip(request)

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

    quota_fallback = False
    if is_real_provider(provider):
        if check_and_consume_quota(
            db, settings.llm_provider, settings.llm_daily_request_cap
        ):
            pass  # quota available: proceed with the real provider
        else:
            provider = MockLLMProvider()
            quota_fallback = True

    try:
        result = run_pipeline(
            message, store_id, db, provider, settings,
            actor_ip=actor_ip, quota_fallback=quota_fallback,
        )
        if quota_fallback:
            # The answer came from the mock, not the configured provider.
            result.provider = "mock"
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

    return _result_to_response(result, quota_fallback=quota_fallback)
