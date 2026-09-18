"""MedicalDocument, extracted identity, and profile-match contracts.

These types back the upload -> verify -> confirm workflow. A document is held in a *pending*
state and is only permanently associated with a patient profile after the caller confirms the
match, so a misfiled document never silently joins the wrong person's history.

`models/` is a pure leaf: no imports from services, repositories, or SDK clients here.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentType:
    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    UNKNOWN = "unknown"


class UploadStatus:
    """Lifecycle of the uploaded bytes."""

    PENDING = "pending"  # in the quarantine area, not yet owned by a profile
    CONFIRMED = "confirmed"  # caller confirmed the profile association
    REJECTED = "rejected"  # mismatch that the caller declined to reassign
    EXPIRED = "expired"  # abandoned past the retention window


class ProcessingStatus:
    AWAITING_VERIFICATION = "awaiting_verification"
    VERIFIED = "verified"
    ANALYZED = "analyzed"
    FAILED = "failed"


class ProfileMatchStatus:
    """Deterministic evaluator verdict - never produced by an LLM."""

    MATCH = "MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    MISMATCH = "MISMATCH"
    INSUFFICIENT_IDENTITY_DATA = "INSUFFICIENT_IDENTITY_DATA"


class FieldEvidence(BaseModel):
    """One extracted identity field with the text it came from and how sure the extractor was."""

    model_config = ConfigDict(populate_by_name=True)

    field: str
    value: str | None = None
    raw_text: str | None = Field(alias="rawText", default=None)
    confidence: float = 0.0
    page: int | None = None


class ExtractedPatientIdentity(BaseModel):
    """Structured identity read off a medical document.

    Purely descriptive - never an authorization decision.
    """

    model_config = ConfigDict(populate_by_name=True)

    patient_name: str | None = Field(alias="patientName", default=None)
    date_of_birth: str | None = Field(alias="dateOfBirth", default=None)
    age: int | None = None
    sex: str | None = None
    document_date: str | None = Field(alias="documentDate", default=None)
    facility_name: str | None = Field(alias="facilityName", default=None)
    doctor_name: str | None = Field(alias="doctorName", default=None)
    document_type: str = Field(alias="documentType", default=DocumentType.UNKNOWN)
    extraction_confidence: float = Field(alias="extractionConfidence", default=0.0)


class IdentityEvidence(BaseModel):
    """Per-field provenance plus what the document did not contain.

    The Identity Evidence Extractor produces this; it must not decide ownership.
    """

    model_config = ConfigDict(populate_by_name=True)

    identity: ExtractedPatientIdentity
    fields: list[FieldEvidence] = Field(default_factory=list)
    missing_fields: list[str] = Field(alias="missingFields", default_factory=list)
    conflicting_fields: list[str] = Field(alias="conflictingFields", default_factory=list)


class FieldComparison(BaseModel):
    """How one identity field compared against the selected profile."""

    model_config = ConfigDict(populate_by_name=True)

    field: str
    profile_value: str | None = Field(alias="profileValue", default=None)
    document_value: str | None = Field(alias="documentValue", default=None)
    outcome: str  # "matched" | "conflicted" | "missing" | "uncertain"
    detail: str = ""


class ProfileMatchExplanation(BaseModel):
    """Result of the deterministic Profile Match Evaluator.

    `status` and `requires_user_confirmation` come from deterministic rules only. `narrative` may
    be written by an LLM to explain the evidence in plain language, but it carries no authority:
    the backend never reads it back when deciding whether to associate a document.
    """

    model_config = ConfigDict(populate_by_name=True)

    status: str
    confidence: float = 0.0
    comparisons: list[FieldComparison] = Field(default_factory=list)
    matched_fields: list[str] = Field(alias="matchedFields", default_factory=list)
    conflicting_fields: list[str] = Field(alias="conflictingFields", default_factory=list)
    missing_fields: list[str] = Field(alias="missingFields", default_factory=list)
    requires_user_confirmation: bool = Field(alias="requiresUserConfirmation", default=True)
    narrative: str = ""
    evaluator_version: str = Field(alias="evaluatorVersion", default="profile-match-1.0.0")


class MedicalDocument(BaseModel):
    """A `documents` container document.

    `profile_id` is the *proposed* profile while `upload_status` is pending; it only becomes the
    binding owner once the caller confirms.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    account_id: str = Field(alias="accountId")
    profile_id: str = Field(alias="profileId")
    document_type: str = Field(alias="documentType", default=DocumentType.UNKNOWN)
    blob_reference: str = Field(alias="blobReference")
    original_file_name: str = Field(alias="originalFileName")
    content_type: str = Field(alias="contentType", default="application/octet-stream")
    file_size: int = Field(alias="fileSize", default=0)
    checksum: str = ""
    upload_status: str = Field(alias="uploadStatus", default=UploadStatus.PENDING)
    processing_status: str = Field(
        alias="processingStatus", default=ProcessingStatus.AWAITING_VERIFICATION
    )
    document_date: str | None = Field(alias="documentDate", default=None)
    extracted_patient_identity: ExtractedPatientIdentity | None = Field(
        alias="extractedPatientIdentity", default=None
    )
    extraction_confidence: float = Field(alias="extractionConfidence", default=0.0)
    profile_match_status: str | None = Field(alias="profileMatchStatus", default=None)
    profile_match_confidence: float = Field(alias="profileMatchConfidence", default=0.0)
    expires_at: datetime | None = Field(alias="expiresAt", default=None)
    created_at: datetime = Field(alias="createdAt", default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(alias="updatedAt", default_factory=lambda: datetime.now(UTC))


class DocumentVerificationResponse(BaseModel):
    """`POST /api/v1/profiles/{profileId}/documents/{documentId}/verify` response `data`."""

    model_config = ConfigDict(populate_by_name=True)

    document_id: str = Field(alias="documentId")
    profile_id: str = Field(alias="profileId")
    profile_display_name: str = Field(alias="profileDisplayName")
    evidence: IdentityEvidence
    match: ProfileMatchExplanation
    next_actions: list[str] = Field(alias="nextActions", default_factory=list)


class DocumentConfirmRequest(BaseModel):
    """`.../confirm` body.

    `targetProfileId` lets the caller redirect a mismatched document to a different profile they
    own; ownership of that profile is re-verified server-side.
    """

    model_config = ConfigDict(populate_by_name=True)

    confirmed: bool = True
    target_profile_id: str | None = Field(alias="targetProfileId", default=None)
    acknowledgement: str | None = None
