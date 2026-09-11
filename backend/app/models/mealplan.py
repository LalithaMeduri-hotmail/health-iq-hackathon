"""AI Meal Planner request, response, and nutrition knowledge contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.common import SourceRef

MEAL_PLAN_DISCLAIMER = (
    "General nutrition guidance only; not medical nutrition therapy. "
    "Discuss with a doctor or registered dietitian."
)


class MealPlanPreferences(BaseModel):
    """Per-request choices; cuisine and budget are intentionally not persisted on profiles."""

    model_config = ConfigDict(extra="forbid")

    allergies: list[str] = Field(default_factory=list, max_length=32)
    cuisine: str = Field(default="general", min_length=1, max_length=64)
    budget: Literal["low", "medium", "high"] = "medium"
    goals: list[str] = Field(default_factory=list, max_length=32)
    days: int = Field(default=3, ge=1, le=7)

    @field_validator("allergies", "goals")
    @classmethod
    def normalize_tokens(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            token = " ".join(value.strip().casefold().split())
            if not token or len(token) > 64:
                raise ValueError("entries must contain between 1 and 64 characters")
            if token not in normalized:
                normalized.append(token)
        return normalized

    @field_validator("cuisine")
    @classmethod
    def normalize_cuisine(cls, value: str) -> str:
        return "-".join(value.strip().casefold().split())


class MealPlanRequest(BaseModel):
    """`POST /api/v1/meal-plan/generate` request body."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    report_id: str = Field(alias="reportId", min_length=1, max_length=128)
    preferences: MealPlanPreferences = Field(default_factory=MealPlanPreferences)


class MealPlanMeal(BaseModel):
    """One grounded meal suggestion."""

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["breakfast", "lunch", "dinner", "snack"]
    items: list[str] = Field(min_length=1)
    notes: str
    source: SourceRef


class MealDay(BaseModel):
    """One day in a meal plan."""

    day: int = Field(ge=1)
    meals: list[MealPlanMeal] = Field(min_length=1)


class MealPlanRationale(BaseModel):
    """One sourced reason for the plan."""

    text: str
    source: SourceRef


class MealPlanSelection(BaseModel):
    """Effective transient choices used to generate the response."""

    cuisine: str
    budget: Literal["low", "medium", "high"]
    days: int


class MealPlan(BaseModel):
    """LLD-aligned `MealPlannerAgent` output contract."""

    model_config = ConfigDict(populate_by_name=True)

    condition_tags: list[str] = Field(alias="conditionTags", default_factory=list)
    preferences: MealPlanSelection
    days: list[MealDay] = Field(min_length=1)
    rationale: list[MealPlanRationale] = Field(default_factory=list)
    avoid_list: list[str] = Field(alias="avoidList", default_factory=list)
    disclaimer: str = MEAL_PLAN_DISCLAIMER


class NutritionRule(BaseModel):
    """One structured record in the shared nutrition knowledge base."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    condition_tags: list[str] = Field(alias="conditionTags", min_length=1)
    cuisines: list[str] = Field(min_length=1)
    budgets: list[Literal["low", "medium", "high"]] = Field(min_length=1)
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] = Field(alias="mealType")
    items: list[str] = Field(min_length=1)
    guidance: str
    avoid_list: list[str] = Field(alias="avoidList", default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    source: SourceRef