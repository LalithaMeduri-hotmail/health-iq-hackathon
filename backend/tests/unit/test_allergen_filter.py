"""Unit tests for deterministic meal-plan allergen matching."""

from app.services.allergen_filter import allergens_in_text


def test_short_synonym_does_not_match_inside_another_food_name() -> None:
    assert allergens_in_text("Lentil soup with vegetables", ["sesame"]) == []


def test_short_synonym_matches_as_a_complete_word() -> None:
    assert allergens_in_text("Garnish with til before serving", ["sesame"]) == ["til"]


def test_common_synonym_is_detected() -> None:
    assert allergens_in_text("Groundnut chutney", ["peanut"]) == ["groundnut"]