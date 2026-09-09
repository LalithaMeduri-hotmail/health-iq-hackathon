"""Unit tests for `services/security.py` (PIN hashing, session token issue/verify)."""

from app.services import security


def test_hash_pin_produces_a_verifiable_but_non_reversible_hash() -> None:
    pin_hash = security.hash_pin("4821")

    assert pin_hash != "4821"
    assert security.verify_pin("4821", pin_hash) is True
    assert security.verify_pin("0000", pin_hash) is False


def test_hash_pin_uses_a_unique_salt_per_call() -> None:
    assert security.hash_pin("4821") != security.hash_pin("4821")


def test_issue_and_decode_session_token_round_trips_the_user_id() -> None:
    token, expires_in = security.issue_session_token("user-123")

    assert expires_in > 0
    assert security.decode_session_token(token) == "user-123"


def test_decode_session_token_rejects_a_tampered_token() -> None:
    token, _ = security.issue_session_token("user-123")

    assert security.decode_session_token(token + "tampered") is None


def test_decode_session_token_rejects_garbage() -> None:
    assert security.decode_session_token("not-a-jwt") is None


def test_decode_session_token_rejects_an_expired_token(monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta

    import jwt as pyjwt

    payload = {
        "sub": "user-123",
        "iat": datetime.now(UTC) - timedelta(hours=2),
        "exp": datetime.now(UTC) - timedelta(hours=1),
    }
    expired_token = pyjwt.encode(payload, security._jwt_secret(), algorithm="HS256")

    assert security.decode_session_token(expired_token) is None
