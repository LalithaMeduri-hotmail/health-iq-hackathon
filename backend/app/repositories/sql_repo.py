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
from app.models.report import LabParameter, TrendPoint

_CATALOG_CSV_PATH = Path(__file__).resolve().parents[3] / "data" / "medicines" / "medicine_catalog.csv"
_DEMO_SHARE_LINKS: dict[str, dict] = {}

# Demo `LabMetric` rows keyed by `(userId, canonicalKey, reportId)` so re-analyzing one report
# replaces its metrics instead of duplicating trend points.
_DEMO_LAB_METRICS: dict[tuple[str, str, str], TrendPoint] = {}
_DEMO_LAB_METRICS_SEEDED: set[str] = set()


def _use_demo_store() -> bool:
    settings = get_settings()
    return settings.demo_mode or not settings.azure_sql_server_fqdn


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


async def save_lab_metrics(user_id: str, report_id: str, parameters: list[LabParameter]) -> int:
    """Insert one `LabMetric` row per canonical parameter of an analyzed report (FR2.4).

    Idempotent: re-analyzing the same `report_id` replaces its rows rather than duplicating them.
    Returns the number of persisted rows. Real: TODO(D1) `MERGE` into `LabMetric` via pyodbc.
    """
    settings = get_settings()
    if not settings.demo_mode and settings.azure_sql_server_fqdn:
        raise NotImplementedError(
            "Live Azure SQL LabMetric writes are not wired yet; set DEMO_MODE=true or seed via "
            "scripts/seed_sql.py and implement the pyodbc path here."
        )

    await _seed_demo_lab_metrics(user_id)
    for parameter in parameters:
        _DEMO_LAB_METRICS[(user_id, parameter.canonical_key, report_id)] = TrendPoint(
            reportDate=parameter.report_date, value=parameter.value
        )
    return len(parameters)


async def _seed_demo_lab_metrics(user_id: str) -> None:
    """Back-fill the demo `LabMetric` store from the recorded report history, once per user.

    Keeps trend charts populated for the seeded demo history without a live `LabMetric` table.
    """
    if user_id in _DEMO_LAB_METRICS_SEEDED:
        return
    _DEMO_LAB_METRICS_SEEDED.add(user_id)

    from app.repositories.cosmos_repo import list_reports

    for report in await list_reports(user_id):
        for parameter in report.parameters:
            _DEMO_LAB_METRICS.setdefault(
                (user_id, parameter.canonical_key, report.id),
                TrendPoint(reportDate=parameter.report_date, value=parameter.value),
            )


async def get_trend(user_id: str, canonical_key: str) -> list[TrendPoint]:
    """Longitudinal history for one lab parameter, scoped by `userId`.

    Demo/dev: served from the in-process `LabMetric` store, back-filled from the same recorded
    report history the `reports` container serves. Real: TODO(D1) query `LabMetric` over
    `IX_LabMetric_Trend(UserId, CanonicalKey, ReportDate)`.
    """
    settings = get_settings()
    if not settings.demo_mode and settings.azure_sql_server_fqdn:
        raise NotImplementedError(
            "Live Azure SQL LabMetric reads are not wired yet; set DEMO_MODE=true or seed via "
            "scripts/seed_sql.py and implement the pyodbc path here."
        )

    await _seed_demo_lab_metrics(user_id)
    points = [
        point
        for (owner, key, _report_id), point in _DEMO_LAB_METRICS.items()
        if owner == user_id and key == canonical_key
    ]
    return sorted(points, key=lambda point: point.report_date)


async def create_share_link(share_id_hash: str, blob_path: str, expires_at: str) -> None:
    """Insert one `ShareLink` row. Only the SHA-256 hash of the token is ever stored."""
    if _use_demo_store():
        _DEMO_SHARE_LINKS[share_id_hash] = {"blobPath": blob_path, "expiresAt": expires_at, "accessCount": 0}
        return
    raise NotImplementedError(
        "Live Azure SQL ShareLink writes are not wired yet; set DEMO_MODE=true or implement the pyodbc path here."
    )


async def get_share_link(share_id_hash: str) -> dict | None:
    """Look up one `ShareLink` row by token hash; returns `None` when the token is unknown."""
    if _use_demo_store():
        return _DEMO_SHARE_LINKS.get(share_id_hash)
    raise NotImplementedError(
        "Live Azure SQL ShareLink reads are not wired yet; set DEMO_MODE=true or implement the pyodbc path here."
    )
