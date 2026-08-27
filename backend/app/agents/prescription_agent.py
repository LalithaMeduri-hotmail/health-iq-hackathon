"""`PrescriptionAnalyzerAgent` (implementation-plan.md Section 4.2). Owner: D3.

Tools: `ocr_extract`, `normalize_medicine`, `search_medicines`, `find_alternatives`,
`generate_pdf`. Output: `MedicineAnalysis`. Guardrails: never suggest stopping/starting a drug;
alternatives always carry `doctorApprovalRequired=true`.
"""

from app.models.medicine import MedicineAnalysis


async def run(payload: dict) -> MedicineAnalysis:
    raise NotImplementedError
