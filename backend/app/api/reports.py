"""POST /api/v1/reports/analyze, /compare (implementation-plan.md Section 5.1).

Calls `ReportAnalysisAgent` / `ComparisonAgent`, `services/normalize_lab.py`, `comparison.py`.
Keep handlers thin: validate input, call a service/agent, shape the `ApiResponse` envelope.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.agents import orchestrator
from app.agents.report_agent import score_breakdown
from app.config import get_settings
from app.deps import CurrentUser, get_current_user
from app.errors import (
    NoComparableParametersError,
    ProfileMismatchError,
    ValidationError,
    WrongDocumentTypeError,
)
from app.models.common import ApiResponse, SafetyBlock
from app.models.medical_document import ProfileMatchStatus
from app.models.profile import CONSENT_VERSION
from app.models.report import (
    ABNORMAL_STATUSES,
    ComparisonRequest,
    ComparisonResult,
    ReportAnalyzeResponse,
    ReportDetailResponse,
    ReportListItem,
    ReportListResponse,
    StoredReport,
    TrendPoint,
)
from app.repositories import cosmos_repo, sql_repo
from app.services import blob, document_type, identity_extract, identity_match, patient_profiles
from app.services.normalize_lab import find_report_date
from app.services.normalize_lab import normalize as normalize_lab
from app.services.ocr import extract as ocr_extract
from app.services.profile_authorization import assert_same_profile, authorize_profile

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


async def _resolve_profile(account_id: str, profile_id: str | None, *, correlation_id: str = ""):
    """Authorize `profile_id`, or fall back to the account owner's own profile.

    The fallback keeps every pre-profile client working: omitting `profileId` means "me", which
    is exactly what the single-profile app always meant.
    """
    owner = await patient_profiles.ensure_owner_profile(account_id, correlation_id=correlation_id)
    if not profile_id or profile_id == owner.id:
        return owner, owner
    profile = await authorize_profile(
        account_id, profile_id, require_consent=True, correlation_id=correlation_id
    )
    return profile, owner


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
    profileId: str | None = Form(default=None),  # noqa: N803 - multipart field name is camelCase
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[ReportAnalyzeResponse]:
    """Multipart `file` + `consent=true` -> normalized parameters, system cards, and a score."""
    if not consent:
        raise ValidationError("consent must be true before any upload is processed")

    correlation_id = getattr(request.state, "request_id", "")
    profile, _owner = await _resolve_profile(
        current_user.user_id, profileId, correlation_id=correlation_id
    )

    content = await file.read()
    blob_path = await blob.upload_raw(
        current_user.user_id,
        file.filename or "report.pdf",
        content,
        consent_version=CONSENT_VERSION,
    )

    envelope = await ocr_extract(content, mode="layout")
    unverified_type = False

    if envelope.was_read:
        kind = document_type.classify(
            document_type.text_of([line.text for line in envelope.lines], envelope.tables)
        )
        if kind != "lab_report":
            raise WrongDocumentTypeError(
                "This does not look like a lab report. Upload a lab report here, and use the "
                "Prescription Analyzer for a prescription or tablet strip."
            )
    elif not get_settings().demo_mode:
        # Nothing read the bytes, so claiming this is a lab report would be a guess.
        raise WrongDocumentTypeError(
            "This upload could not be read, so we cannot confirm it is a lab report. "
            "Upload a PDF instead."
        )
    else:
        unverified_type = True

    # Checked whenever the document names a patient - including a replayed demo envelope, which
    # stands in for the uploaded document - because a name is comparable however it was obtained.
    evidence = identity_extract.extract(envelope)
    if evidence.identity.patient_name:
        match = identity_match.evaluate(profile, evidence.identity)
        if match.status == ProfileMatchStatus.MISMATCH:
            raise ProfileMismatchError(
                "This lab report appears to belong to a different patient. Select an existing "
                "profile or create a separate profile before analyzing it.",
                errors=[
                    {"field": "patientName", "issue": evidence.identity.patient_name or ""},
                    {"field": "profileId", "issue": profile.id},
                ],
            )

    parameters = normalize_lab(envelope)
    if not parameters:
        raise ValidationError("No recognizable lab parameters were found in this document")

    result = await orchestrator.run("report", {"parameters": parameters})
    summary = result.data

    report = await cosmos_repo.save_report(
        StoredReport(
            id=f"report-{uuid.uuid4().hex[:12]}",
            userId=current_user.user_id,
            profileId=profile.id,
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
            "profileId": profile.id,
            "blobPath": blob_path,
            "toolCalls": ["ocr_layout", "normalize_lab", "lookup_reference_range"],
            "agentVersions": {"report": "1.0.0", "safety": "safety-1.0.0"},
            "safety": {"pass": result.safety_pass, "violations": result.safety_notes},
            "createdAt": datetime.now(UTC).isoformat(),
        },
    )

    # FR2.4: the snapshot lands in Cosmos, its per-parameter metrics in SQL `LabMetric` (the trend
    # source Feature 3 reads), and the profile records consent plus the newest analysis.
    await sql_repo.save_lab_metrics(
        current_user.user_id, report.id, parameters, profile_id=profile.id
    )
    await cosmos_repo.record_report_analysis(current_user.user_id, report.id, CONSENT_VERSION)

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
    if unverified_type:
        notes.append("document-type-unverified")
    if not evidence.identity.patient_name:
        # No readable name means the patient was never checked, so say so rather than letting the
        # report look verified for whichever profile happened to be active.
        notes.append("patient-identity-unverified")
    safety = SafetyBlock(pass_=result.safety_pass, notes=notes, reviewer_version="safety-1.0.0")
    return _envelope(request, safety, data)


async def _build_trend_series(
    user_id: str,
    old_report: StoredReport,
    current_report: StoredReport,
    *,
    profile_id: str,
    owner_profile_id: str,
) -> dict[str, list[TrendPoint]]:
    """One series per repeated parameter (FR3.4), sourced from `LabMetric` for longer history.

    Scoped to one patient profile so a longer history never reaches across family members.
    """
    repeated_keys = {p.canonical_key for p in old_report.parameters} & {
        p.canonical_key for p in current_report.parameters
    }
    return {
        key: await sql_repo.get_trend(
            user_id, key, profile_id=profile_id, owner_profile_id=owner_profile_id
        )
        for key in sorted(repeated_keys)
    }


@router.get("")
async def list_reports(
    request: Request,
    profileId: str | None = None,  # noqa: N803 - query parameter name is camelCase
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[ReportListResponse]:
    """Report history for the two-report picker (FR3.1), newest first, for one profile only."""
    profile, owner = await _resolve_profile(current_user.user_id, profileId)
    reports = await cosmos_repo.list_reports_for_profile(
        current_user.user_id, profile.id, owner_profile_id=owner.id
    )
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


@router.get("/{report_id}")
async def get_report(
    request: Request,
    report_id: str,
    profileId: str | None = None,  # noqa: N803 - query parameter name is camelCase
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[ReportDetailResponse]:
    """One stored report expanded: parameters, out-of-range flags, cards, and the score derivation."""
    profile, owner = await _resolve_profile(current_user.user_id, profileId)
    report = await cosmos_repo.get_report_for_profile(
        current_user.user_id, profile.id, report_id, owner_profile_id=owner.id
    )

    result = await orchestrator.run("report", {"parameters": report.parameters})
    summary = result.data

    data = ReportDetailResponse(
        reportId=report.id,
        reportDate=report.report_date,
        labName=report.lab_name,
        parameters=summary.parameters,
        abnormal=summary.abnormal,
        systemCards=summary.system_cards,
        healthScore=summary.health_score,
        scoreBreakdown=score_breakdown(report.parameters),
        narrative=summary.narrative,
    )
    safety = SafetyBlock(
        pass_=result.safety_pass, notes=list(result.safety_notes), reviewer_version="safety-1.0.0"
    )
    return _envelope(request, safety, data)


@router.post("/compare")
async def compare(
    request: Request,
    body: ComparisonRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[ComparisonResult]:
    """`{ oldReportId, currentReportId }` -> deterministic `ComparisonResult` + `trendSeries[]`.

    Both reports must belong to the same authorized patient profile. Names that merely look
    alike are irrelevant: the check is on the stored `profileId`.
    """
    correlation_id = getattr(request.state, "request_id", "")
    profile, owner = await _resolve_profile(
        current_user.user_id, body.profile_id, correlation_id=correlation_id
    )

    if body.old_report_id == body.current_report_id:
        raise ValidationError("oldReportId and currentReportId must reference different reports")

    old_report = await cosmos_repo.get_report_for_profile(
        current_user.user_id, profile.id, body.old_report_id, owner_profile_id=owner.id
    )
    current_report = await cosmos_repo.get_report_for_profile(
        current_user.user_id, profile.id, body.current_report_id, owner_profile_id=owner.id
    )
    assert_same_profile(
        profile,
        cosmos_repo.owning_profile_id(old_report, owner.id),
        cosmos_repo.owning_profile_id(current_report, owner.id),
    )

    shared_keys = {p.canonical_key for p in old_report.parameters} & {
        p.canonical_key for p in current_report.parameters
    }
    if not shared_keys:
        raise NoComparableParametersError("The two reports share no comparable parameters")

    trend_series = await _build_trend_series(
        current_user.user_id,
        old_report,
        current_report,
        profile_id=profile.id,
        owner_profile_id=owner.id,
    )
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
            "profileId": profile.id,
            "comparison": result.data.model_dump(by_alias=True),
            "toolCalls": ["load_report", "align_parameters", "classify_change", "get_trend"],
            "agentVersions": {"comparison": "1.0.0", "safety": "safety-1.0.0"},
            "safety": {"pass": result.safety_pass, "violations": result.safety_notes},
            "createdAt": datetime.now(UTC).isoformat(),
        },
    )

    safety = SafetyBlock(pass_=result.safety_pass, notes=notes, reviewer_version="safety-1.0.0")
    return _envelope(request, safety, result.data)
