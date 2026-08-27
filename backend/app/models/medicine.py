"""Prescription & Medicine Analyzer contracts (docs/lld/2-low-level-design-prescription-medicine-analyzer.md).

`models/` is a pure leaf: no imports from services, repositories, or SDK clients here.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import SourceRef


class MedicineEntity(BaseModel):
    """Normalized medicine line item (implementation-plan.md Section 2.2)."""

    model_config = ConfigDict(populate_by_name=True)

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


class AlternativeMedicine(BaseModel):
    """One row of the alternatives table (implementation-plan.md Section 2.3)."""

    model_config = ConfigDict(populate_by_name=True)

    original: str
    generic: str
    cheaper: str
    savings_pct: float = Field(alias="savingsPct")
    savings_estimated: bool = Field(alias="savingsEstimated", default=True)
    source: SourceRef
    doctor_approval_required: bool = Field(alias="doctorApprovalRequired", default=True)


class MedicinesAlternativesResponse(BaseModel):
    """`POST /api/v1/medicines/alternatives` response `data` (implementation-plan.md Section 5.1)."""

    alternatives: list[AlternativeMedicine]
