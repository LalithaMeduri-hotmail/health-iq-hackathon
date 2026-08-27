"""Medicine normalization (implementation-plan.md Section 2.2-2.3). Owner: D2.

Contract frozen for D3/D4 consumption: `normalize(ocr) -> list[MedicineEntity]`.
"""

from app.models.medicine import MedicineEntity
from app.services.ocr import OcrEnvelope

FUZZY_ACCEPT_THRESHOLD = 88
FUZZY_REVIEW_THRESHOLD = 75


def normalize(ocr: OcrEnvelope) -> list[MedicineEntity]:
    """Clean OCR text, fuzzy-match brand names (RapidFuzz `token_set_ratio`), parse strength.

    Accept >= 88, review band 75-87, reject below. Emit `MedicineEntity` with
    `needsUserConfirmation` set for anything below the accept threshold.
    """
    raise NotImplementedError


def find_alternatives(item: MedicineEntity) -> list[dict]:
    """Alternative-matching hard constraints (implementation-plan.md Section 2.3):

    identical active ingredient set, strength value+unit, dosage form, and `sourceDate` within
    24 months. Combination drugs require an exact multiset match or are excluded. Rank by price
    ascending; `savingsPct = round((orig - alt) / orig * 100)`.
    """
    raise NotImplementedError
