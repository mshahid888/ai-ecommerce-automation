"""POST /api/demo/reset — reseed the demo store.

Wipes and re-seeds ONLY demo rows (``is_demo=1`` / store
``demo-muster-shop``); non-demo rows are preserved. Requires
``DEMO_MODE=true``, otherwise 403.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..config import Settings
from ..db.seed import DEMO_STORE_ID, create_demo_store
from .deps import get_db, get_settings

router = APIRouter()


@router.post("/demo/reset")
def demo_reset(
    db: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not settings.demo_mode:
        raise HTTPException(
            status_code=403, detail="demo reset disabled (DEMO_MODE=false)"
        )
    create_demo_store(db)
    return {"status": "reset", "demo_store": DEMO_STORE_ID}
