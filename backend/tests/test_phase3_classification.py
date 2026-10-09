"""Phase 3 tests: extended intent set, confidence calibration, escalation
policy, strict classification validation, and stubbed-provider fallbacks.

Run against the same isolated temp DB fixture as the Phase 2 tests.
The mock provider stays the default; stubbed providers exercise the
strict-validation path without any real AI calls.
"""

from __future__ import annotations

import json
import sqlite3

from test_chat_pipeline import _chat, _count, _event_keys, isolated_client  # noqa: F401

from app.ai.providers import LLMError, LLMProvider, MockLLMProvider
from app.rules.escalation import (
    REASON_ALWAYS_HUMAN,
    REASON_LOW_CONFIDENCE,
    decide_escalation,
)
from app.services.classification import (
    Classification,
    detect_language,
    safe_fallback,
    validate_classification,
)
from app.services.intent import ALWAYS_HUMAN, Intent

__all__ = ["isolated_client"]


# --- stub providers (strict-validation path, no real AI) ------------------


class StubProvider(LLMProvider):
    """Returns a fixed raw reply, whatever the message."""

    def __init__(self, raw: str) -> None:
        self.raw = raw

    def classify(self, message: str) -> str:
        return self.raw


class FailingProvider(LLMProvider):
    """Simulates an unreachable AI provider."""

    def classify(self, message: str) -> str:
        raise LLMError("simulated provider outage")


def _valid_stub(**overrides) -> StubProvider:
    payload = {
        "intent": "order_status",
        "confidence": 0.95,
        "order_ref": "10482",
        "product_hint": None,
        "return_reason": None,
        "language": "de",
        "requires_human": False,
        "reason": "stubbed valid classification",
    }
    payload.update(overrides)
    return StubProvider(json.dumps(payload))


def _chat_with(client, stub: LLMProvider, message: str, monkeypatch) -> dict:
    from app.api import chat as chat_module

    monkeypatch.setattr(chat_module, "get_provider", lambda settings: stub)
    resp = client.post("/api/chat", json={"message": message})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _ticket_for(db_path, conversation_id: int) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM tickets WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


# --- 1. new intent routing (mock, German, grounded in seed data) ----------


def test_greeting_no_ticket(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "Hallo")
    assert body["intent"] == "greeting"
    assert body["confidence"] >= 0.6
    assert not body["escalated"]
    assert body["ticket_id"] is None
    assert "Muster-Shop" in body["answer"]
    assert "Wie kann ich Ihnen helfen" in body["answer"]
    assert _event_keys(body) == [
        "message_received",
        "intent_classified",
        "response_generated",
        "interaction_logged",
    ]


def test_greeting_does_not_shadow_order_status(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "Hallo, wo bleibt meine Bestellung #10482?")
    assert body["intent"] == "order_status"


def test_shipping_info_grounded_in_policy(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "Wie hoch sind die Versandkosten?")
    assert body["intent"] == "shipping_info"
    assert "4,99" in body["answer"] and "50,00" in body["answer"]
    assert "2-4 Werktage" in body["answer"]
    assert "DHL" in body["answer"]
    assert "store_info" in _event_keys(body)
    assert not body["escalated"]


def test_payment_question_grounded_in_policy(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "Kann ich mit PayPal zahlen?")
    assert body["intent"] == "payment_question"
    assert "PayPal" in body["answer"]
    assert "Kauf auf Rechnung" in body["answer"]
    assert "keine echten Zahlungen" in body["answer"]
    assert not body["escalated"]


def test_product_availability_in_stock(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "Ist die AquaPure 750 noch auf Lager?")
    assert body["intent"] == "product_availability"
    assert "auf Lager" in body["answer"]
    assert "42 Stück" in body["answer"]
    assert "product_search" in _event_keys(body)


def test_product_availability_out_of_stock(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "Ist die Kaffeemühle lieferbar?")
    assert body["intent"] == "product_availability"
    assert "nicht auf Lager" in body["answer"]
    assert not body["escalated"]


def test_product_availability_unknown_product_asks(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "Ist das Einhorn-Fahrrad auf Lager?")
    assert body["intent"] == "product_availability"
    assert "Für welches Produkt" in body["answer"]
    assert body["ticket_id"] is None


def test_order_cancel_escalates_with_ticket(isolated_client):
    client, _db_path = isolated_client
    body = _chat(client, "Ich möchte meine Bestellung #10482 stornieren.")
    assert body["intent"] == "order_cancel"
    assert body["escalated"] is True
    assert body["ticket_id"] is not None
    assert "Stornierung" in body["answer"]
    assert "Mitarbeiter" in body["answer"]
    # The order context is looked up deterministically for the ticket.
    assert body["order"] is not None
    assert body["order"]["order_ref"] == "10482"
    ticket = _ticket_for(_db_path, body["conversation_id"])
    assert ticket["escalation_reason"] == REASON_ALWAYS_HUMAN
    assert ticket["priority"] == "high"
    assert ticket["intent"] == "order_cancel"


def test_widerrufen_routes_to_order_cancel(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "Ich möchte meine Bestellung widerrufen.")
    assert body["intent"] == "order_cancel"
    assert body["escalated"] is True


# --- 2. confidence calibration --------------------------------------------


def test_confidence_calibration_more_keywords_higher():
    single = json.loads(MockLLMProvider().classify("Was kostet der Versand?"))
    multi = json.loads(
        MockLLMProvider().classify(
            "Versandkosten und Lieferzeit — wie lange dauert der Versand?"
        )
    )
    assert single["intent"] == "shipping_info"
    assert multi["intent"] == "shipping_info"
    assert multi["confidence"] > single["confidence"]
    assert 0.0 <= multi["confidence"] <= 1.0


def test_low_confidence_escalates_with_ticket(isolated_client, monkeypatch):
    client, db_path = isolated_client
    stub = _valid_stub(intent="order_status", confidence=0.55, order_ref="10482")
    body = _chat_with(client, stub, "irgendwas Unklares", monkeypatch)
    assert body["escalated"] is True
    assert body["ticket_id"] is not None
    assert "nicht ganz sicher" in body["answer"]
    ticket = _ticket_for(db_path, body["conversation_id"])
    assert ticket["escalation_reason"] == REASON_LOW_CONFIDENCE


def test_confidence_just_above_threshold_answers(isolated_client, monkeypatch):
    client, _ = isolated_client
    stub = _valid_stub(intent="order_status", confidence=0.61, order_ref="10482")
    body = _chat_with(client, stub, "Bestellung 10482", monkeypatch)
    assert body["escalated"] is False
    assert body["ticket_id"] is None
    assert "versendet" in body["answer"]


# --- 3. ALWAYS_HUMAN policy -----------------------------------------------


def test_always_human_set():
    assert ALWAYS_HUMAN == {"complaint", "order_cancel", "human_support", "unknown"}


def test_always_human_ignores_high_confidence(isolated_client, monkeypatch):
    client, db_path = isolated_client
    for intent in ["complaint", "order_cancel", "human_support", "unknown"]:
        stub = _valid_stub(intent=intent, confidence=0.99, order_ref=None)
        body = _chat_with(client, stub, "stubbed", monkeypatch)
        assert body["escalated"] is True, intent
        assert body["ticket_id"] is not None, intent
        ticket = _ticket_for(db_path, body["conversation_id"])
        assert ticket["escalation_reason"] == REASON_ALWAYS_HUMAN, intent


def test_human_request_alias_normalizes_to_human_support(isolated_client, monkeypatch):
    client, _ = isolated_client
    stub = _valid_stub(intent="human_request", confidence=0.95, order_ref=None)
    body = _chat_with(client, stub, "stubbed", monkeypatch)
    assert body["intent"] == "human_support"
    assert body["escalated"] is True


def test_decide_escalation_policy_unit():
    escalate, reason = decide_escalation("complaint", 0.99)
    assert (escalate, reason) == (True, REASON_ALWAYS_HUMAN)
    escalate, reason = decide_escalation("order_cancel", 0.99)
    assert (escalate, reason) == (True, REASON_ALWAYS_HUMAN)
    escalate, reason = decide_escalation("order_status", 0.55)
    assert (escalate, reason) == (True, REASON_LOW_CONFIDENCE)
    escalate, reason = decide_escalation("order_status", 0.60)
    assert (escalate, reason) == (False, None)
    escalate, reason = decide_escalation("shipping_info", 0.9, requires_human=True)
    assert escalate is True and reason is not None


# --- 4. strict validation: stubbed failing provider outputs ---------------


def test_invalid_json_falls_back_to_human(isolated_client, monkeypatch):
    client, db_path = isolated_client
    body = _chat_with(client, StubProvider("this is not json"), "Hallo?", monkeypatch)
    assert body["intent"] == "unknown"
    assert body["confidence"] == 0.0
    assert body["escalated"] is True
    assert body["ticket_id"] is not None
    ticket = _ticket_for(db_path, body["conversation_id"])
    assert ticket["intent"] == "unknown"


def test_bad_intent_falls_back_to_human(isolated_client, monkeypatch):
    client, _ = isolated_client
    stub = _valid_stub(intent="teleport", confidence=0.95)
    body = _chat_with(client, stub, "Hallo?", monkeypatch)
    assert body["intent"] == "unknown"
    assert body["escalated"] is True


def test_bad_confidence_falls_back_to_human(isolated_client, monkeypatch):
    client, _ = isolated_client
    for bad in (1.5, -0.2, "high", True):
        stub = _valid_stub(confidence=bad)
        body = _chat_with(client, stub, "Hallo?", monkeypatch)
        assert body["intent"] == "unknown", bad
        assert body["confidence"] == 0.0, bad
        assert body["escalated"] is True, bad


def test_bad_order_ref_falls_back_to_human(isolated_client, monkeypatch):
    client, _ = isolated_client
    stub = _valid_stub(order_ref="abc123")
    body = _chat_with(client, stub, "Hallo?", monkeypatch)
    assert body["intent"] == "unknown"
    assert body["escalated"] is True


def test_provider_outage_returns_honest_error(isolated_client, monkeypatch):
    client, _ = isolated_client
    from app.api import chat as chat_module

    monkeypatch.setattr(chat_module, "get_provider", lambda settings: FailingProvider())
    resp = client.post("/api/chat", json={"message": "Wo ist meine Bestellung?"})
    assert resp.status_code == 502
    body = resp.json()
    assert body["error"] == "ai_provider_unavailable"
    assert "KI-Dienst" in body["reply_de"]


# --- 5. validated schema unit tests ---------------------------------------


def test_validate_classification_full_schema():
    raw = json.dumps({
        "intent": "return_request",
        "confidence": 0.9,
        "order_ref": "10482",
        "product_hint": "AquaPure 750",
        "return_reason": "defekt",
        "language": "de",
        "requires_human": True,
        "reason": "unit test",
    })
    result = validate_classification(raw)
    assert isinstance(result, Classification)
    assert result.intent == "return_request"
    assert result.confidence == 0.9
    assert result.order_ref == "10482"
    assert result.product_hint == "AquaPure 750"
    assert result.return_reason == "defekt"
    assert result.language == "de"


def test_validate_classification_tolerates_fences_and_alias():
    raw = '```json\n{"intent": "human_request", "confidence": 0.8, "requires_human": false, "reason": "x"}\n```'
    result = validate_classification(raw)
    assert result.intent == Intent.HUMAN_SUPPORT.value


def test_safe_fallback_never_raises():
    for raw in ["", "{", "[]", "null", '{"intent": 42}']:
        result = validate_classification(raw)
        assert result.intent == "unknown"
        assert result.confidence == 0.0
        assert result.requires_human is True


def test_safe_fallback_shape():
    result = safe_fallback("unit")
    assert result.reason == "unit"
    assert result.requires_human is True


def test_detect_language_de_en():
    assert detect_language("Hallo, wo bleibt meine Bestellung?") == "de"
    assert detect_language("Where is my order, please?") == "en"


def test_mock_output_contract_extended():
    parsed = json.loads(MockLLMProvider().classify("Hallo"))
    for key in (
        "intent", "confidence", "order_ref", "product_hint",
        "return_reason", "language", "requires_human", "reason",
    ):
        assert key in parsed, key
    assert parsed["language"] == "de"
    parsed = json.loads(
        MockLLMProvider().classify("Die Trinkflasche ist defekt, ich will sie zurücksenden.")
    )
    assert parsed["intent"] == "return_request"
    assert parsed["product_hint"] == "AquaPure 750"
    assert parsed["return_reason"] == "defekt"


# --- 6. German edge cases --------------------------------------------------


def test_order_status_without_number_asks(isolated_client):
    client, _ = isolated_client
    body = _chat(client, "Wo bleibt meine Bestellung?")
    assert body["intent"] == "order_status"
    assert "Bestellnummer" in body["answer"]
    assert body["ticket_id"] is None
    assert not body["escalated"]


def test_mixed_language_complaint_escalates(isolated_client):
    client, _ = isolated_client
    body = _chat(
        client,
        "My package never arrived, ich will sofort mein Geld zurück!",
    )
    assert body["intent"] == "complaint"
    assert body["escalated"] is True
    assert body["ticket_id"] is not None
    assert "keine falsche" not in body["answer"]  # no invented promises
