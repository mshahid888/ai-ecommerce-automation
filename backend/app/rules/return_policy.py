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
                "Ohne Bestellnummer kann ich die Rückgabefrist nicht prüfen."
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
                "Die Bestellung wurde noch nicht versendet — statt einer "
                "Retoure ist eine Stornierung möglich."
            ),
            "days_since_order": days,
            "window_days": window_days,
        }

    if days is not None and days > window_days:
        return {
            "eligible": False,
            "verdict": "window_expired",
            "details_de": (
                f"Die {window_days}-tägige Rückgabefrist ist überschritten "
                f"(Bestellung vor {days} Tagen)."
            ),
            "days_since_order": days,
            "window_days": window_days,
        }

    if status in ("shipped", "delivered", "delayed"):
        return {
            "eligible": True,
            "verdict": "preliminary_eligible",
            "details_de": (
                f"Vorläufige Prüfung: Die Bestellung liegt innerhalb der "
                f"{window_days}-tägigen Rückgabefrist. Die endgültige "
                f"Prüfung übernimmt ein Mitarbeiter."
            ),
            "days_since_order": days,
            "window_days": window_days,
        }

    return {
        "eligible": None,
        "verdict": "unclear",
        "details_de": (
            "Der Bestellstatus lässt keine automatische Prüfung zu — "
            "ein Mitarbeiter übernimmt den Fall."
        ),
        "days_since_order": days,
        "window_days": window_days,
    }
