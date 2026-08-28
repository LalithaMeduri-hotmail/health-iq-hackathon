"""`PrescriptionAnalyzerAgent` (implementation-plan.md Section 4.2). Owner: D3.

Tools: `ocr_extract`, `normalize_medicine`, `search_medicines`, `find_alternatives`,
`generate_pdf`. Output: `MedicineAnalysis`. Guardrails: never suggest stopping/starting a drug;
alternatives always carry `doctorApprovalRequired=true`.

`MedicineAnalysis` carries no narrative field, so this agent runs the deterministic
OCR-normalization pipeline directly (no LLM round trip): the determinism boundary
(agents.instructions.md) puts all numbers/verdicts in Python, and there is no plain-language
wrapper to write here. `find_alternatives` is intentionally *not* called here - it is served by
the stateless `POST /medicines/alternatives` endpoint per the frozen API contract (LLD Section 1.3).
"""

import statistics

from app.models.medicine import MedicineAnalysis
from app.models.common import DISCLAIMER_TEXT
from app.services.normalize_medicine import normalize
from app.services.ocr import OcrEnvelope


async def run(payload: dict) -> MedicineAnalysis:
    """`payload` is `{"ocr_envelope": OcrEnvelope}` - built by the router from OCR output or
    manually-entered medicine lines wrapped as a synthetic, full-confidence `OcrEnvelope`.
    """
    ocr_envelope: OcrEnvelope = payload["ocr_envelope"]
    items = normalize(ocr_envelope)
    confidence = statistics.mean(line.confidence for line in ocr_envelope.lines) if ocr_envelope.lines else 1.0
    return MedicineAnalysis(items=items, disclaimers=[DISCLAIMER_TEXT], confidence=round(confidence, 4))
