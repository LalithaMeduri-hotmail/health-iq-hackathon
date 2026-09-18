"""Uploads land on the right feature, and a digital PDF is read rather than replayed.

Guards the two failure modes a user actually hit: a lab report analyzed as a prescription (so
they were asked to confirm medicines that were not on their document), and uploads returning
fixture content regardless of the file.
"""

from pathlib import Path

import pytest

from app.services import document_type
from app.services.ocr import extract

SAMPLES = Path(__file__).resolve().parents[3] / "data" / "samples" / "documents"
PRESCRIPTION_PDF = SAMPLES / "prescription-01-three-medicines.pdf"
LAB_REPORT_PDF = SAMPLES / "lab-report-01-older-2026-03-10.pdf"


def _read(path: Path) -> bytes:
    """Skip only the tests needing a given sample, so one missing file cannot mask the rest."""
    if not path.exists():
        pytest.skip(f"missing sample document: {path.name}")
    return path.read_bytes()


def test_classifier_separates_the_two_document_kinds() -> None:
    assert (
        document_type.classify("Rx\n1. Glycomet 500mg 1-0-1 x10 days\nDr. A Mehta MBBS")
        == "prescription"
    )
    assert (
        document_type.classify("Report Date: 2026-03-10\nHbA1c 6.4 %\nReference Range\nmg/dL")
        == "lab_report"
    )
    assert document_type.classify("") == "unknown"
    assert document_type.classify("hello world") == "unknown"


async def test_a_digital_pdf_is_read_not_replayed() -> None:
    envelope = await extract(_read(PRESCRIPTION_PDF), mode="read")
    text = "\n".join(line.text for line in envelope.lines)

    assert "Glycomet 500mg 1-0-1 x10 days" in text
    # The prescription fixture that would otherwise be replayed names a different prescriber.
    assert "Demo Clinic" in text
    assert all(line.confidence == 1.0 for line in envelope.lines)


async def test_a_lab_table_survives_pdf_extraction() -> None:
    envelope = await extract(_read(LAB_REPORT_PDF), mode="layout")

    assert envelope.tables, "the analyte table should be reconstructed from the flattened text"
    header, *rows = envelope.tables[0]
    assert header == ["Test", "Result", "Unit", "Reference Range"]
    assert ["FBS", "118", "mg/dL", "70 - 99"] in rows
    # The footer below the table must not be swept in as a data row.
    assert all(len(row) == len(header) for row in rows)


async def test_every_sample_photo_has_its_own_fixture() -> None:
    """An image cannot be read locally, so its replayed fixture is what the app reports.

    One fixture per photo, each replaying distinct medicines - otherwise a demo shows medicines
    that are not on the picture the audience is looking at.
    """
    photos = sorted((SAMPLES.parent / "photoes").glob("prescription-photo-*.jpg"))
    if not photos:
        pytest.skip("no sample prescription photos generated")

    from app.services import ocr

    assert len(ocr._DEMO_READ_FIXTURES) == len(photos)

    ocr._demo_read_calls = 0
    leads = []
    for _ in photos:
        envelope = await extract(b"\xff\xd8\xff not a readable jpeg", mode="read")
        leads.append(envelope.lines[2].text)

    assert len(set(leads)) == len(photos)


async def test_image_ocr_confidence_drives_the_confirmation_gate(monkeypatch) -> None:
    """A photo's own OCR score decides which lines the user must check.

    Tesseract is optional, so the recogniser is stubbed: what is under test is that per-word
    confidence becomes per-line confidence, and that a poorly-read line lands below the gate.
    """
    from app.services import normalize_medicine, ocr

    class _FakeTesseract:
        Output = type("Output", (), {"DICT": "dict"})

        @staticmethod
        def image_to_data(_image, output_type=None):
            return {
                "text": ["Glycomet", "500mg", "Amlong", "5mg"],
                "conf": [96, 94, 41, 38],
                "block_num": [1, 1, 1, 1],
                "par_num": [1, 1, 1, 1],
                "line_num": [1, 1, 2, 2],
            }

    monkeypatch.setitem(__import__("sys").modules, "pytesseract", _FakeTesseract)

    photo = (SAMPLES.parent / "photoes" / "prescription-photo-01.jpg")
    if not photo.exists():
        pytest.skip("no sample prescription photo generated")

    envelope = await ocr.extract(photo.read_bytes(), mode="read")

    assert [line.text for line in envelope.lines] == ["Glycomet 500mg", "Amlong 5mg"]
    assert envelope.lines[0].confidence == pytest.approx(0.95)
    assert envelope.lines[1].confidence == pytest.approx(0.395)

    items = normalize_medicine.normalize(envelope)
    by_brand = {item.brand_name: item for item in items}
    assert by_brand["Glycomet"].needs_user_confirmation is False
    assert by_brand["Amlong"].needs_user_confirmation is True


def test_lab_report_is_rejected_by_the_prescription_analyzer(client) -> None:
    response = client.post(
        "/api/v1/prescriptions/analyze",
        data={"consent": "true"},
        files={"file": ("report.pdf", _read(LAB_REPORT_PDF), "application/pdf")},
    )

    assert response.status_code == 422
    problem = response.json()
    assert problem["type"] == "https://healthiq/errors/wrong-document-type"
    assert "lab report" in problem["detail"]


def test_prescription_is_rejected_by_the_report_analyzer(client) -> None:
    response = client.post(
        "/api/v1/reports/analyze",
        data={"consent": "true"},
        files={"file": ("rx.pdf", _read(PRESCRIPTION_PDF), "application/pdf")},
    )

    assert response.status_code == 422
    problem = response.json()
    assert problem["type"] == "https://healthiq/errors/wrong-document-type"
    assert "prescription" in problem["detail"]


def test_matching_documents_still_analyze(client) -> None:
    prescription = client.post(
        "/api/v1/prescriptions/analyze",
        data={"consent": "true"},
        files={"file": ("rx.pdf", _read(PRESCRIPTION_PDF), "application/pdf")},
    )
    assert prescription.status_code == 200
    brands = [item["brandName"] for item in prescription.json()["data"]["items"]]
    assert brands == ["Glycomet", "Amlong", "Atocor"]

    # The sample report names a patient who is not the account owner, so it has to be filed
    # under that patient's own profile before it is analyzed.
    blocked = client.post(
        "/api/v1/reports/analyze",
        data={"consent": "true"},
        files={"file": ("report.pdf", _read(LAB_REPORT_PDF), "application/pdf")},
    )
    assert blocked.status_code == 422
    assert blocked.json()["type"] == "https://healthiq/errors/profile-mismatch"

    patient = client.post(
        "/api/v1/profiles",
        json={
            "displayName": "Rohan Sharma",
            "relationshipToAccountOwner": "child",
            "consentAccepted": True,
        },
    ).json()["data"]

    report = client.post(
        "/api/v1/reports/analyze",
        data={"consent": "true", "profileId": patient["id"]},
        files={"file": ("report.pdf", _read(LAB_REPORT_PDF), "application/pdf")},
    )
    assert report.status_code == 200
    data = report.json()["data"]
    assert data["reportDate"] == "2026-03-10"
    assert {p["displayName"] for p in data["parameters"]} >= {"FBS", "LDL-C", "Haemoglobin"}
