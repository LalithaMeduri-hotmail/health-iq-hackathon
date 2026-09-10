"""Doctor review-by-email flow: request -> emailed token -> confirm page -> decision.

`smtp_host` is unset under the test settings, so the mailer stays in preview mode and nothing
leaves the machine.
"""

import json
import re

import pytest

from app.repositories import sql_repo
from app.services import email, reviews


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


async def test_doctor_approval_is_visible_to_the_patient(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    run_id = _analyzed_run_id(client)
    token = await _issue(run_id)

    decision = client.post(
        f"/api/v1/reviews/{token}/decision",
        data={"decision": "approved", "notes": "Fine to switch at the next refill."},
    )
    assert decision.status_code == 200
    assert "Approved" in decision.text

    status = client.get("/api/v1/reviews", params={"runId": run_id})
    body = status.json()["data"]
    assert body["approved"] is True
    assert body["reviews"][0]["status"] == "approved"
    assert body["reviews"][0]["notes"] == "Fine to switch at the next refill."


async def test_a_decision_cannot_be_overwritten(client, monkeypatch) -> None:
    monkeypatch.setattr(email, "send", _noop_send)
    run_id = _analyzed_run_id(client)
    token = await _issue(run_id)

    client.post(f"/api/v1/reviews/{token}/decision", data={"decision": "approved", "notes": ""})
    second = client.post(f"/api/v1/reviews/{token}/decision", data={"decision": "rejected", "notes": ""})

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

    from app.repositories import sql_repo as repo

    token = secrets.token_urlsafe(16)
    await repo.create_doctor_review(
        reviews._hash(token),
        {
            "reviewId": token[:8],
            "userId": "demo-user",
            "runId": run_id,
            "doctorId": "doc-001",
            "doctorName": "Dr. Debopriya Dutta",
            "doctorSpecialty": "General Physician",
            "doctorEmailMasked": "d***@gmail.com",
            "medicines": ["Glycomet 500mg"],
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
