"""Unit tests for `agents/safety_agent.py` rules R1-R6 (agents.instructions.md)."""

from app.agents.safety_agent import review
from app.models.common import DISCLAIMER_TEXT


def _base_payload(**overrides) -> dict:
    payload = {
        "items": [{"lineId": "li-1", "ocrConfidence": 0.9, "needsUserConfirmation": False}],
        "disclaimers": [DISCLAIMER_TEXT],
    }
    payload.update(overrides)
    return payload


def test_review_passes_clean_payload() -> None:
    verdict = review(_base_payload())

    assert verdict.passed is True
    assert verdict.violations == []


def test_review_flags_missing_disclaimer() -> None:
    verdict = review(_base_payload(disclaimers=["some other text"]))

    assert verdict.passed is False
    assert any(v.startswith("R1") for v in verdict.violations)


def test_review_flags_banned_phrase() -> None:
    verdict = review(_base_payload(disclaimers=[DISCLAIMER_TEXT, "You have a condition"]))

    assert verdict.passed is False
    assert any(v.startswith("R3") for v in verdict.violations)


def test_review_flags_alternative_missing_doctor_approval() -> None:
    payload = _base_payload(
        alternatives=[
            {
                "original": "Brand A 500 mg",
                "doctorApprovalRequired": False,
                "savingsEstimated": True,
                "source": {"sourceUrl": "https://example.com", "sourceDate": "2026-01-01"},
            }
        ]
    )

    verdict = review(payload)

    assert verdict.passed is False
    assert any(v.startswith("R4") for v in verdict.violations)


def test_review_flags_alternative_missing_source() -> None:
    payload = _base_payload(
        alternatives=[
            {
                "original": "Brand A 500 mg",
                "doctorApprovalRequired": True,
                "savingsEstimated": True,
                "source": {},
            }
        ]
    )

    verdict = review(payload)

    assert verdict.passed is False
    assert any(v.startswith("R2") for v in verdict.violations)


def test_review_flags_low_confidence_without_confirmation_flag() -> None:
    payload = _base_payload(items=[{"lineId": "li-1", "ocrConfidence": 0.5, "needsUserConfirmation": False}])

    verdict = review(payload)

    assert verdict.passed is False
    assert any(v.startswith("R5") for v in verdict.violations)


def test_review_flags_leaked_phi() -> None:
    verdict = review(_base_payload(disclaimers=[DISCLAIMER_TEXT, "contact patient@example.com"]))

    assert verdict.passed is False
    assert any(v.startswith("R6") for v in verdict.violations)


def test_review_fails_closed_on_non_dict_payload() -> None:
    verdict = review(["not", "a", "dict"])

    assert verdict.passed is False
    assert verdict.violations
