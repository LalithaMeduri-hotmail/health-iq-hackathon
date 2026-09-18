"""Patient-profile lifecycle: create, read, update, archive, consent, summary, history.

Ownership decisions are not made here - every entry point either receives an already-authorized
profile from `services/profile_authorization.py`, or an `account_id` taken from a validated
session. Nothing in this module reads an identifier out of a request body.
"""

import uuid
from datetime import UTC, datetime

from app.errors import ConflictError, ValidationError
from app.models.audit import AuditAction, ConsentRecord
from app.models.medical_document import DocumentType
from app.models.patient_profile import (
    MAX_PROFILES_PER_ACCOUNT,
    PROFILE_CONSENT_TYPES,
    PROFILE_CONSENT_VERSION,
    ConsentStatus,
    PatientProfile,
    PatientProfileCreate,
    PatientProfileUpdate,
    ProfileHistoryItem,
    ProfileHistoryResponse,
    ProfileStatus,
    ProfileSummary,
)
from app.repositories import cosmos_repo
from app.services import audit
from app.services.health_score import health_score


def _new_profile_id() -> str:
    return f"{cosmos_repo.PATIENT_PROFILE_ID_PREFIX}{uuid.uuid4().hex[:16]}"


async def ensure_owner_profile(account_id: str, *, correlation_id: str = "") -> PatientProfile:
    """Return the account owner's own profile, creating it on first use.

    Every account has exactly one `isAccountOwnerProfile` profile. Creating it lazily keeps an
    account that predates this feature working: its pre-profile reports resolve to this profile,
    so no historical data is stranded.
    """
    profiles = await cosmos_repo.list_patient_profiles(account_id)
    owner = next((profile for profile in profiles if profile.is_account_owner_profile), None)
    if owner is not None:
        return owner

    legacy = await cosmos_repo.get_profile(account_id)
    account = await cosmos_repo.get_account(account_id)
    display_name = (account or {}).get("displayName") or (account or {}).get("username") or "Me"

    owner = PatientProfile(
        id=_new_profile_id(),
        accountId=account_id,
        displayName=str(display_name),
        relationshipToAccountOwner="self",
        isAccountOwnerProfile=True,
        status=ProfileStatus.ACTIVE,
        # The account-level consent modal already gated the legacy upload flow, so carrying that
        # decision over avoids re-prompting a user who has been using the app since before
        # profiles existed.
        consentStatus=(
            ConsentStatus.GRANTED if legacy.consent.accepted_at else ConsentStatus.PENDING
        ),
        consentVersion=legacy.consent.version,
        allergies=list(legacy.preferences.allergies),
        healthGoals=list(legacy.preferences.goals),
        city=legacy.preferences.location or legacy.demographics.location,
        sex=legacy.demographics.sex,
    )
    saved = await cosmos_repo.save_patient_profile(owner)
    await audit.record(
        account_id=account_id,
        profile_id=saved.id,
        action=AuditAction.PROFILE_CREATED,
        resource_type="patientProfile",
        resource_id=saved.id,
        correlation_id=correlation_id,
        detail="owner-profile-autocreated",
    )
    return saved


async def list_profiles(account_id: str, *, correlation_id: str = "") -> list[PatientProfile]:
    """All profiles for the account: the owner profile first, then oldest-first."""
    await ensure_owner_profile(account_id, correlation_id=correlation_id)
    profiles = await cosmos_repo.list_patient_profiles(account_id)
    return sorted(profiles, key=lambda p: (not p.is_account_owner_profile, p.created_at))


async def create_profile(
    account_id: str, body: PatientProfileCreate, *, correlation_id: str = ""
) -> PatientProfile:
    """Create a dependent/family profile after recording an explicit consent decision."""
    if not body.consent_accepted:
        raise ValidationError(
            "Consent is required before a profile can be created",
            errors=[{"field": "consentAccepted", "issue": "required"}],
        )

    existing = await list_profiles(account_id, correlation_id=correlation_id)
    if len(existing) >= MAX_PROFILES_PER_ACCOUNT:
        raise ConflictError(
            f"An account can hold at most {MAX_PROFILES_PER_ACCOUNT} patient profiles"
        )

    relationship = body.relationship_to_account_owner
    if relationship == "self" and any(p.is_account_owner_profile for p in existing):
        # Exactly one profile may represent the account owner; anything else is a dependent.
        relationship = "other"

    if any(
        profile.display_name.casefold() == body.display_name.casefold()
        and profile.status == ProfileStatus.ACTIVE
        for profile in existing
    ):
        raise ConflictError(
            f"An active profile named {body.display_name!r} already exists for this account"
        )

    now = datetime.now(UTC)
    profile = PatientProfile(
        **body.model_dump(exclude={"consent_accepted", "relationship_assertion"}),
        id=_new_profile_id(),
        accountId=account_id,
        isAccountOwnerProfile=False,
        status=ProfileStatus.ACTIVE,
        consentStatus=ConsentStatus.GRANTED,
        consentVersion=PROFILE_CONSENT_VERSION,
        createdAt=now,
        updatedAt=now,
    )
    profile.relationship_to_account_owner = relationship
    saved = await cosmos_repo.save_patient_profile(profile)

    for consent_type in PROFILE_CONSENT_TYPES:
        await cosmos_repo.record_consent(
            ConsentRecord(
                id=f"consent-{uuid.uuid4().hex[:16]}",
                accountId=account_id,
                profileId=saved.id,
                consentType=consent_type,
                consentVersion=PROFILE_CONSENT_VERSION,
                accepted=True,
                acceptedAt=now,
                relationshipAssertion=body.relationship_assertion,
            )
        )

    await audit.record(
        account_id=account_id,
        profile_id=saved.id,
        action=AuditAction.PROFILE_CREATED,
        resource_type="patientProfile",
        resource_id=saved.id,
        correlation_id=correlation_id,
        detail=f"relationship={relationship}",
    )
    await audit.record(
        account_id=account_id,
        profile_id=saved.id,
        action=AuditAction.CONSENT_GRANTED,
        resource_type="consentRecord",
        resource_id=saved.id,
        correlation_id=correlation_id,
        detail=f"version={PROFILE_CONSENT_VERSION}",
    )
    return saved


async def update_profile(
    profile: PatientProfile, body: PatientProfileUpdate, *, correlation_id: str = ""
) -> PatientProfile:
    """Full-resource update of the editable fields.

    `id`, `accountId`, `status`, `consentStatus`, and `isAccountOwnerProfile` are never read from
    the request body, which closes the over-posting hole.
    """
    for field, value in body.model_dump(exclude={"etag"}).items():
        setattr(profile, field, value)
    if profile.is_account_owner_profile:
        profile.relationship_to_account_owner = "self"
    profile.updated_at = datetime.now(UTC)

    saved = await cosmos_repo.save_patient_profile(profile, if_match=body.etag)
    await audit.record(
        account_id=profile.account_id,
        profile_id=profile.id,
        action=AuditAction.PROFILE_UPDATED,
        resource_type="patientProfile",
        resource_id=profile.id,
        correlation_id=correlation_id,
    )
    return saved


async def archive_profile(profile: PatientProfile, *, correlation_id: str = "") -> PatientProfile:
    """Archive (never hard-delete) a profile that may hold medical records.

    The owner profile cannot be archived: it is the account's own record and the fallback owner
    for every pre-profile artifact.
    """
    if profile.is_account_owner_profile:
        raise ConflictError("The account owner's own profile cannot be archived")

    profile.status = ProfileStatus.ARCHIVED
    profile.updated_at = datetime.now(UTC)
    saved = await cosmos_repo.save_patient_profile(profile)
    await audit.record(
        account_id=profile.account_id,
        profile_id=profile.id,
        action=AuditAction.PROFILE_ARCHIVED,
        resource_type="patientProfile",
        resource_id=profile.id,
        correlation_id=correlation_id,
    )
    return saved


async def restore_profile(profile: PatientProfile, *, correlation_id: str = "") -> PatientProfile:
    profile.status = ProfileStatus.ACTIVE
    profile.updated_at = datetime.now(UTC)
    saved = await cosmos_repo.save_patient_profile(profile)
    await audit.record(
        account_id=profile.account_id,
        profile_id=profile.id,
        action=AuditAction.PROFILE_UPDATED,
        resource_type="patientProfile",
        resource_id=profile.id,
        correlation_id=correlation_id,
        detail="restored",
    )
    return saved


async def grant_consent(profile: PatientProfile, *, correlation_id: str = "") -> PatientProfile:
    profile.consent_status = ConsentStatus.GRANTED
    profile.consent_version = PROFILE_CONSENT_VERSION
    profile.updated_at = datetime.now(UTC)
    saved = await cosmos_repo.save_patient_profile(profile)
    await cosmos_repo.record_consent(
        ConsentRecord(
            id=f"consent-{uuid.uuid4().hex[:16]}",
            accountId=profile.account_id,
            profileId=profile.id,
            consentType="medical_document_processing",
            consentVersion=PROFILE_CONSENT_VERSION,
            accepted=True,
            acceptedAt=datetime.now(UTC),
        )
    )
    await audit.record(
        account_id=profile.account_id,
        profile_id=profile.id,
        action=AuditAction.CONSENT_GRANTED,
        resource_type="consentRecord",
        resource_id=profile.id,
        correlation_id=correlation_id,
    )
    return saved


async def withdraw_consent(profile: PatientProfile, *, correlation_id: str = "") -> PatientProfile:
    """Withdraw consent: stored records stay readable, but no new processing is permitted."""
    profile.consent_status = ConsentStatus.WITHDRAWN
    profile.updated_at = datetime.now(UTC)
    saved = await cosmos_repo.save_patient_profile(profile)
    await cosmos_repo.record_consent(
        ConsentRecord(
            id=f"consent-{uuid.uuid4().hex[:16]}",
            accountId=profile.account_id,
            profileId=profile.id,
            consentType="medical_document_processing",
            consentVersion=profile.consent_version or PROFILE_CONSENT_VERSION,
            accepted=False,
            withdrawnAt=datetime.now(UTC),
        )
    )
    await audit.record(
        account_id=profile.account_id,
        profile_id=profile.id,
        action=AuditAction.CONSENT_WITHDRAWN,
        resource_type="consentRecord",
        resource_id=profile.id,
        correlation_id=correlation_id,
    )
    return saved


async def summarize(profile: PatientProfile, *, owner_profile_id: str) -> ProfileSummary:
    """Counts and the latest score for one profile - never individual medical values."""
    reports = await cosmos_repo.list_reports_for_profile(
        profile.account_id, profile.id, owner_profile_id=owner_profile_id
    )
    documents = await cosmos_repo.list_documents(profile.account_id, profile.id)
    newest = max(reports, key=lambda report: report.report_date, default=None)

    return ProfileSummary(
        profileId=profile.id,
        displayName=profile.display_name,
        reportCount=len(reports),
        prescriptionCount=sum(
            1 for document in documents if document.document_type == DocumentType.PRESCRIPTION
        ),
        latestReportDate=newest.report_date if newest else None,
        latestHealthScore=health_score(newest.parameters) if newest else None,
    )


async def history(profile: PatientProfile, *, owner_profile_id: str) -> ProfileHistoryResponse:
    """Chronological timeline of the profile's artifacts, newest first."""
    reports = await cosmos_repo.list_reports_for_profile(
        profile.account_id, profile.id, owner_profile_id=owner_profile_id
    )
    documents = await cosmos_repo.list_documents(profile.account_id, profile.id)

    items = [
        ProfileHistoryItem(
            kind="report",
            resourceId=report.id,
            occurredAt=report.report_date,
            label=report.lab_name or "Lab report",
        )
        for report in reports
    ]
    items.extend(
        ProfileHistoryItem(
            kind="document",
            resourceId=document.id,
            occurredAt=(document.document_date or document.created_at.date().isoformat()),
            label=document.document_type.replace("_", " ").title(),
        )
        for document in documents
    )
    items.sort(key=lambda item: item.occurred_at, reverse=True)
    return ProfileHistoryResponse(profileId=profile.id, items=items)