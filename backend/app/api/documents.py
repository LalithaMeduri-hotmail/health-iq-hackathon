"""Document upload, identity verification, and profile confirmation.

Endpoints are nested under the owning profile (`/api/v1/profiles/{profileId}/documents/...`) so
the profile is authorized before the document is ever looked up. An upload is parked in a
quarantine area and only becomes part of a patient's history once the caller confirms the
association - which is why `POST /documents` never triggers analysis on its own.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.agents import identity_agent
from app.config import get_settings
from app.deps import CurrentUser, get_current_user
from app.errors import (
    ConfirmationRequiredError,
    InvalidStateTransitionError,
    ProfileMismatchError,
    ValidationError,
)
from app.models.audit import AuditAction, AuditOutcome
from app.models.common import ApiResponse, SafetyBlock
from app.models.medical_document import (
    DocumentConfirmRequest,
    DocumentVerificationResponse,
    MedicalDocument,
    ProcessingStatus,
    ProfileMatchStatus,
    UploadStatus,
)
from app.models.patient_profile import PROFILE_CONSENT_VERSION
from app.repositories import cosmos_repo
from app.services import audit, blob, identity_extract, identity_match
from app.services.ocr import extract as ocr_extract
from app.services.profile_authorization import authorize_document, authorize_profile

router = APIRouter(prefix="/api/v1/profiles/{profile_id}/documents", tags=["documents"])


def _envelope(request: Request, data) -> ApiResponse:
    return ApiResponse(
        request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
        generated_at=datetime.now(UTC),
        safety=SafetyBlock(pass_=True, notes=[]),
        data=data,
    )


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


@router.post("", status_code=201)
async def upload_document(
    request: Request,
    profile_id: str,
    consent: bool = Form(...),
    file: UploadFile = File(...),  # noqa: B008 - FastAPI multipart marker, the router convention
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[MedicalDocument]:
    """Park an upload against a profile as *pending*.

    Nothing is analyzed here and the document is not yet part of the profile's history - the
    caller must run `/verify` and then `/confirm`.
    """
    if not consent:
        raise ValidationError("consent must be true before any upload is processed")

    correlation_id = _correlation_id(request)
    profile = await authorize_profile(
        current_user.user_id, profile_id, require_consent=True, correlation_id=correlation_id
    )

    content = await file.read()
    digest = blob.checksum(content)

    existing = await cosmos_repo.list_documents(current_user.user_id, profile.id)
    duplicate = next(
        (
            document
            for document in existing
            if document.checksum == digest and document.upload_status != UploadStatus.REJECTED
        ),
        None,
    )
    if duplicate is not None:
        raise ValidationError(
            "This document has already been uploaded to this profile",
            errors=[{"field": "file", "issue": "duplicate-checksum"}],
        )

    document_id = f"doc-{uuid.uuid4().hex[:16]}"
    blob_path = await blob.upload_pending(
        current_user.user_id,
        document_id,
        file.filename or "upload.pdf",
        content,
        consent_version=PROFILE_CONSENT_VERSION,
    )

    document = MedicalDocument(
        id=document_id,
        accountId=current_user.user_id,
        profileId=profile.id,
        blobReference=blob_path,
        originalFileName=file.filename or "upload.pdf",
        contentType=file.content_type or "application/octet-stream",
        fileSize=len(content),
        checksum=digest,
        uploadStatus=UploadStatus.PENDING,
        processingStatus=ProcessingStatus.AWAITING_VERIFICATION,
        expiresAt=datetime.now(UTC)
        + timedelta(hours=get_settings().pending_upload_retention_hours),
    )
    saved = await cosmos_repo.save_document(document)

    await audit.record(
        account_id=current_user.user_id,
        profile_id=profile.id,
        action=AuditAction.DOCUMENT_UPLOADED,
        resource_type="medicalDocument",
        resource_id=document_id,
        correlation_id=correlation_id,
        detail=f"bytes={len(content)}",
    )
    return _envelope(request, saved)


@router.post("/{document_id}/verify")
async def verify_document(
    request: Request,
    profile_id: str,
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[DocumentVerificationResponse]:
    """Extract the document's identity and compare it to the selected profile.

    The verdict comes from `services/identity_match.py` (plain Python). An agent is then asked
    for a plain-language narrative, but only after the verdict is fixed, and its text is never
    read back into the decision.
    """
    correlation_id = _correlation_id(request)
    profile = await authorize_profile(
        current_user.user_id, profile_id, require_consent=True, correlation_id=correlation_id
    )
    document = await authorize_document(
        current_user.user_id, profile, document_id, correlation_id=correlation_id
    )
    if document.upload_status != UploadStatus.PENDING:
        raise InvalidStateTransitionError("This document has already been confirmed or rejected")

    content = await blob.read(document.blob_reference)
    envelope = await ocr_extract(content, mode="layout")
    evidence = identity_extract.extract(envelope)
    match = identity_match.evaluate(profile, evidence.identity)
    match.narrative = await identity_agent.explain(profile, evidence, match)

    document.extracted_patient_identity = evidence.identity
    document.extraction_confidence = evidence.identity.extraction_confidence
    document.document_type = evidence.identity.document_type
    document.document_date = evidence.identity.document_date
    document.profile_match_status = match.status
    document.profile_match_confidence = match.confidence
    document.updated_at = datetime.now(UTC)
    await cosmos_repo.save_document(document)

    await audit.record(
        account_id=current_user.user_id,
        profile_id=profile.id,
        action=AuditAction.DOCUMENT_VERIFIED,
        resource_type="medicalDocument",
        resource_id=document_id,
        correlation_id=correlation_id,
        detail=f"match={match.status}",
    )

    data = DocumentVerificationResponse(
        documentId=document.id,
        profileId=profile.id,
        profileDisplayName=profile.display_name,
        evidence=evidence,
        match=match,
        nextActions=identity_match.next_actions(match.status),
    )
    return _envelope(request, data)


@router.post("/{document_id}/confirm")
async def confirm_document(
    request: Request,
    profile_id: str,
    document_id: str,
    body: DocumentConfirmRequest,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[MedicalDocument]:
    """Bind a verified document to a profile, or reject it.

    `targetProfileId` redirects the document to another profile the account owns; that profile is
    authorized from scratch rather than trusted from the body.
    """
    correlation_id = _correlation_id(request)
    profile = await authorize_profile(
        current_user.user_id, profile_id, require_consent=True, correlation_id=correlation_id
    )
    document = await authorize_document(
        current_user.user_id, profile, document_id, correlation_id=correlation_id
    )
    if document.upload_status != UploadStatus.PENDING:
        raise InvalidStateTransitionError("This document has already been confirmed or rejected")
    if document.profile_match_status is None:
        raise InvalidStateTransitionError("Verify this document before confirming it")

    if not body.confirmed:
        return _envelope(request, await _reject(document, profile.id, correlation_id))

    target = profile
    if body.target_profile_id and body.target_profile_id != profile.id:
        target = await authorize_profile(
            current_user.user_id,
            body.target_profile_id,
            require_consent=True,
            correlation_id=correlation_id,
        )

    # A document whose identity positively contradicts the selected profile can never be forced
    # onto it; the caller must pick or create the right profile instead.
    if document.profile_match_status == ProfileMatchStatus.MISMATCH and target.id == profile.id:
        await audit.record(
            account_id=current_user.user_id,
            profile_id=profile.id,
            action=AuditAction.DOCUMENT_CONFIRMED,
            resource_type="medicalDocument",
            resource_id=document_id,
            correlation_id=correlation_id,
            outcome=AuditOutcome.DENIED,
            detail="mismatch-confirm-refused",
        )
        raise ProfileMismatchError(
            "The identity on this document does not match this profile. Choose the correct "
            "profile or create a new one."
        )

    if (
        document.profile_match_status == ProfileMatchStatus.INSUFFICIENT_IDENTITY_DATA
        and not (body.acknowledgement or "").strip()
    ):
        raise ConfirmationRequiredError(
            "This document does not carry enough identity information. Confirm explicitly that "
            "it belongs to this person before it is processed."
        )

    reassigned = target.id != document.profile_id
    document.blob_reference = await blob.promote_pending(
        document.blob_reference, current_user.user_id, target.id
    )
    document.profile_id = target.id
    document.upload_status = UploadStatus.CONFIRMED
    document.processing_status = ProcessingStatus.VERIFIED
    document.expires_at = None
    document.updated_at = datetime.now(UTC)
    saved = await cosmos_repo.save_document(document)

    await audit.record(
        account_id=current_user.user_id,
        profile_id=target.id,
        action=(
            AuditAction.DOCUMENT_REASSIGNED if reassigned else AuditAction.DOCUMENT_CONFIRMED
        ),
        resource_type="medicalDocument",
        resource_id=document_id,
        correlation_id=correlation_id,
        detail=f"match={document.profile_match_status}"
        + (";acknowledged" if body.acknowledgement else ""),
    )
    return _envelope(request, saved)


async def _reject(
    document: MedicalDocument, profile_id: str, correlation_id: str
) -> MedicalDocument:
    """Discard a pending upload the caller declined to associate."""
    await blob.delete(document.blob_reference)
    document.upload_status = UploadStatus.REJECTED
    document.processing_status = ProcessingStatus.FAILED
    document.updated_at = datetime.now(UTC)
    saved = await cosmos_repo.save_document(document)
    await audit.record(
        account_id=document.account_id,
        profile_id=profile_id,
        action=AuditAction.DOCUMENT_REJECTED,
        resource_type="medicalDocument",
        resource_id=document.id,
        correlation_id=correlation_id,
    )
    return saved


@router.get("")
async def list_documents(
    request: Request,
    profile_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[list[MedicalDocument]]:
    correlation_id = _correlation_id(request)
    profile = await authorize_profile(
        current_user.user_id,
        profile_id,
        require_active=False,
        correlation_id=correlation_id,
    )
    documents = await cosmos_repo.list_documents(current_user.user_id, profile.id)
    return _envelope(request, [_expire_if_due(document) for document in documents])


@router.get("/{document_id}")
async def get_document(
    request: Request,
    profile_id: str,
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[MedicalDocument]:
    correlation_id = _correlation_id(request)
    profile = await authorize_profile(
        current_user.user_id,
        profile_id,
        require_active=False,
        correlation_id=correlation_id,
    )
    document = await authorize_document(
        current_user.user_id, profile, document_id, correlation_id=correlation_id
    )
    return _envelope(request, _expire_if_due(document))


@router.delete("/{document_id}")
async def delete_document(
    request: Request,
    profile_id: str,
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ApiResponse[dict]:
    correlation_id = _correlation_id(request)
    profile = await authorize_profile(
        current_user.user_id, profile_id, correlation_id=correlation_id
    )
    document = await authorize_document(
        current_user.user_id, profile, document_id, correlation_id=correlation_id
    )
    await blob.delete(document.blob_reference)
    await cosmos_repo.delete_document(current_user.user_id, document.id)
    await audit.record(
        account_id=current_user.user_id,
        profile_id=profile.id,
        action=AuditAction.DOCUMENT_DELETED,
        resource_type="medicalDocument",
        resource_id=document_id,
        correlation_id=correlation_id,
    )
    return _envelope(request, {"deleted": True})


def _expire_if_due(document: MedicalDocument) -> MedicalDocument:
    """Present an abandoned pending upload as expired.

    The status is derived on read rather than by a background job so the retention rule holds
    even without a scheduler; the sweeper then only has to delete bytes.
    """
    if (
        document.upload_status == UploadStatus.PENDING
        and document.expires_at is not None
        and document.expires_at < datetime.now(UTC)
    ):
        document.upload_status = UploadStatus.EXPIRED
    return document
