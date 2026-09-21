"""Patient profiles owned by the authenticated account (`/api/v1/profiles`).

Every handler resolves the profile through `services/profile_authorization.py` before doing
anything else. `profileId` is the only identifier accepted from the caller: the account is always
taken from the validated session, so a forged `accountId` in a body has no effect.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response

from app.deps import CurrentUser, get_current_user
from app.errors import NotFoundError
from app.models.audit import AuditAction
from app.models.common import ApiResponse, SafetyBlock
from app.models.patient_profile import (
    PatientProfile,
    PatientProfileCreate,
    PatientProfileListResponse,
    PatientProfileUpdate,
    ProfileHistoryResponse,
    ProfileSummary,
)
from app.models.review import IssuedPrescription, IssuedPrescriptionListResponse
from app.repositories import cosmos_repo
from app.services import audit, doctor_pdf, patient_profiles
from app.services.profile_authorization import authorize_profile

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


def _envelope(request: Request, data) -> ApiResponse:
    return ApiResponse(
        request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
        generated_at=datetime.now(UTC),
        safety=SafetyBlock(pass_=True, notes=[]),
        data=data,
    )


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


@router.get("")
async def list_profiles(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[PatientProfileListResponse]:
    """Every profile this account may act for; the owner profile is created on first call."""
    profiles = await patient_profiles.list_profiles(
        current_user.user_id, correlation_id=_correlation_id(request)
    )
    active = next((profile for profile in profiles if profile.is_account_owner_profile), None)
    data = PatientProfileListResponse(
        profiles=profiles, activeProfileId=active.id if active else None
    )
    return _envelope(request, data)


@router.post("", status_code=201)
async def create_profile(
    request: Request,
    body: PatientProfileCreate,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[PatientProfile]:
    """Create a profile for a family member or dependent, recording consent at the same time."""
    created = await patient_profiles.create_profile(
        current_user.user_id, body, correlation_id=_correlation_id(request)
    )
    return _envelope(request, created)


@router.get("/{profile_id}")
async def get_profile(
    request: Request,
    profile_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[PatientProfile]:
    """Read one profile. An archived profile is still readable, so history stays accessible."""
    profile = await authorize_profile(
        current_user.user_id,
        profile_id,
        require_active=False,
        correlation_id=_correlation_id(request),
    )
    return _envelope(request, profile)


@router.put("/{profile_id}")
async def update_profile(
    request: Request,
    profile_id: str,
    body: PatientProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[PatientProfile]:
    """Full-resource update of the editable fields; archived profiles are read-only."""
    profile = await authorize_profile(
        current_user.user_id, profile_id, correlation_id=_correlation_id(request)
    )
    saved = await patient_profiles.update_profile(
        profile, body, correlation_id=_correlation_id(request)
    )
    return _envelope(request, saved)


@router.post("/{profile_id}/archive")
async def archive_profile(
    request: Request,
    profile_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[PatientProfile]:
    """Archive a profile: its records stay readable, but it accepts no new uploads or analysis."""
    profile = await authorize_profile(
        current_user.user_id, profile_id, correlation_id=_correlation_id(request)
    )
    saved = await patient_profiles.archive_profile(
        profile, correlation_id=_correlation_id(request)
    )
    return _envelope(request, saved)


@router.post("/{profile_id}/restore")
async def restore_profile(
    request: Request,
    profile_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[PatientProfile]:
    profile = await authorize_profile(
        current_user.user_id,
        profile_id,
        require_active=False,
        correlation_id=_correlation_id(request),
    )
    saved = await patient_profiles.restore_profile(
        profile, correlation_id=_correlation_id(request)
    )
    return _envelope(request, saved)


@router.post("/{profile_id}/consent/withdraw")
async def withdraw_consent(
    request: Request,
    profile_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[PatientProfile]:
    profile = await authorize_profile(
        current_user.user_id,
        profile_id,
        require_active=False,
        correlation_id=_correlation_id(request),
    )
    saved = await patient_profiles.withdraw_consent(
        profile, correlation_id=_correlation_id(request)
    )
    return _envelope(request, saved)


@router.post("/{profile_id}/consent/grant")
async def grant_consent(
    request: Request,
    profile_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[PatientProfile]:
    profile = await authorize_profile(
        current_user.user_id, profile_id, correlation_id=_correlation_id(request)
    )
    saved = await patient_profiles.grant_consent(
        profile, correlation_id=_correlation_id(request)
    )
    return _envelope(request, saved)


@router.get("/{profile_id}/summary")
async def profile_summary(
    request: Request,
    profile_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[ProfileSummary]:
    """Artifact counts and the newest health score - no individual medical values."""
    owner = await patient_profiles.ensure_owner_profile(current_user.user_id)
    profile = await authorize_profile(
        current_user.user_id,
        profile_id,
        require_active=False,
        correlation_id=_correlation_id(request),
    )
    summary = await patient_profiles.summarize(profile, owner_profile_id=owner.id)
    return _envelope(request, summary)


@router.get("/{profile_id}/history")
async def profile_history(
    request: Request,
    profile_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[ProfileHistoryResponse]:
    """This profile's medical timeline, newest first."""
    owner = await patient_profiles.ensure_owner_profile(current_user.user_id)
    profile = await authorize_profile(
        current_user.user_id,
        profile_id,
        require_active=False,
        correlation_id=_correlation_id(request),
    )
    timeline = await patient_profiles.history(profile, owner_profile_id=owner.id)
    return _envelope(request, timeline)


@router.get("/{profile_id}/prescriptions")
async def list_issued_prescriptions(
    request: Request,
    profile_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[IssuedPrescriptionListResponse]:
    """Health IQ prescriptions issued for this profile after a clinician decided, newest first."""
    profile = await authorize_profile(
        current_user.user_id,
        profile_id,
        require_active=False,
        correlation_id=_correlation_id(request),
    )
    issued = await cosmos_repo.list_prescriptions(current_user.user_id, profile.id)
    return _envelope(
        request, IssuedPrescriptionListResponse(profileId=profile.id, prescriptions=issued)
    )


@router.get("/{profile_id}/prescriptions/{prescription_id}")
async def get_issued_prescription(
    request: Request,
    profile_id: str,
    prescription_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[IssuedPrescription]:
    """One issued prescription exactly as approved: medicines, alternatives, verdicts, prices."""
    profile = await authorize_profile(
        current_user.user_id,
        profile_id,
        require_active=False,
        correlation_id=_correlation_id(request),
    )
    issued = await cosmos_repo.get_prescription(current_user.user_id, profile.id, prescription_id)
    if issued is None:
        raise NotFoundError("No such prescription for this profile")
    return _envelope(request, issued)


@router.get("/{profile_id}/prescriptions/{prescription_id}/document")
async def get_issued_prescription_pdf(
    request: Request,
    profile_id: str,
    prescription_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> Response:
    """Re-render the stored prescription. Replayed from the snapshot, never recomputed."""
    profile = await authorize_profile(
        current_user.user_id,
        profile_id,
        require_active=False,
        correlation_id=_correlation_id(request),
    )
    issued = await cosmos_repo.get_prescription(current_user.user_id, profile.id, prescription_id)
    if issued is None:
        raise NotFoundError("No such prescription for this profile")

    filename, content = doctor_pdf.render_document(issued.document, issued.issued_at[:10])
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{profile_id}/activate")
async def activate_profile(
    request: Request,
    profile_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[PatientProfile]:
    """Record a profile switch.

    The active profile lives in client state; this endpoint exists so the switch is auditable and
    so the client cannot "activate" a profile the account does not own.
    """
    profile = await authorize_profile(
        current_user.user_id,
        profile_id,
        require_active=False,
        correlation_id=_correlation_id(request),
    )
    await audit.record(
        account_id=current_user.user_id,
        profile_id=profile.id,
        action=AuditAction.PROFILE_SWITCHED,
        resource_type="patientProfile",
        resource_id=profile.id,
        correlation_id=_correlation_id(request),
    )
    return _envelope(request, profile)