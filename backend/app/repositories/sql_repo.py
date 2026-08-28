"""Azure SQL repository (backend.instructions.md). Owner: D1/D2.

All persistence for `Medicine`, `MedicinePrice`, `LabMetric`, `ShareLink` goes through this
module - no SQL strings anywhere else. Parameterized queries only; never build SQL via string
concatenation/f-strings with user input. AAD-only auth (see infra/modules/sql.bicep).

Demo/dev fallback: when `Settings.demo_mode` is true or `azure_sql_server_fqdn` is unset, the
medicine catalog is served from `data/medicines/medicine_catalog.csv` (see A2/A1 in
docs/lld/2-low-level-design-prescription-medicine-analyzer.md) so match/alternative logic stays
unit-testable without a live database. `list_catalog()` is the single, cached source of truth;
`search_medicine()` is its async wrapper for agent/tool consumption.
"""

import asyncio
import csv
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.models.report import TrendPoint

_CATALOG_CSV_PATH = Path(__file__).resolve().parents[3] / "data" / "medicines" / "medicine_catalog.csv"


@lru_cache
def list_catalog() -> list[dict]:
    """Synchronous, cached catalog load - the single source of truth for match/price logic.

    Demo/dev: reads `data/medicines/medicine_catalog.csv`. Real: TODO(D1) query `Medicine` JOIN
    `MedicinePrice` via pyodbc + AAD token auth once `azure_sql_server_fqdn` is deployed/seeded.
    """
    settings = get_settings()
    if not settings.demo_mode and settings.azure_sql_server_fqdn:
        raise NotImplementedError(
            "Live Azure SQL catalog reads are not wired yet; set DEMO_MODE=true or seed via "
            "scripts/seed_sql.py and implement the pyodbc path here."
        )

    with _CATALOG_CSV_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        row["strengthValue"] = float(row["strengthValue"])
        row["mrpInr"] = float(row["mrpInr"])
        row["isDemoData"] = row["isDemoData"].strip().lower() == "true"
    return rows


def _ingredient_set(value: str) -> frozenset[str]:
    """Split a `+`-joined ingredient string into a normalized multiset for combination-drug matching."""
    return frozenset(part.strip().casefold() for part in value.split("+") if part.strip())


def search_medicine_sync(
    active_ingredient: str, strength_value: float, strength_unit: str, dosage_form: str
) -> list[dict]:
    """Exact match on `(activeIngredient set, strengthValue, strengthUnit, dosageForm)`.

    Combination drugs require an identical ingredient multiset (implementation-plan.md Section 2.3).
    """
    wanted = _ingredient_set(active_ingredient)
    matches = [
        row
        for row in list_catalog()
        if _ingredient_set(row["activeIngredient"]) == wanted
        and row["strengthValue"] == strength_value
        and row["strengthUnit"].casefold() == strength_unit.casefold()
        and row["dosageForm"].casefold() == dosage_form.casefold()
    ]
    return sorted(matches, key=lambda row: row["mrpInr"])


async def search_medicine(active_ingredient: str, strength_value: float, strength_unit: str, dosage_form: str) -> list[dict]:
    """Async wrapper over `search_medicine_sync` for agent/tool consumption."""
    return await asyncio.to_thread(search_medicine_sync, active_ingredient, strength_value, strength_unit, dosage_form)


async def get_trend(user_id: str, canonical_key: str) -> list[TrendPoint]:
    """Longitudinal history for one lab parameter, scoped by `userId`."""
    raise NotImplementedError


async def create_share_link(share_id_hash: str, blob_path: str, expires_at: str) -> None:
    raise NotImplementedError
