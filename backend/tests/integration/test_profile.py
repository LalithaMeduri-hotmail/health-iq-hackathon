"""Contract tests for the Health Profile endpoints (docs/lld/3-low-level-design-*.md Section 2.3).

Runs against the recorded demo report history (`DEMO_MODE=true`), so no live Azure is needed.
"""

import pytest

_UPLOAD = b"%PDF-1.4 lab report " + b"0" * 40


@pytest.fixture(autouse=True)
def _isolated_profile_store():
    """Each test starts from an empty `profiles` container so etag assertions stay deterministic."""
    from app.repositories.cosmos_repo import _DEMO_PROFILES

    _DEMO_PROFILES.clear()
    yield
    _DEMO_PROFILES.clear()


def _put(client, **body):
    return client.put("/api/v1/profile/preferences", json=body)


def test_get_profile_returns_an_empty_profile_for_a_first_time_caller(client) -> None:
    response = client.get("/api/v1/profile")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["profile"]["userId"] == "demo-user"
    assert data["profile"]["preferences"]["allergies"] == []
    assert data["profile"]["consent"]["version"] is None


def test_get_profile_returns_report_history_newest_first_with_scores(client) -> None:
    data = client.get("/api/v1/profile").json()["data"]

    reports = data["reports"]
    assert len(reports) >= 2
    assert reports[0]["reportDate"] > reports[-1]["reportDate"]
    assert all(0 <= report["healthScore"] <= 100 for report in reports)
    assert data["latestSummary"]["reportId"] == reports[0]["reportId"]


def test_update_preferences_persists_and_normalizes_tokens(client) -> None:
    response = _put(
        client,
        allergies=["  Peanut ", "shellfish", "PEANUT"],
        cuisine="south-indian-veg",
        goals=["reduce-hba1c"],
        location="Bengaluru",
        budget="low",
    )

    assert response.status_code == 200
    preferences = response.json()["data"]["preferences"]
    assert preferences["allergies"] == ["peanut", "shellfish"]
    assert preferences["cuisine"] == "south-indian-veg"
    assert preferences["budget"] == "low"

    stored = client.get("/api/v1/profile").json()["data"]["profile"]
    assert stored["preferences"]["allergies"] == ["peanut", "shellfish"]
    assert stored["demographics"]["location"] == "Bengaluru"


def test_update_preferences_is_idempotent(client) -> None:
    body = {"allergies": ["peanut"], "cuisine": "south-indian-veg", "goals": [], "location": None}

    first = _put(client, **body).json()["data"]
    second = _put(client, **body).json()["data"]

    assert first["preferences"] == second["preferences"]
    assert first["etag"] == second["etag"]


def test_update_preferences_rejects_a_malformed_allergen_token(client) -> None:
    response = _put(client, allergies=["peanut", "<script>alert(1)</script>"])

    assert response.status_code == 400
    problem = response.json()
    assert problem["type"] == "https://healthiq/errors/validation-error"
    assert problem["errors"][0]["field"] == "allergies"


def test_update_preferences_rejects_an_empty_allergen_token(client) -> None:
    assert _put(client, allergies=["   "]).status_code == 400


def test_update_preferences_rejects_a_stale_etag(client) -> None:
    """LLD Section 2.3.3: optimistic concurrency via `etag` -> `409 conflict`."""
    _put(client, allergies=["peanut"])

    response = _put(client, allergies=["shellfish"], etag="not-the-current-etag")

    assert response.status_code == 409
    assert response.json()["type"] == "https://healthiq/errors/conflict"


def test_update_preferences_accepts_the_current_etag(client) -> None:
    current = _put(client, allergies=["peanut"]).json()["data"]["etag"]

    response = _put(client, allergies=["shellfish"], etag=current)

    assert response.status_code == 200
    assert response.json()["data"]["preferences"]["allergies"] == ["shellfish"]


def test_analyzing_a_report_records_consent_and_the_latest_summary(client) -> None:
    analyzed = client.post(
        "/api/v1/reports/analyze",
        data={"consent": "true"},
        files={"file": ("report.pdf", _UPLOAD, "application/pdf")},
    ).json()["data"]

    data = client.get("/api/v1/profile").json()["data"]

    assert data["profile"]["consent"]["version"] == "1.0"
    assert data["profile"]["consent"]["purposes"] == ["ocr", "analysis", "pdf"]
    assert data["profile"]["consent"]["acceptedAt"]
    assert data["profile"]["latestSummaryId"] == analyzed["reportId"]
    assert data["latestSummary"]["reportId"] == analyzed["reportId"]
    assert data["latestSummary"]["healthScore"] == analyzed["healthScore"]


def test_profile_is_scoped_to_the_calling_user(client) -> None:
    _put(client, allergies=["peanut"])

    other = client.get("/api/v1/profile", headers={"X-Demo-User-Id": "someone-else"})

    assert other.json()["data"]["profile"]["userId"] == "someone-else"
    assert other.json()["data"]["profile"]["preferences"]["allergies"] == []
