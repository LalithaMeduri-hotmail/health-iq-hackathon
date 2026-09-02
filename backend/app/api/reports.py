"""POST /api/v1/reports/analyze, /compare (implementation-plan.md Section 5.1).

Calls `ReportAnalysisAgent` / `ComparisonAgent`, `services/normalize_lab.py`, `comparison.py`.
Keep handlers thin: validate input, call a service/agent, shape the `ApiResponse` envelope.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.agents import orchestrator
from app.deps import CurrentUser, get_current_user
from app.errors import NoComparableParametersError, ValidationError
from app.models.common import ApiResponse, SafetyBlock
from app.models.report import (
    ABNORMAL_STATUSES,
    ComparisonRequest,
    ComparisonResult,
    ReportAnalyzeResponse,
    ReportListItem,
    ReportListResponse,
    StoredReport,
    TrendPoint,
)
from app.repositories import cosmos_repo, sql_repo
from app.services import blob
from app.services.normalize_lab import find_report_date
from app.services.normalize_lab import normalize as normalize_lab
from app.services.ocr import extract as ocr_extract

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _envelope(request: Request, safety: SafetyBlock, data) -> ApiResponse:
    return ApiResponse(
        request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
        generated_at=datetime.now(UTC),
        safety=safety,
        data=data,
    )


@router.post("/analyze")
async def analyze(
    request: Request,
    consent: bool = Form(...),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[ReportAnalyzeResponse]:
    """Multipart `file` + `consent=true` -> normalized parameters, system cards, and a score."""
    if not consent:
        raise ValidationError("consent must be true before any upload is processed")

    content = await file.read()
    blob_path = await blob.upload_raw(
        current_user.user_id, file.filename or "report.pdf", content, consent_version="1.0"
    )

    envelope = await ocr_extract(content, mode="layout")
    parameters = normalize_lab(envelope)
    if not parameters:
        raise ValidationError("No recognizable lab parameters were found in this document")

    result = await orchestrator.run("report", {"parameters": parameters})
    summary = result.data

    report = await cosmos_repo.save_report(
        StoredReport(
            id=f"report-{uuid.uuid4().hex[:12]}",
            userId=current_user.user_id,
            reportDate=parameters[0].report_date,
            labName="Uploaded report",
            parameters=parameters,
        )
    )

    await cosmos_repo.record_run(
        current_user.user_id,
        f"run-{uuid.uuid4().hex[:12]}",
        {
            "type": "report-analyze",
            "reportId": report.id,
            "blobPath": blob_path,
            "toolCalls": ["ocr_layout", "normalize_lab", "lookup_reference_range"],
            "agentVersions": {"report": "1.0.0", "safety": "safety-1.0.0"},
            "safety": {"pass": result.safety_pass, "violations": result.safety_notes},
            "createdAt": datetime.now(UTC).isoformat(),
        },
    )

    data = ReportAnalyzeResponse(
        reportId=report.id,
        reportDate=report.report_date,
        blobPath=blob_path,
        parameters=summary.parameters,
        abnormal=summary.abnormal,
        systemCards=summary.system_cards,
        healthScore=summary.health_score,
        narrative=summary.narrative,
    )
    notes = list(result.safety_notes)
    if find_report_date(envelope) is None:
        notes.append("report-date-not-detected")
    safety = SafetyBlock(pass_=result.safety_pass, notes=notes, reviewer_version="safety-1.0.0")
    return _envelope(request, safety, data)


async def _build_trend_series(
    user_id: str, old_report: StoredReport, current_report: StoredReport
) -> dict[str, list[TrendPoint]]:
    """One series per repeated parameter (FR3.4), sourced from `LabMetric` for longer history."""
    repeated_keys = {p.canonical_key for p in old_report.parameters} & {
        p.canonical_key for p in current_report.parameters
    }
    return {key: await sql_repo.get_trend(user_id, key) for key in sorted(repeated_keys)}


@router.get("")
async def list_reports(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[ReportListResponse]:
    """Report history for the two-report picker (FR3.1), newest first."""
    reports = await cosmos_repo.list_reports(current_user.user_id)
    items = [
        ReportListItem(
            reportId=report.id,
            reportDate=report.report_date,
            labName=report.lab_name,
            parameterCount=len(report.parameters),
            abnormalCount=sum(1 for parameter in report.parameters if parameter.status in ABNORMAL_STATUSES),
        )
        for report in sorted(reports, key=lambda report: report.report_date, reverse=True)
    ]
    safety = SafetyBlock(pass_=True, notes=[])
    return _envelope(request, safety, ReportListResponse(reports=items))


@router.post("/compare")
async def compare(
    request: Request,
    body: ComparisonRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[ComparisonResult]:
    """`{ oldReportId, currentReportId }` -> deterministic `ComparisonResult` + `trendSeries[]`."""
    if body.old_report_id == body.current_report_id:
        raise ValidationError("oldReportId and currentReportId must reference different reports")

    old_report = await cosmos_repo.get_report(current_user.user_id, body.old_report_id)
    current_report = await cosmos_repo.get_report(current_user.user_id, body.current_report_id)

    shared_keys = {p.canonical_key for p in old_report.parameters} & {
        p.canonical_key for p in current_report.parameters
    }
    if not shared_keys:
        raise NoComparableParametersError("The two reports share no comparable parameters")

    trend_series = await _build_trend_series(current_user.user_id, old_report, current_report)
    result = await orchestrator.run(
        "comparison",
        {"old_report": old_report, "current_report": current_report, "trend_series": trend_series},
    )

    notes = list(result.safety_notes)
    if not result.data.narrative:
        notes.append("narrative-unavailable")

    run_id = f"run-{uuid.uuid4().hex[:12]}"
    result.data.run_id = run_id
    await cosmos_repo.record_run(
        current_user.user_id,
        run_id,
        {
            "type": "comparison",
            "oldReportId": old_report.id,
            "currentReportId": current_report.id,
            "comparison": result.data.model_dump(by_alias=True),
            "toolCalls": ["load_report", "align_parameters", "classify_change", "get_trend"],
            "agentVersions": {"comparison": "1.0.0", "safety": "safety-1.0.0"},
            "safety": {"pass": result.safety_pass, "violations": result.safety_notes},
            "createdAt": datetime.now(UTC).isoformat(),
        },
    )

    safety = SafetyBlock(pass_=result.safety_pass, notes=notes, reviewer_version="safety-1.0.0")
    return _envelope(request, safety, result.data)
