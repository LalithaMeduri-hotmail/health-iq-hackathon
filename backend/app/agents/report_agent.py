"""`ReportAnalysisAgent` (implementation-plan.md Section 4.2). Owner: D3.

Tools: `ocr_layout`, `normalize_lab`, `lookup_reference_range`, `search_reference_explanations`.
Output: `ReportSummary`. Guardrails: use "possible concern"; never name a disease.
"""

from app.models.report import ReportSummary


async def run(payload: dict) -> ReportSummary:
    raise NotImplementedError
