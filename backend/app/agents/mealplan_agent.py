"""Deterministic, grounded `MealPlannerAgent` (implementation-plan.md Section 4.2).

Tools: `search_nutrition_rules`, `get_profile_preferences`. Output: `MealPlan`.
Guardrails: hard-block allergens; no supplement dosing; no calorie prescriptions for minors.
"""

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

_MEAL_TYPES = ("breakfast", "lunch", "dinner")


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

    days = [
        MealDay(
            day=day,
            meals=[
                _meal(grouped[meal_type][(day - 1) % len(grouped[meal_type])])
                for meal_type in _MEAL_TYPES
            ],
        )
        for day in range(1, preferences.days + 1)
    ]

    rationales: list[MealPlanRationale] = []
    for tag in condition_tags:
        rule = next(
            (candidate for candidate in safe_rules if tag in candidate.condition_tags),
            None,
        )
        if rule is not None:
            rationales.append(MealPlanRationale(text=rule.guidance, source=rule.source))

    selected_rules = [
        grouped[meal_type][(day - 1) % len(grouped[meal_type])]
        for day in range(1, preferences.days + 1)
        for meal_type in _MEAL_TYPES
    ]
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
    validate_plan(plan, allergies)
    return plan
