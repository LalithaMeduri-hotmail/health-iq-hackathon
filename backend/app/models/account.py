"""Account/auth contracts: username|mobile|email + PIN login (docs/lld/1-*.md Section 0.5).

`models/` is a pure leaf: no imports from services, repositories, or SDK clients here.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

PIN_RE = re.compile(r"^\d{4}$")
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.]{3,32}$")
MOBILE_RE = re.compile(r"^\+?[0-9]{7,15}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Sequential/repeated PINs are trivially guessable and must never be accepted, since a 4-digit
# PIN is inherently low-entropy and this is the *only* secret gating an account.
_TRIVIAL_PINS = {
    "0000", "1111", "2222", "3333", "4444", "5555", "6666", "7777", "8888", "9999",
    "1234", "4321", "0123", "1000", "2000",
}


class RegisterRequest(BaseModel):
    """`POST /api/v1/auth/register` body. At least one of `mobile`/`email` is required."""

    model_config = ConfigDict(populate_by_name=True)

    username: str
    mobile: str | None = None
    email: str | None = None
    pin: str
    display_name: str | None = Field(alias="displayName", default=None)

    @field_validator("username")
    @classmethod
    def _username_format(cls, value: str) -> str:
        if not USERNAME_RE.match(value):
            raise ValueError("username must be 3-32 characters: letters, digits, '.', or '_'")
        return value.casefold()

    @field_validator("mobile")
    @classmethod
    def _mobile_format(cls, value: str | None) -> str | None:
        if value is not None and not MOBILE_RE.match(value):
            raise ValueError("mobile must be 7-15 digits, optionally prefixed with '+'")
        return value

    @field_validator("email")
    @classmethod
    def _email_format(cls, value: str | None) -> str | None:
        if value is not None and not EMAIL_RE.match(value):
            raise ValueError("email is not a valid address")
        return value.casefold() if value else value

    @field_validator("pin")
    @classmethod
    def _pin_format(cls, value: str) -> str:
        if not PIN_RE.match(value):
            raise ValueError("pin must be exactly 4 digits")
        if value in _TRIVIAL_PINS:
            raise ValueError("pin is too predictable; choose a less obvious PIN")
        return value


class LoginRequest(BaseModel):
    """`POST /api/v1/auth/login` body. `identifier` may be the username, mobile, or email."""

    identifier: str
    pin: str


class AccountPublic(BaseModel):
    """Caller-facing account view - never includes `pinHash` or lockout counters."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    username: str
    mobile: str | None = None
    email: str | None = None
    display_name: str | None = Field(alias="displayName", default=None)


class AuthResult(BaseModel):
    """`data` payload for `/register`, `/login`: the session cookie is set separately (HttpOnly)."""

    model_config = ConfigDict(populate_by_name=True)

    account: AccountPublic
    expires_in: int = Field(alias="expiresIn")
