"""Tells a prescription apart from a lab report, so each upload lands on the right feature.

Both analyzers accept the same file types, so without this an uploaded lab report is happily
parsed as a prescription (and vice versa) and the user sees medicines that are not on their
document. Signal counting only - no LLM, no network - so the verdict is deterministic and
testable (agents.instructions.md: classification stays in Python).
"""

import re

DocumentKind = str  # "prescription" | "lab_report" | "unknown"

# Lab-report markers: result tables, ranges, and canonical analyte names.
_LAB_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\breference\s+range\b", re.I),
    re.compile(r"\breport\s+date\b", re.I),
    re.compile(r"\b(?:biochemistry|haematology|hematology|pathology|diagnostics|laborator)", re.I),
    re.compile(r"\b(?:hba1c|glycated|haemoglobin|hemoglobin|creatinine)\b", re.I),
    re.compile(r"\b(?:cholesterol|triglyceride|bilirubin|albumin)\b", re.I),
    re.compile(r"\b(?:ldl|hdl|tsh|fbs|vitamin\s*d)\b", re.I),
    re.compile(r"\b(?:mg/dl|g/dl|ng/ml|miu/l|mmol/l)\b", re.I),
    re.compile(r"\bspecimen|\bsample\s+type|\bcollected\s+on", re.I),
)

# Prescription markers: dosing shorthand, prescriber furniture, and dispensing verbs.
_RX_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:^|\s)Rx(?:\s|$|\.)", re.I),
    re.compile(r"\b\d-\d-\d\b"),  # 1-0-1 dosing
    re.compile(r"\bx\s?\d+\s?days?\b", re.I),
    re.compile(r"\b(?:tablet|tab\.|capsule|cap\.|syrup|ointment|mg\b|mcg\b)", re.I),
    re.compile(r"\b(?:once|twice|thrice)\s+(?:a\s+)?daily\b", re.I),
    re.compile(r"\b(?:after|before)\s+(?:food|meals?)\b", re.I),
    re.compile(r"\b(?:MBBS|MD|prescriber|clinic|prescription)\b", re.I),
)


def _score(text: str, patterns: tuple[re.Pattern[str], ...]) -> int:
    return sum(1 for pattern in patterns if pattern.search(text))


def classify(text: str) -> DocumentKind:
    """Best-effort document kind. Returns `"unknown"` when neither side has enough signal."""
    if not text or not text.strip():
        return "unknown"

    lab = _score(text, _LAB_PATTERNS)
    rx = _score(text, _RX_PATTERNS)

    # A lab report mentions "mg/dL" and analyte names far more distinctively than a prescription
    # mentions dosing, so require a clear margin rather than a bare majority.
    if lab >= 3 and lab > rx:
        return "lab_report"
    if rx >= 3 and rx > lab:
        return "prescription"
    if lab >= 2 and rx == 0:
        return "lab_report"
    if rx >= 2 and lab == 0:
        return "prescription"
    return "unknown"


def text_of(lines: list[str], tables: list[list[list[str]]] | None = None) -> str:
    """Flatten an OCR envelope's lines and table cells into one blob for classification."""
    parts = list(lines)
    for table in tables or []:
        for row in table:
            parts.extend(row)
    return "\n".join(parts)
