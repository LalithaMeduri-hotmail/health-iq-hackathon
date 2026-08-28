"""Prescription & Medicine Analyzer contracts (docs/lld/2-low-level-design-prescription-medicine-analyzer.md).

`models/` is a pure leaf: no imports from services, repositories, or SDK clients here.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import SourceRef


class MedicineEntity(BaseModel):
    """Normalized medicine line item (implementation-plan.md Section 2.2)."""

    model_config = ConfigDict(populate_by_name=True)

    line_id: str = Field(alias="lineId")
    raw_text: str = Field(alias="rawText")
    brand_name: str | None = Field(alias="brandName", default=None)
    active_ingredient: str | None = Field(alias="activeIngredient", default=None)
    strength_value: float | None = Field(alias="strengthValue", default=None)
    strength_unit: str | None = Field(alias="strengthUnit", default=None)
    dosage_form: str | None = Field(alias="dosageForm", default=None)
    frequency: str | None = None
    duration: str | None = None
    match_score: float | None = Field(alias="matchScore", default=None)
    ocr_confidence: float | None = Field(alias="ocrConfidence", default=None)
    needs_user_confirmation: bool = Field(alias="needsUserConfirmation", default=False)


class MedicineAnalysis(BaseModel):
    """`PrescriptionAnalyzerAgent` output contract (implementation-plan.md Section 4.2)."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[MedicineEntity]
    disclaimers: list[str] = Field(default_factory=list)
    confidence: float


class ManualMedicineInput(BaseModel):
    """One manually-entered medicine line (FR1.1 manual-entry path, bypasses OCR)."""

    model_config = ConfigDict(populate_by_name=True)

    raw_text: str = Field(alias="rawText")


class PrescriptionAnalyzeResponse(BaseModel):
    """`POST /api/v1/prescriptions/analyze` response `data` (LLD Section 1.3.1)."""

    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    blob_path: str | None = Field(alias="blobPath", default=None)
    ocr_confidence: float = Field(alias="ocrConfidence")
    handwritten_ratio: float = Field(alias="handwrittenRatio", default=0.0)
    items: list[MedicineEntity]
    needs_confirmation: list[MedicineEntity] = Field(alias="needsConfirmation", default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)


class MedicineCorrection(BaseModel):
    """User-supplied correction for one low-confidence line (LLD Section 1.3.2)."""

    model_config = ConfigDict(populate_by_name=True)

    line_id: str = Field(alias="lineId")
    brand_name: str | None = Field(alias="brandName", default=None)
    strength_value: float | None = Field(alias="strengthValue", default=None)
    strength_unit: str | None = Field(alias="strengthUnit", default=None)
    dosage_form: str | None = Field(alias="dosageForm", default=None)


class PrescriptionConfirmRequest(BaseModel):
    """`POST /api/v1/prescriptions/confirm` request body (LLD Section 1.3.2)."""

    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    corrections: list[MedicineCorrection]


class PrescriptionConfirmResponse(BaseModel):
    """`POST /api/v1/prescriptions/confirm` response `data`."""

    items: list[MedicineEntity]


class AlternativeMedicine(BaseModel):
    """One row of the alternatives table (implementation-plan.md Section 2.3)."""

    model_config = ConfigDict(populate_by_name=True)

    original: str
    generic: str
    cheaper: str
    original_mrp_inr: float = Field(alias="originalMrpInr")
    cheaper_mrp_inr: float = Field(alias="cheaperMrpInr")
    savings_pct: float = Field(alias="savingsPct")
    savings_estimated: bool = Field(alias="savingsEstimated", default=True)
    source: SourceRef
    doctor_approval_required: bool = Field(alias="doctorApprovalRequired", default=True)
    match_basis: str = Field(alias="matchBasis", default="exact-ingredient-strength-form")


class MedicineAlternativeQuery(BaseModel):
    """One lookup key for `POST /api/v1/medicines/alternatives` (LLD Section 1.3.3)."""

    model_config = ConfigDict(populate_by_name=True)

    brand_name: str | None = Field(alias="brandName", default=None)
    active_ingredient: str = Field(alias="activeIngredient")
    strength_value: float = Field(alias="strengthValue")
    strength_unit: str = Field(alias="strengthUnit")
    dosage_form: str = Field(alias="dosageForm")


class MedicinesAlternativesRequest(BaseModel):
    """`POST /api/v1/medicines/alternatives` request body."""

    items: list[MedicineAlternativeQuery]


class MedicinesAlternativesResponse(BaseModel):
    """`POST /api/v1/medicines/alternatives` response `data` (implementation-plan.md Section 5.1)."""

    alternatives: list[AlternativeMedicine]
    unmatched: list[str] = Field(default_factory=list)

