"""Phase 7 security layer: rate limiting, admin auth, audit logging.

All helpers here use only the standard library plus FastAPI; no Redis,
no external services. The public demo is the threat model: strangers can
reach the chat, so expensive or mutating operations are guarded.
"""

from . import admin, audit, middleware, rate_limit  # noqa: F401
