"""Intent enum and classification helpers.

Phase 1: ``classify()`` is a stub that returns ``("unknown", 0.0, None)``.
The pipeline always prefers a real ``LLMProvider`` (mock or remote); this
stub exists so the service layer has a defined fallback shape and later
phases have a documented place for local classification logic.
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


def classify(message: str) -> tuple[str, float, str | None]:
    """Stub classifier: always returns ``("unknown", 0.0, None)``.

    Phase 2+ will wire real classification here (LLM result validation,
    confidence calibration). The pipeline uses the configured
    ``LLMProvider`` first and only falls back here on failure.
    """
    return ("unknown", 0.0, None)
