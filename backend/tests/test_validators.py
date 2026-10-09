"""Validator tests: message cap, empty rejection, body-size cap."""

from app.config import Settings
from app.validators import body_within_cap, validate_message_payload


def _settings() -> Settings:
    s = Settings()
    s.max_message_length = 2000
    s.max_body_bytes = 65536
    return s


def test_valid_payload_accepted():
    ok, err = validate_message_payload({"message": "Hello"}, _settings())
    assert ok and err == ""


def test_empty_message_rejected():
    # Phase 7: English, customer-facing error messages.
    for bad in ["", "   "]:
        ok, err = validate_message_payload({"message": bad}, _settings())
        assert not ok, bad
        assert "message" in err
    for bad in [None, 123]:
        ok, err = validate_message_payload({"message": bad}, _settings())
        assert not ok, bad
        assert "message" in err


def test_missing_message_rejected():
    ok, err = validate_message_payload({}, _settings())
    assert not ok


def test_non_dict_rejected():
    ok, _ = validate_message_payload(["message"], _settings())
    assert not ok


def test_message_length_cap_enforced():
    settings = _settings()
    ok, err = validate_message_payload({"message": "x" * 2000}, settings)
    assert ok
    ok, err = validate_message_payload({"message": "x" * 2001}, settings)
    assert not ok
    assert "too long" in err


def test_body_cap_logic():
    settings = _settings()
    assert body_within_cap(b"x" * 65536, settings)
    assert not body_within_cap(b"x" * 65537, settings)
    assert body_within_cap(b"", settings)
