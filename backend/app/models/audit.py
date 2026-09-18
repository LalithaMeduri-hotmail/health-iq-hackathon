"""Consent and audit contracts.

Audit events record *that* something happened to *which* resource - never what the document
said. No raw prescription text, lab values, file content, or tokens may be placed on these
models (docs/lld/8-low-level-design-cross-cutting-platform.md).

`models/` is a pure leaf: no imports from services, repositories, or SDK clients here.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditAction:
    PROFILE_CREATED = "profile.created"
    PROFILE_UPDATED = "profile.updated"
    PROFILE_ARCHIVED = "profile.archived"
    PROFILE_SWITCHED = "profile.switched"
    CONSENT_GRANTED = "consent.granted"
    CONSENT_WITHDRAWN = "consent.withdrawn"
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_VERIFIED = "document.verified"
    DOCUMENT_CONFIRMED = "document.confirmed"
    DOCUMENT_REASSIGNED = "document.reassigned"
    DOCUMENT_REJECTED = "document.rejected"
    DOCUMENT_DELETED = "document.deleted"
    DOCUMENT_EXPIRED = "document.expired"
    ANALYSIS_RUN = "analysis.run"
    AUTHORIZATION_DENIED = "authorization.denied"


class AuditOutcome:
    SUCCESS = "success"
    DENIED = "denied"
    FAILED = "failed"


class AuditEvent(BaseModel):
    """One `audit` container document. Structural facts only - never medical content."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    account_id: str = Field(alias="accountId")
    profile_id: str | None = Field(alias="profileId", default=None)
    action: str
    resource_type: str = Field(alias="resourceType", default="")
    resource_id: str | None = Field(alias="resourceId", default=None)
    correlation_id: str = Field(alias="correlationId", default="")
    outcome: str = AuditOutcome.SUCCESS
    # Bounded, non-PHI structural detail (e.g. a match status or a denial reason code).
    detail: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConsentRecord(BaseModel):
    """An immutable consent decision for one profile and purpose."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    account_id: str = Field(alias="accountId")
    profile_id: str = Field(alias="profileId")
    consent_type: str = Field(alias="consentType")
    consent_version: str = Field(alias="consentVersion")
    accepted: bool = False
    accepted_at: datetime | None = Field(alias="acceptedAt", default=None)
    withdrawn_at: datetime | None = Field(alias="withdrawnAt", default=None)
    # Free-text assertion that the account owner is authorized to act for this person.
    relationship_assertion: str | None = Field(alias="relationshipAssertion", default=None)
    created_at: datetime = Field(alias="createdAt", default_factory=lambda: datetime.now(UTC))
