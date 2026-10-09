"""Chat pipeline (Phase 2): full deterministic workflow.

Pipeline: validate → classify (provider) → extract entities →
deterministic rules/lookups → generate German reply from verified data →
validate output → log events → persist conversation.

Rules (iron-clad):
- The provider only classifies and suggests an intent. It never executes
  actions, never reads the database, never decides eligibility.
- All data shown to the customer comes from the SQLite demo store via
  ``db/repositories.py`` + ``rules/`` — never from the provider output.
- Every ``workflow_events`` row is logged only when the corresponding
  operation actually executed. A skipped step leaves no event behind.
- Unknown order/product/attribute → honest German clarification or human
  escalation, never invented data.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from ..ai.providers import LLMError, LLMProvider
from ..config import Settings
from ..db.repositories import EventRepository, TicketRepository
from ..rules import product_rules
from ..rules.escalation import should_escalate
from ..rules.order_rules import lookup_order, normalize_order_ref
from ..rules.return_policy import evaluate_return_eligibility
from .intent import Intent

DEMO_STORE_ID = "demo-muster-shop"

# Event keys — each maps to a German label shown in the UI timeline.
EVENT_MESSAGE_RECEIVED = "message_received"
EVENT_INTENT_CLASSIFIED = "intent_classified"
EVENT_ORDER_REF_EXTRACTED = "order_ref_extracted"
EVENT_ORDER_LOOKUP = "order_lookup"
EVENT_PRODUCT_SEARCH = "product_search"
EVENT_POLICY_CHECK = "policy_check"
EVENT_RETURN_REQUEST_CREATED = "return_request_created"
EVENT_TICKET_CREATED = "ticket_created"
EVENT_ESCALATED = "escalated"
EVENT_RULES_APPLIED = "rules_applied"
EVENT_RESPONSE_GENERATED = "response_generated"
EVENT_INTERACTION_LOGGED = "interaction_logged"

_EVENT_LABELS = {
    EVENT_MESSAGE_RECEIVED: "Anfrage empfangen",
    EVENT_INTENT_CLASSIFIED: "Anliegen erkannt",
    EVENT_ORDER_REF_EXTRACTED: "Bestellnummer extrahiert",
    EVENT_ORDER_LOOKUP: "Demo-Bestellung geprüft",
    EVENT_PRODUCT_SEARCH: "Produktkatalog durchsucht",
    EVENT_POLICY_CHECK: "Retourenrichtlinie geprüft",
    EVENT_RETURN_REQUEST_CREATED: "Retourenantrag erstellt",
    EVENT_TICKET_CREATED: "Support-Ticket erstellt",
    EVENT_ESCALATED: "An Mitarbeiter eskaliert",
    EVENT_RULES_APPLIED: "Geschäftsregeln angewendet",
    EVENT_RESPONSE_GENERATED: "Antwort erstellt",
    EVENT_INTERACTION_LOGGED: "Supportvorgang protokolliert",
}

_DEMO_DISCLAIMER = "Hinweis: Demo-Umgebung — alle Daten sind simuliert."

_STATUS_DE = {
    "shipped": "versendet",
    "processing": "in Bearbeitung",
    "delivered": "zugestellt",
    "delayed": "verzögert",
}


@dataclass
class PipelineResult:
    conversation_id: int
    intent: str
    confidence: float
    order_ref: str | None
    reply_de: str
    order: dict[str, Any] | None = None
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


def _de_date(iso: str | None) -> str | None:
    """'2026-10-14' → '14.10.2026' (None-safe)."""
    if not iso:
        return None
    try:
        year, month, day = str(iso)[:10].split("-")
        return f"{int(day):02d}.{int(month):02d}.{year}"
    except ValueError:
        return None


def _format_eur(cents: int | None, currency: str | None = "EUR") -> str:
    if cents is None:
        return ""
    return f"{cents / 100:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _minimal_order(order: dict[str, Any] | None) -> dict[str, Any] | None:
    if order is None:
        return None
    return {
        "order_ref": order.get("order_ref"),
        "status": order.get("status"),
        "status_de": _STATUS_DE.get(order.get("status"), order.get("status")),
        "carrier": order.get("carrier"),
        "tracking_ref": order.get("tracking_ref"),
        "eta_date": order.get("eta_date"),
        "eta_date_de": _de_date(order.get("eta_date")),
        "total": _format_eur(order.get("total_cents"), order.get("currency")),
    }


def _load_policy(conn: sqlite3.Connection, store_id: str, key: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT policy_json FROM store_policies WHERE store_id = ? AND policy_key = ?",
        (store_id, key),
    ).fetchone()
    if row is None:
        return {}
    try:
        parsed = json.loads(row["policy_json"])
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


class _Pipeline:
    """Per-request pipeline state; keeps ``run_pipeline`` readable."""

    def __init__(
        self,
        message: str,
        store_id: str,
        conn: sqlite3.Connection,
        provider: LLMProvider,
        settings: Settings,
    ) -> None:
        self.message = message
        self.store_id = store_id
        self.conn = conn
        self.provider = provider
        self.settings = settings
        self.events = EventRepository(conn)
        self.tickets = TicketRepository(conn)
        self.conversation_id: int = 0
        self.ticket_id: int | str | None = None
        self.escalated = False
        self.order: dict[str, Any] | None = None

    # -- helpers ---------------------------------------------------------
    def log(self, key: str, payload: dict[str, Any] | None = None,
            status: str = "done") -> None:
        self.events.log_event(
            self.store_id, self.conversation_id, key,
            _EVENT_LABELS[key], payload, status=status,
        )

    def create_ticket(self, intent: str, order_ref: str | None, summary: str,
                      escalation_reason: str, recommended_action: str,
                      priority: str = "normal") -> int | str | None:
        ticket = self.tickets.create(
            self.store_id,
            conversation_id=self.conversation_id,
            intent=intent,
            order_ref=order_ref,
            summary=summary[:200],
            status="open",
            priority=priority,
            escalation_reason=escalation_reason,
            recommended_action=recommended_action,
        )
        self.ticket_id = ticket.get("id")
        self.log(EVENT_TICKET_CREATED, {
            "ticket_id": self.ticket_id, "intent": intent,
            "order_ref": order_ref,
        })
        return self.ticket_id

    def timeline(self) -> list[dict[str, Any]]:
        return [
            {"key": r["event_key"], "label_de": r["label_de"],
             "status": r["status"]}
            for r in self.conn.execute(
                "SELECT event_key, label_de, status FROM workflow_events "
                "WHERE conversation_id = ? ORDER BY id ASC",
                (self.conversation_id,),
            ).fetchall()
        ]

    # -- intent handlers -------------------------------------------------
    def handle_order_status(self, order_ref: str | None) -> str:
        if not order_ref:
            return (
                "Um den Bestellstatus zu prüfen, benötige ich Ihre "
                "Bestellnummer — zum Beispiel #10482. "
                f"{_DEMO_DISCLAIMER}"
            )
        self.log(EVENT_ORDER_REF_EXTRACTED, {"order_ref": order_ref})

        order = lookup_order(self.conn, self.store_id, order_ref)
        self.log(EVENT_ORDER_LOOKUP, {
            "order_ref": order_ref, "found": order is not None,
        })
        if order is None:
            return (
                f"Die Bestellung #{order_ref} wurde nicht gefunden. "
                "Bitte prüfen Sie die Nummer — oder soll sich ein "
                "Mitarbeiter bei Ihnen melden? "
                f"{_DEMO_DISCLAIMER}"
            )

        self.order = order
        status = order.get("status") or ""
        status_de = _STATUS_DE.get(status, status)
        self.log(EVENT_RULES_APPLIED, {"status": status})

        parts = [
            f"Ihre Bestellung #{order['order_ref']} ist {status_de}."
        ]
        if order.get("carrier"):
            parts.append(f"Versandpartner: {order['carrier']}.")
        if order.get("tracking_ref"):
            parts.append(
                f"Sendungsnummer: {order['tracking_ref']} (Demo-Referenz, "
                "keine Live-Sendungsverfolgung)."
            )
        eta_de = _de_date(order.get("eta_date"))
        if status == "delivered" and eta_de:
            parts.append(f"Zugestellt am {eta_de}.")
        elif eta_de:
            parts.append(f"Voraussichtliche Zustellung: {eta_de}.")
        if order.get("total_cents"):
            parts.append(
                f"Bestellwert: {_format_eur(order['total_cents'], order.get('currency'))}."
            )
        if status == "delayed":
            parts.append(
                "Die Lieferung verzögert sich leider. Soll ein Mitarbeiter "
                "den Fall prüfen?"
            )
        if status == "delivered":
            parts.append(
                "Innerhalb von 30 Tagen können Sie die Bestellung "
                "zurückgeben — sagen Sie einfach „Retoure anmelden“."
            )
        parts.append(_DEMO_DISCLAIMER)
        return " ".join(parts)

    def handle_product_question(self) -> str:
        self.log(EVENT_PRODUCT_SEARCH, {"query": self.message[:80]})
        product = product_rules.find_product(
            self.conn, self.store_id, self.message
        )
        if product is None:
            return (
                "Zu welchem Produkt möchten Sie etwas wissen? Nennen Sie mir "
                "zum Beispiel die Trinkflasche „AquaPure 750“. "
                f"{_DEMO_DISCLAIMER}"
            )

        attrs = product_rules.product_attributes(product)
        requested = product_rules.detect_requested_attributes(self.message)
        known = [(k, attrs[k]) for k in requested if k in attrs]
        missing = [k for k in requested if k not in attrs]
        name = product.get("name") or "das Produkt"

        if requested and not known:
            labels = ", ".join(
                product_rules.attribute_label(k) for k in missing
            )
            return (
                f"Zu „{labels}“ liegen mir im Produktkatalog des Demo-Shops "
                f"leider keine Informationen für {name} vor — ich erfinde "
                "keine Angaben. Soll ich Ihre Frage an einen Mitarbeiter "
                "weitergeben? "
                f"{_DEMO_DISCLAIMER}"
            )

        if known:
            answers = [
                f"{product_rules.attribute_label(k)}: "
                f"{product_rules.format_attribute_value(k, v)}"
                for k, v in known
            ]
            if missing:
                answers.append(
                    "Zu "
                    + ", ".join(product_rules.attribute_label(k) for k in missing)
                    + " liegen mir leider keine Informationen vor"
                )
            prefix = "Ja" if known[0][1] is True else "Laut Produktkatalog"
            return (
                f"{prefix}, {name} — {'; '.join(answers)}. "
                f"(Angaben aus dem Produktkatalog des Demo-Shops.) "
                f"{_DEMO_DISCLAIMER}"
            )

        # No specific attribute detected → general product info.
        available = ", ".join(
            product_rules.attribute_label(k) for k in attrs
        )
        return (
            f"{name}: {product.get('description') or 'Keine Beschreibung verfügbar.'} "
            f"Verfügbare Angaben: {available}. "
            f"(Angaben aus dem Produktkatalog des Demo-Shops.) "
            f"{_DEMO_DISCLAIMER}"
        )

    def handle_return_request(self, order_ref: str | None,
                              intent: str) -> str:
        if not order_ref:
            return (
                "Gerne nehme ich Ihre Retoure auf. Bitte nennen Sie mir Ihre "
                "Bestellnummer — zum Beispiel #10482. "
                f"{_DEMO_DISCLAIMER}"
            )
        self.log(EVENT_ORDER_REF_EXTRACTED, {"order_ref": order_ref})

        order = lookup_order(self.conn, self.store_id, order_ref)
        self.log(EVENT_ORDER_LOOKUP, {
            "order_ref": order_ref, "found": order is not None,
        })
        if order is None:
            return (
                f"Die Bestellung #{order_ref} wurde nicht gefunden. "
                "Bitte prüfen Sie die Nummer — oder soll sich ein "
                "Mitarbeiter bei Ihnen melden? "
                f"{_DEMO_DISCLAIMER}"
            )
        self.order = order

        policy = _load_policy(self.conn, self.store_id, "returns")
        result = evaluate_return_eligibility(policy, order)
        self.log(EVENT_POLICY_CHECK, {
            "order_ref": order_ref,
            "verdict": result["verdict"],
            "eligible": result["eligible"],
        })

        verdict = result["verdict"]
        if verdict in ("preliminary_eligible", "not_shipped"):
            # Information gathering + preliminary check are done here.
            # Authorization and any refund stay human — the demo only
            # records a pending return request, never a real refund.
            cur = self.conn.execute(
                "INSERT INTO return_requests (store_id, order_ref, status, reason) "
                "VALUES (?, ?, 'pending_review', ?)",
                (self.store_id, order_ref,
                 f"Demo-Retourenantrag, {verdict}"),
            )
            self.log(EVENT_RETURN_REQUEST_CREATED, {
                "return_request_id": cur.lastrowid, "order_ref": order_ref,
            })
            self.create_ticket(
                intent, order_ref,
                summary=f"Retourenantrag Bestellung #{order_ref} "
                        f"({result['details_de'][:120]})",
                escalation_reason=(
                    "Retouren-Triage: vorläufige Prüfung abgeschlossen, "
                    "Freigabe durch Mitarbeiter erforderlich"
                ),
                recommended_action=(
                    "Mitarbeiter prüft Antrag und sendet Rücksendeetikett "
                    "(Demo — keine echte Retoure)"
                ),
            )
            address = policy.get("ruecksendeadresse", "")
            return (
                f"Ihr Retourenantrag für Bestellung #{order_ref} wurde als "
                f"Demo-Vorgang angelegt (Ticket #{self.ticket_id}) — es wird "
                f"keine echte Retoure autorisiert und keine Rückerstattung "
                f"ausgeführt. {result['details_de']} "
                f"Nächster Schritt: Ein Mitarbeiter prüft den Antrag und "
                f"sendet Ihnen das Rücksendeetikett. "
                f"Rücksendeadresse: {address}. "
                f"{_DEMO_DISCLAIMER}"
            )

        if verdict == "window_expired":
            self.create_ticket(
                intent, order_ref,
                summary=f"Retoure abgelehnt (Frist): Bestellung #{order_ref}",
                escalation_reason=(
                    "Rückgabefrist überschritten — Kulanzentscheidung "
                    "durch Mitarbeiter"
                ),
                recommended_action="Mitarbeiter kontaktiert Kunden",
            )
            return (
                f"{result['details_de']} Ich habe den Fall als Ticket "
                f"#{self.ticket_id} an einen Mitarbeiter weitergegeben, der "
                f"prüft, ob eine Kulanzlösung möglich ist. "
                f"{_DEMO_DISCLAIMER}"
            )

        # verdict "unclear" / "order_missing" → human review.
        self.create_ticket(
            intent, order_ref,
            summary=f"Retoure unklar: Bestellung #{order_ref}",
            escalation_reason=(
                "Automatische Prüfung nicht möglich — manuelle Prüfung"
            ),
            recommended_action="Mitarbeiter prüft Retourenberechtigung",
        )
        self.escalated = True
        return (
            f"{result['details_de']} Ich habe ein Ticket #{self.ticket_id} "
            f"erstellt — ein Mitarbeiter wird sich so bald wie möglich bei "
            f"Ihnen melden. {_DEMO_DISCLAIMER}"
        )

    def handle_escalation(self, intent: str, confidence: float,
                          order_ref: str | None,
                          requires_human: bool) -> str:
        if order_ref:
            normalized = normalize_order_ref(order_ref)
            self.log(EVENT_ORDER_REF_EXTRACTED, {"order_ref": normalized})
            order = lookup_order(self.conn, self.store_id, normalized)
            self.log(EVENT_ORDER_LOOKUP, {
                "order_ref": normalized, "found": order is not None,
            })
            if order is not None:
                self.order = order

        reason = (
            "requires_human flag des Klassifikators"
            if requires_human
            else f"Konfidenz {confidence:.2f} unter Schwelle oder kritische Absicht"
        )
        self.create_ticket(
            intent, normalize_order_ref(order_ref),
            summary=self.message[:200],
            escalation_reason=reason,
            recommended_action="Mitarbeiter antwortet dem Kunden",
            priority="high" if intent == "complaint" else "normal",
        )
        self.escalated = True
        self.log(EVENT_ESCALATED, {
            "ticket_id": self.ticket_id, "reason": reason,
        })

        if intent == "unknown":
            return (
                "Ich bin mir nicht sicher, ob ich Ihre Anfrage richtig "
                f"verstanden habe. Ich habe ein Ticket #{self.ticket_id} "
                "erstellt — ein Mitarbeiter wird sich so bald wie möglich "
                f"bei Ihnen melden. {_DEMO_DISCLAIMER}"
            )
        if intent == "complaint":
            return (
                "Das tut mir leid zu hören. Ich habe Ihr Anliegen mit hoher "
                f"Priorität an unser Team weitergegeben (Ticket "
                f"#{self.ticket_id}). Ein Mitarbeiter wird sich so bald wie "
                "möglich bei Ihnen melden — wir versprechen nichts, was wir "
                f"nicht geprüft haben. {_DEMO_DISCLAIMER}"
            )
        return (
            "Verstanden — ich gebe Ihr Anliegen an unser Team weiter "
            f"(Ticket #{self.ticket_id}). Ein Mitarbeiter wird sich so bald "
            f"wie möglich bei Ihnen melden. {_DEMO_DISCLAIMER}"
        )


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
    pipe = _Pipeline(message, store_id, conn, provider, settings)

    # --- Step 1: conversation + persist user message ----------------------
    convo = conn.execute(
        "INSERT INTO conversations (store_id, session_key) VALUES (?, ?)",
        (store_id, None),
    )
    pipe.conversation_id = convo.lastrowid
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (pipe.conversation_id, "user", message),
    )
    pipe.log(EVENT_MESSAGE_RECEIVED, {"length": len(message)})

    # --- Step 2: classify via provider ------------------------------------
    raw = provider.classify(message)  # may raise LLMError
    intent, confidence, order_ref, requires_human = _parse_classification(raw)
    pipe.log(EVENT_INTENT_CLASSIFIED, {
        "intent": intent, "confidence": confidence,
        "order_ref": order_ref,
        "provider": type(provider).__name__,
    })

    # --- Step 3: deterministic action plan --------------------------------
    normalized_ref = normalize_order_ref(order_ref)
    if intent == Intent.ORDER_STATUS.value:
        if should_escalate(intent, confidence) or requires_human:
            reply = pipe.handle_escalation(
                intent, confidence, normalized_ref, requires_human)
        else:
            reply = pipe.handle_order_status(normalized_ref)
    elif intent == Intent.PRODUCT_QUESTION.value:
        if should_escalate(intent, confidence) or requires_human:
            reply = pipe.handle_escalation(
                intent, confidence, normalized_ref, requires_human)
        else:
            reply = pipe.handle_product_question()
    elif intent == Intent.RETURN_REQUEST.value:
        # Returns always create a structured ticket for staff review —
        # this IS the human handoff for the return workflow.
        reply = pipe.handle_return_request(normalized_ref, intent)
    else:  # complaint, human_support, unknown
        reply = pipe.handle_escalation(
            intent, confidence, normalized_ref, requires_human)

    # --- Step 4: persist assistant message + closing events ----------------
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (pipe.conversation_id, "assistant", reply),
    )
    pipe.log(EVENT_RESPONSE_GENERATED, {"escalated": pipe.escalated})
    pipe.log(EVENT_INTERACTION_LOGGED, {
        "intent": intent, "ticket_id": pipe.ticket_id,
    })
    conn.commit()

    return PipelineResult(
        conversation_id=pipe.conversation_id,
        intent=intent,
        confidence=confidence,
        order_ref=normalized_ref,
        reply_de=reply,
        order=_minimal_order(pipe.order),
        timeline=pipe.timeline(),
        ticket_id=pipe.ticket_id,
        provider=settings.llm_provider,
        escalated=pipe.escalated,
    )
