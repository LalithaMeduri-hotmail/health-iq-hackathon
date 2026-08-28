"""PHI de-identification (implementation-plan.md Section 1.5). Owner: D1.

Runs before any OCR text reaches the LLM: regex + Presidio-style redaction of name, phone,
email, MRN, and address. Keep the reversible map in memory only - never persist it.
"""

import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?(?:\d{10}|\d{5}[-.\s]\d{5}|\(\d{3}\)\s?\d{3}[-.\s]?\d{4})")
_MRN_RE = re.compile(r"\b(?:MRN|UHID|Patient\s*ID)[:\s#]*([A-Za-z0-9-]{4,})\b", re.IGNORECASE)
_NAME_RE = re.compile(r"\b(?:Patient|Name|Mr|Mrs|Ms|Dr)\.?\s*[:\-]?[ \t]*([A-Z][a-zA-Z]+(?:[ \t]+[A-Z][a-zA-Z]+){0,2})")
_ADDRESS_RE = re.compile(r"\b(?:Address|Addr)[:\s]*([^\n,]{5,80})", re.IGNORECASE)

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", EMAIL_RE),
    ("PHONE", PHONE_RE),
    ("MRN", _MRN_RE),
    ("ADDRESS", _ADDRESS_RE),
    ("NAME", _NAME_RE),
)


def deidentify(text: str) -> tuple[str, dict[str, str]]:
    """Redact PHI from `text`.

    Returns `(redacted_text, reversible_map)`. `reversible_map` must never be logged or persisted.
    Each match is replaced with a stable placeholder token (`[REDACTED-EMAIL-1]`, ...) so the
    same original value always maps to the same token within one call.
    """
    reversible_map: dict[str, str] = {}
    redacted = text

    for label, pattern in _PATTERNS:
        counter = 0

        def _replace(match: re.Match[str], label: str = label) -> str:
            nonlocal counter
            original = match.group(1) if match.groups() else match.group(0)
            for token, value in reversible_map.items():
                if value == original:
                    return token
            counter += 1
            token = f"[REDACTED-{label}-{counter}]"
            reversible_map[token] = original
            return match.group(0).replace(original, token) if match.groups() else token

        redacted = pattern.sub(_replace, redacted)

    return redacted, reversible_map
