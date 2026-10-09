"""LLM provider abstraction.

Contract (ported from ``ai-customer-support-automation/src/llm.py``):
``classify(message) -> raw JSON string`` with the 7-field classification
contract below; system prompt shape, mock rule structure, and the
OpenAI-compatible provider (stdlib urllib, temperature 0.0, max_tokens 300)
are kept identical. Imports are adapted to this package.

The rest of the system only talks to the ``LLMProvider`` interface, so the
model vendor can be swapped by changing ``LLM_PROVIDER`` in the environment —
no code changes needed.

Providers shipping with this project:

* ``MockLLMProvider`` — deterministic, rule-based demo classifier (no AI).
* ``OpenAICompatibleProvider`` — any OpenAI-style ``/chat/completions``.
* ``GeminiProvider`` — Google Gemini via the OpenAI-compatible endpoint,
  authenticated through the Secure Vault surrogate helper (never an env key).
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

from ..config import Settings


# The exact JSON contract the classifier must return. The system prompt below
# teaches the model this shape; the pipeline validates it strictly.
CLASSIFICATION_SYSTEM_PROMPT = """\
You are an intent classifier for an e-commerce customer-support chatbot.

Read the customer message and reply with ONLY a single JSON object — no
markdown, no explanations, no extra text — with exactly these fields:

{
  "intent": "order_status | product_question | return_request | complaint | human_support | unknown",
  "confidence": 0.0,
  "order_ref": "string or null",
  "requires_human": false,
  "reason": "one short sentence"
}

Rules:
- "intent" must be exactly one of the six values above.
- "confidence" is a number between 0.0 and 1.0.
- "order_ref" is the order number mentioned by the customer (digits only,
  e.g. "10482"), or null when no order number is present.
- "requires_human" is true for return_request, complaint, human_support,
  unknown, and whenever you are unsure (confidence below 0.6).
- "reason" briefly explains the classification in plain words.
"""


class LLMError(Exception):
    """Raised when the LLM provider cannot produce a usable answer."""


class LLMProvider(ABC):
    """Interface every LLM backend must implement."""

    @abstractmethod
    def classify(self, message: str) -> str:
        """Return the model's raw reply for *message* (expected: a JSON string).

        May raise :class:`LLMError` when the provider is unreachable or the
        request fails. The caller treats any failure as "route to human".
        """


class MockLLMProvider(LLMProvider):
    """Deterministic rule-based DEMO classifier (no real AI involved).

    Useful for local development, demos, and automated tests: it behaves like
    the real classifier contract (JSON in, JSON out) without needing an API
    key or network access. Never mistake its output for a production model.

    Phase 2: German keyword rules covering the four demo scenarios
    (order_status, product_question, return_request, human_support). The
    pipeline validates everything downstream — the mock only suggests an
    intent; lookups, policy checks, and replies are deterministic code.
    """

    # Checked in order — first matching group wins. German keywords come
    # first inside each group; the English set keeps the predecessor's
    # contract tests green.
    _RULES: tuple[tuple[str, tuple[str, ...], float], ...] = (
        ("human_support", (
            "mitarbeiter", "mensch", "support", "kontakt zum team",
            "human", "real person", "agent", "representative",
            "someone real", "call me", "talk to",
        ), 0.95),
        ("complaint", (
            "beschwerde", "unverschämt", "ärgerlich", "nie angekommen",
            "nicht angekommen", "nicht erhalten",
            "never arrived", "did not arrive", "complain", "terrible",
            "awful", "angry", "furious",
            "disappointed", "worst", "rude", "unacceptable",
            "horrible",
        ), 0.90),
        ("return_request", (
            "zurücksenden", "rücksenden", "retoure", "rückgabe",
            "zurückgeben", "umtausch", "widerruf", "retourenschein",
            "refund", "money back", "chargeback", "give me my money",
        ), 0.92),
        ("order_status", (
            "wo bleibt meine bestellung", "bestellstatus", "lieferstatus",
            "sendungsverfolgung", "wo ist mein", "wo ist meine",
            "wann kommt", "liefertermin", "paket", "tracking",
            "bestellung",
            "where is my order", "order status", "track my order",
            "tracking", "delivery status", "when will",
            "has my order", "order #", "my package",
        ), 0.93),
        ("product_question", (
            "spülmaschinengeeignet", "spülmaschine", "material", "volumen",
            "farbe", "frage zum", "eigenschaft", "ist diese", "ist dieses",
            "ist dieser", "ist das", "ist der", "ist die",
            "wie groß", "wie viel", "gibt es",
            "how do", "how can", "what is", "do you ship",
            "shipping time", "shipping", "delivery",
            "how long", "return policy", "payment method",
            "opening hours", "where are you located",
        ), 0.85),
    )

    # Order references: optional '#', 4–6 digits (e.g. "#10482", "10482").
    _ORDER_REF_RE = re.compile(r"#?(\d{4,6})")

    def classify(self, message: str) -> str:
        text = message.lower()
        order_match = self._ORDER_REF_RE.search(message)
        order_ref = order_match.group(1) if order_match else None

        for intent, keywords, confidence in self._RULES:
            if any(k in text for k in keywords):
                return json.dumps({
                    "intent": intent,
                    "confidence": confidence,
                    "order_ref": order_ref,
                    "requires_human": intent in {
                        "return_request", "complaint", "human_support",
                    },
                    "reason": f"[demo rule-based classifier] matched '{intent}' keywords",
                })

        # Fallback: any bare order reference is treated as an order question.
        if order_ref:
            return json.dumps({
                "intent": "order_status",
                "confidence": 0.70,
                "order_ref": order_ref,
                "requires_human": False,
                "reason": "[demo rule-based classifier] order number detected",
            })

        return json.dumps({
            "intent": "unknown",
            "confidence": 0.35,
            "order_ref": order_ref,
            "requires_human": True,
            "reason": "[demo rule-based classifier] no rule matched",
        })


class OpenAICompatibleProvider(LLMProvider):
    """Calls any OpenAI-style ``/chat/completions`` endpoint via stdlib only."""

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise LLMError(
                "LLM_API_KEY is not set but LLM_PROVIDER='openai_compatible' "
                "was requested."
            )
        self._settings = settings

    def classify(self, message: str) -> str:
        payload = json.dumps({
            "model": self._settings.llm_model,
            "messages": [
                {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            "temperature": 0.0,   # deterministic output for classification
            "max_tokens": 300,
        }).encode("utf-8")

        request = urllib.request.Request(
            f"{self._settings.llm_base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._settings.llm_api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self._settings.llm_timeout_seconds
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # network error, timeout, bad status, ...
            raise LLMError(f"LLM request failed: {type(exc).__name__}") from exc

        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM response had an unexpected shape") from exc


class GeminiProvider(LLMProvider):
    """Google Gemini via the OpenAI-compatible endpoint.

    Authentication comes ONLY from the Secure Vault via the surrogate helper
    (``add_surrogate_to_request``); no API key is ever read from the
    environment or hardcoded. Uses the ``/v1beta/openai`` base URL with the
    ``/chat/completions`` endpoint — the same shape as the skill's
    ``gemini_chat.py`` CLI. stdlib urllib only.

    The helper import is guarded: constructing this provider when the helper
    file is absent raises :class:`LLMError` only at construction/call time,
    so the rest of the backend keeps working without it.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
    _HELPERS_PATH = "/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        try:
            helpers_dir = str(Path(self._HELPERS_PATH).parent)
            if helpers_dir not in sys.path:
                sys.path.insert(0, helpers_dir)
            import dynamic_credentials  # noqa: E402

            self._add_surrogate = dynamic_credentials.add_surrogate_to_request
            self._read_json = dynamic_credentials.read_json_response
        except Exception as exc:
            raise LLMError(
                "Gemini provider requires the Secure Vault credential helper "
                f"({self._HELPERS_PATH}), which is unavailable: {exc}"
            ) from exc

    def classify(self, message: str) -> str:
        payload = json.dumps({
            "model": self._settings.llm_model,
            "messages": [
                {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            "temperature": 0.0,   # deterministic output for classification
            "max_tokens": 300,
        }).encode("utf-8")

        request = urllib.request.Request(
            f"{self.BASE_URL}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            # Credential surrogate attaches the Secure Vault token; the raw
            # key never touches this process's environment or logs.
            self._add_surrogate(
                request,
                "custom.google-gemini",
                entry_name="access_token",
                allowed_hosts=["generativelanguage.googleapis.com"],
            )
            with urllib.request.urlopen(
                request, timeout=self._settings.llm_timeout_seconds
            ) as response:
                body = self._read_json(response)
        except Exception as exc:
            raise LLMError(f"Gemini request failed: {type(exc).__name__}") from exc

        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Gemini response had an unexpected shape") from exc


def get_provider(settings: Settings) -> LLMProvider:
    """Factory: pick the provider from ``LLM_PROVIDER``."""
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleProvider(settings)
    if settings.llm_provider == "gemini":
        return GeminiProvider(settings)
    raise LLMError(
        f"Unknown LLM_PROVIDER={settings.llm_provider!r} "
        "(expected 'mock', 'openai_compatible', or 'gemini')"
    )
