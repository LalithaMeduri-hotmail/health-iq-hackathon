"""Reference range lookups (implementation-plan.md Section 2.5). Owner: D2.

Backed by `data/reference_ranges/lab_reference_ranges.csv`
(`canonicalKey, sex, ageMin, ageMax, refLow, refHigh, unit, plainLanguage, sourceName, sourceUrl`).
Ranges are labeled educational, never diagnostic.
"""

import csv
from functools import lru_cache
from pathlib import Path

from app.errors import NotFoundError
from app.models.common import SourceRef

_RANGES_CSV_PATH = Path(__file__).resolve().parents[3] / "data" / "reference_ranges" / "lab_reference_ranges.csv"

DEFAULT_SEX = "any"
DEFAULT_AGE = 35

# Seed vintage of the curated CSV; surfaced as `sourceDate` on every citation (safety rule R2).
_SOURCE_DATE = "2026-06-01"


@lru_cache
def _load_ranges() -> list[dict]:
    with _RANGES_CSV_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        row["ageMin"] = int(row["ageMin"])
        row["ageMax"] = int(row["ageMax"])
        row["refLow"] = float(row["refLow"])
        row["refHigh"] = float(row["refHigh"])
    return rows


def _match_row(canonical_key: str, sex: str, age: int) -> dict | None:
    candidates = [
        row for row in _load_ranges() if row["canonicalKey"] == canonical_key and row["ageMin"] <= age <= row["ageMax"]
    ]
    if not candidates:
        return None
    sex_initial = (sex or DEFAULT_SEX).strip().upper()[:1]
    # A sex-specific band wins; the "any" band is the fallback so every seeded key stays resolvable.
    return next((row for row in candidates if row["sex"].upper()[:1] == sex_initial), None) or next(
        (row for row in candidates if row["sex"] == DEFAULT_SEX), None
    )


def get_reference_range(canonical_key: str, *, sex: str = DEFAULT_SEX, age: int = DEFAULT_AGE) -> dict:
    """Return `{ refLow, refHigh, unit, plainLanguage }` for the closest matching age/sex band."""
    row = _match_row(canonical_key, sex, age)
    if row is None:
        raise NotFoundError(f"No reference range seeded for parameter {canonical_key!r}")
    return {
        "refLow": row["refLow"],
        "refHigh": row["refHigh"],
        "unit": row["unit"],
        "plainLanguage": row["plainLanguage"],
    }


def get_source(canonical_key: str) -> SourceRef:
    """Return the provenance record required by SafetyReviewerAgent rule R2."""
    row = _match_row(canonical_key, DEFAULT_SEX, DEFAULT_AGE)
    if row is None:
        raise NotFoundError(f"No reference range seeded for parameter {canonical_key!r}")
    return SourceRef(sourceName=row["sourceName"], sourceUrl=row["sourceUrl"], sourceDate=_SOURCE_DATE)


def classify_status(value: float, ref_low: float | None, ref_high: float | None) -> str:
    """`low | normal | high` for a value against its band; an unknown band reads as `normal`."""
    if ref_low is not None and value < ref_low:
        return "low"
    if ref_high is not None and value > ref_high:
        return "high"
    return "normal"
