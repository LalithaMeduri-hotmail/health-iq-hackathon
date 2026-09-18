"""PatientProfile contracts: the person a medical artifact belongs to.

Hierarchy: `Account` (authentication root) -> `PatientProfile` (one real person) -> every
medical artifact. The account owns *access*; the patient profile owns *medical history*. Two
profiles under the same account never share history.

`models/` is a pure leaf: no imports from services, repositories, or SDK clients here.
"""

from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Relationship of the patient to the person who owns the sign-in account. `self` is reserved for
# the single owner profile that is auto-created on first sign-in.
RELATIONSHIPS = (
    "self",
    "spouse",
    "parent",
    "child",
    "sibling",
    "grandparent",
    "dependent",
    "other",
)

# A hard ceiling keeps one account from being used as a bulk clinic record store, which is well
# outside the consent model this app collects.
MAX_PROFILES_PER_ACCOUNT = 12

PROFILE_CONSENT_VERSION = "1.0"
PROFILE_CONSENT_TYPES = ("medical_document_processing", "ai_analysis")

_MAX_NAME_LENGTH = 64
_MAX_TOKENS = 32
_MAX_TOKEN_LENGTH = 64


class ProfileStatus:
    ACTIVE = "active"
    ARCHIVED = "archived"


class ConsentStatus:
    PENDING = "pending"
    GRANTED = "granted"
    WITHDRAWN = "withdrawn"


def _clean_tokens(values: list[str]) -> list[str]:
    """Trim, case-fold, and de-duplicate a free-text token list (allergies, goals, ...)."""
    cleaned: list[str] = []
    for value in values[:_MAX_TOKENS]:
        token = " ".join(value.strip().casefold().split())
        if token and len(token) <= _MAX_TOKEN_LENGTH and token not in cleaned:
            cleaned.append(token)
    return cleaned


class PatientProfileBase(BaseModel):
    """Fields a caller may set on a patient profile.

    Only demographics that a supported workflow actually consumes are collected: `date_of_birth`
    is the second deterministic identity signal in the document-match evaluator, and `sex` feeds
    sex-specific lab reference ranges. Neither is ever used for eligibility or ranking.
    """

    model_config = ConfigDict(populate_by_name=True)

    display_name: str = Field(alias="displayName")
    relationship_to_account_owner: str = Field(alias="relationshipToAccountOwner", default="self")
    date_of_birth: date | None = Field(alias="dateOfBirth", default=None)
    sex: str | None = None
    preferred_language: str = Field(alias="preferredLanguage", default="en")
    country: str | None = None
    city: str | None = None
    dietary_preference: str | None = Field(alias="dietaryPreference", default=None)
    allergies: list[str] = Field(default_factory=list)
    food_intolerances: list[str] = Field(alias="foodIntolerances", default_factory=list)
    disliked_foods: list[str] = Field(alias="dislikedFoods", default_factory=list)
    known_conditions: list[str] = Field(alias="knownConditions", default_factory=list)
    health_goals: list[str] = Field(alias="healthGoals", default_factory=list)

    @field_validator("display_name")
    @classmethod
    def _name_format(cls, value: str) -> str:
        trimmed = " ".join(value.strip().split())
        if not trimmed:
            raise ValueError("displayName is required")
        if len(trimmed) > _MAX_NAME_LENGTH:
            raise ValueError(f"displayName must be {_MAX_NAME_LENGTH} characters or fewer")
        return trimmed

    @field_validator("relationship_to_account_owner")
    @classmethod
    def _relationship_known(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized not in RELATIONSHIPS:
            raise ValueError(f"relationshipToAccountOwner must be one of {list(RELATIONSHIPS)}")
        return normalized

    @field_validator("sex")
    @classmethod
    def _sex_known(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().casefold()
        if normalized not in {"female", "male", "other", "prefer_not_to_say", ""}:
            raise ValueError("sex must be female, male, other, or prefer_not_to_say")
        return normalized or None

    @field_validator("date_of_birth")
    @classmethod
    def _dob_plausible(cls, value: date | None) -> date | None:
        if value is None:
            return None
        today = datetime.now(UTC).date()
        if value > today:
            raise ValueError("dateOfBirth cannot be in the future")
        if value.year < today.year - 130:
            raise ValueError("dateOfBirth is not a plausible date")
        return value

    @field_validator(
        "allergies", "food_intolerances", "disliked_foods", "known_conditions", "health_goals"
    )
    @classmethod
    def _normalize_tokens(cls, value: list[str]) -> list[str]:
        return _clean_tokens(value)


class PatientProfileCreate(PatientProfileBase):
    """`POST /api/v1/profiles` body.

    `consentAccepted` must be true: no profile is created without an explicit, recorded consent
    decision, because creating one is the prerequisite for processing that person's documents.
    """

    consent_accepted: bool = Field(alias="consentAccepted", default=False)
    relationship_assertion: str | None = Field(alias="relationshipAssertion", default=None)


class PatientProfileUpdate(PatientProfileBase):
    """`PUT /api/v1/profiles/{profileId}` body - a full-resource PUT of the editable fields.

    `etag` is optional; when supplied it must match the stored profile or the write is rejected
    with `409 conflict`, matching the existing preferences-update contract.
    """

    etag: str | None = None


class PatientProfile(PatientProfileBase):
    """A `profiles` container document (`id` prefixed `pp-`), and the caller-facing profile view.

    `account_id` is always taken from the validated session, never from the request body.
    """

    id: str
    account_id: str = Field(alias="accountId")
    is_account_owner_profile: bool = Field(alias="isAccountOwnerProfile", default=False)
    status: str = ProfileStatus.ACTIVE
    consent_status: str = Field(alias="consentStatus", default=ConsentStatus.PENDING)
    consent_version: str | None = Field(alias="consentVersion", default=None)
    created_at: datetime = Field(alias="createdAt", default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(alias="updatedAt", default_factory=lambda: datetime.now(UTC))
    etag: str | None = None

    @property
    def is_active(self) -> bool:
        return self.status == ProfileStatus.ACTIVE

    @property
    def has_consent(self) -> bool:
        return self.consent_status == ConsentStatus.GRANTED


class PatientProfileListResponse(BaseModel):
    """`GET /api/v1/profiles` response `data`."""

    model_config = ConfigDict(populate_by_name=True)

    profiles: list[PatientProfile] = Field(default_factory=list)
    active_profile_id: str | None = Field(alias="activeProfileId", default=None)


class ProfileSummary(BaseModel):
    """`GET /api/v1/profiles/{profileId}/summary` - counts only, never medical values."""

    model_config = ConfigDict(populate_by_name=True)

    profile_id: str = Field(alias="profileId")
    display_name: str = Field(alias="displayName")
    report_count: int = Field(alias="reportCount", default=0)
    prescription_count: int = Field(alias="prescriptionCount", default=0)
    latest_report_date: str | None = Field(alias="latestReportDate", default=None)
    latest_health_score: float | None = Field(alias="latestHealthScore", default=None)


class ProfileHistoryItem(BaseModel):
    """One entry on a profile's medical timeline."""

    model_config = ConfigDict(populate_by_name=True)

    kind: str
    resource_id: str = Field(alias="resourceId")
    occurred_at: str = Field(alias="occurredAt")
    label: str


class ProfileHistoryResponse(BaseModel):
    """`GET /api/v1/profiles/{profileId}/history` response `data`."""

    model_config = ConfigDict(populate_by_name=True)

    profile_id: str = Field(alias="profileId")
    items: list[ProfileHistoryItem] = Field(default_factory=list)


class PrescriptionAssignment(BaseModel):
    """Assign one analyzed prescription run to a patient profile owned by this account."""

    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    profile_id: str = Field(alias="profileId")
