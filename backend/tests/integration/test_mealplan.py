"""Contract tests for the AI Meal Planner (docs/lld/5-low-level-design-ai-meal-planner.md)."""

from typing import Any


def _generate(client, report_id: str, preferences: dict | None = None, **kwargs):
    body: dict[str, Any] = {"reportId": report_id}
    if preferences is not None:
        body["preferences"] = preferences
    return client.post("/api/v1/meal-plan/generate", json=body, **kwargs)


def _assert_grounded(data: dict) -> None:
    for day in data["days"]:
        for meal in day["meals"]:
            assert meal["source"]["sourceUrl"]
            assert meal["source"]["sourceDate"]
    for rationale in data["rationale"]:
        assert rationale["source"]["sourceUrl"]
        assert rationale["source"]["sourceDate"]


def test_generate_uses_api_defaults(client) -> None:
    response = _generate(client, "report-2026-08-22")

    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data["preferences"] == {"cuisine": "general", "budget": "medium", "days": 3}
    assert data["conditionTags"] == ["elevated-glucose", "elevated-ldl", "low-vitamin-d"]
    assert [day["day"] for day in data["days"]] == [1, 2, 3]
    assert body["safety"]["pass"] is True
    _assert_grounded(data)


def test_generate_accepts_request_preferences(client) -> None:
    response = _generate(
        client,
        "report-2026-08-22",
        {
            "allergies": ["sesame"],
            "cuisine": "south-indian-veg",
            "budget": "low",
            "goals": ["balanced-meals"],
            "days": 2,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["preferences"] == {
        "cuisine": "south-indian-veg",
        "budget": "low",
        "days": 2,
    }
    assert len(data["days"]) == 2
    assert "peanut (allergen)" in data["avoidList"]
    assert "sesame (allergen)" in data["avoidList"]


def test_generate_hard_blocks_profile_and_request_allergens(client) -> None:
    data = _generate(
        client,
        "report-2026-08-22",
        {"allergies": ["sesame"]},
    ).json()["data"]

    meal_text = " ".join(
        " ".join([*meal["items"], meal["notes"]])
        for day in data["days"]
        for meal in day["meals"]
    ).casefold()
    assert "peanut" not in meal_text
    assert "groundnut" not in meal_text
    assert "sesame" not in meal_text


def test_generate_is_deterministic(client) -> None:
    first = _generate(client, "report-2026-08-22").json()["data"]
    second = _generate(client, "report-2026-08-22").json()["data"]

    assert first == second


def test_generate_unknown_report_returns_404(client) -> None:
    response = _generate(client, "report-does-not-exist")

    assert response.status_code == 404
    assert response.json()["type"] == "https://healthiq/errors/resource-not-found"


def test_generate_is_scoped_to_calling_user(client) -> None:
    response = _generate(
        client,
        "report-2026-08-22",
        headers={"X-Demo-User-Id": "someone-else"},
    )

    assert response.status_code in {403, 404}


def test_generate_rejects_invalid_day_count(client) -> None:
    response = _generate(client, "report-2026-08-22", {"days": 8})

    assert response.status_code == 422