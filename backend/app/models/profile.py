"""Profile, specialist advisor, and meal planner contracts (docs/lld/3- and 5-low-level-design-*.md).

`models/` is a pure leaf: no imports from services, repositories, or SDK clients here.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import SourceRef


class Preferences(BaseModel):
    """User-editable profile preferences (`PUT /api/v1/profile/preferences`)."""

    model_config = ConfigDict(populate_by_name=True)

    allergies: list[str] = Field(default_factory=list)
    cuisine: str | None = None
    goals: list[str] = Field(default_factory=list)
    location: str | None = None


class Profile(BaseModel):
    """`GET /api/v1/profile` response `data.profile`."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    consent_version: str | None = Field(alias="consentVersion", default=None)
    consent_at: str | None = Field(alias="consentAt", default=None)
    preferences: Preferences = Field(default_factory=Preferences)


class SpecialistGuidance(BaseModel):
    """`SpecialistAdvisorAgent` output contract (implementation-plan.md Section 4.2)."""

    model_config = ConfigDict(populate_by_name=True)

    categories: list[str]
    rationale: str
    doctor_links: list[SourceRef] = Field(alias="doctorLinks", default_factory=list)
    disclaimer: str


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
