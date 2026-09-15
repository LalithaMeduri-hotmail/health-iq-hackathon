"""Unit tests for `services/deidentify.py` PHI redaction (backend.instructions.md)."""

from app.services.deidentify import deidentify, find_patient_name


def test_deidentify_redacts_email_and_phone() -> None:
    text = "Contact Rohan at rohan.sharma@example.com or 9876543210 for follow-up."

    redacted, reversible_map = deidentify(text)

    assert "rohan.sharma@example.com" not in redacted
    assert "9876543210" not in redacted
    assert any(value == "rohan.sharma@example.com" for value in reversible_map.values())
    assert any(value == "9876543210" for value in reversible_map.values())


def test_deidentify_redacts_patient_name_line() -> None:
    text = "Patient: Rohan Sharma\nGlycomet 500mg 1-0-1 x10 days"

    redacted, _ = deidentify(text)

    assert "Rohan Sharma" not in redacted
    assert "Glycomet 500mg 1-0-1 x10 days" in redacted


def test_deidentify_is_idempotent_for_repeated_values() -> None:
    text = "Email a@b.com and again a@b.com"

    redacted, reversible_map = deidentify(text)

    tokens = [token for token in reversible_map if reversible_map[token] == "a@b.com"]
    assert len(tokens) == 1
    assert redacted.count(tokens[0]) == 2


def test_find_patient_name_reads_the_prescription_header() -> None:
    text = "City Clinic\nPatient Name: Ramesh Kumar\nGlycomet 500mg 1-0-1 x10 days"

    assert find_patient_name(text) == "Ramesh Kumar"


def test_find_patient_name_prefers_the_patient_over_the_prescriber() -> None:
    text = "Dr. Ashok Mehta, MBBS MD\nPatient: Ramesh Kumar\nGlycomet 500mg"

    assert find_patient_name(text) == "Ramesh Kumar"


def test_find_patient_name_returns_nothing_when_the_header_has_none() -> None:
    assert find_patient_name("Glycomet 500mg 1-0-1 x10 days") is None
