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
    return payload.get("sub")
