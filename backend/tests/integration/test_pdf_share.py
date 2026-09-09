"""End-to-end contract tests for Feature 5: doctor-review PDF generation and secure share
(docs/lld/6-low-level-design-doctor-review-pdf-secure-share.md).
"""

import json


def _analyzed_run_id(client) -> str:
    response = client.post(
        "/api/v1/prescriptions/analyze",
        data={
            "consent": "true",
            "manualMedicines": json.dumps([{"rawText": "Glycomet 500mg 1-0-1 x10 days"}]),
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["runId"]


def test_generate_returns_a_share_link_that_serves_the_pdf(client) -> None:
    run_id = _analyzed_run_id(client)

    generated = client.post("/api/v1/pdf/generate", json={"runId": run_id})
    assert generated.status_code == 200
    data = generated.json()["data"]
    assert data["pdfBlobUrl"].startswith("generated-pdfs/")
    assert data["shareUrl"] == f"/api/v1/share/{data['shareId']}"
    assert data["expiresAt"] > ""

    shared = client.get(data["shareUrl"])
    assert shared.status_code == 200
    assert shared.headers["content-type"] == "application/pdf"
    assert shared.headers["cache-control"] == "no-store"
    assert shared.content.startswith(b"%PDF")


def test_share_url_carries_no_phi_and_the_token_is_opaque(client) -> None:
    run_id = _analyzed_run_id(client)
    data = client.post("/api/v1/pdf/generate", json={"runId": run_id}).json()["data"]

    assert "demo-user" not in data["shareUrl"]
    assert "Glycomet" not in data["shareUrl"]
    assert run_id not in data["shareUrl"]


def test_regenerate_false_reuses_the_rendered_pdf(client) -> None:
    run_id = _analyzed_run_id(client)

    first = client.post("/api/v1/pdf/generate", json={"runId": run_id}).json()["data"]
    second = client.post("/api/v1/pdf/generate", json={"runId": run_id}).json()["data"]
    third = client.post("/api/v1/pdf/generate", json={"runId": run_id, "regenerate": True}).json()["data"]

    assert second["pdfBlobUrl"] == first["pdfBlobUrl"]
    assert third["pdfBlobUrl"] != first["pdfBlobUrl"]
    # A fresh token every time: only its hash is stored, so an old one can never be re-issued.
    assert len({first["shareId"], second["shareId"], third["shareId"]}) == 3


def test_revoked_share_link_returns_410(client) -> None:
    run_id = _analyzed_run_id(client)
    data = client.post("/api/v1/pdf/generate", json={"runId": run_id}).json()["data"]

    assert client.get(data["shareUrl"]).status_code == 200

    revoked = client.post(f"/api/v1/share/{data['shareId']}/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["data"]["revoked"] is True

    gone = client.get(data["shareUrl"])
    assert gone.status_code == 410
    assert gone.json()["type"] == "https://healthiq/errors/gone"


def test_unknown_share_token_is_not_found(client) -> None:
    response = client.get("/api/v1/share/definitely-not-a-real-token")

    assert response.status_code == 404
    assert response.json()["type"] == "https://healthiq/errors/resource-not-found"


def test_download_flag_serves_the_pdf_as_an_attachment(client) -> None:
    run_id = _analyzed_run_id(client)
    data = client.post("/api/v1/pdf/generate", json={"runId": run_id}).json()["data"]

    inline = client.get(data["shareUrl"])
    attachment = client.get(data["shareUrl"], params={"download": "1"})

    assert inline.headers["content-disposition"].startswith("inline;")
    assert attachment.headers["content-disposition"].startswith("attachment;")
    assert "HealthIQ-Medicine-Review-" in attachment.headers["content-disposition"]
    assert attachment.content == inline.content


def test_a_corrected_low_confidence_line_can_still_be_rendered(client) -> None:
    """Regression: R5 blocked the PDF for every line the user fixed at the confirm step."""
    analyze = client.post(
        "/api/v1/prescriptions/analyze",
        data={
            "consent": "true",
            "manualMedicines": json.dumps([{"rawText": "Unknownbrand 500mg 1-0-1 x5 days"}]),
        },
    )
    assert analyze.status_code == 422
    problem = analyze.json()
    run_id = next(e["issue"] for e in problem["errors"] if e["field"] == "runId")

    confirmed = client.post(
        "/api/v1/prescriptions/confirm",
        json={"runId": run_id, "corrections": [{"lineId": "li-1", "brandName": "Glycomet"}]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["items"][0]["needsUserConfirmation"] is False

    generated = client.post("/api/v1/pdf/generate", json={"runId": run_id})
    assert generated.status_code == 200, generated.json()


def test_generate_rejects_a_run_that_cannot_be_rendered(client) -> None:
    run_id = _analyzed_run_id(client)
    generated = client.post("/api/v1/pdf/generate", json={"runId": run_id}).json()["data"]

    # The audit run written for the PDF itself is not a renderable source document.
    pdf_runs = client.post("/api/v1/pdf/generate", json={"runId": generated["shareId"]})
    assert pdf_runs.status_code == 404
