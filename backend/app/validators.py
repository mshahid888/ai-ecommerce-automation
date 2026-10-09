"""Input validation for the chat API.

Ported from the predecessor project
(``ai-customer-support-automation/src/validators.py``); caps stay the same:
2,000 characters per message, 64 KiB per request body.
"""

from __future__ import annotations

from typing import Any

from .config import Settings


def validate_message_payload(
    payload: Any, settings: Settings
) -> tuple[bool, str]:
    """Validate the JSON body of an incoming customer message.

    Returns ``(True, "")`` when valid, otherwise ``(False, error_message)``.
    Error messages are deliberately generic — they must not leak internals.
    """
    if not isinstance(payload, dict):
        return False, "Request body must be a JSON object."

    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        return False, "Field 'message' is required and must be a non-empty string."
    if len(message) > settings.max_message_length:
        return False, (
            "Field 'message' is too long "
            f"(max {settings.max_message_length} characters)."
        )

    customer_id = payload.get("customer_id")
    if customer_id is not None and (
        not isinstance(customer_id, str) or len(customer_id) > 64
    ):
        return False, "Field 'customer_id' must be a short string when provided."

    store_id = payload.get("store_id")
    if store_id is not None and (
        not isinstance(store_id, str) or len(store_id) > 64
    ):
        return False, "Field 'store_id' must be a short string when provided."

    return True, ""


def body_within_cap(body: bytes, settings: Settings) -> bool:
    """True when the raw request body fits inside ``max_body_bytes``."""
    return len(body) <= settings.max_body_bytes
