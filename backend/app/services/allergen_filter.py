"""Deterministic allergen normalization, filtering, and post-assembly validation."""

import re

from app.errors import AllergenConflictError
from app.models.mealplan import MealPlan, NutritionRule

_ALLERGEN_SYNONYMS: dict[str, frozenset[str]] = {
    "peanut": frozenset({"peanut", "groundnut"}),
    "sesame": frozenset({"sesame", "til"}),
    "dairy": frozenset({"dairy", "milk", "paneer", "curd", "yogurt"}),
    "tree nut": frozenset({"tree nut", "almond", "cashew", "walnut", "pistachio"}),
}


def expanded_allergens(allergies: list[str]) -> set[str]:
    """Expand canonical allergen names and common food-name synonyms."""
    expanded: set[str] = set()
    for allergy in allergies:
        normalized = allergy.strip().casefold()
        expanded.update(_ALLERGEN_SYNONYMS.get(normalized, {normalized}))
    return expanded


def allergens_in_text(text: str, allergies: list[str]) -> list[str]:
    """Return allergen names found as complete words or phrases in normalized meal text."""
    normalized = " ".join(text.casefold().split())
    return sorted(
        allergen
        for allergen in expanded_allergens(allergies)
        if re.search(rf"(?<!\w){re.escape(allergen)}(?!\w)", normalized)
    )


def filter_rules(rules: list[NutritionRule], allergies: list[str]) -> list[NutritionRule]:
    """Remove any candidate explicitly tagged with an authoritative user allergen."""
    blocked = expanded_allergens(allergies)
    return [
        rule
        for rule in rules
        if not blocked.intersection(expanded_allergens(rule.allergens))
        and not allergens_in_text(" ".join([*rule.items, rule.guidance]), allergies)
    ]


def validate_plan(plan: MealPlan, allergies: list[str]) -> None:
    """Fail closed if any assembled meal text contains an allergen or synonym."""
    blocked = expanded_allergens(allergies)
    meal_text = " ".join(
        " ".join([*meal.items, meal.notes])
        for day in plan.days
        for meal in day.meals
    )
    leaked = allergens_in_text(meal_text, list(blocked))
    if leaked:
        raise AllergenConflictError(
            "No safe meal plan could be assembled for the supplied allergies",
            errors=[{"field": "preferences.allergies", "issue": "allergen-leakage"}],
        )