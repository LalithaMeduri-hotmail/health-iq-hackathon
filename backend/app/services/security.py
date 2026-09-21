"""PIN hashing and session-token helpers (backend.instructions.md security section).

Deterministic, network-free crypto helpers - unit-testable without any Azure dependency. Never
import FastAPI/HTTP types here; callers (api/auth.py, deps.py) translate failures to HTTP.
"""

import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import bcrypt
import jwt

from app.config import get_settings

_JWT_ALGORITHM = "HS256"


@lru_cache
def _dev_jwt_secret() -> str:
    """Per-process random fallback so local/demo runs never share one hardcoded secret.

    Production MUST set `JWT_SECRET` (Key Vault/env, see config.py) - this fallback exists only so
    `DEMO_MODE` works out of the box without a real secret ever being committed to source. Because
    it is regenerated per process, restarting the server invalidates all existing sessions.
    """
    return secrets.token_hex(32)


def _jwt_secret() -> str:
    settings = get_settings()
    return settings.jwt_secret or _dev_jwt_secret()


def hash_pin(pin: str) -> str:
    """Bcrypt hash (unique salt per call) - never store or log a raw PIN."""
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_pin(pin: str, pin_hash: str) -> bool:
    return bcrypt.checkpw(pin.encode("utf-8"), pin_hash.encode("utf-8"))


def issue_session_token(user_id: str) -> tuple[str, int]:
    """Return `(token, expires_in_seconds)`; `sub` is the only claim callers may trust."""
    settings = get_settings()
    expires_in = settings.jwt_expires_minutes * 60
    now = datetime.now(UTC)
    payload = {"sub": user_id, "iat": now, "exp": now + timedelta(seconds=expires_in)}
    token = jwt.encode(payload, _jwt_secret(), algorithm=_JWT_ALGORITHM)
    return token, expires_in


def decode_session_token(token: str) -> str | None:
    """Return the `user_id` (`sub` claim) if the token is valid and unexpired, else `None`."""
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("scope") is not None:
        return None
    return payload.get("sub")


_REVIEW_UNLOCK_SCOPE = "review-unlock"


def generate_review_pin() -> str:
    """Six digits, uniformly random. Emailed to the clinician; only its hash is ever stored."""
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_review_unlock(token_hash: str, minutes: int) -> tuple[str, int]:
    """Proof that this browser answered the PIN for one review. Scoped to that review alone."""
    expires_in = minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": token_hash,
        "scope": _REVIEW_UNLOCK_SCOPE,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_JWT_ALGORITHM), expires_in


def review_unlock_matches(value: str, token_hash: str) -> bool:
    """True when `value` is an unexpired unlock issued for exactly this review."""
    try:
        payload = jwt.decode(value, _jwt_secret(), algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return False
    if payload.get("scope") != _REVIEW_UNLOCK_SCOPE:
        return False
    return secrets.compare_digest(str(payload.get("sub", "")), token_hash)
