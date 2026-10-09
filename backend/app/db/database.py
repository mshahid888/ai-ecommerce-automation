"""SQLite connection helpers (stdlib ``sqlite3`` only).

Phase 1: single-file SQLite is the whole database. Foreign keys are always
on; rows are returned as ``sqlite3.Row`` for column-name access.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def connect(db_path: str | Path, check_same_thread: bool = True) -> sqlite3.Connection:
    """Open a SQLite connection with FK enforcement and Row rows.

    ``check_same_thread=False`` is for per-request connections used inside
    FastAPI, where dependency resolution and the endpoint body may run in
    different threads. Each request gets its own connection, so this is
    safe.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | Path) -> None:
    """Create all tables from ``schema.sql`` (idempotent)."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = connect(db_path)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()
