"""Intent vocabulary for the e-commerce support pipeline (Phase 3).

Canonical intent values used everywhere (DB, events, API responses).
The provider's raw output is never trusted: it passes through
``services.classification.validate_classification`` first, which
normalizes aliases and enforces the schema.
"""

from __future__ import annotations

from enum import Enum


class Intent(str, Enum):
    ORDER_STATUS = "order_status"
    PRODUCT_QUESTION = "product_question"
    RETURN_REQUEST = "return_request"
    COMPLAINT = "complaint"
    HUMAN_SUPPORT = "human_support"
    UNKNOWN = "unknown"
    # Phase 3 additions
    SHIPPING_INFO = "shipping_info"
    PAYMENT_QUESTION = "payment_question"
    PRODUCT_AVAILABILITY = "product_availability"
    ORDER_CANCEL = "order_cancel"
    GREETING = "greeting"


#: Alias names some models produce — normalized to canonical values
#: during strict validation.
INTENT_ALIASES = {
    "human_request": Intent.HUMAN_SUPPORT.value,
    "support_request": Intent.HUMAN_SUPPORT.value,
    "cancel_order": Intent.ORDER_CANCEL.value,
    "order_cancellation": Intent.ORDER_CANCEL.value,
    "product_availability_check": Intent.PRODUCT_AVAILABILITY.value,
    "payment": Intent.PAYMENT_QUESTION.value,
    "shipping": Intent.SHIPPING_INFO.value,
}

VALID_INTENTS = {i.value for i in Intent}

#: Intents that must ALWAYS go to a human, no matter the confidence.
#: ``human_request`` (the alias form used in some prompts) normalizes to
#: ``human_support``, so the policy covers both spellings.
ALWAYS_HUMAN = {
    Intent.COMPLAINT.value,
    Intent.ORDER_CANCEL.value,
    Intent.HUMAN_SUPPORT.value,
    Intent.UNKNOWN.value,
}


def normalize_intent_name(raw: object) -> str | None:
    """Map a raw model string to a canonical intent value, or None."""
    if not isinstance(raw, str):
        return None
    name = raw.strip().lower()
    if name in VALID_INTENTS:
        return name
    return INTENT_ALIASES.get(name)


def classify(message: str) -> tuple[str, float, str | None]:
    """Stub classifier: always returns ``("unknown", 0.0, None)``.

    Kept for API compatibility with Phase 1. The pipeline uses the
    configured ``LLMProvider`` (mock by default) plus strict validation;
    this stub is only reached in code paths that bypass the provider.
    """
    return (Intent.UNKNOWN.value, 0.0, None)
