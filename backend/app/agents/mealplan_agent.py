"""Grounded `MealPlannerAgent` (implementation-plan.md Section 4.2).

The model composes the week; Python decides what is safe to put in front of it. Condition tags,
rule retrieval and allergen filtering all run first, so the LLM only ever chooses between rules
that are already sourced and allergy-safe, and it may only reference them by id. The composed
plan is re-validated against the allergy list afterwards, and any failure falls back to the
deterministic rotation - the hard allergen block never depends on the model behaving.

Tools: `search_nutrition_rules`, `get_profile_preferences`. Output: `MealPlan`.
Guardrails: hard-block allergens; no supplement dosing; no calorie prescriptions for minors.
"""

import json
import logging

from pydantic import BaseModel, ConfigDict, Field

from app.agents import llm
from app.errors import NoGroundedGuidanceError
from app.models.mealplan import (
    MealDay,
    MealPlan,
    MealPlanMeal,
    MealPlanPreferences,
    MealPlanRationale,
    MealPlanSelection,
    NutritionRule,
)
from app.models.report import StoredReport
from app.rag.nutrition import retrieve_nutrition_rules
from app.services.allergen_filter import filter_rules, validate_plan
from app.services.mealplan_signals import derive_condition_tags

logger = logging.getLogger(__name__)

_MEAL_TYPES = ("breakfast", "lunch", "dinner")


class _ComposedMeal(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    meal_type: str = Field(alias="mealType")
    rule_id: str = Field(alias="ruleId")
    note: str = ""


class _ComposedDay(BaseModel):
    day: int
    meals: list[_ComposedMeal] = Field(default_factory=list)


class _ComposedPlan(BaseModel):
    days: list[_ComposedDay] = Field(default_factory=list)


def _rules_by_meal_type(rules: list[NutritionRule]) -> dict[str, list[NutritionRule]]:
    grouped = {meal_type: [] for meal_type in _MEAL_TYPES}
    for rule in rules:
        if rule.meal_type in grouped:
            grouped[rule.meal_type].append(rule)
    missing = [meal_type for meal_type, candidates in grouped.items() if not candidates]
    if missing:
        raise NoGroundedGuidanceError(
            f"No grounded nutrition guidance is available for: {', '.join(missing)}"
        )
    return grouped


def _meal(rule: NutritionRule) -> MealPlanMeal:
    return MealPlanMeal(
        type=rule.meal_type,
        items=rule.items,
        notes=rule.guidance,
        source=rule.source,
    )


def _rotation_days(grouped: dict[str, list[NutritionRule]], days: int) -> list[MealDay]:
    """Deterministic round-robin plan; also the fallback when the composer is unavailable."""
    return [
        MealDay(
            day=day,
            meals=[
                _meal(grouped[meal_type][(day - 1) % len(grouped[meal_type])])
                for meal_type in _MEAL_TYPES
            ],
        )
        for day in range(1, days + 1)
    ]


async def _compose_days(
    grouped: dict[str, list[NutritionRule]], condition_tags: list[str], days: int
) -> list[MealDay] | None:
    """Let the model pick and narrate the rotation, choosing only from `grouped` by rule id."""
    by_id = {rule.id: rule for rule in (rule for rules in grouped.values() for rule in rules)}
    catalogue = [
        {"id": rule.id, "mealType": rule.meal_type, "items": rule.items, "guidance": rule.guidance}
        for rule in by_id.values()
    ]

    composed = await llm.structured(
        instructions=llm.prompt("mealplan_composer"),
        task=(
            f"Compose {days} day(s) for a user whose report suggests planning around: "
            f"{', '.join(condition_tags) or 'general wellbeing'}.\n\n"
            f"Available rules:\n{json.dumps(catalogue)}"
        ),
        schema=_ComposedPlan,
        name="MealComposerAgent",
    )
    if composed is None or len(composed.days) != days:
        return None

    plan_days: list[MealDay] = []
    for index, day in enumerate(sorted(composed.days, key=lambda d: d.day), start=1):
        chosen = {meal.meal_type: meal for meal in day.meals}
        meals: list[MealPlanMeal] = []
        for meal_type in _MEAL_TYPES:
            picked = chosen.get(meal_type)
            rule = by_id.get(picked.rule_id) if picked else None
            # A hallucinated id, or one borrowed from another meal type, drops the whole plan.
            if rule is None or rule.meal_type != meal_type:
                return None
            meals.append(
                MealPlanMeal(
                    type=meal_type,
                    items=rule.items,
                    notes=(picked.note or rule.guidance).strip(),
                    source=rule.source,
                )
            )
        plan_days.append(MealDay(day=index, meals=meals))
    return plan_days


async def run(payload: dict) -> MealPlan:
    """Build a sourced plan from a stored report and effective request/profile preferences."""
    report: StoredReport = payload["report"]
    preferences: MealPlanPreferences = payload["preferences"]
    allergies: list[str] = payload["allergies"]

    condition_tags = derive_condition_tags(report.parameters)
    retrieved = retrieve_nutrition_rules(
        condition_tags,
        preferences.cuisine,
        preferences.budget,
    )
    safe_rules = filter_rules(retrieved, allergies)
    grouped = _rules_by_meal_type(safe_rules)

    days = await _compose_days(grouped, condition_tags, preferences.days)
    if days is None:
        days = _rotation_days(grouped, preferences.days)

    rationales: list[MealPlanRationale] = []
    for tag in condition_tags:
        rule = next(
            (candidate for candidate in safe_rules if tag in candidate.condition_tags),
            None,
        )
        if rule is not None:
            rationales.append(MealPlanRationale(text=rule.guidance, source=rule.source))

    # Avoid-list is derived from the rules that actually made it into the plan, whoever picked them.
    chosen_items = {item for day in days for meal in day.meals for item in meal.items}
    selected_rules = [rule for rule in safe_rules if set(rule.items) & chosen_items]
    avoid_list = sorted(
        {
            *(item for rule in selected_rules for item in rule.avoid_list),
            *(f"{allergen} (allergen)" for allergen in allergies),
        }
    )
    plan = MealPlan(
        conditionTags=condition_tags,
        preferences=MealPlanSelection(
            cuisine=preferences.cuisine,
            budget=preferences.budget,
            days=preferences.days,
        ),
        days=days,
        rationale=rationales,
        avoidList=avoid_list,
    )

    try:
        validate_plan(plan, allergies)
    except Exception:
        # Fail closed: an unsafe composed plan is rebuilt from the deterministic rotation, and
        # that rotation is validated without a net - if it fails, the request must fail.
        logger.warning("composed meal plan failed allergen validation; using rotation", exc_info=True)
        plan = plan.model_copy(update={"days": _rotation_days(grouped, preferences.days)})
        validate_plan(plan, allergies)
    return plan
