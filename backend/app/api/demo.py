"""POST /api/demo/reset — reseed the demo store.

Wipes and re-seeds ONLY demo rows (``is_demo=1`` / store
``demo-muster-shop``); non-demo rows are preserved. Requires
``DEMO_MODE=true``, otherwise 403.

Phase 7: requires the server-side admin API key
(``X-Admin-Key`` header, constant-time compare) — 401 without it.
Every reset is audit-logged (action ``demo_reset``). The audit log
itself is never wiped by the reset.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from ..config import Settings
from ..db.seed import DEMO_STORE_ID, create_demo_store
from ..security.admin import require_admin
from ..security.audit import log_audit
from .deps import get_db, get_settings

router = APIRouter()


@router.post("/demo/reset")
def demo_reset(
    request: Request,
    _admin: None = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not settings.demo_mode:
        raise HTTPException(
            status_code=403, detail="demo reset disabled (DEMO_MODE=false)"
        )
    create_demo_store(db)
    client = request.client.host if request.client else None
    log_audit(
        db,
        action="demo_reset",
        ip=client,
        details={"demo_store": DEMO_STORE_ID},
        store_id=DEMO_STORE_ID,
    )
    db.commit()
    return {"status": "reset", "demo_store": DEMO_STORE_ID}
