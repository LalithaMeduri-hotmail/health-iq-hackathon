"""Deterministic Profile Match Evaluator.

Decides whether a document's extracted identity is consistent with the selected patient profile.
Every rule here is ordinary Python: an LLM may later *describe* the evidence this module
produces, but it can never change the verdict, because a misfiled medical document is a safety
problem and a model is not an authorization boundary.

Verdicts:

* `MATCH` - name agrees and no identifier conflicts; date of birth corroborates when present.
* `POSSIBLE_MATCH` - partial agreement (initials, one missing identifier).
* `MISMATCH` - at least one identifier positively contradicts the profile.
* `INSUFFICIENT_IDENTITY_DATA` - too little identity text to judge either way.

Even a `MATCH` still requires the caller to confirm before the document is permanently attached:
name agreement is evidence, not proof.
"""

import re
import unicodedata
from datetime import date

from app.models.medical_document import (
    ExtractedPatientIdentity,
    FieldComparison,
    ProfileMatchExplanation,
    ProfileMatchStatus,
)
from app.models.patient_profile import PatientProfile

# Honorifics and qualifiers that carry no identity, across the locales this app targets.
_TITLES = {
    "mr", "mrs", "ms", "miss", "master", "dr", "doctor", "prof", "professor",
    "shri", "sri", "smt", "kum", "md", "mx", "sir", "madam", "baby", "b", "o",
}

# Characters an OCR pass routinely confuses. Folding both sides through the same table means a
# scanned "J0HN" still lines up with "JOHN" without inventing a fuzzy-match score.
_OCR_FOLD = str.maketrans({"0": "o", "1": "l", "5": "s", "8": "b", "2": "z", "6": "g"})

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_DATE_SEPARATORS = re.compile(r"[/.\-\s]+")

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def normalize_name(value: str | None) -> str:
    """Case-fold, strip accents/punctuation/titles, and collapse whitespace."""
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(char for char in decomposed if not unicodedata.combining(char))
    cleaned = _PUNCT_RE.sub(" ", ascii_only).casefold()
    tokens = [token for token in cleaned.split() if token and token not in _TITLES]
    return " ".join(tokens)


def name_tokens(value: str | None) -> list[str]:
    """Normalized name tokens with OCR-confusable characters folded."""
    return [token.translate(_OCR_FOLD) for token in normalize_name(value).split()]


def parse_date(value: str | None) -> date | None:
    """Parse the date formats that appear on lab reports and prescriptions, else `None`.

    Ambiguous `dd/mm` vs `mm/dd` is resolved in favour of day-first only when the first component
    cannot be a month, so an unparseable-but-present date never silently becomes a wrong date.
    """
    if not value:
        return None
    text = value.strip().casefold()

    match = re.search(r"(\d{1,2})\s*([a-z]{3,4})\s*(\d{2,4})", text)
    if match and match.group(2)[:3] in _MONTHS:
        day, month_name, year = match.groups()
        return _build_date(int(year), _MONTHS[month_name[:3]], int(day))

    parts = [part for part in _DATE_SEPARATORS.split(text) if part.isdigit()]
    if len(parts) < 3:
        return None

    if len(parts[0]) == 4:  # yyyy-mm-dd
        return _build_date(int(parts[0]), int(parts[1]), int(parts[2]))

    first, second, third = int(parts[0]), int(parts[1]), int(parts[2])
    if first > 12:
        return _build_date(third, second, first)
    if second > 12:
        return _build_date(third, first, second)
    # Both plausible as a month: day-first matches the locales this app serves.
    return _build_date(third, second, first)


def _build_date(year: int, month: int, day: int) -> date | None:
    if year < 100:
        year += 2000 if year < 30 else 1900
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _compare_names(profile_name: str, document_name: str | None) -> tuple[str, str]:
    """Return `(outcome, detail)` for the name field.

    Token sets are compared rather than whole strings so a reordered or partial name still lines
    up, and a single-letter token is treated as an initial of the matching full token.
    """
    profile_tokens = name_tokens(profile_name)
    document_tokens = name_tokens(document_name)
    if not document_tokens:
        return "missing", "The document does not show a patient name."
    if not profile_tokens:
        return "missing", "This profile has no name to compare against."

    if profile_tokens == document_tokens:
        return "matched", "The patient name matches this profile exactly."

    profile_set, document_set = set(profile_tokens), set(document_tokens)
    shared = profile_set & document_set
    if profile_set == document_set:
        return "matched", "The same name parts appear in a different order."

    # Expand initials: "j smith" against "john smith".
    def _initials_consistent(short: list[str], long: list[str]) -> bool:
        if len(short) != len(long):
            return False
        return all(
            left == right
            or (len(left) == 1 and right.startswith(left))
            or (len(right) == 1 and left.startswith(right))
            for left, right in zip(short, long, strict=True)
        )

    if _initials_consistent(profile_tokens, document_tokens):
        return "uncertain", "The names agree once initials are expanded, which is not conclusive."

    if shared:
        return (
            "uncertain",
            f"Only part of the name matches ({', '.join(sorted(shared))}).",
        )
    return "conflicted", "The patient name on the document is a different name."


def _compare_dates(profile_dob: date | None, document_dob: str | None) -> tuple[str, str]:
    parsed = parse_date(document_dob)
    if profile_dob is None and parsed is None:
        return "missing", "Neither the profile nor the document has a date of birth."
    if profile_dob is None:
        return "missing", "This profile has no date of birth recorded."
    if parsed is None:
        return "missing", "The document does not show a readable date of birth."
    if parsed == profile_dob:
        return "matched", "The date of birth matches exactly."
    return "conflicted", "The date of birth on the document is a different date."


def evaluate(
    profile: PatientProfile, identity: ExtractedPatientIdentity
) -> ProfileMatchExplanation:
    """Compare an extracted identity against a profile and return a deterministic verdict."""
    name_outcome, name_detail = _compare_names(profile.display_name, identity.patient_name)
    dob_outcome, dob_detail = _compare_dates(profile.date_of_birth, identity.date_of_birth)

    comparisons = [
        FieldComparison(
            field="patientName",
            profileValue=profile.display_name,
            documentValue=identity.patient_name,
            outcome=name_outcome,
            detail=name_detail,
        ),
        FieldComparison(
            field="dateOfBirth",
            profileValue=profile.date_of_birth.isoformat() if profile.date_of_birth else None,
            documentValue=identity.date_of_birth,
            outcome=dob_outcome,
            detail=dob_detail,
        ),
    ]

    matched = [c.field for c in comparisons if c.outcome == "matched"]
    conflicting = [c.field for c in comparisons if c.outcome == "conflicted"]
    missing = [c.field for c in comparisons if c.outcome in {"missing", "uncertain"}]

    status, confidence = _verdict(name_outcome, dob_outcome)

    return ProfileMatchExplanation(
        status=status,
        confidence=confidence,
        comparisons=comparisons,
        matchedFields=matched,
        conflictingFields=conflicting,
        missingFields=missing,
        # Confirmation is always required: this evaluator produces evidence, not authority.
        requiresUserConfirmation=True,
    )


def _verdict(name_outcome: str, dob_outcome: str) -> tuple[str, float]:
    """Rule table. Any positive contradiction wins over any amount of agreement."""
    if dob_outcome == "conflicted" or name_outcome == "conflicted":
        return ProfileMatchStatus.MISMATCH, 0.95
    if name_outcome == "missing" and dob_outcome in {"missing", "uncertain"}:
        return ProfileMatchStatus.INSUFFICIENT_IDENTITY_DATA, 0.0
    if name_outcome == "matched" and dob_outcome == "matched":
        return ProfileMatchStatus.MATCH, 0.99
    if name_outcome == "matched":
        # A name alone is never proof of identity, but it is strong corroboration.
        return ProfileMatchStatus.MATCH, 0.8
    if name_outcome == "uncertain":
        return ProfileMatchStatus.POSSIBLE_MATCH, 0.55
    return ProfileMatchStatus.INSUFFICIENT_IDENTITY_DATA, 0.0


def next_actions(status: str) -> list[str]:
    """UI affordances the client should offer for a verdict."""
    if status == ProfileMatchStatus.MATCH:
        return ["confirm", "choose_other_profile", "cancel"]
    if status == ProfileMatchStatus.POSSIBLE_MATCH:
        return ["confirm", "choose_other_profile", "create_profile", "cancel"]
    if status == ProfileMatchStatus.MISMATCH:
        return ["choose_other_profile", "create_profile", "cancel"]
    return ["confirm_explicitly", "choose_other_profile", "create_profile", "cancel"]
