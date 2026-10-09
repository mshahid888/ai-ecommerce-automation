"""POST /api/integrations/shopify/webhooks — Shopify webhook receiver.

SIMULATED until a Shopify dev store exists: ``SHOPIFY_WEBHOOK_SECRET``
is unset, so the endpoint honestly returns 503 ("shopify_not_configured")
instead of pretending to process webhooks. When the secret IS
configured, the endpoint:

1. verifies ``X-Shopify-Hmac-Sha256`` against the raw body (401 on failure),
2. dedupes on ``X-Shopify-Webhook-Id`` (duplicate → 200, no reprocessing),
3. records the delivery in ``shopify_webhook_events`` + one ``audit_log`` row,
4. returns 200.

Even then it only RECORDS deliveries — no business action (no order
creation, no refunds) is taken automatically. Real processing against a
dev store is Phase 9b work (see docs/SHOPIFY.md).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from ..config import Settings
from ..integrations.webhooks import record_webhook_event, verify_webhook_hmac
from ..security.audit import log_audit
from ..validators import body_within_cap
from .deps import get_db, get_settings

router = APIRouter()

_HMAC_HEADER = "X-Shopify-Hmac-Sha256"
_WEBHOOK_ID_HEADER = "X-Shopify-Webhook-Id"


@router.post("/integrations/shopify/webhooks")
async def shopify_webhook(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    raw_body = await request.body()
    if not body_within_cap(raw_body, settings):
        return JSONResponse(
            status_code=413,
            content={"error": "payload_too_large"},
        )

    secret = settings.shopify_webhook_secret
    if not secret:
        # Honest 503: no dev store is connected; there is nothing real
        # to verify against. This is SIMULATED by design.
        return JSONResponse(
            status_code=503,
            content={
                "error": "shopify_not_configured",
                "detail": (
                    "Kein Shopify-Shop verbunden (Demo-Umgebung). "
                    "SHOPIFY_WEBHOOK_SECRET ist nicht gesetzt."
                ),
                "simulated": True,
            },
        )

    hmac_header = request.headers.get(_HMAC_HEADER)
    if not verify_webhook_hmac(raw_body, hmac_header, secret):
        log_audit(
            db,
            action="shopify_webhook_rejected",
            ip=request.client.host if request.client else None,
            details={"reason": "bad_hmac"},
        )
        db.commit()
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_webhook_signature"},
        )

    webhook_id = request.headers.get(_WEBHOOK_ID_HEADER)
    if not webhook_id:
        return JSONResponse(
            status_code=400,
            content={"error": "missing_webhook_id"},
        )
    topic = request.headers.get("X-Shopify-Topic")
    shop_domain = request.headers.get("X-Shopify-Shop-Domain")

    is_new = record_webhook_event(db, webhook_id, topic, shop_domain)
    if not is_new:
        # Duplicate delivery: acknowledge, do NOT reprocess.
        db.commit()
        return {"status": "duplicate", "simulated": True}

    log_audit(
        db,
        action="shopify_webhook_received",
        ip=request.client.host if request.client else None,
        details={
            "webhook_id": webhook_id,
            "topic": topic,
            "shop_domain": shop_domain,
        },
    )
    db.commit()
    return {"status": "received", "simulated": True}
