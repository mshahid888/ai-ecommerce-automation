"""Deterministic return-eligibility engine (Phase 2).

Evaluates the store's configured return policy
(``store_policies.policy_key = 'returns'``) against order facts using plain
app code — never an LLM verdict. The engine only produces a PRELIMINARY
assessment ("vorläufig berechtigt"); authorization and refunds are human
decisions, and the demo never executes a real refund.
"""

from __future__ import annotations

from datetime import date
from typing import Any


#: English display text for return-reason codes (``defekt``,
#: ``passt_nicht``, ...). The codes themselves stay as-is — they are
#: internal identifiers — but only this mapping is ever shown to
#: customers; raw codes must never reach a customer-facing reply.
RETURN_REASON_DISPLAY = {
    "defekt": "defective",
    "passt_nicht": "doesn't fit",
    "falsche_ware": "wrong item",
    "verspaetete_lieferung": "late delivery",
    "gefaellt_nicht": "not as expected",
    "sonstiges": "other",
}


def _order_date(order: dict[str, Any]) -> date | None:
    raw = (order or {}).get("created_at") or ""
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def evaluate_return_eligibility(
    policy: dict[str, Any] | None,
    order: dict[str, Any] | None,
    reason: str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Evaluate return eligibility against the store's returns policy.

    Returns a dict with:
    - ``eligible``: True (preliminary) / False / None (unclear → human)
    - ``verdict``: machine-readable reason code
    - ``details_de``: German explanation for the customer reply
    - ``days_since_order`` / ``window_days`` when computable
    """
    today = today or date.today()
    policy = policy or {}
    window_days = int(policy.get("rueckgabefrist_tage", 30))

    if order is None:
        return {
            "eligible": None,
            "verdict": "order_missing",
            "details_de": (
                "I can't check the return window without an order number."
            ),
            "days_since_order": None,
            "window_days": window_days,
        }

    status = (order.get("status") or "").lower()
    ordered_on = _order_date(order)
    days = (today - ordered_on).days if ordered_on else None

    if status == "processing":
        return {
            "eligible": True,
            "verdict": "not_shipped",
            "details_de": (
                "The order hasn't been shipped yet — cancellation is "
                "possible instead of a return."
            ),
            "days_since_order": days,
            "window_days": window_days,
        }

    if days is not None and days > window_days:
        return {
            "eligible": False,
            "verdict": "window_expired",
            "details_de": (
                f"The {window_days}-day return window has expired "
                f"(order placed {days} days ago)."
            ),
            "days_since_order": days,
            "window_days": window_days,
        }

    if status in ("shipped", "delivered", "delayed"):
        return {
            "eligible": True,
            "verdict": "preliminary_eligible",
            "details_de": (
                f"Preliminary check: the order is within the "
                f"{window_days}-day return window. A team member will do "
                f"the final review."
            ),
            "days_since_order": days,
            "window_days": window_days,
        }

    return {
        "eligible": None,
        "verdict": "unclear",
        "details_de": (
            "The order status doesn't allow an automatic check — "
            "a team member will take the case."
        ),
        "days_since_order": days,
        "window_days": window_days,
    }
