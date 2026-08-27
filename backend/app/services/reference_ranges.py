"""Reference range lookups (implementation-plan.md Section 2.5). Owner: D2.

Backed by `data/reference_ranges/lab_reference_ranges.csv`
(`canonicalKey, sex, ageMin, ageMax, refLow, refHigh, unit, plainLanguage, sourceName, sourceUrl`).
Ranges are labeled educational, never diagnostic.
"""

from app.models.common import SourceRef


def get_reference_range(canonical_key: str, *, sex: str, age: int) -> dict:
    """Return `{ refLow, refHigh, unit, plainLanguage }` for the closest matching age/sex band."""
    raise NotImplementedError


def get_source(canonical_key: str) -> SourceRef:
    """Return the provenance record required by SafetyReviewerAgent rule R2."""
    raise NotImplementedError
