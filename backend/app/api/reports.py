"""POST /api/v1/reports/analyze, /compare (implementation-plan.md Section 5.1).

Calls `ReportAnalysisAgent` / `ComparisonAgent`, `services/normalize_lab.py`, `comparison.py`.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

# TODO: POST /analyze - multipart `file` -> { reportId, parameters[], abnormal[], healthScore,
#       systemCards[], narrative } (app.models.report.ReportSummary)
# TODO: POST /compare - { oldReportId, currentReportId } -> ComparisonResult + trendSeries[]
#       (app.models.report.ComparisonResult)
