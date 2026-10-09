"""FastAPI application entry point.

Mounts the ``/api`` router; exposes ``/`` and ``/health``.
On startup the SQLite schema is created, the admin API key is ensured,
and the demo store is seeded (if missing) so the demo works out of the
box.

Phase 7: ``@app.on_event("startup")`` was replaced by a lifespan handler
(the ``on_event`` decorator is deprecated and removed in newer FastAPI
versions). A sliding-window rate limiter runs as ASGI middleware.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import chat, demo, events, integrations, ops
from .config import settings
from .db.database import connect, init_db
from .db.seed import DEMO_STORE_ID, create_demo_store
from .security.admin import ensure_admin_key
from .security.middleware import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ------------------------------------------------------
    init_db(settings.database_path)
    ensure_admin_key(settings)
    conn = connect(settings.database_path)
    try:
        store = conn.execute(
            "SELECT id FROM stores WHERE id = ?", (DEMO_STORE_ID,)
        ).fetchone()
        if store is None:
            create_demo_store(conn)
        conn.commit()
    finally:
        conn.close()
    yield
    # --- shutdown -----------------------------------------------------
    # Nothing to tear down: per-request connections close themselves and
    # the in-memory rate limiter is intentionally ephemeral.


app = FastAPI(title="ai-ecommerce-automation-backend", lifespan=lifespan)

# Phase 7: rate limiting runs outermost, before CORS preflight handling.
app.add_middleware(RateLimitMiddleware)

# Phase 2: allow the Next.js dev frontend to call the API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)


@app.get("/")
def root():
    return {
        "service": "ai-ecommerce-automation-backend",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-ecommerce-automation-backend",
        "llm_provider": settings.llm_provider,
        "demo_mode": settings.demo_mode,
    }


app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(ops.router, prefix="/api", tags=["ops"])
app.include_router(events.router, prefix="/api", tags=["events"])
app.include_router(demo.router, prefix="/api", tags=["demo"])
app.include_router(
    integrations.router, prefix="/api", tags=["integrations"]
)
