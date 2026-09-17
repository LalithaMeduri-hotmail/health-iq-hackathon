"""POST /api/v1/auth/register, /login, /logout, GET /me (username|mobile|email + PIN login).

Calls `services/security.py` (PIN hashing, session tokens) and `repositories/cosmos_repo.py`
(account storage). Session is an HttpOnly cookie (never exposed to JS - see
frontend.instructions.md "never persist secrets in localStorage/sessionStorage").
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response

from app.config import get_settings
from app.deps import SESSION_COOKIE_NAME, CurrentUser, get_current_user
from app.errors import ConflictError, RateLimitedError, UnauthenticatedError, ValidationError
from app.models.account import AccountPublic, AuthResult, LoginRequest, RegisterRequest
from app.models.common import ApiResponse, SafetyBlock
from app.repositories import cosmos_repo
from app.services.security import hash_pin, issue_session_token, verify_pin

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Auth responses carry no medical/nutritional content, so the mandatory safety stage always
# passes trivially here (SafetyReviewerAgent has nothing to review on an account payload).
_SAFETY_OK = SafetyBlock(**{"pass": True}, notes=[])

# Generic message for every rejected login - never reveals whether the identifier exists or the
# PIN was wrong (user-enumeration defense, OWASP A07).
_INVALID_CREDENTIALS = "Invalid username/mobile/email or PIN"


def _envelope(request: Request, data) -> ApiResponse:
    return ApiResponse(
        request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
        generated_at=datetime.now(UTC),
        safety=_SAFETY_OK,
        data=data,
    )


def _to_public(document: dict) -> AccountPublic:
    return AccountPublic(
        userId=document["id"],
        username=document["username"],
        mobile=document.get("mobile"),
        email=document.get("email"),
        displayName=document.get("displayName"),
    )


def _set_session_cookie(response: Response, user_id: str) -> int:
    settings = get_settings()
    token, expires_in = issue_session_token(user_id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=expires_in,
        httponly=True,
        samesite="lax",
        secure=not settings.demo_mode,
        path="/",
    )
    return expires_in


@router.post("/register")
async def register(
    body: RegisterRequest, request: Request, response: Response
) -> ApiResponse[AuthResult]:
    if not body.mobile and not body.email:
        raise ValidationError(
            "At least one of mobile or email is required",
            errors=[{"field": "mobile", "issue": "required-with-email"}],
        )

    for identifier in filter(None, (body.username, body.mobile, body.email)):
        if await cosmos_repo.find_account_by_identifier(identifier) is not None:
            raise ConflictError(f"{identifier!r} is already registered")

    user_id = uuid.uuid4().hex
    document = {
        "id": user_id,
        "username": body.username,
        "usernameKey": body.username.casefold(),
        "mobile": body.mobile,
        "mobileKey": body.mobile.casefold() if body.mobile else None,
        "email": body.email,
        "emailKey": body.email.casefold() if body.email else None,
        "displayName": body.display_name,
        "pinHash": hash_pin(body.pin),
        "failedAttempts": 0,
        "lockedUntil": None,
        "createdAt": datetime.now(UTC).isoformat(),
    }
    await cosmos_repo.create_account(document)

    expires_in = _set_session_cookie(response, user_id)
    return _envelope(request, AuthResult(account=_to_public(document), expiresIn=expires_in))


@router.post("/login")
async def login(
    body: LoginRequest, request: Request, response: Response
) -> ApiResponse[AuthResult]:
    settings = get_settings()
    account = await cosmos_repo.find_account_by_identifier(body.identifier)
    if account is None:
        raise UnauthenticatedError(_INVALID_CREDENTIALS)

    locked_until = account.get("lockedUntil")
    if locked_until and datetime.fromisoformat(locked_until) > datetime.now(UTC):
        raise RateLimitedError("Too many failed attempts; account is temporarily locked")

    if not verify_pin(body.pin, account["pinHash"]):
        account["failedAttempts"] = account.get("failedAttempts", 0) + 1
        if account["failedAttempts"] >= settings.pin_max_failed_attempts:
            account["lockedUntil"] = (
                datetime.now(UTC) + timedelta(minutes=settings.pin_lockout_minutes)
            ).isoformat()
        await cosmos_repo.save_account(account)
        raise UnauthenticatedError(_INVALID_CREDENTIALS)

    account["failedAttempts"] = 0
    account["lockedUntil"] = None
    await cosmos_repo.save_account(account)

    expires_in = _set_session_cookie(response, account["id"])
    return _envelope(request, AuthResult(account=_to_public(account), expiresIn=expires_in))


@router.post("/logout")
async def logout(request: Request, response: Response) -> ApiResponse[dict]:
    # Mirrors the attributes `_set_session_cookie` wrote: a browser only overwrites a cookie whose
    # name, path, domain *and* security attributes match, so a mismatch here leaves it alive.
    settings = get_settings()
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=not settings.demo_mode,
    )
    return _envelope(request, {"loggedOut": True})


@router.get("/me")
async def me(
    request: Request, current_user: CurrentUser = Depends(get_current_user)
) -> ApiResponse[AccountPublic]:
    account = await cosmos_repo.get_account(current_user.user_id)
    if account is None:
        raise UnauthenticatedError("Sign in required")
    return _envelope(request, _to_public(account))
