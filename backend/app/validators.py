"""Input validation for the chat API.

Ported from the predecessor project
(``ai-customer-support-automation/src/validators.py``); caps stay the same:
2,000 characters per message, 64 KiB per request body.

Phase 7: error messages are German (customer-facing), still deliberately
generic — they must not leak internals. Empty/whitespace messages are
rejected with HTTP 400.
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
        return False, "The request must be a JSON object."
    if "message" not in payload:
        return False, "The 'message' field is required."

    message = payload.get("message")
    if not isinstance(message, str):
        return False, "The 'message' field must be a string."
    if not message.strip():
        return False, (
            "Please enter a message — empty messages "
            "cannot be processed."
        )
    if len(message) > settings.max_message_length:
        return False, (
            "Your message is too long "
            f"(max {settings.max_message_length} characters)."
        )

    customer_id = payload.get("customer_id")
    if customer_id is not None and (
        not isinstance(customer_id, str) or len(customer_id) > 64
    ):
        return False, (
            "The 'customer_id' field must be a short string."
        )

    store_id = payload.get("store_id")
    if store_id is not None and (
        not isinstance(store_id, str) or len(store_id) > 64
    ):
        return False, "The 'store_id' field must be a short string."

    return True, ""


def body_within_cap(body: bytes, settings: Settings) -> bool:
    """True when the raw request body fits inside ``max_body_bytes``."""
    return len(body) <= settings.max_body_bytes
