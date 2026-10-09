"""Strict classification validation + safe fallback (Phase 3).

Ported approach from the predecessor project
(``ai-customer-support-automation/src/classifier.py``): the model is asked
for structured JSON, but its output is never trusted blindly. Every reply
is parsed and validated, and ANY problem — invalid JSON, unknown intent,
out-of-range confidence, malformed order reference, wrong types —
results in :func:`safe_fallback`, which routes the conversation to a
human. Fail-safe beats fail-smart.

All downstream code (pipeline handlers, escalation policy, API responses)
uses the validated :class:`Classification` schema below — never raw model
text.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .intent import Intent, normalize_intent_name

log = logging.getLogger(__name__)

# Order references are 3-6 digits (the demo shop uses 4-5, e.g. "10482").
_ORDER_REF_RE = re.compile(r"^\d{3,6}$")

_VALID_LANGUAGES = {"de", "en", "unknown"}

_DE_TOKENS = {
    "der", "die", "das", "und", "ist", "ich", "meine", "mein", "nicht",
    "bitte", "wie", "was", "wo", "hallo", "danke", "bestellung", "mit",
    "für", "für", "eine", "einer", "sind", "haben", "möchte", "kann",
}
_EN_TOKENS = {
    "the", "and", "is", "are", "my", "package", "order", "please",
    "want", "never", "arrived", "money", "back", "hello", "can", "you",
}
_WORD_RE = re.compile(r"[a-zäöüß]+")


@dataclass(frozen=True)
class Classification:
    """Validated, downstream-safe classification result."""

    intent: str = Intent.UNKNOWN.value
    confidence: float = 0.0
    order_ref: str | None = None
    product_hint: str | None = None
    return_reason: str | None = None
    language: str = "unknown"
    requires_human: bool = True
    reason: str = "unvalidated"
    # Free-form extras from the model, kept for debugging only.
    extras: dict[str, Any] = field(default_factory=dict)


def safe_fallback(reason: str) -> Classification:
    """The classification used when the AI output cannot be trusted.

    Routes to a human with zero confidence. Never raises, never guesses.
    """
    return Classification(
        intent=Intent.UNKNOWN.value,
        confidence=0.0,
        order_ref=None,
        product_hint=None,
        return_reason=None,
        language="unknown",
        requires_human=True,
        reason=reason,
    )


def detect_language(message: str) -> str:
    """Deterministic de/en language guess (documented heuristic).

    Counts common German vs. English stop-words; an umlaut/ß immediately
    tips the balance to German. Returns "de", "en", or "unknown" on ties.
    """
    text = message.lower()
    tokens = set(_WORD_RE.findall(text))
    if re.search(r"[äöüß]", text):
        return "de"
    de_hits = len(tokens & _DE_TOKENS)
    en_hits = len(tokens & _EN_TOKENS)
    if de_hits > en_hits:
        return "de"
    if en_hits > de_hits:
        return "en"
    return "unknown"


def _extract_json(raw: str) -> Any:
    """Parse a model reply, tolerating ```json fences some models add."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def validate_classification(raw: str) -> Classification:
    """Validate a raw provider reply into a :class:`Classification`.

    Never raises for bad model output: any validation failure returns
    :func:`safe_fallback` (intent=unknown, confidence=0.0,
    requires_human=True).
    """
    try:
        parsed = _extract_json(raw)
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
        log.warning("Classifier returned non-JSON output; safe fallback")
        return safe_fallback("model returned non-JSON output")

    if not isinstance(parsed, dict):
        log.warning("Classifier returned non-object JSON; safe fallback")
        return safe_fallback("model output was not a JSON object")

    intent = normalize_intent_name(parsed.get("intent"))
    if intent is None:
        log.warning("Classifier returned invalid intent; safe fallback")
        return safe_fallback("model returned an invalid intent")

    confidence = parsed.get("confidence")
    # bool is a subclass of int — reject explicitly, like the predecessor.
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        log.warning("Classifier returned invalid confidence; safe fallback")
        return safe_fallback("model returned an invalid confidence")
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        log.warning("Classifier returned out-of-range confidence; safe fallback")
        return safe_fallback("model returned an out-of-range confidence")

    order_ref = parsed.get("order_ref")
    if order_ref is not None:
        if not isinstance(order_ref, str):
            order_ref = str(order_ref)
        order_ref = order_ref.strip().lstrip("#")
        if not _ORDER_REF_RE.match(order_ref):
            log.warning("Classifier returned malformed order_ref; safe fallback")
            return safe_fallback("model returned a malformed order reference")

    product_hint = parsed.get("product_hint")
    if product_hint is not None and not isinstance(product_hint, str):
        product_hint = str(product_hint)
    return_reason = parsed.get("return_reason")
    if return_reason is not None and not isinstance(return_reason, str):
        return_reason = str(return_reason)

    language = parsed.get("language")
    if language not in _VALID_LANGUAGES:
        language = "unknown"

    requires_human = parsed.get("requires_human")
    if not isinstance(requires_human, bool):
        requires_human = True  # fail closed: unsure → human

    reason = parsed.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = "no reason given"

    return Classification(
        intent=intent,
        confidence=confidence,
        order_ref=order_ref,
        product_hint=(product_hint.strip()[:120] if product_hint else None),
        return_reason=(return_reason.strip()[:120] if return_reason else None),
        language=language,
        requires_human=requires_human,
        reason=reason.strip()[:300],
    )
