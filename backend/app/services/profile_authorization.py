"""The single authorization gate for every patient-scoped request.

Deterministic application logic only. No LLM, agent, or model output may influence any decision
made in this module - an agent's job is to explain evidence, never to grant access.

Order of checks, deny-by-default:

1. The caller is authenticated (already proven by `deps.get_current_user`).
2. The profile exists *and* its `accountId` equals the caller's account -> otherwise `404`.
3. The profile is active (unless the caller explicitly asked for read-only access) -> `403`.
4. Consent is granted, when the operation processes medical content -> `403`.
5. Every referenced resource carries the same `accountId` *and* `profileId` -> otherwise `404`.

Steps 2 and 5 collapse "does not exist" and "is not yours" into one `404` with an identical
message. That is deliberate: a `403` here would confirm to an attacker that the identifier they
guessed belongs to somebody, which is the information an insecure-direct-object-reference probe
is looking for.

Ownership is always derived from the validated session. `accountId`, `ownerId`, and `userId`
sent by the browser are ignored everywhere.
"""

from app.errors import (
    ConsentRequiredError,
    NotFoundError,
    ProfileArchivedError,
    ProfileMismatchError,
)
from app.models.audit import AuditAction, AuditOutcome
from app.models.medical_document import MedicalDocument
from app.models.patient_profile import PatientProfile
from app.repositories import cosmos_repo
from app.services import audit

# One message for every ownership failure, so responses are indistinguishable.
_PROFILE_NOT_FOUND = "Profile not found"
_DOCUMENT_NOT_FOUND = "Document not found"


async def _deny(account_id: str, profile_id: str, reason: str, correlation_id: str) -> None:
    await audit.record(
        account_id=account_id,
        profile_id=profile_id,
        action=AuditAction.AUTHORIZATION_DENIED,
        resource_type="patientProfile",
        resource_id=profile_id,
        correlation_id=correlation_id,
        outcome=AuditOutcome.DENIED,
        detail=reason,
    )


async def authorize_profile(
    account_id: str,
    profile_id: str,
    *,
    require_active: bool = True,
    require_consent: bool = False,
    correlation_id: str = "",
) -> PatientProfile:
    """Resolve a profile the caller is allowed to use, or raise.

    `require_active=False` is for read-only views (viewing an archived person's history is
    allowed); any write or AI-processing path must leave it at the default.
    """
    if not profile_id or not profile_id.strip():
        raise NotFoundError(_PROFILE_NOT_FOUND)

    profile = await cosmos_repo.get_patient_profile(account_id, profile_id)
    if profile is None:
        await _deny(account_id, profile_id, "profile-not-owned-or-missing", correlation_id)
        raise NotFoundError(_PROFILE_NOT_FOUND)

    if require_active and not profile.is_active:
        await _deny(account_id, profile_id, "profile-archived", correlation_id)
        raise ProfileArchivedError(
            "This profile is archived and is read-only. Restore it before adding new documents "
            "or running new analysis."
        )

    if require_consent and not profile.has_consent:
        await _deny(account_id, profile_id, "consent-not-granted", correlation_id)
        raise ConsentRequiredError(
            "Consent to process medical documents for this profile has not been granted, "
            "or has been withdrawn."
        )

    return profile


async def authorize_document(
    account_id: str,
    profile: PatientProfile,
    document_id: str,
    *,
    correlation_id: str = "",
) -> MedicalDocument:
    """Resolve a document that belongs to *this* account and *this* profile, or raise `404`."""
    document = await cosmos_repo.get_document(account_id, document_id)
    if document is None or document.profile_id != profile.id:
        await audit.record(
            account_id=account_id,
            profile_id=profile.id,
            action=AuditAction.AUTHORIZATION_DENIED,
            resource_type="medicalDocument",
            resource_id=document_id,
            correlation_id=correlation_id,
            outcome=AuditOutcome.DENIED,
            detail="document-not-owned-or-missing",
        )
        raise NotFoundError(_DOCUMENT_NOT_FOUND)
    return document


def assert_same_profile(profile: PatientProfile, *owners: str | None) -> None:
    """Guard combined-resource operations (e.g. comparison) against cross-profile mixing.

    A resource stored before patient profiles existed carries no `profileId`; it belongs to the
    account owner profile, so that is the only profile it may be read under.
    """
    for owner in owners:
        resolved = owner or (profile.id if profile.is_account_owner_profile else None)
        if resolved != profile.id:
            raise ProfileMismatchError(
                "Every selected document must belong to the same patient profile."
            )
