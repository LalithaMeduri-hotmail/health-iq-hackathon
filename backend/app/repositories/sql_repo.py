"""Azure SQL repository (backend.instructions.md). Owner: D1/D2.

All persistence for `Medicine`, `MedicinePrice`, `LabMetric`, `ShareLink` goes through this
module - no SQL strings anywhere else. Parameterized queries only; never build SQL via string
concatenation/f-strings with user input. AAD-only auth (see infra/modules/sql.bicep).
"""

from app.models.report import TrendPoint


async def search_medicine(active_ingredient: str, strength_value: float, strength_unit: str, dosage_form: str) -> list[dict]:
    raise NotImplementedError


async def get_trend(user_id: str, canonical_key: str) -> list[TrendPoint]:
    """Longitudinal history for one lab parameter, scoped by `userId`."""
    raise NotImplementedError


async def create_share_link(share_id_hash: str, blob_path: str, expires_at: str) -> None:
    raise NotImplementedError
