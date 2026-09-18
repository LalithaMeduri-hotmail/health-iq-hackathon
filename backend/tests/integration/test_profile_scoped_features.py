"""Profile scoping of the four analysis features.

Proves that lab reports, comparisons, and meal plans are partitioned by patient profile: one
family member's history must never be readable, comparable, or usable as AI context under
another. All data here is synthetic.
"""

import pytest

ALICE = {"X-Demo-User-Id": "acct-alice"}
BOB = {"X-Demo-User-Id": "acct-bob"}

_PDF = b"%PDF-1.4 synthetic lab report "


def _owner_profile_id(client, headers) -> str:
    return client.get("/api/v1/profiles", headers=headers).json()["data"]["activeProfileId"]


def _create_profile(client, headers, name: str) -> str:
    response = client.post(
        "/api/v1/profiles",
        headers=headers,
        json={
            "displayName": name,
            "relationshipToAccountOwner": "child",
            "consentAccepted": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _analyze_report(client, headers, profile_id: str | None, salt: bytes) -> str:
    """Analyze a lab report under `profile_id` and return the stored report id."""
    data = {"consent": "true"}
    if profile_id is not None:
        data["profileId"] = profile_id
    response = client.post(
        "/api/v1/reports/analyze",
        headers=headers,
        data=data,
        files={"file": ("report.pdf", _PDF + salt, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["reportId"]


# ------------------------------------------------------------------------------- report scoping


def test_reports_are_listed_per_profile(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    owner = _owner_profile_id(client, ALICE)
    owner_report = _analyze_report(client, ALICE, owner, b"a" * 40)
    child_report = _analyze_report(client, ALICE, child, b"b" * 40)

    owner_ids = [
        item["reportId"]
        for item in client.get(
            f"/api/v1/reports?profileId={owner}", headers=ALICE
        ).json()["data"]["reports"]
    ]
    child_ids = [
        item["reportId"]
        for item in client.get(
            f"/api/v1/reports?profileId={child}", headers=ALICE
        ).json()["data"]["reports"]
    ]

    assert owner_report in owner_ids and owner_report not in child_ids
    assert child_report in child_ids and child_report not in owner_ids


def test_report_of_another_profile_is_not_readable(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    owner = _owner_profile_id(client, ALICE)
    child_report = _analyze_report(client, ALICE, child, b"c" * 40)

    response = client.get(f"/api/v1/reports/{child_report}?profileId={owner}", headers=ALICE)

    assert response.status_code == 404
    assert response.json()["detail"] == "Report not found"


def test_report_of_another_account_is_not_readable(client) -> None:
    bob_owner = _owner_profile_id(client, BOB)
    bob_report = _analyze_report(client, BOB, bob_owner, b"d" * 40)
    alice_owner = _owner_profile_id(client, ALICE)

    response = client.get(
        f"/api/v1/reports/{bob_report}?profileId={alice_owner}", headers=ALICE
    )

    assert response.status_code == 404


def test_report_list_ignores_a_profile_id_from_another_account(client) -> None:
    bob_child = _create_profile(client, BOB, "Bob Junior")

    response = client.get(f"/api/v1/reports?profileId={bob_child}", headers=ALICE)

    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found"


# --------------------------------------------------------------------------- comparison scoping


def test_reports_from_the_same_profile_can_be_compared(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    first = _analyze_report(client, ALICE, child, b"e" * 40)
    second = _analyze_report(client, ALICE, child, b"f" * 40)

    response = client.post(
        "/api/v1/reports/compare",
        headers=ALICE,
        json={"oldReportId": first, "currentReportId": second, "profileId": child},
    )

    assert response.status_code == 200


def test_reports_from_different_profiles_cannot_be_compared(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    sibling = _create_profile(client, ALICE, "Nita Junior")
    child_report = _analyze_report(client, ALICE, child, b"g" * 40)
    sibling_report = _analyze_report(client, ALICE, sibling, b"h" * 40)

    response = client.post(
        "/api/v1/reports/compare",
        headers=ALICE,
        json={
            "oldReportId": child_report,
            "currentReportId": sibling_report,
            "profileId": child,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Report not found"


def test_comparison_rejects_another_accounts_report(client) -> None:
    bob_owner = _owner_profile_id(client, BOB)
    bob_report = _analyze_report(client, BOB, bob_owner, b"i" * 40)
    alice_child = _create_profile(client, ALICE, "Ravi Junior")
    alice_report = _analyze_report(client, ALICE, alice_child, b"j" * 40)

    response = client.post(
        "/api/v1/reports/compare",
        headers=ALICE,
        json={
            "oldReportId": bob_report,
            "currentReportId": alice_report,
            "profileId": alice_child,
        },
    )

    assert response.status_code == 404


def test_comparison_under_another_accounts_profile_is_denied(client) -> None:
    bob_child = _create_profile(client, BOB, "Bob Junior")
    alice_child = _create_profile(client, ALICE, "Ravi Junior")
    first = _analyze_report(client, ALICE, alice_child, b"k" * 40)
    second = _analyze_report(client, ALICE, alice_child, b"l" * 40)

    response = client.post(
        "/api/v1/reports/compare",
        headers=ALICE,
        json={"oldReportId": first, "currentReportId": second, "profileId": bob_child},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found"


# ---------------------------------------------------------------------------- meal-plan scoping


def test_meal_plan_uses_only_the_selected_profiles_allergies(client) -> None:
    """The profile's own allergy drives a hard exclusion, and never appears in a meal."""
    child = _create_profile(client, ALICE, "Ravi Junior")
    client.put(
        f"/api/v1/profiles/{child}",
        headers=ALICE,
        json={
            "displayName": "Ravi Junior",
            "relationshipToAccountOwner": "child",
            "allergies": ["peanut"],
        },
    )
    report = _analyze_report(client, ALICE, child, b"m" * 40)

    response = client.post(
        "/api/v1/meal-plan/generate",
        headers=ALICE,
        json={"reportId": report, "profileId": child},
    )

    assert response.status_code == 200, response.text
    plan = response.json()["data"]

    served = " ".join(
        " ".join([*meal["items"], meal.get("notes", "")])
        for day in plan["days"]
        for meal in day["meals"]
    ).casefold()
    assert "peanut" not in served

    # The allergy came from the profile, not the request body, so it must show up as an exclusion.
    assert any("peanut" in entry.casefold() for entry in plan["avoidList"])


def test_meal_plan_does_not_borrow_a_siblings_allergies(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    sibling = _create_profile(client, ALICE, "Nita Junior")
    client.put(
        f"/api/v1/profiles/{sibling}",
        headers=ALICE,
        json={
            "displayName": "Nita Junior",
            "relationshipToAccountOwner": "child",
            "allergies": ["shellfish"],
        },
    )
    report = _analyze_report(client, ALICE, child, b"s" * 40)

    plan = client.post(
        "/api/v1/meal-plan/generate",
        headers=ALICE,
        json={"reportId": report, "profileId": child},
    ).json()["data"]

    assert not any("shellfish" in entry.casefold() for entry in plan["avoidList"])


def test_meal_plan_rejects_a_report_from_another_profile(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    sibling = _create_profile(client, ALICE, "Nita Junior")
    child_report = _analyze_report(client, ALICE, child, b"n" * 40)

    response = client.post(
        "/api/v1/meal-plan/generate",
        headers=ALICE,
        json={"reportId": child_report, "profileId": sibling},
    )

    assert response.status_code == 404


def test_meal_plan_rejects_another_accounts_profile(client) -> None:
    bob_child = _create_profile(client, BOB, "Bob Junior")
    alice_child = _create_profile(client, ALICE, "Ravi Junior")
    report = _analyze_report(client, ALICE, alice_child, b"o" * 40)

    response = client.post(
        "/api/v1/meal-plan/generate",
        headers=ALICE,
        json={"reportId": report, "profileId": bob_child},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found"


def test_archived_profile_cannot_generate_a_meal_plan(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    report = _analyze_report(client, ALICE, child, b"p" * 40)
    client.post(f"/api/v1/profiles/{child}/archive", headers=ALICE)

    response = client.post(
        "/api/v1/meal-plan/generate",
        headers=ALICE,
        json={"reportId": report, "profileId": child},
    )

    assert response.status_code == 403


def test_archived_profile_cannot_analyze_a_new_report(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    client.post(f"/api/v1/profiles/{child}/archive", headers=ALICE)

    response = client.post(
        "/api/v1/reports/analyze",
        headers=ALICE,
        data={"consent": "true", "profileId": child},
        files={"file": ("report.pdf", _PDF + b"q" * 40, "application/pdf")},
    )

    assert response.status_code == 403


def test_comparison_trend_series_does_not_span_profiles(client) -> None:
    """A longer trend history must still come from one patient only."""
    child = _create_profile(client, ALICE, "Ravi Junior")
    sibling = _create_profile(client, ALICE, "Nita Junior")
    _analyze_report(client, ALICE, sibling, b"t" * 40)
    first = _analyze_report(client, ALICE, child, b"u" * 40)
    second = _analyze_report(client, ALICE, child, b"v" * 40)

    comparison = client.post(
        "/api/v1/reports/compare",
        headers=ALICE,
        json={"oldReportId": first, "currentReportId": second, "profileId": child},
    ).json()["data"]

    series_lengths = [len(series) for series in comparison["trendSeries"].values()]
    # Non-vacuous: at least one parameter really does carry this child's two data points.
    assert series_lengths and max(series_lengths) == 2
    # And none carries a third point borrowed from the sibling's history.
    assert max(series_lengths) <= 2


@pytest.mark.asyncio
async def test_run_records_carry_the_owning_profile(client) -> None:
    """Every AI execution record is tagged with the profile it ran for."""
    from app.repositories.cosmos_repo import _DEMO_RUNS_STORE

    child = _create_profile(client, ALICE, "Ravi Junior")
    _analyze_report(client, ALICE, child, b"r" * 40)

    runs = [
        run
        for run in _DEMO_RUNS_STORE.values()
        if run.get("userId") == "acct-alice" and run.get("type") == "report-analyze"
    ]

    assert runs
    assert runs[-1]["profileId"] == child
