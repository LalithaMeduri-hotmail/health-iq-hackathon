"""Profile Match Evaluator rules (services/identity_match.py).

These assert the *deterministic* contract: the same profile and the same extracted identity must
always produce the same verdict, and a positive contradiction must always beat agreement.
All identities here are synthetic.
"""

from datetime import date

import pytest

from app.models.medical_document import ExtractedPatientIdentity, ProfileMatchStatus
from app.models.patient_profile import PatientProfile
from app.services import identity_match


def _profile(name: str = "Asha Ramanathan", dob: date | None = date(1985, 4, 12)) -> PatientProfile:
    return PatientProfile(
        id="pp-test", accountId="acct-1", displayName=name, dateOfBirth=dob
    )


def _identity(name: str | None = None, dob: str | None = None) -> ExtractedPatientIdentity:
    return ExtractedPatientIdentity(patientName=name, dateOfBirth=dob)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Mrs.  Asha   Ramanathan ", "asha ramanathan"),
        ("Dr Asha Ramanathan", "asha ramanathan"),
        ("ASHA RAMANATHAN", "asha ramanathan"),
        ("Asha  Ramanathan,", "asha ramanathan"),
    ],
)
def test_normalize_name_strips_titles_case_and_punctuation(raw: str, expected: str) -> None:
    assert identity_match.normalize_name(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12/04/1985", date(1985, 4, 12)),
        ("1985-04-12", date(1985, 4, 12)),
        ("12 Apr 1985", date(1985, 4, 12)),
        ("12.04.85", date(1985, 4, 12)),
        ("not a date", None),
    ],
)
def test_parse_date_handles_common_document_formats(raw: str, expected: date | None) -> None:
    assert identity_match.parse_date(raw) == expected


def test_exact_name_and_dob_is_a_match() -> None:
    result = identity_match.evaluate(_profile(), _identity("Asha Ramanathan", "12/04/1985"))

    assert result.status == ProfileMatchStatus.MATCH
    assert result.matched_fields == ["patientName", "dateOfBirth"]
    # Even a perfect match still asks the user to confirm - the evaluator produces evidence only.
    assert result.requires_user_confirmation is True


def test_conflicting_dob_is_a_mismatch_even_when_the_name_matches() -> None:
    result = identity_match.evaluate(_profile(), _identity("Asha Ramanathan", "03/09/1990"))

    assert result.status == ProfileMatchStatus.MISMATCH
    assert "dateOfBirth" in result.conflicting_fields


def test_different_name_is_a_mismatch() -> None:
    result = identity_match.evaluate(_profile(), _identity("Vikram Iyer", "12/04/1985"))

    assert result.status == ProfileMatchStatus.MISMATCH
    assert "patientName" in result.conflicting_fields


def test_initials_only_is_a_possible_match_not_a_match() -> None:
    result = identity_match.evaluate(_profile(), _identity("A Ramanathan"))

    assert result.status == ProfileMatchStatus.POSSIBLE_MATCH
    assert result.confidence < 0.8


def test_partial_name_overlap_is_a_possible_match() -> None:
    result = identity_match.evaluate(_profile(), _identity("Asha Kumari"))

    assert result.status == ProfileMatchStatus.POSSIBLE_MATCH


def test_document_without_identity_fields_is_insufficient() -> None:
    result = identity_match.evaluate(_profile(), _identity())

    assert result.status == ProfileMatchStatus.INSUFFICIENT_IDENTITY_DATA
    assert result.confidence == 0.0


def test_ocr_digit_confusion_still_matches_the_name() -> None:
    result = identity_match.evaluate(_profile("John Doe", None), _identity("J0hn D0e"))

    assert result.status == ProfileMatchStatus.MATCH


def test_evaluation_is_deterministic() -> None:
    profile, identity = _profile(), _identity("Asha Ramanathan", "12/04/1985")

    first = identity_match.evaluate(profile, identity)
    second = identity_match.evaluate(profile, identity)

    assert first.model_dump() == second.model_dump()


@pytest.mark.parametrize(
    ("status", "expected_action"),
    [
        (ProfileMatchStatus.MISMATCH, "create_profile"),
        (ProfileMatchStatus.INSUFFICIENT_IDENTITY_DATA, "confirm_explicitly"),
    ],
)
def test_next_actions_offer_a_recovery_path(status: str, expected_action: str) -> None:
    assert expected_action in identity_match.next_actions(status)


def test_mismatch_never_offers_a_plain_confirm() -> None:
    assert "confirm" not in identity_match.next_actions(ProfileMatchStatus.MISMATCH)
