"""Daily AI-spending quota for the public demo (Phase 7).

Only REAL provider calls count against ``LLM_DAILY_REQUEST_CAP``
(default 500). Mock calls never count. When the cap is reached, chat
requests fall back to the deterministic mock classifier with an honest
event + note — the chat never fails because of the quota.

Counting lives in the ``ai_usage`` SQLite table (per UTC day), so it
survives restarts without Redis/Postgres.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .providers import LLMError, LLMProvider, MockLLMProvider


class QuotaExhausted(LLMError):
    """Raised when the daily real-provider cap is exhausted."""


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def check_and_consume_quota(
    conn: sqlite3.Connection, provider_name: str, cap: int
) -> bool:
    """Try to consume one real-provider call for today.

    Returns True when the call is allowed (counter incremented),
    False when the daily cap is already reached. Commits immediately so
    concurrent requests cannot overshoot the cap.
    """
    today = utc_today()
    row = conn.execute(
        "SELECT calls FROM ai_usage WHERE usage_date = ? AND provider = ?",
        (today, provider_name),
    ).fetchone()
    used = row["calls"] if row else 0
    if used >= cap:
        return False
    conn.execute(
        "INSERT INTO ai_usage (usage_date, provider, calls)"
        " VALUES (?, ?, 1)"
        " ON CONFLICT(usage_date, provider) DO UPDATE SET calls = calls + 1",
        (today, provider_name),
    )
    conn.commit()
    return True


def quota_used_today(conn: sqlite3.Connection, provider_name: str) -> int:
    """How many real-provider calls were consumed today (for tests/ops)."""
    row = conn.execute(
        "SELECT calls FROM ai_usage WHERE usage_date = ? AND provider = ?",
        (utc_today(), provider_name),
    ).fetchone()
    return row["calls"] if row else 0


def is_real_provider(provider: LLMProvider) -> bool:
    """Mock calls never count against the quota."""
    return not isinstance(provider, MockLLMProvider)


class QuotaGuardedProvider(LLMProvider):
    """Wraps a real provider; raises QuotaExhausted when the cap is hit.

    The caller (``api/chat.py``) catches this and retries the request
    with the mock provider, so the customer still gets an honest answer.
    """

    def __init__(
        self,
        inner: LLMProvider,
        conn: sqlite3.Connection,
        provider_name: str,
        cap: int,
    ) -> None:
        self._inner = inner
        self._conn = conn
        self._provider_name = provider_name
        self._cap = cap

    def classify(self, message: str) -> str:
        if not check_and_consume_quota(
            self._conn, self._provider_name, self._cap
        ):
            raise QuotaExhausted(
                f"Daily LLM quota ({self._cap}) for provider "
                f"'{self._provider_name}' exhausted; falling back to mock."
            )
        return self._inner.classify(message)


# Event key/label for the honest quota-fallback workflow event.
EVENT_LLM_QUOTA_FALLBACK = "llm_quota_fallback"
EVENT_LLM_QUOTA_FALLBACK_LABEL = (
    "Daily AI quota reached — demo rule engine used"
)
QUOTA_FALLBACK_NOTE_DE = (
    "Note: this demo's daily AI quota has been used up. "
    "This reply was created by the demo rule engine — no "
    "AI costs were incurred."
)
