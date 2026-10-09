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
  "intent": "order_status | product_question | return_request | complaint | human_support | shipping_info | payment_question | product_availability | order_cancel | greeting | unknown",
  "confidence": 0.0,
  "order_ref": "string or null",
  "product_hint": "product name hint or null",
  "return_reason": "short reason code or null",
  "language": "de | en | unknown",
  "requires_human": false,
  "reason": "one short sentence"
}

Rules:
- "intent" must be exactly one of the eleven values above.
  - order_status: where is my order / delivery status questions
  - shipping_info: shipping costs, delivery time in general (no order ref)
  - payment_question: payment methods, PayPal, invoice
  - product_availability: in stock / availability questions
  - order_cancel: customer wants to cancel (stornieren/widerrufen) an order
  - greeting: a plain greeting with no other request
- "confidence" is a number between 0.0 and 1.0.
- "order_ref" is the order number mentioned by the customer (digits only,
  e.g. "10482"), or null when no order number is present.
- "product_hint" names the product the customer asks about, or null.
- "return_reason" is a short code (e.g. "defekt", "passt_nicht",
  "falsche_ware", "verspaetete_lieferung", "gefaellt_nicht", "sonstiges"),
  or null when the message is not a return request.
- "language" is the customer's language: "de", "en", or "unknown".
- "requires_human" is true for return_request, complaint, human_support,
  order_cancel, unknown, and whenever you are unsure (confidence below 0.6).
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

    Phase 2: English keyword rules covering the four demo scenarios
    (order_status, product_question, return_request, human_support). The
    pipeline validates everything downstream — the mock only suggests an
    intent; lookups, policy checks, and replies are deterministic code.

    Phase 3: extended intent set (shipping_info, payment_question,
    product_availability, order_cancel, greeting) with English keyword
    rules, a documented keyword-strength confidence heuristic, and
    structured extraction fields (product_hint, return_reason, language).

    Confidence calibration (mock):
      confidence = min(base + 0.03 * (matched_keywords - 1), 0.98)
    i.e. each rule carries a base confidence and every additional matched
    keyword from the same rule adds 0.03, capped at 0.98. A single weak
    keyword match (e.g. just "bestellung") stays near its base; a message
    matching three shipping keywords scores near the cap. Bare order
    references score 0.70; no rule match → unknown at 0.35 (always human).
    """

    # Checked in order — first matching group wins. Specific intents
    # (complaint, cancel, return, shipping, payment, availability) are
    # checked BEFORE the generic order_status and product_question rules
    # so that e.g. "shipping for my order" routes to shipping_info even
    # though it contains "order". Complaint is checked BEFORE
    # return_request so a message like "I want to return this, it's
    # terrible" routes to complaint, not return_request.
    _RULES: tuple[tuple[str, tuple[str, ...], float], ...] = (
        ("human_support", (
            "human", "real person", "agent", "representative",
            "someone real", "call me", "support", "contact the team",
        ), 0.95),
        ("complaint", (
            "complaint", "never arrived", "did not arrive", "not arrived",
            "terrible", "awful", "angry", "furious",
            "disappointed", "worst", "rude", "unacceptable",
            "horrible",
        ), 0.90),
        ("order_cancel", (
            "cancel my order", "cancel the order", "cancel order",
        ), 0.92),
        ("return_request", (
            "return", "send back", "send it back",
            "refund", "chargeback", "exchange", "i would like to return",
        ), 0.92),
        ("shipping_info", (
            "shipping cost", "delivery time",
            "how long does shipping take", "shipping",
        ), 0.88),
        ("payment_question", (
            "payment methods", "pay with", "paypal", "invoice",
            "prepayment",
        ), 0.88),
        ("product_availability", (
            "in stock", "still available", "available",
        ), 0.87),
        ("order_status", (
            "where is my order", "order status", "delivery status",
            "track my order", "tracking", "where is", "when will",
            "my package", "has my order", "order #", "order",
        ), 0.93),
        ("product_question", (
            "dishwasher-safe", "dishwasher", "material", "volume",
            "color", "is this", "is the", "how big", "how much",
            "do you have", "question about",
        ), 0.85),
    )

    # Greeting is deliberately checked LAST: "Hello, where is my order
    # #10482?" must route to order_status, not greeting. Short "hi"
    # needs a word boundary so it doesn't match inside other words.
    _GREETING_PHRASES = (
        "hello", "good morning", "good afternoon", "good evening",
        "hey",
    )
    _GREETING_WORD_RE = re.compile(r"\bhi\b")

    # product_hint extraction: message substrings → demo product name.
    _PRODUCT_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("AquaPure 750", ("water bottle", "bottle", "aquapure", "trinkflasche")),
        ("SolarBank 30000mAh", ("solar bank", "solarbank", "power bank", "powerbank")),
        ("Manual Coffee Grinder", ("coffee grinder", "coffee", "kaffeemühle", "kaffeemuehle")),
        ("LED Desk Lamp", ("desk lamp", "led lamp", "lamp", "schreibtischlampe")),
    )

    # return_reason extraction for return_request messages. The reason
    # *codes* stay as-is — they are internal identifiers referenced by
    # the CLASSIFICATION_SYSTEM_PROMPT contract and the return policy.
    _RETURN_REASONS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("defekt", ("defective", "defect", "broken", "damaged",
                    "not working", "faulty")),
        ("passt_nicht", ("doesn't fit", "does not fit", "too small",
                         "too big", "wrong size")),
        ("falsche_ware", ("wrong item", "wrong product", "wrong one",
                          "mixed up", "not what i ordered")),
        ("verspaetete_lieferung", ("late", "delayed", "took too long",
                                  "arrived late")),
        ("gefaellt_nicht", ("don't like", "do not like", "didn't like",
                            "not as expected", "dislike")),
    )

    # Order references: optional '#', 4–6 digits (e.g. "#10482", "10482").
    _ORDER_REF_RE = re.compile(r"#?(\d{4,6})")

    def classify(self, message: str) -> str:
        text = message.lower()
        order_match = self._ORDER_REF_RE.search(message)
        order_ref = order_match.group(1) if order_match else None

        for intent, keywords, base_confidence in self._RULES:
            matched = [k for k in keywords if k in text]
            if matched:
                # Keyword-strength heuristic: more matched keywords from
                # the same rule → higher confidence, capped at 0.98.
                confidence = min(
                    base_confidence + 0.03 * (len(matched) - 1), 0.98
                )
                return json.dumps({
                    "intent": intent,
                    "confidence": round(confidence, 2),
                    "order_ref": order_ref,
                    "product_hint": self._extract_product_hint(text),
                    "return_reason": self._extract_return_reason(text)
                    if intent == "return_request" else None,
                    "language": _detect_language(text),
                    "requires_human": intent in {
                        "return_request", "complaint", "human_support",
                        "order_cancel",
                    },
                    "reason": (
                        "[demo rule-based classifier] matched "
                        f"'{intent}' keywords: {', '.join(matched[:3])}"
                    ),
                })

        # Greeting last: only when nothing else matched.
        if any(p in text for p in self._GREETING_PHRASES) or self._GREETING_WORD_RE.search(text):
            return json.dumps({
                "intent": "greeting",
                "confidence": 0.90,
                "order_ref": order_ref,
                "product_hint": None,
                "return_reason": None,
                "language": _detect_language(text),
                "requires_human": False,
                "reason": "[demo rule-based classifier] greeting detected",
            })

        # Fallback: any bare order reference is treated as an order question.
        if order_ref:
            return json.dumps({
                "intent": "order_status",
                "confidence": 0.70,
                "order_ref": order_ref,
                "product_hint": None,
                "return_reason": None,
                "language": _detect_language(text),
                "requires_human": False,
                "reason": "[demo rule-based classifier] order number detected",
            })

        return json.dumps({
            "intent": "unknown",
            "confidence": 0.35,
            "order_ref": order_ref,
            "product_hint": None,
            "return_reason": None,
            "language": _detect_language(text),
            "requires_human": True,
            "reason": "[demo rule-based classifier] no rule matched",
        })

    @classmethod
    def _extract_product_hint(cls, text: str) -> str | None:
        for name, keywords in cls._PRODUCT_HINTS:
            if any(k in text for k in keywords):
                return name
        return None

    @classmethod
    def _extract_return_reason(cls, text: str) -> str:
        for code, keywords in cls._RETURN_REASONS:
            if any(k in text for k in keywords):
                return code
        return "sonstiges"


_DE_WORD_RE = re.compile(r"[a-zäöüß]+")


def _detect_language(text: str) -> str:
    """Deterministic de/en language guess for the mock classifier."""
    de_tokens = {
        "der", "die", "das", "und", "ist", "ich", "meine", "mein", "nicht",
        "bitte", "wie", "was", "wo", "hallo", "danke", "bestellung", "mit",
        "für", "eine", "sind", "haben", "möchte", "kann",
    }
    en_tokens = {
        "the", "and", "is", "are", "my", "package", "order", "please",
        "want", "never", "arrived", "money", "back", "hello", "can", "you",
    }
    tokens = set(_DE_WORD_RE.findall(text.lower()))
    if re.search(r"[äöüß]", text.lower()):
        return "de"
    de_hits = len(tokens & de_tokens)
    en_hits = len(tokens & en_tokens)
    if de_hits > en_hits:
        return "de"
    if en_hits > de_hits:
        return "en"
    return "unknown"


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
            "max_tokens": self._settings.llm_max_tokens_per_request,
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
            "max_tokens": self._settings.llm_max_tokens_per_request,
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
