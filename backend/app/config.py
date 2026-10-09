"""Environment-based application settings (no pydantic-settings dependency).

Phase 1: plain ``os.environ`` reads with sane defaults. A later phase may
move this to ``pydantic-settings`` if the configuration surface grows.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return default
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name, None)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env(name, None)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name, None)
    try:
        return float(raw) if raw is not None else default
    except ValueError:
        return default


_BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings:
    """Runtime configuration, read from the environment at import time."""

    def __init__(self) -> None:
        self.llm_provider: str = _env("LLM_PROVIDER", "mock") or "mock"
        self.llm_model: str = (
            _env("LLM_MODEL", "gemini-3.8-flash") or "gemini-3.8-flash"
        )
        self.llm_api_key: str | None = _env("LLM_API_KEY", None)
        self.llm_base_url: str = (
            _env("LLM_BASE_URL", "https://api.openai.com/v1")
            or "https://api.openai.com/v1"
        )
        self.llm_timeout_seconds: int = _env_int("LLM_TIMEOUT_SECONDS", 15)
        # Per-request token ceiling for real providers (cost guardrail).
        self.llm_max_tokens_per_request: int = _env_int(
            "LLM_MAX_TOKENS_PER_REQUEST", 300
        )
        # Daily AI request cap for the public demo. NOTE: enforced in
        # Phase 7 (rate limiting); the setting is defined here now so
        # dashboards and quotas can reference it early.
        self.llm_daily_request_cap: int = _env_int(
            "LLM_DAILY_REQUEST_CAP", 500
        )
        # Confidence below this routes to a human (see rules/escalation.py).
        self.confidence_threshold: float = _env_float(
            "CONFIDENCE_THRESHOLD", 0.6
        )
        self.max_message_length: int = _env_int("MAX_MESSAGE_LENGTH", 2000)
        self.max_body_bytes: int = _env_int("MAX_BODY_BYTES", 65536)
        # -- Phase 7: abuse protection -----------------------------------
        # Server-side admin key for mutating admin endpoints
        # (POST /api/demo/reset, ...). Generated + persisted on first run
        # when absent (see security/admin.py). Never sent to the frontend.
        self.admin_api_key: str | None = _env("ADMIN_API_KEY", None)
        self.admin_key_file: Path = _BACKEND_ROOT / "data" / ".admin_key"
        # Rate limiting (in-memory sliding window, per client IP).
        self.rate_limit_enabled: bool = _env_bool("RATE_LIMIT_ENABLED", True)
        self.rl_chat_per_minute: int = _env_int("RL_CHAT_PER_MINUTE", 30)
        self.rl_chat_per_day: int = _env_int("RL_CHAT_PER_DAY", 200)
        self.rl_read_per_minute: int = _env_int("RL_READ_PER_MINUTE", 60)
        self.rl_reset_per_hour: int = _env_int("RL_RESET_PER_HOUR", 5)
        # Fraction of rate-limit rejections written to the audit log.
        self.audit_sample_rate: float = _env_float("AUDIT_SAMPLE_RATE", 0.05)
        # Accept either "sqlite:///./data/demo.db" or a bare path.
        raw_db = _env("DATABASE_URL", "sqlite:///./data/demo.db") or ""
        if raw_db.startswith("sqlite:///"):
            raw_db = raw_db[len("sqlite:///"):]
        db_path = Path(raw_db)
        if not db_path.is_absolute():
            db_path = _BACKEND_ROOT / db_path
        self.database_path: Path = db_path
        self.demo_mode: bool = _env_bool("DEMO_MODE", True)
        raw_origins = _env(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ) or ""
        self.cors_origins: list[str] = [
            origin.strip()
            for origin in raw_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
