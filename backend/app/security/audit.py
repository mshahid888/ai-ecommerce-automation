"""Append-only audit logging (Phase 7).

Security-relevant events go into the ``audit_log`` table, which the
application never updates or deletes — not even on demo reset — so abuse
evidence survives. Actor IPs are stored as truncated SHA-256 hashes, not
raw addresses.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

_IP_HASH_PREFIX_LEN = 16


def hash_ip(ip: str | None) -> str | None:
    """One-way hash of a client IP for the audit log (None-safe)."""
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:_IP_HASH_PREFIX_LEN]


def log_audit(
    conn: sqlite3.Connection,
    *,
    action: str,
    ip: str | None = None,
    details: dict[str, Any] | None = None,
    store_id: str | None = None,
) -> None:
    """Insert one audit row. The caller owns the transaction (commit)."""
    conn.execute(
        "INSERT INTO audit_log (actor_ip_hash, action, details_json, store_id)"
        " VALUES (?, ?, ?, ?)",
        (
            hash_ip(ip),
            action,
            json.dumps(details or {}, ensure_ascii=False),
            store_id,
        ),
    )


def recent_audits(
    conn: sqlite3.Connection, action: str | None = None, limit: int = 50
) -> list[sqlite3.Row]:
    """Read audit rows (newest first); helper for tests and ops."""
    if action is not None:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE action = ?"
            " ORDER BY id DESC LIMIT ?",
            (action, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return rows
