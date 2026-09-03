"""GET /api/v1/profile, PUT /api/v1/profile/preferences (implementation-plan.md Section 5.1).

Calls `repositories/cosmos_repo.py` for the `profiles` and `reports` containers.
"""

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request

from app.agents.report_agent import health_score
from app.deps import CurrentUser, get_current_user
from app.errors import ValidationError
from app.models.common import ApiResponse, SafetyBlock
from app.models.profile import (
    LatestSummary,
    Preferences,
    PreferencesUpdate,
    Profile,
    ProfileReportItem,
    ProfileResponse,
)
from app.repositories import cosmos_repo

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])

# Preference tokens are free text typed by the user, so they are constrained structurally rather
# than against a clinical allowlist: the authoritative allergen list is the profile itself
# (docs/lld/5-low-level-design-ai-meal-planner.md assumption A4).
_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9 \-]{0,63}$")
_MAX_TOKENS = 32
_MAX_TEXT_LENGTH = 64


def _envelope(request: Request, safety: SafetyBlock, data) -> ApiResponse:
    return ApiResponse(
        request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
        generated_at=datetime.now(UTC),
        safety=safety,
        data=data,
    )


def _tokens(values: list[str], field: str) -> list[str]:
    """Normalize a token list (case-folded, trimmed, de-duplicated) or raise `validation-error`."""
    if len(values) > _MAX_TOKENS:
        raise ValidationError(
            f"{field} accepts at most {_MAX_TOKENS} entries",
            errors=[{"field": field, "issue": "too-many-entries"}],
        )

    normalized: list[str] = []
    for value in values:
        token = " ".join(value.strip().casefold().split())
        if not _TOKEN_RE.match(token):
            raise ValidationError(
                f"{field} contains an unrecognized token {value!r}",
                errors=[{"field": field, "issue": "unrecognized-token", "value": value}],
            )
        if token not in normalized:
            normalized.append(token)
    return normalized


def _text(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > _MAX_TEXT_LENGTH:
        raise ValidationError(
            f"{field} must be {_MAX_TEXT_LENGTH} characters or fewer",
            errors=[{"field": field, "issue": "too-long"}],
        )
    return trimmed


def _validated(body: PreferencesUpdate) -> Preferences:
    return Preferences(
        allergies=_tokens(body.allergies, "allergies"),
        cuisine=_text(body.cuisine, "cuisine"),
        budget=_text(body.budget, "budget"),
        goals=_tokens(body.goals, "goals"),
        location=_text(body.location, "location"),
    )


@router.get("")
async def get_profile(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[ProfileResponse]:
    """`{ profile, reports[], latestSummary }` - consent, preferences, report history (FR2.5)."""
    profile = await cosmos_repo.get_profile(current_user.user_id)
    reports = sorted(
        await cosmos_repo.list_reports(current_user.user_id),
        key=lambda report: report.report_date,
        reverse=True,
    )

    history = [
        ProfileReportItem(
            reportId=report.id,
            reportDate=report.report_date,
            healthScore=health_score(report.parameters),
        )
        for report in reports
    ]

    latest = next((item for item in history if item.report_id == profile.latest_summary_id), None)
    if latest is None and history:
        latest = history[0]

    data = ProfileResponse(
        profile=profile,
        reports=history,
        latestSummary=LatestSummary(reportId=latest.report_id, healthScore=latest.health_score)
        if latest
        else None,
    )
    return _envelope(request, SafetyBlock(pass_=True, notes=[]), data)


@router.put("/preferences")
async def update_preferences(
    request: Request,
    body: PreferencesUpdate,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[Profile]:
    """Full-resource PUT of `{ allergies[], cuisine, budget, goals[], location }` -> new profile.

    A supplied `etag` must match the stored profile; a stale one is rejected with `409 conflict`.
    """
    preferences = _validated(body)

    profile = await cosmos_repo.get_profile(current_user.user_id)
    profile.preferences = preferences
    # `location` lives on both blocks in the LLD contract: preferences drives meal planning, while
    # demographics carries it for reference-range and specialist context.
    profile.demographics.location = preferences.location or profile.demographics.location

    saved = await cosmos_repo.save_profile(profile, if_match=body.etag)
    return _envelope(request, SafetyBlock(pass_=True, notes=[]), saved)
