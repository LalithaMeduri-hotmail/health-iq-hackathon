"""Specialist mapping lookups (docs/lld/3-low-level-design-*.md Section 2.4). Owner: D2.

Backed by `data/specialists/specialist_mapping.csv`
(`parameterGroup, canonicalKeys, specialtyCategory, whenToConsult, disclaimer, doctorLinkName,
doctorLinkUrl, sourceName, sourceUrl`), which is also the seed source for `idx-specialists`.

The mapping is curated (assumption A3) and returns specialty *categories* only - never a named
doctor. Every link is flagged `public/demo` (assumption A4), and every row carries provenance so
callers can satisfy NFR2.2 / safety rule R2.
"""

import csv
from functools import lru_cache
from pathlib import Path

from app.errors import NotFoundError
from app.models.common import SourceRef
from app.models.profile import DoctorLink

_MAPPING_CSV_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "specialists" / "specialist_mapping.csv"
)

# Fallback group used when nothing abnormal maps to a specific group (LLD Section 2.9).
GENERAL_GROUP = "general"

# Seed vintage of the curated CSV; surfaced as `sourceDate` on every citation (safety rule R2).
_SOURCE_DATE = "2026-06-01"


@lru_cache
def _load_rows() -> dict[str, dict]:
    """Curated mapping rows keyed by `parameterGroup`; cached because the CSV rarely changes."""
    with _MAPPING_CSV_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    mapping: dict[str, dict] = {}
    for row in rows:
        keys = [key.strip() for key in row["canonicalKeys"].split("|") if key.strip()]
        mapping[row["parameterGroup"]] = {**row, "canonicalKeys": tuple(keys)}
    return mapping


@lru_cache
def _keys_to_group() -> dict[str, str]:
    """Reverse index `canonicalKey -> parameterGroup`; the first seeded group for a key wins."""
    index: dict[str, str] = {}
    for group, row in _load_rows().items():
        for key in row["canonicalKeys"]:
            index.setdefault(key, group)
    return index


def parameter_group_for(canonical_key: str) -> str | None:
    """Group that owns `canonical_key`, or `None` when the key is not mapped to any specialty."""
    return _keys_to_group().get(canonical_key)


def get_mapping(parameter_group: str) -> dict:
    """Return `{ specialtyCategory, whenToConsult, disclaimer }` for one curated group."""
    row = _load_rows().get(parameter_group)
    if row is None:
        raise NotFoundError(f"No specialist mapping seeded for parameter group {parameter_group!r}")
    return {
        "specialtyCategory": row["specialtyCategory"],
        "whenToConsult": row["whenToConsult"],
        "disclaimer": row["disclaimer"],
    }


def get_source(parameter_group: str) -> SourceRef:
    """Return the provenance record required by SafetyReviewerAgent rule R2."""
    row = _load_rows().get(parameter_group)
    if row is None:
        raise NotFoundError(f"No specialist mapping seeded for parameter group {parameter_group!r}")
    return SourceRef(
        sourceName=row["sourceName"], sourceUrl=row["sourceUrl"], sourceDate=_SOURCE_DATE
    )


def get_doctor_link(parameter_group: str) -> DoctorLink:
    """Public/demo directory link for one group; never an endorsement of a named practitioner."""
    row = _load_rows().get(parameter_group)
    if row is None:
        raise NotFoundError(f"No specialist mapping seeded for parameter group {parameter_group!r}")
    return DoctorLink(
        name=row["doctorLinkName"], url=row["doctorLinkUrl"], provenance="public/demo"
    )
