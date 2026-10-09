"""Chat pipeline skeleton (Phase 1).

``run_pipeline`` executes the real control flow with stubbed intelligence:

1. validate input
2. open (or reuse) a conversation and persist the user message
3. classify the message via the configured ``LLMProvider``
4. decide the action plan (Phase 1: stub — escalation decision is real)
5. generate a reply (Phase 1: clearly labeled demo stub text)
6. persist the assistant message and the timeline

IMPORTANT: every step that executes logs a real ``workflow_events`` row via
``EventRepository.log_event``. Events are only recorded when the step
actually runs — a skipped step leaves no event behind.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from ..ai.providers import LLMError, LLMProvider
from ..config import Settings
from ..db.repositories import EventRepository, TicketRepository
from ..rules.escalation import should_escalate
from .intent import Intent

DEMO_STORE_ID = "demo-muster-shop"

# Event keys used in Phase 1. Later phases add their own keys; the
# ``timeline`` in the chat response is built from these events.
EVENT_MESSAGE_RECEIVED = "message_received"
EVENT_INTENT_CLASSIFIED = "intent_classified"
EVENT_ACTION_PLANNED = "action_planned"
EVENT_RESPONSE_GENERATED = "response_generated"


@dataclass
class PipelineResult:
    conversation_id: int
    intent: str
    confidence: float
    order_ref: str | None
    reply_de: str
    timeline: list[dict[str, Any]] = field(default_factory=list)
    ticket_id: int | str | None = None
    provider: str = "mock"
    escalated: bool = False


def _parse_classification(raw: str) -> tuple[str, float, str | None, bool]:
    """Parse the provider's raw JSON into (intent, confidence, order_ref,
    requires_human). Unparseable output → unknown with 0.0 confidence."""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return Intent.UNKNOWN.value, 0.0, None, True
    intent = parsed.get("intent")
    if intent not in {i.value for i in Intent}:
        intent = Intent.UNKNOWN.value
    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    order_ref = parsed.get("order_ref") or parsed.get("order_id")
    if order_ref is not None and not isinstance(order_ref, str):
        order_ref = str(order_ref)
    requires_human = bool(parsed.get("requires_human", False))
    return intent, confidence, order_ref, requires_human


def run_pipeline(
    message: str,
    store_id: str,
    conn: sqlite3.Connection,
    provider: LLMProvider,
    settings: Settings,
) -> PipelineResult:
    """Run the chat pipeline for one customer message.

    Raises:
        LLMError: when the AI provider fails. The caller converts this to
            the honest ``ai_provider_unavailable`` response.
    """
    events = EventRepository(conn)
    tickets = TicketRepository(conn)

    # --- Step 1: conversation + persist user message ----------------------
    convo = conn.execute(
        "INSERT INTO conversations (store_id, session_key) VALUES (?, ?)",
        (store_id, None),
    )
    conversation_id = convo.lastrowid
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (conversation_id, "user", message),
    )
    events.log_event(
        store_id,
        conversation_id,
        EVENT_MESSAGE_RECEIVED,
        "Nachricht empfangen",
        {"length": len(message)},
    )

    # --- Step 2: classify via provider ------------------------------------
    raw = provider.classify(message)  # may raise LLMError
    intent, confidence, order_ref, requires_human = _parse_classification(raw)
    events.log_event(
        store_id,
        conversation_id,
        EVENT_INTENT_CLASSIFIED,
        "Absicht erkannt",
        {
            "intent": intent,
            "confidence": confidence,
            "order_ref": order_ref,
            "provider": type(provider).__name__,
        },
    )

    # --- Step 3: action plan (stub) ----------------------------------------
    escalated = should_escalate(intent, confidence) or requires_human
    ticket_id: int | str | None = None
    if escalated:
        ticket = tickets.create(
            store_id,
            conversation_id=conversation_id,
            intent=intent,
            order_ref=order_ref,
            summary=f"[Phase 1 Stub] Eskalation: {intent} "
                    f"(confidence {confidence:.2f})",
            status="open",
            priority="high" if intent == "complaint" else "normal",
            escalation_reason=(
                "requires_human flag" if requires_human
                else f"confidence {confidence:.2f} < threshold oder kritische Absicht"
            ),
            recommended_action="Phase 4: echte Ticket-Workflow-Anbindung",
        )
        ticket_id = ticket.get("id")
    events.log_event(
        store_id,
        conversation_id,
        EVENT_ACTION_PLANNED,
        "Aktionsplan erstellt",
        {
            "escalated": escalated,
            "ticket_id": ticket_id,
            "plan": "phase_1_stub",
        },
    )

    # --- Step 4: reply (Phase 1 demo stub — never invents order data) ------
    if escalated:
        reply_de = (
            "Dies ist eine Demo-Antwort (Phase 1 – Stub). "
            "Deine Anfrage wurde an unser Team weitergeleitet; "
            "wir melden uns so bald wie möglich bei dir."
        )
    else:
        reply_de = (
            "Dies ist eine Demo-Antwort (Phase 1 – Stub). "
            "Der KI-Workflow ist noch nicht angebunden – "
            "in Phase 4 beantworten wir hier Bestell- und Produktfragen "
            "mit echten Daten aus dem Demo-Shop."
        )
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (conversation_id, "assistant", reply_de),
    )
    events.log_event(
        store_id,
        conversation_id,
        EVENT_RESPONSE_GENERATED,
        "Antwort erstellt",
        {"escalated": escalated},
    )
    conn.commit()

    timeline = [
        {
            "key": row["event_key"],
            "label_de": row["label_de"],
            "status": row["status"],
        }
        for row in conn.execute(
            "SELECT event_key, label_de, status FROM workflow_events "
            "WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
    ]

    return PipelineResult(
        conversation_id=conversation_id,
        intent=intent,
        confidence=confidence,
        order_ref=order_ref,
        reply_de=reply_de,
        timeline=timeline,
        ticket_id=ticket_id,
        provider=settings.llm_provider,
        escalated=escalated,
    )
