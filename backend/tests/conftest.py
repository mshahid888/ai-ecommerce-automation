"""TestClient fixture: runs the real app (startup seeds the dev DB).

Phase 7: the admin API key is fixed for the whole test session and the
rate limiter is disabled globally here — abuse tests enable it
explicitly on an isolated middleware settings object. Env vars must be
set BEFORE ``app.main`` is imported (Settings reads them at import).
"""

from __future__ import annotations

import os

os.environ.setdefault("ADMIN_API_KEY", "phase7-test-admin-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
