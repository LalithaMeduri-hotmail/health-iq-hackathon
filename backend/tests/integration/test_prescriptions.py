"""Contract tests for the Prescription & Medicine Analyzer vertical slice (manual-entry path,
which bypasses OCR/blob so it needs no live Azure - see NFR1.6 in
docs/lld/2-low-level-design-prescription-medicine-analyzer.md).
"""

import json


def test_analyze_with_manual_entry_returns_items(client) -> None:
    response = client.post(
        "/api/v1/prescriptions/analyze",
        data={"consent": "true", "manualMedicines": json.dumps([{"rawText": "Glycomet 500mg 1-0-1 x10 days"}])},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["safety"]["pass"] is True
    assert body["data"]["items"][0]["brandName"] == "Glycomet"
    assert body["data"]["items"][0]["needsUserConfirmation"] is False
    assert body["data"]["runId"].startswith("run-")


def test_analyze_without_consent_is_rejected(client) -> None:
    response = client.post(
        "/api/v1/prescriptions/analyze",
        data={"consent": "false", "manualMedicines": json.dumps([{"rawText": "Glycomet 500mg 1-0-1 x10 days"}])},
    )

    assert response.status_code == 400
    assert response.json()["type"] == "https://healthiq/errors/validation-error"


def test_analyze_low_confidence_returns_422_with_run_id(client) -> None:
    response = client.post(
        "/api/v1/prescriptions/analyze",
        data={"consent": "true", "manualMedicines": json.dumps([{"rawText": "Unknownbrand 500mg 1-0-1 x5 days"}])},
    )

    assert response.status_code == 422
    problem = response.json()
    assert problem["type"] == "https://healthiq/errors/low-confidence-ocr"
    run_id = next(e["issue"] for e in problem["errors"] if e["field"] == "runId")
    assert run_id.startswith("run-")


def test_confirm_resolves_low_confidence_item(client) -> None:
    analyze_response = client.post(
        "/api/v1/prescriptions/analyze",
        data={"consent": "true", "manualMedicines": json.dumps([{"rawText": "Unknownbrand 500mg 1-0-1 x5 days"}])},
    )
    run_id = next(e["issue"] for e in analyze_response.json()["errors"] if e["field"] == "runId")

    confirm_response = client.post(
        "/api/v1/prescriptions/confirm",
        json={"runId": run_id, "corrections": [{"lineId": "li-1", "brandName": "Glycomet"}]},
    )

    assert confirm_response.status_code == 200
    body = confirm_response.json()["data"]
    assert body["items"][0]["brandName"] == "Glycomet"
    assert body["items"][0]["needsUserConfirmation"] is False


def test_alternatives_endpoint_returns_savings(client) -> None:
    response = client.post(
        "/api/v1/medicines/alternatives",
        json={
            "items": [
                {
                    "brandName": "Glycomet",
                    "activeIngredient": "Metformin",
                    "strengthValue": 500,
                    "strengthUnit": "mg",
                    "dosageForm": "tablet",
                }
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["alternatives"][0]["savingsPct"] > 0
    assert body["alternatives"][0]["doctorApprovalRequired"] is True
