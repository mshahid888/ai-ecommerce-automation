"""Server-side admin API key (Phase 7).

Mutating admin endpoints (demo reset, future admin ops) require the key
in the ``X-Admin-Key`` header. Comparison is constant-time
(``hmac.compare_digest``). The key is:

* read from ``ADMIN_API_KEY`` when set (production), or
* generated once with ``secrets.token_urlsafe`` and persisted with 0600
  permissions to ``data/.admin_key`` — printed to stdout exactly once,
  never logged again.

The file is git-ignored (``.admin_key``); the key never appears in code,
commits, the frontend, or API responses.
"""

from __future__ import annotations

import hmac
import os
import secrets

from fastapi import Depends, HTTPException, Request

from ..api.deps import get_db, get_settings
from ..config import Settings
from .audit import log_audit

_ADMIN_HEADER = "X-Admin-Key"


def ensure_admin_key(settings: Settings) -> str:
    """Return the admin key, generating + persisting it on first run.

    Prints the freshly generated key to stdout exactly once (operator
    setup); it is never logged afterwards.
    """
    if settings.admin_api_key:
        return settings.admin_api_key

    key_file = settings.admin_key_file
    if key_file.exists():
        stored = key_file.read_text(encoding="utf-8").strip()
        if stored:
            settings.admin_api_key = stored
            return stored

    key = secrets.token_urlsafe(32)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    # 0600 from the first byte: no world/group-readable window.
    fd = os.open(
        str(key_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
    )
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(key + "\n")
    os.chmod(str(key_file), 0o600)
    settings.admin_api_key = key
    print(
        "[ai-ecommerce-automation] ADMIN_API_KEY generated and saved to "
        f"{key_file} (mode 0600). Use header 'X-Admin-Key' for admin "
        "endpoints. Set ADMIN_API_KEY in the environment to override. "
        f"Key: {key}",
        flush=True,
    )
    return key


async def require_admin(
    request: Request,
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    """Dependency: 401 unless a valid admin key is presented.

    Failed attempts are audit-logged (action ``admin_auth_failure``).
    """
    expected = settings.admin_api_key
    provided = request.headers.get(_ADMIN_HEADER, "")
    if expected and hmac.compare_digest(provided, expected):
        return
    client = request.client.host if request.client else None
    try:
        log_audit(
            db,
            action="admin_auth_failure",
            ip=client,
            details={"path": request.url.path, "method": request.method},
        )
        db.commit()
    except Exception:
        # Audit logging must never break the auth decision itself.
        pass
    raise HTTPException(
        status_code=401,
        detail="Admin key missing or invalid.",
    )
