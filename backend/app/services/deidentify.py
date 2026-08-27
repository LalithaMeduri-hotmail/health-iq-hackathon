"""PHI de-identification (implementation-plan.md Section 1.5). Owner: D1.

Runs before any OCR text reaches the LLM: regex + Presidio-style redaction of name, phone,
email, MRN, and address. Keep the reversible map in memory only - never persist it.
"""


def deidentify(text: str) -> tuple[str, dict[str, str]]:
    """Redact PHI from `text`.

    Returns `(redacted_text, reversible_map)`. `reversible_map` must never be logged or persisted.
    """
    raise NotImplementedError
