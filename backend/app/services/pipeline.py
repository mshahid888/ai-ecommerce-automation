"""Chat pipeline (Phase 3): full deterministic workflow.

Pipeline: validate → classify (provider) → STRICT validation of the
provider output into a ``Classification`` schema → extract entities →
deterministic rules/lookups → generate German reply from verified data →
validate output → log events → persist conversation.

Rules (iron-clad):
- The provider only classifies and suggests an intent. It never executes
  actions, never reads the database, never decides eligibility.
- All downstream code uses the validated ``Classification`` schema from
  ``services/classification.py`` — never raw model text.
- All data shown to the customer comes from the SQLite demo store via
  ``db/repositories.py`` + ``rules/`` — never from the provider output.
- Escalation policy (rules/escalation.py): ALWAYS_HUMAN intents
  {complaint, order_cancel, human_support, unknown} always go to a human;
  confidence < 0.6 → human with reason "low_confidence".
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
from ..ai.quota import (
    EVENT_LLM_QUOTA_FALLBACK,
    EVENT_LLM_QUOTA_FALLBACK_LABEL,
)
from ..config import Settings
from ..db.repositories import EventRepository, TicketRepository
from ..integrations import (
    IntegrationError,
    StoreIntegration,
    get_store_integration,
)
from ..rules import product_rules
from ..security.audit import log_audit
from ..rules.escalation import (
    REASON_ALWAYS_HUMAN,
    REASON_LOW_CONFIDENCE,
    decide_escalation,
)
from ..rules.order_rules import normalize_order_ref
from ..rules.return_policy import (
    RETURN_REASON_DISPLAY,
    evaluate_return_eligibility,
)
from .classification import Classification, validate_classification
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
EVENT_STORE_INFO = "store_info"
EVENT_STORE_BACKEND_ERROR = "store_backend_error"

_EVENT_LABELS = {
    EVENT_MESSAGE_RECEIVED: "Message received",
    EVENT_INTENT_CLASSIFIED: "Intent detected",
    EVENT_ORDER_REF_EXTRACTED: "Order number extracted",
    EVENT_ORDER_LOOKUP: "Demo order checked",
    EVENT_PRODUCT_SEARCH: "Product catalog searched",
    EVENT_POLICY_CHECK: "Return policy checked",
    EVENT_RETURN_REQUEST_CREATED: "Return request created",
    EVENT_TICKET_CREATED: "Support ticket created",
    EVENT_ESCALATED: "Escalated to staff",
    EVENT_RULES_APPLIED: "Business rules applied",
    EVENT_RESPONSE_GENERATED: "Response generated",
    EVENT_INTERACTION_LOGGED: "Support interaction logged",
    EVENT_STORE_INFO: "Store information retrieved",
    EVENT_STORE_BACKEND_ERROR: "Store connection failed",
    EVENT_LLM_QUOTA_FALLBACK: EVENT_LLM_QUOTA_FALLBACK_LABEL,
}

_DEMO_DISCLAIMER = "Demo environment—all data is simulated."

_STATUS_DE = {
    "shipped": "shipped",
    "processing": "processing",
    "delivered": "delivered",
    "delayed": "delayed",
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


_MONTHS_EN = (
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
)


def _de_date(iso: str | None) -> str | None:
    """'2026-10-14' → '14 October 2026' (None-safe)."""
    if not iso:
        return None
    try:
        year, month, day = str(iso)[:10].split("-")
        return f"{int(day)} {_MONTHS_EN[int(month) - 1]} {year}"
    except (ValueError, IndexError):
        return None


def _format_eur(cents: int | None, currency: str | None = "EUR") -> str:
    if cents is None:
        return ""
    return f"€{cents / 100:,.2f}"


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
        actor_ip: str | None = None,
        store: StoreIntegration | None = None,
    ) -> None:
        self.message = message
        self.store_id = store_id
        self.conn = conn
        self.provider = provider
        self.settings = settings
        self.actor_ip = actor_ip
        # Phase 9: product/order lookups go through the StoreIntegration
        # interface, never direct DB queries. Falls back to the demo
        # adapter when not provided (unit-test convenience).
        self.store: StoreIntegration = store or get_store_integration(
            settings, conn, store_id
        )
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
        # Phase 7: ticket creations are audit-logged (committed with the
        # pipeline transaction at the end of run_pipeline).
        log_audit(
            self.conn,
            action="ticket_created",
            ip=self.actor_ip,
            details={
                "ticket_id": self.ticket_id,
                "intent": intent,
                "order_ref": order_ref,
                "priority": priority,
            },
            store_id=self.store_id,
        )
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
                "To check your order status, I need your order number — "
                "for example #10482. "
                f"{_DEMO_DISCLAIMER}"
            )
        self.log(EVENT_ORDER_REF_EXTRACTED, {"order_ref": order_ref})

        order = self.store.get_order(order_ref)
        self.log(EVENT_ORDER_LOOKUP, {
            "order_ref": order_ref, "found": order is not None,
        })
        if order is None:
            return (
                f"Order #{order_ref} was not found. "
                "Please check the number — or would you like a team member "
                "to get in touch? "
                f"{_DEMO_DISCLAIMER}"
            )

        self.order = order
        status = order.get("status") or ""
        self.log(EVENT_RULES_APPLIED, {"status": status})

        parts = []
        if status == "shipped" and order.get("carrier"):
            parts.append(
                f"Your order #{order['order_ref']} has been shipped via "
                f"{order['carrier']}."
            )
        elif status == "shipped":
            parts.append(f"Your order #{order['order_ref']} has been shipped.")
        elif status == "processing":
            parts.append(
                f"Your order #{order['order_ref']} is being processed."
            )
        elif status == "delivered":
            parts.append(f"Your order #{order['order_ref']} was delivered.")
        elif status == "delayed":
            parts.append(
                f"Your order #{order['order_ref']} is currently delayed."
            )
        else:
            parts.append(f"Your order #{order['order_ref']}: {status}.")
        if order.get("tracking_ref"):
            parts.append(
                f"Tracking reference: {order['tracking_ref']} (simulated "
                "reference; live tracking is unavailable)."
            )
        eta_en = _de_date(order.get("eta_date"))
        if status == "delivered" and eta_en:
            parts.append(f"Delivered on {eta_en}.")
        elif eta_en:
            parts.append(f"Estimated delivery: {eta_en}.")
        if order.get("total_cents"):
            parts.append(
                f"Order total: {_format_eur(order['total_cents'], order.get('currency'))}."
            )
        if status == "delayed":
            parts.append(
                "Unfortunately, delivery is delayed. Would you like a team "
                "member to look into this?"
            )
        if status == "delivered":
            parts.append(
                "You can return this order within 30 days — just say "
                '"start a return".'
            )
        parts.append(_DEMO_DISCLAIMER)
        return " ".join(parts)

    def handle_product_question(self) -> str:
        self.log(EVENT_PRODUCT_SEARCH, {"query": self.message[:80]})
        # Phase 9: product search goes through the store adapter; the
        # best match is matches[0] (identical ranking to before).
        matches = self.store.search_products(self.message)
        product = matches[0] if matches else None
        if product is None:
            return (
                "Which product would you like to know about? For example, "
                'the water bottle "AquaPure 750". '
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
                f"I don't have any information on \"{labels}\" in the demo "
                f"shop's product catalog for {name} — I don't invent "
                "specifications. Should I forward your question to a team "
                "member? "
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
                    "I don't have any information on "
                    + ", ".join(product_rules.attribute_label(k) for k in missing)
                    + ", unfortunately"
                )
            prefix = "Yes" if known[0][1] is True else "According to the product catalog"
            return (
                f"{prefix}, {name} — {'; '.join(answers)}. "
                f"(Details from the demo shop's product catalog.) "
                f"{_DEMO_DISCLAIMER}"
            )

        # No specific attribute detected → general product info.
        available = ", ".join(
            product_rules.attribute_label(k) for k in attrs
        )
        return (
            f"{name}: {product.get('description') or 'No description available.'} "
            f"Available details: {available}. "
            f"(Details from the demo shop's product catalog.) "
            f"{_DEMO_DISCLAIMER}"
        )

    def handle_greeting(self) -> str:
        # A plain greeting: friendly answer, no ticket, no escalation.
        return (
            "Hello and welcome to the demo shop \"Demo Shop GmbH\"! How can "
            "I help you? You can ask me, for example, about the status of "
            "your order, shipping costs, or our payment methods. "
            f"{_DEMO_DISCLAIMER}"
        )

    def handle_shipping_info(self) -> str:
        policy = _load_policy(self.conn, self.store_id, "shipping")
        self.log(EVENT_STORE_INFO, {"policy_key": "shipping"})
        if not policy:
            return (
                "Unfortunately, I don't have any shipping cost information "
                "in this demo — I don't invent details. Should I forward "
                "your question to a team member? "
                f"{_DEMO_DISCLAIMER}"
            )
        self.log(EVENT_RULES_APPLIED, {"policy_key": "shipping"})
        parts = []
        kosten = policy.get("versandkosten_eur")
        frei_ab = policy.get("versandkostenfrei_ab_eur")
        if kosten is not None:
            parts.append(
                f"Shipping: {_format_eur(int(round(kosten * 100)))}"
            )
        if frei_ab is not None:
            parts.append(
                f"free shipping from {_format_eur(int(round(frei_ab * 100)))}"
            )
        lieferzeit = policy.get("lieferzeit_werktage")
        if lieferzeit:
            parts.append(f"Delivery time: {lieferzeit} business days")
        partner = policy.get("versandpartner") or []
        if partner:
            parts.append(f"Carriers: {', '.join(partner)}")
        tracking = policy.get("tracking_hinweis")
        if tracking:
            parts.append(tracking)
        parts.append(_DEMO_DISCLAIMER)
        return " ".join(p if p.endswith(".") else p + "." for p in parts)

    def handle_payment_question(self) -> str:
        policy = _load_policy(self.conn, self.store_id, "payments")
        self.log(EVENT_STORE_INFO, {"policy_key": "payments"})
        if not policy:
            return (
                "Unfortunately, I don't have any payment method information "
                "in this demo — I don't invent details. Should I forward "
                "your question to a team member? "
                f"{_DEMO_DISCLAIMER}"
            )
        self.log(EVENT_RULES_APPLIED, {"policy_key": "payments"})
        arten = policy.get("zahlungsarten") or []
        hinweis = policy.get("hinweis") or ""
        return (
            "We accept the following payment methods: "
            f"{', '.join(arten)}. {hinweis} "
            f"{_DEMO_DISCLAIMER}"
        )

    def handle_product_availability(self) -> str:
        self.log(EVENT_PRODUCT_SEARCH, {"query": self.message[:80]})
        matches = self.store.search_products(self.message)
        product = matches[0] if matches else None
        if product is None:
            return (
                "Which product would you like to check the stock for? For "
                'example, the water bottle "AquaPure 750". '
                f"{_DEMO_DISCLAIMER}"
            )
        name = product.get("name") or "the product"
        stock = product_rules.stock_level(product)
        self.log(EVENT_RULES_APPLIED, {"product": name, "stock": stock})
        if stock is None:
            return (
                f"Unfortunately, I have no stock information for {name} — "
                "I don't invent details. Should I forward your question to "
                "a team member? "
                f"{_DEMO_DISCLAIMER}"
            )
        if stock > 0:
            return (
                f"Good news: {name} is currently in stock "
                f"(demo stock: {stock} units). "
                f"{_DEMO_DISCLAIMER}"
            )
        return (
            f"{name} is currently out of stock, unfortunately. Should I "
            "forward your request to a team member — for example, to be "
            "notified when it's available again? "
            f"{_DEMO_DISCLAIMER}"
        )

    def handle_return_request(self, order_ref: str | None, intent: str,
                              classification: Classification) -> str:
        if not order_ref:
            return (
                "I'd be happy to take your return. Please give me your "
                "order number — for example #10482. "
                f"{_DEMO_DISCLAIMER}"
            )
        self.log(EVENT_ORDER_REF_EXTRACTED, {"order_ref": order_ref})

        order = self.store.get_order(order_ref)
        self.log(EVENT_ORDER_LOOKUP, {
            "order_ref": order_ref, "found": order is not None,
        })
        if order is None:
            return (
                f"Order #{order_ref} was not found. "
                "Please check the number — or would you like a team member "
                "to get in touch? "
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
                (
                    self.store_id,
                    order_ref,
                    f"Demo return request, {verdict}"
                    + (
                        ", reason: "
                        + RETURN_REASON_DISPLAY.get(
                            classification.return_reason or "",
                            classification.return_reason or "",
                        )
                        if classification.return_reason
                        else ""
                    ),
                ),
            )
            self.log(EVENT_RETURN_REQUEST_CREATED, {
                "return_request_id": cur.lastrowid, "order_ref": order_ref,
            })
            self.create_ticket(
                intent, order_ref,
                summary=f"Return request for order #{order_ref} "
                        f"({result['details_de'][:120]})",
                escalation_reason=(
                    "Return triage: preliminary check complete, "
                    "staff approval required"
                ),
                recommended_action=(
                    "Team member reviews the request and sends the return "
                    "label (demo — no real return)"
                ),
            )
            address = policy.get("ruecksendeadresse", "")
            return (
                f"Your return request for order #{order_ref} has been "
                f"created as a demo case (Ticket #{self.ticket_id}) — no "
                f"real return is authorized and no refund is issued. "
                f"{result['details_de']} "
                f"Next step: a team member will review the request and "
                f"send you the return label. "
                f"Return address: {address}. "
                f"{_DEMO_DISCLAIMER}"
            )

        if verdict == "window_expired":
            self.create_ticket(
                intent, order_ref,
                summary=f"Return declined (window expired): order #{order_ref}",
                escalation_reason=(
                    "Return window expired — goodwill decision "
                    "by team member"
                ),
                recommended_action="Team member contacts the customer",
            )
            return (
                f"{result['details_de']} I've forwarded the case as Ticket "
                f"#{self.ticket_id} to a team member, who will check whether "
                f"a goodwill solution is possible. "
                f"{_DEMO_DISCLAIMER}"
            )

        # verdict "unclear" / "order_missing" → human review.
        self.create_ticket(
            intent, order_ref,
            summary=f"Return unclear: order #{order_ref}",
            escalation_reason=(
                "Automatic check not possible — manual review"
            ),
            recommended_action="Team member reviews return eligibility",
        )
        self.escalated = True
        return (
            f"{result['details_de']} I've created Ticket #{self.ticket_id} "
            f"— a team member will get back to you as soon as possible. "
            f"{_DEMO_DISCLAIMER}"
        )

    def handle_escalation(self, classification: Classification,
                          reason_code: str) -> str:
        """Route to a human: create a ticket and explain it honestly.

        ``reason_code`` is one of the ``rules/escalation.py`` codes
        ("low_confidence", "always_human", "classifier_requires_human")
        and is stored on the ticket.
        """
        intent = classification.intent
        order_ref = normalize_order_ref(classification.order_ref)
        if order_ref:
            self.log(EVENT_ORDER_REF_EXTRACTED, {"order_ref": order_ref})
            order = self.store.get_order(order_ref)
            self.log(EVENT_ORDER_LOOKUP, {
                "order_ref": order_ref, "found": order is not None,
            })
            if order is not None:
                self.order = order

        self.create_ticket(
            intent, order_ref,
            summary=self.message[:200],
            escalation_reason=reason_code,
            recommended_action="Team member replies to the customer",
            priority="high" if intent in (
                Intent.COMPLAINT.value, Intent.ORDER_CANCEL.value
            ) else "normal",
        )
        self.escalated = True
        self.log(EVENT_ESCALATED, {
            "ticket_id": self.ticket_id, "reason": reason_code,
        })
        # Phase 7: escalations are audit-logged (human handoffs matter).
        log_audit(
            self.conn,
            action="escalated",
            ip=self.actor_ip,
            details={
                "ticket_id": self.ticket_id,
                "intent": intent,
                "reason": reason_code,
            },
            store_id=self.store_id,
        )

        if reason_code == REASON_LOW_CONFIDENCE:
            return (
                "I'm not entirely sure about your request and I don't want "
                "to give you wrong information. I've created Ticket "
                f"#{self.ticket_id} — a team member will get back to you as "
                "soon as possible. "
                f"{_DEMO_DISCLAIMER}"
            )
        if intent == Intent.UNKNOWN.value:
            return (
                "I'm not sure I understood your request correctly. I've "
                f"created Ticket #{self.ticket_id} — a team member will get "
                "back to you as soon as possible. "
                f"{_DEMO_DISCLAIMER}"
            )
        if intent == Intent.COMPLAINT.value:
            return (
                "I'm sorry to hear that. I've forwarded your concern to our "
                "team with high priority "
                f"(Ticket #{self.ticket_id}). A team member will get back "
                "to you as soon as possible — we promise nothing we haven't "
                f"verified. {_DEMO_DISCLAIMER}"
            )
        if intent == Intent.ORDER_CANCEL.value:
            parts = [
                "Understood — a cancellation must be confirmed by a team "
                "member, especially if the order has already shipped.",
            ]
            if self.order is not None:
                status_de = _STATUS_DE.get(
                    self.order.get("status"), self.order.get("status")
                )
                parts.append(
                    f"Your order #{self.order['order_ref']} is "
                    f"currently {status_de}."
                )
            parts.append(
                f"I've created Ticket #{self.ticket_id} — a team member "
                "will review the cancellation as soon as possible. "
                f"{_DEMO_DISCLAIMER}"
            )
            return " ".join(parts)
        return (
            "Understood — I'll forward your request to our team "
            f"(Ticket #{self.ticket_id}). A team member will get back to "
            f"you as soon as possible. {_DEMO_DISCLAIMER}"
        )


def run_pipeline(
    message: str,
    store_id: str,
    conn: sqlite3.Connection,
    provider: LLMProvider,
    settings: Settings,
    actor_ip: str | None = None,
    quota_fallback: bool = False,
) -> PipelineResult:
    """Run the chat pipeline for one customer message.

    ``actor_ip`` is the caller's client IP for audit logging (hashed
    before storage); it is optional so the pipeline stays usable in
    non-HTTP contexts. ``quota_fallback`` records an honest workflow
    event when the deterministic mock was used because the daily AI
    quota was exhausted.

    Raises:
        LLMError: when the AI provider fails. The caller converts this to
            the honest ``ai_provider_unavailable`` response.

    Phase 9: all product/order lookups go through the configured
    ``StoreIntegration`` backend (``STORE_BACKEND`` env: ``demo`` or
    ``shopify_simulated``). An ``IntegrationError`` from the backend is
    caught here and answered honestly — the pipeline never invents data
    when the store cannot be reached.
    """
    store = get_store_integration(settings, conn, store_id)
    pipe = _Pipeline(message, store_id, conn, provider, settings,
                     actor_ip=actor_ip, store=store)

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

    # --- Step 2: classify via provider + STRICT validation ----------------
    # validate_classification() never raises for bad model output — any
    # invalid JSON/intent/confidence/order_ref → safe fallback (unknown,
    # 0.0, requires_human=True). All downstream code uses this validated
    # schema, never raw model text.
    raw = provider.classify(message)  # may raise LLMError
    classification = validate_classification(raw)
    pipe.log(EVENT_INTENT_CLASSIFIED, {
        "intent": classification.intent,
        "confidence": classification.confidence,
        "order_ref": classification.order_ref,
        "product_hint": classification.product_hint,
        "return_reason": classification.return_reason,
        "language": classification.language,
        "provider": type(provider).__name__,
        "validation_reason": classification.reason,
    })

    # --- Step 3: deterministic action plan --------------------------------
    # Escalation policy: ALWAYS_HUMAN intents and confidence below the
    # threshold always go to a human — regardless of what the classifier
    # claimed. The classifier's own requires_human flag is honored too.
    escalate, esc_reason = decide_escalation(
        classification.intent,
        classification.confidence,
        classification.requires_human,
        threshold=settings.confidence_threshold,
    )
    # return_request is deliberately NOT in ALWAYS_HUMAN: its triage
    # handler always creates a ticket for staff review, which IS the
    # human handoff for the return workflow. The classifier's
    # requires_human flag must not divert it to the generic escalation
    # path — only genuine uncertainty (low confidence) does.
    if classification.intent == Intent.RETURN_REQUEST.value and esc_reason != REASON_LOW_CONFIDENCE:
        escalate = False
    normalized_ref = normalize_order_ref(classification.order_ref)
    intent = classification.intent

    try:
        if escalate:
            # Reason code "low_confidence" when the threshold fired, else
            # "always_human" / "classifier_requires_human".
            reply = pipe.handle_escalation(classification, esc_reason or REASON_ALWAYS_HUMAN)
        elif intent == Intent.GREETING.value:
            reply = pipe.handle_greeting()
        elif intent == Intent.SHIPPING_INFO.value:
            reply = pipe.handle_shipping_info()
        elif intent == Intent.PAYMENT_QUESTION.value:
            reply = pipe.handle_payment_question()
        elif intent == Intent.PRODUCT_AVAILABILITY.value:
            reply = pipe.handle_product_availability()
        elif intent == Intent.ORDER_STATUS.value:
            reply = pipe.handle_order_status(normalized_ref)
        elif intent == Intent.PRODUCT_QUESTION.value:
            reply = pipe.handle_product_question()
        elif intent == Intent.RETURN_REQUEST.value:
            # Returns always create a structured ticket for staff review —
            # this IS the human handoff for the return workflow.
            reply = pipe.handle_return_request(normalized_ref, intent, classification)
        else:  # defensive: should never happen after validation
            reply = pipe.handle_escalation(classification, REASON_ALWAYS_HUMAN)
    except IntegrationError as exc:
        # Phase 9: the store backend failed (network, permissions, ...).
        # Log it as a REAL failed event and answer honestly — never
        # invent order/product data when the lookup did not run.
        pipe.log(EVENT_STORE_BACKEND_ERROR, {
            "backend": store.backend_name,
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
        }, status="failed")
        reply = (
            "The connection to the shop is currently disrupted — I can't "
            "retrieve order or product data right now. Please try again "
            "later or contact our team. "
            f"{_DEMO_DISCLAIMER}"
        )

    # --- Step 4: persist assistant message + closing events ----------------
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (pipe.conversation_id, "assistant", reply),
    )
    if quota_fallback:
        # Honest workflow event: the mock was used because the daily AI
        # quota was exhausted — this really happened.
        pipe.log(EVENT_LLM_QUOTA_FALLBACK, {
            "cap": settings.llm_daily_request_cap,
            "provider": settings.llm_provider,
        })
    pipe.log(EVENT_RESPONSE_GENERATED, {"escalated": pipe.escalated})
    pipe.log(EVENT_INTERACTION_LOGGED, {
        "intent": intent, "ticket_id": pipe.ticket_id,
    })
    conn.commit()

    return PipelineResult(
        conversation_id=pipe.conversation_id,
        intent=classification.intent,
        confidence=classification.confidence,
        order_ref=normalized_ref,
        reply_de=reply,
        order=_minimal_order(pipe.order),
        timeline=pipe.timeline(),
        ticket_id=pipe.ticket_id,
        provider=settings.llm_provider,
        escalated=pipe.escalated,
    )
