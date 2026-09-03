"""Profile, specialist advisor, and meal planner contracts (docs/lld/3- and 5-low-level-design-*.md).

`models/` is a pure leaf: no imports from services, repositories, or SDK clients here.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import SourceRef

# Consent purposes recorded on the profile (LLD Section 2.3.2).
CONSENT_PURPOSES = ("ocr", "analysis", "pdf")
CONSENT_VERSION = "1.0"
SPECIALIST_DISCLAIMER = "Specialist category suggestion only; not a diagnosis or urgency claim."


class Demographics(BaseModel):
    """Minimized demographics: an age *band*, never a date of birth (LLD Section 2.6)."""

    model_config = ConfigDict(populate_by_name=True)

    age_band: str | None = Field(alias="ageBand", default=None)
    sex: str | None = None
    location: str | None = None


class Consent(BaseModel):
    """Recorded consent decision backing every upload (LLD Section 2.3.2)."""

    model_config = ConfigDict(populate_by_name=True)

    version: str | None = None
    accepted_at: str | None = Field(alias="acceptedAt", default=None)
    purposes: list[str] = Field(default_factory=list)


class Preferences(BaseModel):
    """User-editable profile preferences (`PUT /api/v1/profile/preferences`)."""

    model_config = ConfigDict(populate_by_name=True)

    allergies: list[str] = Field(default_factory=list)
    cuisine: str | None = None
    budget: str | None = None
    goals: list[str] = Field(default_factory=list)
    location: str | None = None


class PreferencesUpdate(BaseModel):
    """`PUT /api/v1/profile/preferences` body; a full-resource PUT, so omitted fields are cleared.

    `etag` is optional: when supplied it must match the stored profile, otherwise the write is
    rejected with `409 conflict` (LLD Section 2.3.3 optimistic concurrency).
    """

    model_config = ConfigDict(populate_by_name=True)

    allergies: list[str] = Field(default_factory=list)
    cuisine: str | None = None
    budget: str | None = None
    goals: list[str] = Field(default_factory=list)
    location: str | None = None
    etag: str | None = None


class Profile(BaseModel):
    """`GET /api/v1/profile` response `data.profile`, and the `profiles` Cosmos document."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    demographics: Demographics = Field(default_factory=Demographics)
    consent: Consent = Field(default_factory=Consent)
    preferences: Preferences = Field(default_factory=Preferences)
    latest_summary_id: str | None = Field(alias="latestSummaryId", default=None)
    etag: str | None = None


class ProfileReportItem(BaseModel):
    """One entry of the profile report-history timeline (LLD Section 2.3.2)."""

    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(alias="reportId")
    report_date: str = Field(alias="reportDate")
    health_score: float = Field(alias="healthScore")


class LatestSummary(BaseModel):
    """Pointer to the newest analyzed report (`profiles.latestSummaryId`)."""

    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(alias="reportId")
    health_score: float = Field(alias="healthScore")


class ProfileResponse(BaseModel):
    """`GET /api/v1/profile` response `data` (LLD Section 2.3.2)."""

    model_config = ConfigDict(populate_by_name=True)

    profile: Profile
    reports: list[ProfileReportItem] = Field(default_factory=list)
    latest_summary: LatestSummary | None = Field(alias="latestSummary", default=None)


class SpecialistSuggestRequest(BaseModel):
    """`POST /api/v1/specialists/suggest` body (LLD Section 2.3.4)."""

    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(alias="reportId")


class DoctorLink(BaseModel):
    """A public/demo directory link; `provenance` makes the non-endorsement explicit (LLD A4)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    url: str
    provenance: str = "public/demo"


class SpecialistCategory(BaseModel):
    """One suggested specialty category; `source` satisfies NFR2.2 and safety rule R2."""

    model_config = ConfigDict(populate_by_name=True)

    specialty_category: str = Field(alias="specialtyCategory")
    parameter_group: str = Field(alias="parameterGroup")
    when_to_consult: str = Field(alias="whenToConsult")
    confidence: float
    source: SourceRef


class SpecialistGuidance(BaseModel):
    """`SpecialistAdvisorAgent` output contract (implementation-plan.md Section 4.2)."""

    model_config = ConfigDict(populate_by_name=True)

    categories: list[SpecialistCategory] = Field(default_factory=list)
    rationale: str
    doctor_links: list[DoctorLink] = Field(alias="doctorLinks", default_factory=list)
    disclaimer: str = SPECIALIST_DISCLAIMER


class MealDay(BaseModel):
    """One day of a `MealPlan`."""

    model_config = ConfigDict(populate_by_name=True)

    day: int
    meals: dict[str, str]


class MealPlan(BaseModel):
    """`MealPlannerAgent` output contract (implementation-plan.md Section 4.2)."""

    model_config = ConfigDict(populate_by_name=True)

    days: list[MealDay]
    rationale: list[str] = Field(default_factory=list)
    avoid_list: list[str] = Field(alias="avoidList", default_factory=list)
    disclaimer: str
