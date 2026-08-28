"""Medicine normalization (implementation-plan.md Section 2.2-2.3). Owner: D2.

Contract frozen for D3/D4 consumption: `normalize(ocr) -> list[MedicineEntity]`.
"""

import re
from datetime import UTC, date, datetime

from rapidfuzz import fuzz, process

from app.config import get_settings
from app.models.medicine import MedicineCorrection, MedicineEntity
from app.repositories.sql_repo import list_catalog, search_medicine_sync
from app.services.ocr import OcrEnvelope

FUZZY_ACCEPT_THRESHOLD = 88
FUZZY_REVIEW_THRESHOLD = 75
SOURCE_FRESHNESS_MONTHS = 24

_STRENGTH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|iu|%)", re.IGNORECASE)
_FREQUENCY_RE = re.compile(r"\b(\d(?:[.\-]\d){1,3}|BD|OD|HS|SOS|TDS|QID|STAT)\b", re.IGNORECASE)
_DURATION_RE = re.compile(r"(?:x\s*|for\s*)(\d+)\s*(day|days|week|weeks|month|months)\b", re.IGNORECASE)


def _extract_strength(text: str) -> tuple[float | None, str | None, int | None]:
    match = _STRENGTH_RE.search(text)
    if not match:
        return None, None, None
    return float(match.group(1)), match.group(2).lower(), match.start()


def _extract_frequency(text: str) -> str | None:
    match = _FREQUENCY_RE.search(text)
    return match.group(1) if match else None


def _extract_duration(text: str) -> str | None:
    match = _DURATION_RE.search(text)
    if not match:
        return None
    return f"{match.group(1)} {match.group(2).lower()}"


def _brand_candidate(text: str, strength_start: int) -> str:
    return text[:strength_start].strip(" -:")


def normalize(ocr: OcrEnvelope) -> list[MedicineEntity]:
    """Clean OCR text, fuzzy-match brand names (RapidFuzz `token_set_ratio`), parse strength.

    Accept >= 88, review band 75-87, reject below. Emit `MedicineEntity` with
    `needsUserConfirmation` set for anything below the accept threshold.

    Lines with no parseable strength token (patient/doctor header lines, dates, signatures) are
    treated as non-medicine lines and skipped.
    """
    settings = get_settings()
    brand_names = sorted({row["brandName"] for row in list_catalog()})

    items: list[MedicineEntity] = []
    for index, line in enumerate(ocr.lines):
        strength_value, strength_unit, strength_start = _extract_strength(line.text)
        if strength_value is None:
            continue

        brand_candidate = _brand_candidate(line.text, strength_start)
        best_match = process.extractOne(brand_candidate, brand_names, scorer=fuzz.token_set_ratio) if brand_names else None
        matched_brand, fuzzy_score = (best_match[0], best_match[1]) if best_match else (brand_candidate, 0.0)

        active_ingredient: str | None = None
        dosage_form: str | None = None
        if fuzzy_score >= FUZZY_REVIEW_THRESHOLD:
            catalog_row = next((row for row in list_catalog() if row["brandName"] == matched_brand), None)
            if catalog_row is not None:
                active_ingredient = catalog_row["activeIngredient"]
                dosage_form = catalog_row["dosageForm"]

        needs_confirmation = (
            line.confidence < settings.ocr_confidence_threshold
            or fuzzy_score < FUZZY_ACCEPT_THRESHOLD
            or active_ingredient is None
        )

        items.append(
            MedicineEntity(
                lineId=f"li-{index + 1}",
                rawText=line.text,
                brandName=matched_brand if fuzzy_score >= FUZZY_REVIEW_THRESHOLD else brand_candidate,
                activeIngredient=active_ingredient,
                strengthValue=strength_value,
                strengthUnit=strength_unit,
                dosageForm=dosage_form,
                frequency=_extract_frequency(line.text),
                duration=_extract_duration(line.text),
                matchScore=round(fuzzy_score / 100, 4),
                ocrConfidence=line.confidence,
                needsUserConfirmation=needs_confirmation,
            )
        )
    return items


def _is_source_fresh(source_date: str) -> bool:
    parsed = date.fromisoformat(source_date)
    months_old = (datetime.now(UTC).date().year - parsed.year) * 12 + (datetime.now(UTC).date().month - parsed.month)
    return months_old <= SOURCE_FRESHNESS_MONTHS


def find_alternatives(item: MedicineEntity) -> list[dict]:
    """Alternative-matching hard constraints (implementation-plan.md Section 2.3):

    identical active ingredient set, strength value+unit, dosage form, and `sourceDate` within
    24 months. Combination drugs require an exact multiset match or are excluded. Rank by price
    ascending; `savingsPct = round((orig - alt) / orig * 100)`.
    """
    if not item.active_ingredient or item.strength_value is None or not item.strength_unit or not item.dosage_form:
        return []

    rows = search_medicine_sync(item.active_ingredient, item.strength_value, item.strength_unit, item.dosage_form)
    rows = [row for row in rows if _is_source_fresh(row["sourceDate"])]
    if not rows:
        return []

    original_row = next((row for row in rows if row["brandName"].casefold() == (item.brand_name or "").casefold()), None)
    original_price = original_row["mrpInr"] if original_row else max(row["mrpInr"] for row in rows)
    original_label = original_row["brandName"] if original_row else (item.brand_name or rows[0]["brandName"])

    cheaper_candidates = [row for row in rows if row["brandName"] != original_label]
    if not cheaper_candidates:
        return []
    cheapest = cheaper_candidates[0]  # rows are already sorted by mrpInr ascending

    strength_label = f"{item.strength_value:g} {item.strength_unit}"
    savings_pct = round((original_price - cheapest["mrpInr"]) / original_price * 100) if original_price else 0

    return [
        {
            "original": f"{original_label} {strength_label}",
            "generic": f"{cheapest['genericName']} {strength_label}",
            "cheaper": f"{cheapest['manufacturer']} {cheapest['brandName']} {strength_label}",
            "originalMrpInr": original_price,
            "cheaperMrpInr": cheapest["mrpInr"],
            "savingsPct": savings_pct,
            "savingsEstimated": True,
            "source": {
                "sourceName": cheapest["sourceName"],
                "sourceUrl": cheapest["sourceUrl"],
                "sourceDate": cheapest["sourceDate"],
            },
            "doctorApprovalRequired": True,
            "matchBasis": "exact-ingredient-strength-form",
        }
    ]


def apply_correction(item: MedicineEntity, correction: MedicineCorrection) -> MedicineEntity:
    """Apply a user-confirmed correction (`POST /prescriptions/confirm`) and recompute the match.

    A corrected line is treated as ground truth: `needsUserConfirmation` clears once the brand
    resolves to a catalog entry (or is accepted as-is when no catalog entry exists).
    """
    brand_name = correction.brand_name or item.brand_name
    strength_value = correction.strength_value if correction.strength_value is not None else item.strength_value
    strength_unit = correction.strength_unit or item.strength_unit
    dosage_form = correction.dosage_form or item.dosage_form

    catalog_row = next(
        (row for row in list_catalog() if brand_name and row["brandName"].casefold() == brand_name.casefold()), None
    )
    active_ingredient = catalog_row["activeIngredient"] if catalog_row else item.active_ingredient
    dosage_form = catalog_row["dosageForm"] if catalog_row else dosage_form

    return item.model_copy(
        update={
            "brand_name": brand_name,
            "strength_value": strength_value,
            "strength_unit": strength_unit,
            "dosage_form": dosage_form,
            "active_ingredient": active_ingredient,
            "match_score": 1.0,
            "needs_user_confirmation": False,
        }
    )
