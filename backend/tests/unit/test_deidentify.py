"""Unit tests for `services/deidentify.py` PHI redaction (backend.instructions.md)."""

from app.services.deidentify import deidentify


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
