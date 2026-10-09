"""Deterministic escalation policy (Phase 3).

Some intents always need a human, and low confidence always needs a
human — no matter what the classifier claimed. Pure functions, no AI
involved, easy to unit test.

Policy (per brief):
- ``ALWAYS_HUMAN`` = {complaint, order_cancel, human_support, unknown}
  → escalate regardless of confidence.
- confidence < threshold (default 0.6) → escalate with reason
  ``"low_confidence"``.
- the classifier's own ``requires_human`` flag is honored as well.
"""

from __future__ import annotations

from ..services.intent import ALWAYS_HUMAN

#: Escalation reason codes stored on tickets and surfaced in the timeline.
REASON_ALWAYS_HUMAN = "always_human"
REASON_LOW_CONFIDENCE = "low_confidence"
REASON_CLASSIFIER_FLAG = "classifier_requires_human"

#: Below this confidence the system routes to a human regardless of intent.
CONFIDENCE_THRESHOLD = 0.6


def decide_escalation(
    intent: str,
    confidence: float,
    requires_human: bool = False,
    threshold: float = CONFIDENCE_THRESHOLD,
) -> tuple[bool, str | None]:
    """Return (escalate, reason_code) for a validated classification.

    Order of checks: unparseable confidence → fail closed (escalate);
    confidence below threshold → escalate with ``"low_confidence"``
    (the most informative reason for staff, checked before the intent
    policy); ALWAYS_HUMAN intents → escalate; classifier flag → escalate.
    """
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        return True, REASON_LOW_CONFIDENCE
    if confidence_value < threshold:
        return True, REASON_LOW_CONFIDENCE
    if intent in ALWAYS_HUMAN:
        return True, REASON_ALWAYS_HUMAN
    if requires_human:
        return True, REASON_CLASSIFIER_FLAG
    return False, None


def should_escalate(
    intent: str,
    confidence: float,
    requires_human: bool = False,
    threshold: float = CONFIDENCE_THRESHOLD,
) -> bool:
    """Backward-compatible boolean wrapper around :func:`decide_escalation`."""
    escalate, _ = decide_escalation(intent, confidence, requires_human, threshold)
    return escalate
