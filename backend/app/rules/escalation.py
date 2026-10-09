"""Deterministic escalation policy.

Ported from the predecessor project's ``classifier.py`` policy:
some intents always need a human, and low confidence always needs a human.
Pure function — no AI involved, easy to unit test.
"""

from __future__ import annotations

# Intents that must ALWAYS go to a human, no matter the confidence score.
ALWAYS_ESCALATE = {"complaint", "human_support", "return_request"}

# Below this confidence the system routes to a human regardless of intent.
CONFIDENCE_THRESHOLD = 0.6


def should_escalate(intent: str, confidence: float) -> bool:
    """Return True when a conversation must be escalated to a human.

    Rules (ported from the predecessor policy):
    - confidence < 0.6  → escalate
    - intent in {complaint, human_support, return_request} → escalate
    """
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        return True
    if confidence_value < CONFIDENCE_THRESHOLD:
        return True
    return intent in ALWAYS_ESCALATE
