"""Identity Evidence Extractor.

Turns an OCR envelope into a structured `IdentityEvidence`: what identity fields the document
shows, the line each came from, and how confident the OCR pass was. It records what is *missing*
and what *conflicts* as first-class results, because "we could not read a date of birth" and
"the date of birth is wrong" lead to completely different user flows.

This module never decides ownership. It only reports evidence; `services/identity_match.py`
applies the rules.
"""

import re
from collections.abc import Callable

from app.models.medical_document import (
    DocumentType,
    ExtractedPatientIdentity,
    FieldEvidence,
    IdentityEvidence,
)
from app.services.identity_match import parse_date
from app.services.ocr import OcrEnvelope

_DOB_RE = re.compile(
    r"\b(?:d\.?o\.?b\.?|date\s+of\s+birth|birth\s*date|born)\b\s*[:\-]?\s*"
    r"([0-9]{1,4}[\s/.\-][0-9a-zA-Z]{1,9}[\s/.\-][0-9]{2,4})",
    re.IGNORECASE,
)
_AGE_RE = re.compile(r"\b(?:age|aged)\b\s*[:\-]?\s*(\d{1,3})\s*(?:y(?:ea)?rs?|y)?\b", re.IGNORECASE)
_SEX_RE = re.compile(r"\b(?:sex|gender)\b\s*[:\-]?\s*(male|female|m|f|other)\b", re.IGNORECASE)
_DOC_DATE_RE = re.compile(
    r"\b(?:report(?:ed)?\s*(?:date|on)|collected(?:\s*on)?|date|issued|prescribed\s*on)\b"
    r"\s*[:\-]?\s*([0-9]{1,4}[\s/.\-][0-9a-zA-Z]{1,9}[\s/.\-][0-9]{2,4})",
    re.IGNORECASE,
)
_FACILITY_RE = re.compile(
    r"^(.{3,60}?(?:hospital|clinic|laborator(?:y|ies)|labs?|diagnostics?|medical\s+cent(?:re|er)))\b",
    re.IGNORECASE,
)
_DOCTOR_RE = re.compile(
    r"\bdr\.?\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})",
)

# Whole-word patient-name capture. `Dr` is deliberately absent: a prescription also names the
# prescriber, and offering the clinician back as "the patient" would be actively misleading.
_PATIENT_NAME_RE = re.compile(
    r"\b(?:patient(?:'s)?(?:\s+name)?|name)\b\s*[:\-]\s*"
    r"([A-Za-z][A-Za-z.\-]*(?:\s+[A-Za-z][A-Za-z.\-]*){0,3})",
    re.IGNORECASE,
)

# Lab headers pack several fields onto one line ("Patient: Rohan Sharma    Age/Sex: 42 / M"), so
# the capture above runs past the name and into the next label unless it is cut here.
_NAME_STOP_TOKENS = {
    "age",
    "sex",
    "gender",
    "dob",
    "date",
    "id",
    "uhid",
    "mrn",
    "ref",
    "referred",
    "reg",
    "lab",
    "report",
    "collected",
    "visit",
}


def _trim_at_next_label(value: str) -> str:
    """Keep the name tokens that appear before the next field label on the same line."""
    kept: list[str] = []
    for token in value.split():
        if token.strip(".:-/").casefold() in _NAME_STOP_TOKENS:
            break
        kept.append(token)
    return " ".join(kept)


def _find(
    pattern: re.Pattern[str], lines: list[tuple[str, float]]
) -> tuple[str | None, float, str | None]:
    """First capture of `pattern` across `lines`, with that line's OCR confidence and raw text."""
    for text, confidence in lines:
        match = pattern.search(text)
        if match:
            value = " ".join(match.group(1).split())
            if value:
                return value, confidence, text
    return None, 0.0, None


def extract(envelope: OcrEnvelope) -> IdentityEvidence:
    """Read identity fields off an OCR envelope."""
    lines = [(line.text, line.confidence) for line in envelope.lines if line.text.strip()]
    joined = "\n".join(text for text, _ in lines)

    fields: list[FieldEvidence] = []

    def _record(
        field: str,
        pattern: re.Pattern[str],
        clean: Callable[[str], str] | None = None,
    ) -> str | None:
        value, confidence, raw = _find(pattern, lines)
        if value and clean:
            value = clean(value) or None
        fields.append(
            FieldEvidence(field=field, value=value, rawText=raw, confidence=confidence)
        )
        return value

    patient_name = _record("patientName", _PATIENT_NAME_RE, _trim_at_next_label)
    date_of_birth = _record("dateOfBirth", _DOB_RE)
    age_text = _record("age", _AGE_RE)
    sex = _record("sex", _SEX_RE)
    document_date = _record("documentDate", _DOC_DATE_RE)
    facility = _record("facilityName", _FACILITY_RE)
    doctor = _record("doctorName", _DOCTOR_RE)

    identity = ExtractedPatientIdentity(
        patientName=patient_name,
        dateOfBirth=date_of_birth,
        age=int(age_text) if age_text and age_text.isdigit() else None,
        sex=_normalize_sex(sex),
        documentDate=document_date,
        facilityName=facility,
        doctorName=doctor,
        documentType=_classify(joined),
        extractionConfidence=_overall_confidence(fields),
    )

    missing = [field.field for field in fields if field.value is None]
    return IdentityEvidence(
        identity=identity,
        fields=fields,
        missingFields=missing,
        conflictingFields=_conflicts(identity),
    )


def _normalize_sex(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.casefold()
    if lowered in {"m", "male"}:
        return "male"
    if lowered in {"f", "female"}:
        return "female"
    return "other"


def _overall_confidence(fields: list[FieldEvidence]) -> float:
    """Mean confidence of the identity fields that were actually found."""
    found = [field.confidence for field in fields if field.value is not None]
    return round(sum(found) / len(found), 3) if found else 0.0


def _conflicts(identity: ExtractedPatientIdentity) -> list[str]:
    """Internal contradictions within one document (not comparisons against a profile)."""
    conflicts: list[str] = []
    dob = parse_date(identity.date_of_birth)
    document_date = parse_date(identity.document_date)
    if dob and identity.age is not None and document_date:
        implied = document_date.year - dob.year
        if abs(implied - identity.age) > 1:
            conflicts.append("age-disagrees-with-dateOfBirth")
    return conflicts


def _classify(text: str) -> str:
    """Coarse document kind from the OCR text, reusing the feature-level classifier."""
    from app.services import document_type

    kind = document_type.classify(text)
    if kind == "lab_report":
        return DocumentType.LAB_REPORT
    if kind == "prescription":
        return DocumentType.PRESCRIPTION
    return DocumentType.UNKNOWN
