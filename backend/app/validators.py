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
        return False, "Die Anfrage muss ein JSON-Objekt sein."
    if "message" not in payload:
        return False, "Das Feld 'message' ist erforderlich."

    message = payload.get("message")
    if not isinstance(message, str):
        return False, "Das Feld 'message' muss eine Zeichenkette sein."
    if not message.strip():
        return False, (
            "Bitte geben Sie eine Nachricht ein — leere Nachrichten "
            "können nicht verarbeitet werden."
        )
    if len(message) > settings.max_message_length:
        return False, (
            "Ihre Nachricht ist zu lang "
            f"(maximal {settings.max_message_length} Zeichen)."
        )

    customer_id = payload.get("customer_id")
    if customer_id is not None and (
        not isinstance(customer_id, str) or len(customer_id) > 64
    ):
        return False, (
            "Das Feld 'customer_id' muss eine kurze Zeichenkette sein."
        )

    store_id = payload.get("store_id")
    if store_id is not None and (
        not isinstance(store_id, str) or len(store_id) > 64
    ):
        return False, "Das Feld 'store_id' muss eine kurze Zeichenkette sein."

    return True, ""


def body_within_cap(body: bytes, settings: Settings) -> bool:
    """True when the raw request body fits inside ``max_body_bytes``."""
    return len(body) <= settings.max_body_bytes
