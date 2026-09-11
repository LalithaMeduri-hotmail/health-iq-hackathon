"""Nutrition retrieval boundary: local structured search now, Azure AI Search later."""

import json
from functools import lru_cache
from pathlib import Path

from app.models.mealplan import NutritionRule

_RULES_PATH = Path(__file__).resolve().parents[3] / "data" / "nutrition" / "nutrition_rules.json"


@lru_cache
def load_rules() -> list[NutritionRule]:
    """Load and validate the shared, curated nutrition knowledge base once."""
    raw = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return [NutritionRule.model_validate(document) for document in raw["rules"]]


def retrieve_nutrition_rules(
    condition_tags: list[str], cuisine: str, budget: str
) -> list[NutritionRule]:
    """Rank grounded rules by condition, requested cuisine, and budget."""
    matches: list[tuple[int, NutritionRule]] = []
    for rule in load_rules():
        if not set(condition_tags).intersection(rule.condition_tags):
            continue
        if budget not in rule.budgets:
            continue
        if cuisine not in rule.cuisines and "general" not in rule.cuisines:
            continue
        score = 2 if cuisine in rule.cuisines else 1
        matches.append((score, rule))
    return [rule for _, rule in sorted(matches, key=lambda item: (-item[0], item[1].id))]