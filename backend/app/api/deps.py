"""Shared FastAPI dependencies: settings and per-request DB connection."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator

from ..config import Settings, settings as _settings
from ..db.database import connect


def get_settings() -> Settings:
    return _settings


def get_db() -> Generator[sqlite3.Connection, None, None]:
    # check_same_thread=False: FastAPI resolves this sync dependency in a
    # threadpool thread while the async endpoint body runs elsewhere.
    conn = connect(get_settings().database_path, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()
