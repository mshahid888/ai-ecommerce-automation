"""ASGI rate-limit middleware (Phase 7).

Rules (configurable via env, defaults in parentheses):

* ``POST /api/chat`` — 30 req/min (``RL_CHAT_PER_MINUTE``) AND
  200 req/day per IP (``RL_CHAT_PER_DAY``): the chat endpoint is the
  expensive one (LLM calls, DB writes).
* ``POST /api/demo/reset`` — 5 req/hour per IP (``RL_RESET_PER_HOUR``):
  admin-authenticated anyway, but belt and braces.
* ``GET /api/*`` — 60 req/min per IP (``RL_READ_PER_MINUTE``).

Rejections return 429 with a German message and a ``Retry-After`` header.
A sampled fraction of rejections is written to the audit log
(``AUDIT_SAMPLE_RATE``) so abuse stays visible without logging every hit.

``settings`` is a module-level reference to the app Settings so tests can
swap it for an isolated one (``monkeypatch.setattr(middleware, "settings",
test_settings)``).
"""

from __future__ import annotations

import random

from fastapi.responses import JSONResponse

from ..config import settings as _app_settings
from ..db.database import connect
from .audit import log_audit
from .rate_limit import client_ip_from_scope, limiter

# Replaceable in tests.
settings = _app_settings

_429_BODY = {
    "error": "rate_limit_exceeded",
    "message": (
        "Too many requests. Please wait a moment and try again."
    ),
}


class RateLimitMiddleware:
    """Pure-ASGI middleware enforcing the sliding-window rules above."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or not settings.rate_limit_enabled:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")
        rules = self._rules_for(path, method)
        if not rules:
            await self.app(scope, receive, send)
            return

        ip = client_ip_from_scope(scope)
        for rule_name, limit, window in rules:
            allowed, retry_after = limiter.hit(
                f"{rule_name}:{ip}", limit, window
            )
            if not allowed:
                self._maybe_audit(ip, rule_name, path)
                response = JSONResponse(
                    status_code=429,
                    content=_429_BODY,
                    headers={"Retry-After": str(int(retry_after))},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)

    @staticmethod
    def _rules_for(path: str, method: str) -> list[tuple[str, int, float]]:
        if method == "POST" and path == "/api/chat":
            return [
                ("chat_min", settings.rl_chat_per_minute, 60.0),
                ("chat_day", settings.rl_chat_per_day, 86_400.0),
            ]
        if method == "POST" and path == "/api/demo/reset":
            return [("reset_hour", settings.rl_reset_per_hour, 3_600.0)]
        if method == "GET" and path.startswith("/api/"):
            return [("read_min", settings.rl_read_per_minute, 60.0)]
        return []

    @staticmethod
    def _maybe_audit(ip: str, rule_name: str, path: str) -> None:
        """Sampled audit of rate-limit rejections (never raises)."""
        try:
            if random.random() >= settings.audit_sample_rate:
                return
            conn = connect(settings.database_path)
            try:
                log_audit(
                    conn,
                    action="rate_limit_hit",
                    ip=ip,
                    details={"rule": rule_name, "path": path},
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass
