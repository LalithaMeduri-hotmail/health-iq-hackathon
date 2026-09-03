"""Contract tests for the Report Comparison Engine (docs/lld/4-low-level-design-*.md Section 3.3.1).

Runs against the recorded demo report history (`DEMO_MODE=true`), so no live Azure is needed.
"""

import pytest

# Demo mode replays the recorded lab fixtures in rotation, so two uploads yield two report dates.
_UPLOAD = b"%PDF-1.4 lab report " + b"0" * 40


def _compare(client, old_report_id: str, current_report_id: str):
    return client.post(
        "/api/v1/reports/compare",
        json={"oldReportId": old_report_id, "currentReportId": current_report_id},
    )


def _analyze(client, filename: str = "report.pdf"):
    return client.post(
        "/api/v1/reports/analyze",
        data={"consent": "true"},
        files={"file": (filename, _UPLOAD, "application/pdf")},
    )


def _analyze_pair(client) -> tuple[dict, dict]:
    """Upload twice and return `(older, newer)` ordered by the extracted report date."""
    first = _analyze(client, "first.pdf").json()["data"]
    second = _analyze(client, "second.pdf").json()["data"]
    return tuple(sorted((first, second), key=lambda report: report["reportDate"]))


def test_list_reports_returns_demo_history_newest_first(client) -> None:
    response = client.get("/api/v1/reports")

    assert response.status_code == 200
    reports = response.json()["data"]["reports"]
    assert len(reports) >= 2
    assert reports[0]["reportDate"] > reports[-1]["reportDate"]
    assert reports[0]["parameterCount"] > 0


def test_list_reports_does_not_count_unknown_status_as_abnormal(client) -> None:
    """A parameter with no reference range is `unknown`, which is not the same as out of range."""
    analyzed = _analyze(client).json()["data"]
    listed = {r["reportId"]: r for r in client.get("/api/v1/reports").json()["data"]["reports"]}
    expected = sum(1 for p in analyzed["parameters"] if p["status"] in {"low", "high", "critical_flag"})

    assert listed[analyzed["reportId"]]["abnormalCount"] == expected
    assert listed[analyzed["reportId"]]["abnormalCount"] == len(analyzed["abnormal"])


def test_compare_classifies_each_bucket(client) -> None:
    response = _compare(client, "report-2026-03-10", "report-2026-06-14")

    assert response.status_code == 200
    body = response.json()
    data = body["data"]

    assert data["oldReportDate"] == "2026-03-10"
    assert data["currentReportDate"] == "2026-06-14"
    assert body["safety"]["pass"] is True

    improved = {item["canonicalKey"]: item for item in data["improved"]}
    worsened = {item["canonicalKey"]: item for item in data["worsened"]}

    assert improved["ldl"]["pctChange"] == -20.0
    assert worsened["hba1c"]["pctChange"] == 15.6
    assert [item["canonicalKey"] for item in data["newlyAbnormal"]] == ["tsh"]
    assert [item["canonicalKey"] for item in data["missing"]] == ["vitamin_d"]
    assert any(item["canonicalKey"] == "creatinine" for item in data["unchanged"])


def test_compare_returns_trend_series_for_repeated_parameters(client) -> None:
    response = _compare(client, "report-2026-03-10", "report-2026-06-14")

    trend_series = response.json()["data"]["trendSeries"]
    assert "hba1c" in trend_series
    assert len(trend_series["hba1c"]) >= 2
    assert trend_series["hba1c"][0]["reportDate"] < trend_series["hba1c"][-1]["reportDate"]


def test_compare_returns_a_grounded_narrative(client) -> None:
    response = _compare(client, "report-2026-03-10", "report-2026-06-14")

    narrative = response.json()["data"]["narrative"]
    assert "2026-03-10" in narrative
    assert "source:" in narrative
    assert "narrative-unavailable" not in response.json()["safety"]["notes"]


def test_get_report_detail_explains_the_health_score(client) -> None:
    """Every deduction that produced the score is itemized (NFR2.5)."""
    response = client.get("/api/v1/reports/report-2026-06-14")

    assert response.status_code == 200
    data = response.json()["data"]
    breakdown = data["scoreBreakdown"]

    assert breakdown["baseScore"] == 100
    assert breakdown["healthScore"] == data["healthScore"]
    assert breakdown["baseScore"] - breakdown["totalPenalty"] == breakdown["healthScore"]
    assert len(breakdown["penalties"]) == len(data["abnormal"])
    assert {p["canonicalKey"] for p in breakdown["penalties"]} == {
        p["canonicalKey"] for p in data["abnormal"]
    }
    assert all(p["penalty"] in {8, 15} for p in breakdown["penalties"])
    assert "not a diagnosis" in breakdown["method"]


def test_get_report_detail_returns_out_of_range_parameters(client) -> None:
    data = client.get("/api/v1/reports/report-2026-06-14").json()["data"]

    assert data["reportDate"] == "2026-06-14"
    assert data["parameters"]
    assert data["systemCards"]
    assert all(p["status"] in {"low", "high", "critical_flag"} for p in data["abnormal"])
    assert len(data["abnormal"]) < len(data["parameters"])


def test_get_report_detail_unknown_report_returns_404(client) -> None:
    response = client.get("/api/v1/reports/report-does-not-exist")

    assert response.status_code == 404
    assert response.json()["type"] == "https://healthiq/errors/resource-not-found"


def test_get_report_detail_is_scoped_to_the_calling_user(client) -> None:
    response = client.get(
        "/api/v1/reports/report-2026-06-14", headers={"X-Demo-User-Id": "someone-else"}
    )

    assert response.status_code in {403, 404}


def test_compare_rejects_identical_report_ids(client) -> None:
    response = _compare(client, "report-2026-06-14", "report-2026-06-14")

    assert response.status_code == 400
    assert response.json()["type"] == "https://healthiq/errors/validation-error"


def test_compare_unknown_report_returns_404(client) -> None:
    response = _compare(client, "report-does-not-exist", "report-2026-06-14")

    assert response.status_code == 404
    assert response.json()["type"] == "https://healthiq/errors/resource-not-found"


def test_analyze_upload_normalizes_and_stores_a_report(client) -> None:
    response = _analyze(client)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["reportId"].startswith("report-")
    assert data["reportDate"] in {"2026-03-10", "2026-06-14"}
    assert {p["canonicalKey"] for p in data["parameters"]} >= {"hba1c", "ldl", "creatinine"}
    assert 0 <= data["healthScore"] <= 100
    assert data["systemCards"]

    listed = client.get("/api/v1/reports").json()["data"]["reports"]
    assert data["reportId"] in {report["reportId"] for report in listed}


def test_analyze_without_consent_is_rejected(client) -> None:
    response = client.post(
        "/api/v1/reports/analyze",
        data={"consent": "false"},
        files={"file": ("report.pdf", _UPLOAD, "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["type"] == "https://healthiq/errors/validation-error"


def test_analyze_rejects_a_disallowed_file_type(client) -> None:
    response = client.post(
        "/api/v1/reports/analyze",
        data={"consent": "true"},
        files={"file": ("report.exe", b"MZ binary", "application/octet-stream")},
    )

    assert response.status_code == 415


def test_two_uploads_can_be_compared_end_to_end(client) -> None:
    older, newer = _analyze_pair(client)
    assert older["reportDate"] < newer["reportDate"]

    response = _compare(client, older["reportId"], newer["reportId"])

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["runId"].startswith("run-")
    assert [item["canonicalKey"] for item in data["worsened"]] == ["hba1c"]
    assert [item["canonicalKey"] for item in data["newlyAbnormal"]] == ["tsh"]


def test_share_pdf_is_generated_and_served_behind_a_token(client) -> None:
    pytest.importorskip("reportlab", reason="PDF rendering requires the reportlab dependency")

    older, newer = _analyze_pair(client)
    run_id = _compare(client, older["reportId"], newer["reportId"]).json()["data"]["runId"]

    pdf_response = client.post("/api/v1/pdf/generate", json={"runId": run_id})
    assert pdf_response.status_code == 200
    share = pdf_response.json()["data"]
    assert share["shareId"] not in share["pdfBlobUrl"]

    shared = client.get(share["shareUrl"])
    assert shared.status_code == 200
    assert shared.headers["content-type"] == "application/pdf"
    assert shared.content.startswith(b"%PDF")


def test_share_link_rejects_an_unknown_token(client) -> None:
    response = client.get("/api/v1/share/not-a-real-token")

    assert response.status_code == 404
    assert response.json()["type"] == "https://healthiq/errors/resource-not-found"
