"""LLM provider contract tests.

Note on the "7-field contract": the predecessor this was ported from
defines five keys (intent, confidence, order_id/order_ref, requires_human,
reason); the port keeps that exact shape — the task's "7-field" mention
was a miscount. The tests assert the real contract.
"""

import json

import pytest

from app.ai.providers import (
    LLMError,
    MockLLMProvider,
    OpenAICompatibleProvider,
    get_provider,
)
from app.config import Settings

_CONTRACT_KEYS = {"intent", "confidence", "order_ref", "requires_human", "reason"}


def test_mock_classify_returns_valid_json_contract():
    provider = MockLLMProvider()
    for message in [
        "Where is my order #10482?",
        "Is the water bottle dishwasher-safe?",
        "I want a refund, this is terrible",
        "I need to talk to a human",
        "asdkfj qwer zzz",
    ]:
        raw = provider.classify(message)
        parsed = json.loads(raw)  # must be valid JSON
        assert _CONTRACT_KEYS <= set(parsed.keys()), parsed
        assert isinstance(parsed["confidence"], (int, float))
        assert 0.0 <= parsed["confidence"] <= 1.0
        assert isinstance(parsed["requires_human"], bool)


def test_mock_classify_extracts_order_ref():
    parsed = json.loads(MockLLMProvider().classify("Where is my order #10482?"))
    assert parsed["order_ref"] == "10482"
    assert parsed["intent"] == "order_status"


def test_mock_classify_unknown_fallback():
    parsed = json.loads(MockLLMProvider().classify("blarg wibble zzz"))
    assert parsed["intent"] == "unknown"
    assert parsed["requires_human"] is True


def test_get_provider_mock():
    settings = Settings()
    settings.llm_provider = "mock"
    assert isinstance(get_provider(settings), MockLLMProvider)


def test_get_provider_unknown_raises():
    settings = Settings()
    settings.llm_provider = "definitely-not-a-provider"
    with pytest.raises(LLMError):
        get_provider(settings)


def test_openai_compatible_requires_key():
    settings = Settings()
    settings.llm_provider = "openai_compatible"
    settings.llm_api_key = None
    with pytest.raises(LLMError):
        OpenAICompatibleProvider(settings)
