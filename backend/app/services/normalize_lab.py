"""Lab result normalization (implementation-plan.md Section 2.4). Owner: D2.

Contract frozen for D3/D4 consumption: `normalize(ocr) -> list[LabParameter]`. Uses
`data/synonyms/lab_synonyms.json` for canonical-key mapping and unit conversion
(mg/dL <-> mmol/L for glucose/cholesterol; ng/mL <-> nmol/L for vitamin D).
"""

from app.models.report import LabParameter
from app.services.ocr import OcrEnvelope


def normalize(ocr: OcrEnvelope) -> list[LabParameter]:
    """Synonym-map parameter names, convert units, extract report date, compute `status`

    via `reference_ranges.py` (`low | normal | high | critical_flag`).
    """
    raise NotImplementedError
