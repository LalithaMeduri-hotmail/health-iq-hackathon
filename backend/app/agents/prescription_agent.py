"""`PrescriptionAnalyzerAgent` (implementation-plan.md Section 4.2). Owner: D3.

The model reads the prescription; Python grounds it. The LLM extracts each medicine line as
written (handwriting, layouts and abbreviations the regex reader could not follow), then every
name is fuzzy-matched onto the curated catalog, so the ingredient, dosage form and any price the
user later sees come from `data/medicines/medicine_catalog.csv` and never from model memory.
`services/normalize_medicine.normalize()` remains the offline fallback for demo mode and tests.

Guardrails: never suggest stopping/starting a drug; alternatives always carry
`doctorApprovalRequired=true`. `find_alternatives` is intentionally *not* called here - it is
served by the stateless `POST /medicines/alternatives` endpoint per the frozen API contract
(LLD Section 1.3).
"""

import statistics

from pydantic import BaseModel, ConfigDict, Field

from app.agents import llm
from app.config import get_settings
from app.models.common import DISCLAIMER_TEXT
from app.models.medicine import MedicineAnalysis, MedicineEntity
from app.services.normalize_medicine import FUZZY_ACCEPT_THRESHOLD, normalize, resolve_brand
from app.services.ocr import OcrEnvelope


class _ReadMedicine(BaseModel):
    """One medicine line as the model read it, before catalog grounding."""

    model_config = ConfigDict(populate_by_name=True)

    raw_text: str = Field(alias="rawText", default="")
    brand_name: str | None = Field(alias="brandName", default=None)
    active_ingredient: str | None = Field(alias="activeIngredient", default=None)
    strength_value: float | None = Field(alias="strengthValue", default=None)
    strength_unit: str | None = Field(alias="strengthUnit", default=None)
    dosage_form: str | None = Field(alias="dosageForm", default=None)
    frequency: str | None = None
    duration: str | None = None
    confidence: float = 0.0


class _ReadResult(BaseModel):
    items: list[_ReadMedicine] = Field(default_factory=list)


def _ground(index: int, read: _ReadMedicine, page_confidence: float) -> MedicineEntity:
    """Anchor one model-read line to the catalog and decide whether the user must confirm it."""
    settings = get_settings()
    brand, score, row = resolve_brand(read.brand_name or read.raw_text)

    active_ingredient = row["activeIngredient"] if row else read.active_ingredient
    dosage_form = row["dosageForm"] if row else read.dosage_form
    # The reader cannot be more certain than the page it read from.
    confidence = min(read.confidence or page_confidence, page_confidence)

    needs_confirmation = (
        confidence < settings.ocr_confidence_threshold
        or score < FUZZY_ACCEPT_THRESHOLD / 100
        or active_ingredient is None
        or read.strength_unit is None
    )

    fallback_text = f"{brand} {read.strength_value or ''}{read.strength_unit or ''}".strip()
    return MedicineEntity(
        lineId=f"li-{index}",
        rawText=read.raw_text or fallback_text,
        brandName=brand or None,
        activeIngredient=active_ingredient,
        strengthValue=read.strength_value,
        strengthUnit=read.strength_unit,
        dosageForm=dosage_form,
        frequency=read.frequency,
        duration=read.duration,
        matchScore=score,
        ocrConfidence=round(confidence, 4),
        needsUserConfirmation=needs_confirmation,
    )


async def _read_with_llm(ocr_envelope: OcrEnvelope, page_confidence: float) -> list[MedicineEntity] | None:
    text = "\n".join(line.text for line in ocr_envelope.lines)
    if not text.strip():
        return None

    result = await llm.structured(
        instructions=llm.prompt("prescription_reader"),
        task="List every prescribed medicine on this document.",
        data=text[:8000],
        schema=_ReadResult,
        name="PrescriptionReaderAgent",
    )
    if result is None or not result.items:
        return None
    return [_ground(index, read, page_confidence) for index, read in enumerate(result.items, start=1)]


async def run(payload: dict) -> MedicineAnalysis:
    """`payload` is `{"ocr_envelope": OcrEnvelope}` - built by the router from OCR output or
    manually-entered medicine lines wrapped as a synthetic, full-confidence `OcrEnvelope`.
    """
    ocr_envelope: OcrEnvelope = payload["ocr_envelope"]
    confidence = (
        statistics.mean(line.confidence for line in ocr_envelope.lines) if ocr_envelope.lines else 1.0
    )

    items = await _read_with_llm(ocr_envelope, confidence)
    if items is None:
        items = normalize(ocr_envelope)

    return MedicineAnalysis(
        items=items, disclaimers=[DISCLAIMER_TEXT], confidence=round(confidence, 4)
    )
