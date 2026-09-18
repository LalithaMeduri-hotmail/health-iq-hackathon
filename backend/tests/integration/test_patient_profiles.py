"""Account/profile isolation contract tests.

The point of this file is to prove the boundary, not the happy path: a caller must never be able
to reach another account's profile, or another profile's document, by editing an identifier in
the request. All patient data here is synthetic.
"""

import pytest

from app.services.ocr import OcrEnvelope, OcrLine

_PDF = b"%PDF-1.4 synthetic lab report " + b"0" * 64
_OTHER_PDF = b"%PDF-1.4 a different synthetic document " + b"0" * 64

ALICE = {"X-Demo-User-Id": "acct-alice"}
BOB = {"X-Demo-User-Id": "acct-bob"}


def _envelope(*lines: str) -> OcrEnvelope:
    return OcrEnvelope(
        pages=1,
        lines=[OcrLine(text=text, confidence=0.95, bbox=[0, 0, 1, 1]) for text in lines],
        tables=[],
        handwritten_ratio=0.0,
        source="docintel",
    )


@pytest.fixture
def fake_ocr(monkeypatch):
    """Replace the OCR pass so a test controls exactly what identity a document shows."""

    def _install(*lines: str):
        async def _extract(_file: bytes, *, mode: str) -> OcrEnvelope:
            return _envelope(*lines)

        monkeypatch.setattr("app.api.documents.ocr_extract", _extract)

    return _install


def _profiles(client, headers):
    return client.get("/api/v1/profiles", headers=headers).json()["data"]


def _create_profile(client, headers, name: str, relationship: str = "child"):
    response = client.post(
        "/api/v1/profiles",
        headers=headers,
        json={
            "displayName": name,
            "relationshipToAccountOwner": relationship,
            "dateOfBirth": "2014-06-02",
            "consentAccepted": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _upload(client, headers, profile_id, content=_PDF, filename="report.pdf"):
    return client.post(
        f"/api/v1/profiles/{profile_id}/documents",
        headers=headers,
        data={"consent": "true"},
        files={"file": (filename, content, "application/pdf")},
    )


# --------------------------------------------------------------------------- profile lifecycle


def test_first_sign_in_creates_a_self_profile(client) -> None:
    data = _profiles(client, ALICE)

    assert len(data["profiles"]) == 1
    owner = data["profiles"][0]
    assert owner["isAccountOwnerProfile"] is True
    assert owner["relationshipToAccountOwner"] == "self"
    assert data["activeProfileId"] == owner["id"]


def test_account_can_hold_multiple_independent_profiles(client) -> None:
    _create_profile(client, ALICE, "Ravi Junior")
    _create_profile(client, ALICE, "Meera Senior", relationship="parent")

    profiles = _profiles(client, ALICE)["profiles"]

    assert len(profiles) == 3
    assert [p["isAccountOwnerProfile"] for p in profiles] == [True, False, False]


def test_creating_a_profile_without_consent_is_rejected(client) -> None:
    response = client.post(
        "/api/v1/profiles",
        headers=ALICE,
        json={"displayName": "No Consent", "relationshipToAccountOwner": "child"},
    )

    assert response.status_code == 400
    assert response.json()["type"].endswith("validation-error")


def test_second_self_profile_is_downgraded_to_a_dependent(client) -> None:
    created = _create_profile(client, ALICE, "Impostor Self", relationship="self")

    assert created["isAccountOwnerProfile"] is False
    assert created["relationshipToAccountOwner"] == "other"


# ------------------------------------------------------------------- insecure direct references


def test_another_accounts_profile_is_not_readable(client) -> None:
    bob_profile = _create_profile(client, BOB, "Bob Junior")

    response = client.get(f"/api/v1/profiles/{bob_profile['id']}", headers=ALICE)

    assert response.status_code == 404
    # The same wording as a genuinely missing profile, so nothing confirms Bob's profile exists.
    assert response.json()["title"] == "Resource not found"
    assert response.json()["detail"] == "Profile not found"


def test_unknown_and_forbidden_profiles_are_indistinguishable(client) -> None:
    bob_profile = _create_profile(client, BOB, "Bob Junior")

    forbidden = client.get(f"/api/v1/profiles/{bob_profile['id']}", headers=ALICE).json()
    missing = client.get("/api/v1/profiles/pp-does-not-exist", headers=ALICE).json()

    assert forbidden["status"] == missing["status"]
    assert forbidden["title"] == missing["title"]
    assert forbidden["detail"] == missing["detail"]


def test_another_accounts_profile_cannot_be_updated(client) -> None:
    bob_profile = _create_profile(client, BOB, "Bob Junior")

    response = client.put(
        f"/api/v1/profiles/{bob_profile['id']}",
        headers=ALICE,
        json={"displayName": "Hijacked", "relationshipToAccountOwner": "child"},
    )

    assert response.status_code == 404


def test_another_accounts_profile_cannot_be_archived(client) -> None:
    bob_profile = _create_profile(client, BOB, "Bob Junior")

    response = client.post(f"/api/v1/profiles/{bob_profile['id']}/archive", headers=ALICE)

    assert response.status_code == 404


def test_account_id_in_the_body_is_ignored(client) -> None:
    """Over-posting `accountId` must not move a profile onto another account."""
    response = client.post(
        "/api/v1/profiles",
        headers=ALICE,
        json={
            "displayName": "Over Posted",
            "relationshipToAccountOwner": "child",
            "consentAccepted": True,
            "accountId": "acct-bob",
            "isAccountOwnerProfile": True,
            "status": "archived",
        },
    )

    created = response.json()["data"]
    assert created["accountId"] == "acct-alice"
    assert created["isAccountOwnerProfile"] is False
    assert created["status"] == "active"
    assert client.get(f"/api/v1/profiles/{created['id']}", headers=BOB).status_code == 404


# ------------------------------------------------------------------------------ document upload


def test_upload_verify_confirm_attaches_the_document(client, fake_ocr) -> None:
    fake_ocr("Demo Diagnostics", "Patient Name: Ravi Junior", "DOB: 02/06/2014")
    child = _create_profile(client, ALICE, "Ravi Junior")

    uploaded = _upload(client, ALICE, child["id"]).json()["data"]
    assert uploaded["uploadStatus"] == "pending"
    assert uploaded["blobReference"].startswith("raw-uploads/pending/")

    verified = client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/verify", headers=ALICE
    ).json()["data"]
    assert verified["match"]["status"] == "MATCH"

    confirmed = client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/confirm",
        headers=ALICE,
        json={"confirmed": True},
    ).json()["data"]

    assert confirmed["uploadStatus"] == "confirmed"
    # Storage layout mirrors the authorization model: account *and* profile are in the path.
    assert confirmed["blobReference"].startswith(f"raw-uploads/acct-alice/{child['id']}/")


def test_mismatched_document_cannot_be_forced_onto_the_profile(client, fake_ocr) -> None:
    fake_ocr("Patient Name: Someone Else Entirely", "DOB: 01/01/1970")
    child = _create_profile(client, ALICE, "Ravi Junior")
    uploaded = _upload(client, ALICE, child["id"]).json()["data"]

    verified = client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/verify", headers=ALICE
    ).json()["data"]
    assert verified["match"]["status"] == "MISMATCH"
    assert "confirm" not in verified["nextActions"]

    response = client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/confirm",
        headers=ALICE,
        json={"confirmed": True},
    )

    assert response.status_code == 422
    assert response.json()["type"].endswith("profile-mismatch")


def test_mismatched_document_can_be_redirected_to_the_right_profile(client, fake_ocr) -> None:
    fake_ocr("Patient Name: Meera Senior", "DOB: 02/06/2014")
    child = _create_profile(client, ALICE, "Ravi Junior")
    parent = _create_profile(client, ALICE, "Meera Senior", relationship="parent")
    uploaded = _upload(client, ALICE, child["id"]).json()["data"]
    client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/verify", headers=ALICE
    )

    confirmed = client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/confirm",
        headers=ALICE,
        json={"confirmed": True, "targetProfileId": parent["id"]},
    ).json()["data"]

    assert confirmed["profileId"] == parent["id"]


def test_document_cannot_be_redirected_to_another_accounts_profile(client, fake_ocr) -> None:
    fake_ocr("Patient Name: Ravi Junior", "DOB: 02/06/2014")
    child = _create_profile(client, ALICE, "Ravi Junior")
    bob_profile = _create_profile(client, BOB, "Bob Junior")
    uploaded = _upload(client, ALICE, child["id"]).json()["data"]
    client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/verify", headers=ALICE
    )

    response = client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/confirm",
        headers=ALICE,
        json={"confirmed": True, "targetProfileId": bob_profile["id"]},
    )

    assert response.status_code == 404


def test_insufficient_identity_requires_an_explicit_acknowledgement(client, fake_ocr) -> None:
    fake_ocr("Demo Diagnostics (sample)", "Biochemistry Panel")
    child = _create_profile(client, ALICE, "Ravi Junior")
    uploaded = _upload(client, ALICE, child["id"]).json()["data"]

    verified = client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/verify", headers=ALICE
    ).json()["data"]
    assert verified["match"]["status"] == "INSUFFICIENT_IDENTITY_DATA"

    blocked = client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/confirm",
        headers=ALICE,
        json={"confirmed": True},
    )
    assert blocked.status_code == 409
    assert blocked.json()["type"].endswith("confirmation-required")

    allowed = client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/confirm",
        headers=ALICE,
        json={"confirmed": True, "acknowledgement": "This is my son's report"},
    )
    assert allowed.status_code == 200


def test_document_of_another_profile_is_not_readable(client, fake_ocr) -> None:
    fake_ocr("Patient Name: Ravi Junior")
    child = _create_profile(client, ALICE, "Ravi Junior")
    sibling = _create_profile(client, ALICE, "Nita Junior")
    uploaded = _upload(client, ALICE, child["id"]).json()["data"]

    response = client.get(
        f"/api/v1/profiles/{sibling['id']}/documents/{uploaded['id']}", headers=ALICE
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_document_of_another_account_is_not_readable(client, fake_ocr) -> None:
    fake_ocr("Patient Name: Bob Junior")
    bob_profile = _create_profile(client, BOB, "Bob Junior")
    uploaded = _upload(client, BOB, bob_profile["id"]).json()["data"]
    alice_owner = _profiles(client, ALICE)["activeProfileId"]

    response = client.get(
        f"/api/v1/profiles/{alice_owner}/documents/{uploaded['id']}", headers=ALICE
    )

    assert response.status_code == 404


def test_duplicate_upload_is_rejected(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    assert _upload(client, ALICE, child["id"]).status_code == 201

    duplicate = _upload(client, ALICE, child["id"])

    assert duplicate.status_code == 400
    assert duplicate.json()["errors"][0]["issue"] == "duplicate-checksum"


def test_declining_a_document_rejects_it(client, fake_ocr) -> None:
    fake_ocr("Patient Name: Ravi Junior")
    child = _create_profile(client, ALICE, "Ravi Junior")
    uploaded = _upload(client, ALICE, child["id"]).json()["data"]
    client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/verify", headers=ALICE
    )

    declined = client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/confirm",
        headers=ALICE,
        json={"confirmed": False},
    ).json()["data"]

    assert declined["uploadStatus"] == "rejected"


def test_confirming_before_verifying_is_rejected(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    uploaded = _upload(client, ALICE, child["id"]).json()["data"]

    response = client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/confirm",
        headers=ALICE,
        json={"confirmed": True},
    )

    assert response.status_code == 409


# ---------------------------------------------------------------------- archive and consent gates


def test_archived_profile_rejects_new_uploads(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    client.post(f"/api/v1/profiles/{child['id']}/archive", headers=ALICE)

    response = _upload(client, ALICE, child["id"])

    assert response.status_code == 403
    assert response.json()["type"].endswith("profile-archived")


def test_archived_profile_is_still_readable(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    client.post(f"/api/v1/profiles/{child['id']}/archive", headers=ALICE)

    response = client.get(f"/api/v1/profiles/{child['id']}/history", headers=ALICE)

    assert response.status_code == 200


def test_owner_profile_cannot_be_archived(client) -> None:
    owner_id = _profiles(client, ALICE)["activeProfileId"]

    response = client.post(f"/api/v1/profiles/{owner_id}/archive", headers=ALICE)

    assert response.status_code == 409


def test_withdrawn_consent_blocks_new_processing(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    client.post(f"/api/v1/profiles/{child['id']}/consent/withdraw", headers=ALICE)

    response = _upload(client, ALICE, child["id"])

    assert response.status_code == 403
    assert response.json()["type"].endswith("consent-required")


def test_consent_can_be_granted_again(client) -> None:
    child = _create_profile(client, ALICE, "Ravi Junior")
    client.post(f"/api/v1/profiles/{child['id']}/consent/withdraw", headers=ALICE)
    client.post(f"/api/v1/profiles/{child['id']}/consent/grant", headers=ALICE)

    assert _upload(client, ALICE, child["id"]).status_code == 201


# ------------------------------------------------------------------------------ summary, audit


def test_profile_summary_is_scoped_to_one_profile(client, fake_ocr) -> None:
    fake_ocr("Patient Name: Ravi Junior")
    child = _create_profile(client, ALICE, "Ravi Junior")
    sibling = _create_profile(client, ALICE, "Nita Junior")
    uploaded = _upload(client, ALICE, child["id"]).json()["data"]
    client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/verify", headers=ALICE
    )
    client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/confirm",
        headers=ALICE,
        json={"confirmed": True},
    )

    sibling_history = client.get(
        f"/api/v1/profiles/{sibling['id']}/history", headers=ALICE
    ).json()["data"]

    assert sibling_history["items"] == []


@pytest.mark.asyncio
async def test_audit_events_carry_no_medical_content(client, fake_ocr) -> None:
    from app.repositories import cosmos_repo

    fake_ocr("Patient Name: Ravi Junior", "Glucose 180 mg/dL", "DOB: 02/06/2014")
    child = _create_profile(client, ALICE, "Ravi Junior")
    uploaded = _upload(client, ALICE, child["id"]).json()["data"]
    client.post(
        f"/api/v1/profiles/{child['id']}/documents/{uploaded['id']}/verify", headers=ALICE
    )

    events = await cosmos_repo.list_audit_events("acct-alice")

    assert events, "expected audit events to be recorded"
    # Generated ids are random hex, so they are excluded: only the human-readable fields are
    # capable of leaking document content.
    opaque_fields = {"id", "accountId", "profileId", "resourceId", "correlationId"}
    for event in events:
        serialized = str(
            {key: value for key, value in event.items() if key not in opaque_fields}
        ).casefold()
        assert "glucose" not in serialized
        assert "180" not in serialized
        assert "ravi junior" not in serialized


@pytest.mark.asyncio
async def test_denied_access_is_audited(client) -> None:
    from app.repositories import cosmos_repo

    bob_profile = _create_profile(client, BOB, "Bob Junior")
    client.get(f"/api/v1/profiles/{bob_profile['id']}", headers=ALICE)

    events = await cosmos_repo.list_audit_events("acct-alice")
    denials = [event for event in events if event["outcome"] == "denied"]

    assert denials
    assert denials[0]["action"] == "authorization.denied"
