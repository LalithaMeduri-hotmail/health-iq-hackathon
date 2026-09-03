"""Contract tests for the Specialist Advisor (docs/lld/3-low-level-design-*.md Section 2.3.4).

Runs against the recorded demo report history (`DEMO_MODE=true`), so no live Azure is needed.
"""


def _suggest(client, report_id: str, **kwargs):
    return client.post("/api/v1/specialists/suggest", json={"reportId": report_id}, **kwargs)


def test_suggest_maps_abnormal_parameters_to_specialty_categories(client) -> None:
    response = _suggest(client, "report-2026-06-14")

    assert response.status_code == 200
    body = response.json()
    data = body["data"]

    categories = {item["parameterGroup"]: item for item in data["categories"]}
    assert categories["metabolic"]["specialtyCategory"] == "diabetologist"
    assert categories["metabolic"]["confidence"] == 0.82
    assert categories["metabolic"]["whenToConsult"]
    assert body["safety"]["pass"] is True


def test_every_category_carries_source_provenance(client) -> None:
    """NFR2.2: every explanation carries `sourceUrl` + `sourceDate`."""
    data = _suggest(client, "report-2026-06-14").json()["data"]

    assert data["categories"]
    for category in data["categories"]:
        assert category["source"]["sourceUrl"]
        assert category["source"]["sourceDate"]


def test_doctor_links_are_flagged_public_demo(client) -> None:
    data = _suggest(client, "report-2026-06-14").json()["data"]

    assert data["doctorLinks"]
    assert all(link["provenance"] == "public/demo" for link in data["doctorLinks"])


def test_response_uses_non_diagnostic_language(client) -> None:
    """FR2.7: safe language only - never a disease name or an urgency claim."""
    data = _suggest(client, "report-2026-06-14").json()["data"]

    assert data["disclaimer"] == (
        "Specialist category suggestion only; not a diagnosis or urgency claim."
    )
    lowered = data["rationale"].lower()
    assert "diabetes" not in lowered
    assert "you have" not in lowered
    assert "urgent" not in lowered


def test_suggest_is_a_pure_function_of_the_report(client) -> None:
    """NFR2.3: the same stored report always yields the same guidance."""
    first = _suggest(client, "report-2026-06-14").json()["data"]
    second = _suggest(client, "report-2026-06-14").json()["data"]

    assert first == second


def test_report_without_abnormal_parameters_returns_general_physician(client, monkeypatch) -> None:
    """LLD Section 2.9: no abnormal parameters -> guidance, not an empty error."""
    from app.repositories import cosmos_repo

    report = cosmos_repo.load_demo_reports()[0].model_copy(deep=True)
    report.id = "report-all-normal"
    for parameter in report.parameters:
        parameter.status = "normal"
    monkeypatch.setitem(cosmos_repo._DEMO_SAVED_REPORTS, report.id, report)

    response = _suggest(client, report.id)

    assert response.status_code == 200
    data = response.json()["data"]
    assert [item["specialtyCategory"] for item in data["categories"]] == ["general-physician"]
    assert "no-abnormal-parameters-general-physician-guidance" in response.json()["safety"]["notes"]


def test_suggest_unknown_report_returns_404(client) -> None:
    response = _suggest(client, "report-does-not-exist")

    assert response.status_code == 404
    assert response.json()["type"] == "https://healthiq/errors/resource-not-found"


def test_suggest_is_scoped_to_the_calling_user(client) -> None:
    """The demo history belongs to `demo-user`; another caller must not read it."""
    response = _suggest(client, "report-2026-06-14", headers={"X-Demo-User-Id": "someone-else"})

    assert response.status_code in {403, 404}
