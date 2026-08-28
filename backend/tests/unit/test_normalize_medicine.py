"""Unit tests for `services/normalize_medicine.py` (backend.instructions.md - deterministic,
network-free tests for strength parsing, fuzzy matching, and savings math).
"""

import pytest

from app.models.medicine import MedicineCorrection, MedicineEntity
from app.services.normalize_medicine import apply_correction, find_alternatives, normalize
from app.services.ocr import OcrEnvelope, OcrLine


def _envelope(*lines: tuple[str, float]) -> OcrEnvelope:
    return OcrEnvelope(
        pages=1,
        lines=[OcrLine(text=text, confidence=confidence, bbox=[]) for text, confidence in lines],
        tables=[],
        handwritten_ratio=0.0,
    )


def test_normalize_skips_non_medicine_header_lines() -> None:
    envelope = _envelope(("Dr. Ashok Mehta, MBBS MD", 0.95), ("Glycomet 500mg 1-0-1 x10 days", 0.92))

    items = normalize(envelope)

    assert len(items) == 1
    assert items[0].raw_text == "Glycomet 500mg 1-0-1 x10 days"


def test_normalize_parses_strength_frequency_and_duration() -> None:
    envelope = _envelope(("Glycomet 500mg 1-0-1 x10 days", 0.92))

    [item] = normalize(envelope)

    assert item.strength_value == 500.0
    assert item.strength_unit == "mg"
    assert item.frequency == "1-0-1"
    assert item.duration == "10 days"
    assert item.brand_name == "Glycomet"
    assert item.active_ingredient == "Metformin"
    assert item.needs_user_confirmation is False


def test_normalize_flags_low_ocr_confidence_for_confirmation() -> None:
    envelope = _envelope(("Amlong 5mg 0-0-1 x30 days", 0.65))

    [item] = normalize(envelope)

    assert item.ocr_confidence == 0.65
    assert item.needs_user_confirmation is True


def test_normalize_flags_unrecognized_brand_for_confirmation() -> None:
    envelope = _envelope(("Xyzzybrand 500mg 1-0-1 x5 days", 0.99))

    [item] = normalize(envelope)

    assert item.active_ingredient is None
    assert item.needs_user_confirmation is True


@pytest.fixture
def glycomet_item() -> MedicineEntity:
    return MedicineEntity(
        lineId="li-1",
        rawText="Glycomet 500mg 1-0-1 x10 days",
        brandName="Glycomet",
        activeIngredient="Metformin",
        strengthValue=500,
        strengthUnit="mg",
        dosageForm="tablet",
    )


def test_find_alternatives_ranks_by_price_and_computes_savings(glycomet_item: MedicineEntity) -> None:
    [alternative] = find_alternatives(glycomet_item)

    assert alternative["original"] == "Glycomet 500 mg"
    assert alternative["cheaper"] == "Cipla Ltd Metfor 500 mg"
    assert alternative["originalMrpInr"] == 32.50
    assert alternative["cheaperMrpInr"] == 18.90
    assert alternative["savingsPct"] == 42
    assert alternative["doctorApprovalRequired"] is True
    assert alternative["savingsEstimated"] is True
    assert alternative["source"]["sourceUrl"]


def test_find_alternatives_returns_empty_without_full_match_keys() -> None:
    incomplete = MedicineEntity(lineId="li-1", rawText="unknown 5mg", activeIngredient="Metformin")

    assert find_alternatives(incomplete) == []


def test_apply_correction_clears_confirmation_and_resolves_catalog() -> None:
    item = MedicineEntity(
        lineId="li-2",
        rawText="Amlong 5mg 0-0-1 x30 days",
        brandName="Amlong",
        strengthValue=5,
        strengthUnit="mg",
        dosageForm="tablet",
        ocrConfidence=0.65,
        needsUserConfirmation=True,
    )
    correction = MedicineCorrection(lineId="li-2", brandName="Amlodac")

    corrected = apply_correction(item, correction)

    assert corrected.brand_name == "Amlodac"
    assert corrected.active_ingredient == "Amlodipine"
    assert corrected.needs_user_confirmation is False
    assert corrected.match_score == 1.0
