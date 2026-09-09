"""Renders the doctor-review PDF for a stored run and names it like a real clinic document.

Shared by `api/pdf.py` (download/share) and `api/reviews.py` (email attachment) so both paths
produce byte-identical documents.
"""

import re
from datetime import UTC, datetime

from app.errors import ValidationError
from app.models.medicine import MedicineAnalysis, MedicineEntity
from app.models.report import ComparisonResult
from app.services import pdf_builder
from app.services.normalize_medicine import find_alternatives

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(value: str, fallback: str) -> str:
    cleaned = _UNSAFE_FILENAME_CHARS.sub("-", value).strip("-")
    return cleaned[:40] or fallback


def medicine_names(run: dict) -> list[str]:
    """Human-readable medicine labels for the run, used in the email body."""
    names = []
    for raw in run.get("items", []):
        item = MedicineEntity.model_validate(raw)
        strength = f" {item.strength_value:g}{item.strength_unit or ''}" if item.strength_value else ""
        names.append(f"{item.brand_name or item.raw_text}{strength}")
    return names


def alternatives_for(items: list[MedicineEntity]) -> list[dict]:
    """The same equivalents the alternatives endpoint would return, for PDF section 4."""
    found: list[dict] = []
    for item in items:
        found.extend(find_alternatives(item))
    return found


def build_for_run(run: dict) -> tuple[str, bytes]:
    """Render a run as `(filename, pdf bytes)`; raises when the run is not renderable."""
    run_type = run.get("type")
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    if run_type == "comparison":
        result = ComparisonResult.model_validate(run["comparison"])
        filename = (
            f"HealthIQ-Lab-Comparison-{_slug(result.old_report_date, 'earlier')}"
            f"-to-{_slug(result.current_report_date, 'latest')}.pdf"
        )
        return filename, pdf_builder.build_comparison(result)

    if run_type == "prescription":
        items = [MedicineEntity.model_validate(raw) for raw in run.get("items", [])]
        analysis = MedicineAnalysis(items=items, confidence=1.0)
        lead = items[0].brand_name or items[0].raw_text if items else "Prescription"
        suffix = f"-and-{len(items) - 1}-more" if len(items) > 1 else ""
        filename = f"HealthIQ-Medicine-Review-{_slug(lead, 'Prescription')}{suffix}-{today}.pdf"
        return filename, pdf_builder.build(analysis, alternatives_for(items))

    raise ValidationError("This run cannot be rendered as a doctor-review PDF")
