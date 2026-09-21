"""Renders the doctor-review PDF for a stored run and names it like a real clinic document.

Shared by `api/pdf.py` (download/share) and `api/reviews.py` (email attachment) so both paths
produce byte-identical documents.
"""

import re
from datetime import UTC, datetime

from app.errors import NotFoundError, ValidationError
from app.models.medicine import MedicineAnalysis, MedicineEntity
from app.models.report import ComparisonResult
from app.models.review import PrescriptionDocument, PrescriptionLine
from app.services import pdf_builder
from app.services.normalize_medicine import find_alternatives

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(value: str, fallback: str) -> str:
    cleaned = _UNSAFE_FILENAME_CHARS.sub("-", value).strip("-")
    return cleaned[:40] or fallback


def _label(item: MedicineEntity) -> str:
    strength = f" {item.strength_value:g}{item.strength_unit or ''}" if item.strength_value else ""
    return f"{item.brand_name or item.raw_text}{strength}"


def medicine_names(run: dict) -> list[str]:
    """Human-readable medicine labels for the run, used in the email body."""
    return [_label(MedicineEntity.model_validate(raw)) for raw in run.get("items", [])]


def medicine_lines(run: dict, selections: dict[str, str] | None = None) -> list[dict]:
    """What the clinician decides on: each medicine plus the equivalent proposed for it.

    `selections` maps `lineId -> cheaperBrand` as picked by the patient in the app. The clinician
    must be asked about the switch the patient actually intends, so a selection wins over the
    best-value default; lines the patient left alone keep that default.
    """
    chosen = selections or {}
    lines = []
    for raw in run.get("items", []):
        item = MedicineEntity.model_validate(raw)
        match = find_alternatives(item)
        pick = chosen.get(item.line_id)
        alternative = next((option for option in match if option["cheaperBrand"] == pick), None)
        if alternative is None:
            alternative = match[0] if match else None
        lines.append(
            {
                "lineId": item.line_id,
                "label": _label(item),
                "maker": alternative["originalMaker"] if alternative else "",
                "ingredient": item.active_ingredient or "",
                "dosageForm": item.dosage_form or "",
                "alternative": alternative["cheaperBrand"] if alternative else "",
                "alternativeMaker": alternative["cheaperMaker"] if alternative else "",
                "alternativeGeneric": alternative["cheaperGeneric"] if alternative else "",
                "savingsPct": alternative["savingsPct"] if alternative else 0,
                "originalMrpInr": alternative["originalMrpInr"] if alternative else 0.0,
                "cheaperMrpInr": alternative["cheaperMrpInr"] if alternative else 0.0,
            }
        )
    return lines


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


def build_outcome_document(run: dict, review: dict, patient_name: str) -> tuple[str, bytes]:
    """Render the single Health IQ review summary for a decided review.

    One document covers every medicine the clinician answered on, so the patient reads the
    prescribed medicine, the equivalent Health IQ proposed, and the verdict on one page instead
    of cross-referencing two separate PDFs.
    """
    if not review.get("decidedAt"):
        raise NotFoundError("This review has not been decided yet")

    verdicts = {entry["lineId"]: entry["decision"] for entry in review.get("decisions", [])}
    proposals = {entry["lineId"]: entry for entry in review.get("lines", [])}
    items = [MedicineEntity.model_validate(raw) for raw in run.get("items", [])]

    lines = []
    for item in items:
        decision = verdicts.get(item.line_id)
        if decision is None:
            continue
        proposal = proposals.get(item.line_id, {})
        alternative = proposal.get("alternative") or ""
        strength = (
            f"{item.strength_value:g} {item.strength_unit or ''}".strip()
            if item.strength_value is not None
            else ""
        )
        generic = proposal.get("ingredient") or ""
        lines.append(
            PrescriptionLine(
                label=_label(item),
                maker=proposal.get("maker", ""),
                generic=f"{generic} ({strength})" if generic and strength else generic,
                form=(item.dosage_form or "").title(),
                strength=strength or "-",
                frequency=item.frequency or "-",
                duration=item.duration or "-",
                decision=decision,
                note=_line_note(decision, alternative, proposal.get("savingsPct", 0)),
                alternative=alternative,
                alternativeMaker=proposal.get("alternativeMaker", ""),
                alternativeGeneric=proposal.get("alternativeGeneric", ""),
                savingsPct=proposal.get("savingsPct", 0) or 0,
                originalMrpInr=proposal.get("originalMrpInr", 0.0) or 0.0,
                cheaperMrpInr=proposal.get("cheaperMrpInr", 0.0) or 0.0,
            )
        )
    if not lines:
        raise NotFoundError("This review has no decided medicines")

    reviewed_at = (review.get("decidedAt") or "")[:16].replace("T", " ") + " UTC"
    document_model = PrescriptionDocument(
        patientName=patient_name,
        doctorName=review["doctorName"],
        doctorSpecialty=review["doctorSpecialty"],
        doctorRegistrationNo=review.get("doctorRegistrationNo", "-"),
        reviewedAt=reviewed_at,
        reference=review["reviewId"],
        notes=review.get("notes") or "",
        lines=lines,
    )

    issued_on = (review.get("decidedAt") or datetime.now(UTC).isoformat())[:10]
    filename = f"HealthIQ-Review-Summary-{_slug(patient_name, 'Patient')}-{issued_on}.pdf"
    return filename, pdf_builder.build_prescription(document_model)


def _line_note(decision: str, alternative: str, savings: int) -> str:
    if decision == "approved":
        if not alternative:
            return "Continue as prescribed"
        return "Switch approved" + (f" - about {savings}% less" if savings else "")
    if decision == "changes_requested":
        return "Change requested - do not switch on your own"
    if alternative:
        return "Switch not approved - stay on the current medicine"
    return "Not approved - discuss at your next visit"
