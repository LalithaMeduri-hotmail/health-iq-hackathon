"""Doctor review-by-email flow: request -> emailed token -> confirm page -> decision.

`smtp_host` is unset under the test settings, so the mailer stays in preview mode and nothing
leaves the machine.
"""

import json
import re

import pytest

from app.repositories import sql_repo
from app.services import email, reviews


def _analyzed_run_id(client, *medicines: str) -> str:
    lines = medicines or ("Glycomet 500mg 1-0-1 x10 days",)
    response = client.post(
        "/api/v1/prescriptions/analyze",
        data={
            "consent": "true",
            "manualMedicines": json.dumps([{"rawText": text} for text in lines]),
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["runId"]


def test_registry_masks_doctor_addresses(client) -> None:
    response = client.get("/api/v1/doctors")

    assert response.status_code == 200
    doctors = response.json()["data"]["doctors"]
    assert any(doctor["doctorId"] == "doc-001" for doctor in doctors)
    for doctor in doctors:
        assert "@" in doctor["emailMasked"]
        assert "***" in doctor["emailMasked"]
        assert "duttadebopriya3" not in json.dumps(doctor)


def test_request_creates_a_pending_review_and_sends_mail(client, monkeypatch) -> None:
    sent: list[tuple[str, str]] = []

    async def fake_send(to_address, subject, text_body, *, attachment=None):
        sent.append((to_address, text_body))
        assert attachment is not None
        assert attachment[0].startswith("HealthIQ-Medicine-Review-")
        assert attachment[1].startswith(b"%PDF")
        return "sent"

    monkeypatch.setattr(email, "send", fake_send)

    run_id = _analyzed_run_id(client)
    response = client.post("/api/v1/reviews/request", json={"runId": run_id, "doctorIds": ["doc-001"]})

    assert response.status_code == 200
    review = response.json()["data"]["reviews"][0]
    assert review["status"] == "pending"
    assert review["doctorName"] == "Dr. Debopriya Dutta"
    assert review["doctorEmailMasked"] == "d***@gmail.com"

    to_address, body = sent[0]
    assert to_address == "duttadebopriya3@gmail.com"
    assert "/api/v1/reviews/" in body
    assert "Glycomet" in body


async def test_opening_the_link_records_nothing(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    run_id = _analyzed_run_id(client)
    token = await _issue(run_id)

    page = client.get(f"/api/v1/reviews/{token}")

    assert page.status_code == 200
    assert "Awaiting your decision" in page.text
    assert sql_repo._DEMO_DOCTOR_REVIEWS[reviews._hash(token)]["status"] == "pending"


async def test_every_medicine_gets_its_own_set_of_options(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    token = await _issue(_analyzed_run_id(client))

    page = client.get(f"/api/v1/reviews/{token}").text

    assert 'name="decision-li-1" value="approved"' in page
    assert 'name="decision-li-1" value="changes_requested"' in page
    assert 'name="decision-li-1" value="rejected"' in page


async def test_the_doctor_decides_on_the_proposed_switch(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    token = await _issue(_analyzed_run_id(client))

    page = client.get(f"/api/v1/reviews/{token}").text

    assert "<th>Current medicine</th><th>Health IQ alternative</th>" in page
    # Medicine name first, its maker after it in brackets and not bold.
    assert '<strong>Metfor 500 mg</strong> <span class="maker">(Cipla Ltd)</span>' in page
    assert '<strong>Glycomet 500mg</strong> <span class="maker">(USV Pvt Ltd)</span>' in page
    assert "about 42% less" in page
    # The icon alone is ambiguous, so each button carries its wording for hover and screen readers.
    assert 'title="Approve"' in page
    assert 'aria-label="Do not approve Glycomet 500mg"' in page


def test_the_request_carries_the_patient_name_from_the_prescription(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    run_id = _analyzed_run_id(client)

    response = client.post(
        "/api/v1/reviews/request",
        json={"runId": run_id, "doctorIds": ["doc-001"], "patientName": "Ramesh Kumar"},
    )

    assert response.status_code == 200
    stored = next(iter(sql_repo._DEMO_DOCTOR_REVIEWS.values()))
    assert stored["patientName"] == "Ramesh Kumar"


async def test_the_summary_document_is_named_after_the_patient(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    run_id = _analyzed_run_id(client)
    client.post(
        "/api/v1/reviews/request",
        json={"runId": run_id, "doctorIds": ["doc-001"], "patientName": "Ramesh Kumar"},
    )
    token_hash, stored = next(iter(sql_repo._DEMO_DOCTOR_REVIEWS.items()))
    await sql_repo.record_doctor_decision(
        token_hash,
        status="approved",
        notes="",
        decided_at="2026-09-15T10:00:00+00:00",
        decisions=[{"lineId": "li-1", "label": "Glycomet 500mg", "decision": "approved"}],
    )

    response = client.get(f"/api/v1/reviews/{stored['reviewId']}/documents")

    assert response.status_code == 200
    assert "HealthIQ-Review-Summary-Ramesh-Kumar" in response.headers["content-disposition"]


async def test_the_alternative_the_patient_picked_is_what_the_doctor_is_asked_about(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    run_id = _analyzed_run_id(client, "Pantocid 40mg 1-0-0 x14 days")

    client.post(
        "/api/v1/reviews/request",
        json={
            "runId": run_id,
            "doctorIds": ["doc-001"],
            "patientName": "Ramesh Kumar",
            # Not the cheapest match - picking it proves the patient's choice beats the default.
            "selections": {"li-1": "Pan 40 mg"},
        },
    )

    _, stored = next(iter(sql_repo._DEMO_DOCTOR_REVIEWS.items()))
    assert stored["lines"][0]["alternative"] == "Pan 40 mg"
    assert stored["lines"][0]["alternativeMaker"] == "Alkem Labs"


async def test_an_unpicked_line_falls_back_to_the_best_value_equivalent(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    run_id = _analyzed_run_id(client, "Pantocid 40mg 1-0-0 x14 days")

    client.post(
        "/api/v1/reviews/request",
        json={"runId": run_id, "doctorIds": ["doc-001"], "patientName": "Ramesh Kumar"},
    )

    _, stored = next(iter(sql_repo._DEMO_DOCTOR_REVIEWS.items()))
    assert stored["lines"][0]["alternative"] == "Pantosec 40 mg"


async def test_a_missing_medicine_verdict_is_rejected(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    run_id = _analyzed_run_id(client)
    token = await _issue(run_id)

    response = client.post(f"/api/v1/reviews/{token}/decision", data={"notes": ""})

    assert response.status_code == 400
    assert sql_repo._DEMO_DOCTOR_REVIEWS[reviews._hash(token)]["status"] == "pending"


async def test_doctor_approval_is_visible_to_the_patient(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    run_id = _analyzed_run_id(client)
    token = await _issue(run_id)

    decision = client.post(
        f"/api/v1/reviews/{token}/decision",
        data={"decision-li-1": "approved", "notes": "Fine to switch at the next refill."},
    )
    assert decision.status_code == 200
    assert "Approved" in decision.text

    status = client.get("/api/v1/reviews", params={"runId": run_id})
    body = status.json()["data"]
    assert body["approved"] is True
    assert body["reviews"][0]["status"] == "approved"
    assert body["reviews"][0]["notes"] == "Fine to switch at the next refill."
    assert body["reviews"][0]["decisions"] == [
        {
            "lineId": "li-1",
            "label": "Glycomet 500mg",
            "decision": "approved",
            "maker": "USV Pvt Ltd",
            "alternative": "Metfor 500 mg",
            "alternativeMaker": "Cipla Ltd",
            "savingsPct": 42,
            "originalMrpInr": 32.5,
            "cheaperMrpInr": 18.9,
        }
    ]


async def test_a_partly_approved_review_is_not_approved_overall(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    run_id = _analyzed_run_id(client, "Glycomet 500mg 1-0-1 x10 days", "Amlong 5mg 0-0-1 x30 days")
    token = await _issue(run_id)

    client.post(
        f"/api/v1/reviews/{token}/decision",
        data={"decision-li-1": "approved", "decision-li-2": "rejected", "notes": ""},
    )

    body = client.get("/api/v1/reviews", params={"runId": run_id}).json()["data"]
    assert body["reviews"][0]["status"] == "changes_requested"
    assert body["approved"] is False


async def test_a_decided_review_becomes_one_health_iq_document(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    run_id = _analyzed_run_id(client, "Glycomet 500mg 1-0-1 x10 days", "Amlong 5mg 0-0-1 x30 days")
    token = await _issue(run_id)
    review_id = sql_repo._DEMO_DOCTOR_REVIEWS[reviews._hash(token)]["reviewId"]

    client.post(
        f"/api/v1/reviews/{token}/decision",
        data={"decision-li-1": "approved", "decision-li-2": "changes_requested", "notes": "Halve the dose."},
    )

    doctor_copy = client.get(f"/api/v1/reviews/{token}/prescription")
    patient_copy = client.get(f"/api/v1/reviews/{review_id}/documents")
    assert doctor_copy.status_code == 200
    assert doctor_copy.content.startswith(b"%PDF")
    assert patient_copy.status_code == 200
    assert patient_copy.content.startswith(b"%PDF")
    assert "HealthIQ-Review-Summary-" in patient_copy.headers["content-disposition"]


async def test_the_document_is_only_offered_once_a_decision_exists(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    token = await _issue(_analyzed_run_id(client))

    assert client.get(f"/api/v1/reviews/{token}/prescription").status_code == 404

    page = client.post(f"/api/v1/reviews/{token}/decision", data={"decision-li-1": "approved", "notes": ""})

    assert page.text.count("/prescription") == 1
    assert client.get(f"/api/v1/reviews/{token}/prescription").status_code == 200


async def test_another_patient_cannot_read_a_review_document(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    token = await _issue(_analyzed_run_id(client))
    review_id = sql_repo._DEMO_DOCTOR_REVIEWS[reviews._hash(token)]["reviewId"]
    client.post(f"/api/v1/reviews/{token}/decision", data={"decision-li-1": "approved", "notes": ""})

    response = client.get(
        f"/api/v1/reviews/{review_id}/documents/approved",
        headers={"X-Demo-User-Id": "someone-else"},
    )

    assert response.status_code == 404


async def test_a_decision_cannot_be_overwritten(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    run_id = _analyzed_run_id(client)
    token = await _issue(run_id)

    client.post(f"/api/v1/reviews/{token}/decision", data={"decision-li-1": "approved", "notes": ""})
    second = client.post(f"/api/v1/reviews/{token}/decision", data={"decision-li-1": "rejected", "notes": ""})

    assert second.status_code == 400
    status = client.get("/api/v1/reviews", params={"runId": run_id}).json()["data"]
    assert status["reviews"][0]["status"] == "approved"


async def test_unknown_review_token_is_not_found(client) -> None:
    assert client.get("/api/v1/reviews/not-a-real-token").status_code == 404


async def test_expired_review_link_is_gone(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    run_id = _analyzed_run_id(client)
    token = await _issue(run_id)
    sql_repo._DEMO_DOCTOR_REVIEWS[reviews._hash(token)]["expiresAt"] = "2020-01-01T00:00:00+00:00"

    assert client.get(f"/api/v1/reviews/{token}").status_code == 410


def test_preview_mode_writes_a_message_instead_of_sending(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(email, "_LOCAL_MAIL_ROOT", tmp_path)
    assert email.is_preview_mode() is True

    run_id = _analyzed_run_id(client)
    response = client.post("/api/v1/reviews/request", json={"runId": run_id, "doctorIds": ["doc-001"]})

    assert response.json()["data"]["reviews"][0]["delivery"] == "preview"
    written = list(tmp_path.glob("*.eml"))
    assert len(written) == 1
    raw = written[0].read_text(encoding="utf-8", errors="replace")
    assert "duttadebopriya3@gmail.com" in raw
    assert re.search(r"/api/v1/reviews/[A-Za-z0-9_-]{20,}", raw)


async def _issue(run_id: str) -> str:
    """Mint a review token directly, since the emailed token is never persisted in the clear."""
    import secrets

    from app.repositories import cosmos_repo
    from app.repositories import sql_repo as repo
    from app.services import doctor_pdf

    run = await cosmos_repo.get_run("demo-user", run_id)
    token = secrets.token_urlsafe(16)
    await repo.create_doctor_review(
        reviews._hash(token),
        {
            "reviewId": token[:8],
            "userId": "demo-user",
            "runId": run_id,
            "patientName": "Ramesh Kumar",
            "doctorId": "doc-001",
            "doctorName": "Dr. Debopriya Dutta",
            "doctorSpecialty": "General Physician",
            "doctorRegistrationNo": "DEMO-GP-1001",
            "doctorEmailMasked": "d***@gmail.com",
            "medicines": doctor_pdf.medicine_names(run),
            "lines": doctor_pdf.medicine_lines(run),
            "decisions": [],
            "pdfFilename": "HealthIQ-Medicine-Review-Glycomet-2026-09-09.pdf",
            "status": "pending",
            "notes": "",
            "requestedAt": "2026-09-09T10:00:00+00:00",
            "decidedAt": None,
            "expiresAt": "2099-01-01T00:00:00+00:00",
            "delivery": "preview",
        },
    )
    return token


async def _noop_send(to_address, subject, text_body, *, attachment=None):
    return "preview"


@pytest.fixture(autouse=True)
def _clear_reviews():
    sql_repo._DEMO_DOCTOR_REVIEWS.clear()
    yield
    sql_repo._DEMO_DOCTOR_REVIEWS.clear()
