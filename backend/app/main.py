"""FastAPI application entry point.

Mounts the ``/api`` router; exposes ``/`` and ``/health``.
On startup the SQLite schema is created and the demo store is seeded
(if missing) so the demo works out of the box.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import chat, demo, events, tickets
from .config import settings
from .db.database import connect, init_db
from .db.seed import DEMO_STORE_ID, create_demo_store

app = FastAPI(title="ai-ecommerce-automation-backend")

# Phase 2: allow the Next.js dev frontend to call the API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db(settings.database_path)
    conn = connect(settings.database_path)
    try:
        store = conn.execute(
            "SELECT id FROM stores WHERE id = ?", (DEMO_STORE_ID,)
        ).fetchone()
        if store is None:
            create_demo_store(conn)
        else:
            conn.commit()
    finally:
        conn.close()


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
app.include_router(tickets.router, prefix="/api", tags=["tickets"])
app.include_router(events.router, prefix="/api", tags=["events"])
app.include_router(demo.router, prefix="/api", tags=["demo"])
