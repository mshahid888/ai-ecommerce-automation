"""Return eligibility policy engine (stub).

The DETERMINISTIC return policy engine lands in Phase 5: it will evaluate
the store's return policy (``store_policies.policy_key = 'returns'``) against
order facts (order date, product category, hygiene-seal exceptions) using
plain app code — never an LLM verdict. This stub keeps the shape stable.
"""

from __future__ import annotations

from typing import Any


def evaluate_return_eligibility(
    policy: dict[str, Any] | None,
    order: dict[str, Any] | None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Evaluate return eligibility against the store's returns policy.

    Phase 5 implements the deterministic engine here. For now it always
    reports ``not_implemented`` so callers cannot mistake a stub for a
    real eligibility decision.
    """
    return {
        "eligible": None,
        "reason": "not_implemented",
        "policy_version": (policy or {}).get("status"),
    }
