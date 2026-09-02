"""POST /api/v1/pdf/generate (implementation-plan.md Section 5.3).

Calls `services/pdf_builder.py` (ReportLab, 6 sections) and `services/blob.py` to persist the
generated PDF into the `generated-pdfs` container.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request

from app.agents import safety_agent
from app.deps import CurrentUser, get_current_user
from app.errors import UpstreamUnavailableError, ValidationError
from app.models.common import ApiResponse, SafetyBlock
from app.models.report import ComparisonResult, PdfGenerateRequest, PdfGenerateResponse
from app.repositories import cosmos_repo
from app.services import blob, pdf_builder, share_links

router = APIRouter(prefix="/api/v1/pdf", tags=["pdf"])


@router.post("/generate")
async def generate(
    request: Request,
    body: PdfGenerateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[PdfGenerateResponse]:
    """`{ runId }` -> a doctor-review PDF plus a revocable 24h share link."""
    run = await cosmos_repo.get_run(current_user.user_id, body.run_id)
    if run.get("type") != "comparison" or "comparison" not in run:
        raise ValidationError(f"Run {body.run_id!r} has no comparison result to render")

    result = ComparisonResult.model_validate(run["comparison"])
    verdict = safety_agent.review(result.model_dump(by_alias=True))
    if not verdict.passed:
        raise ValidationError("Safety review blocked this document", errors=[{"field": "safety", "issue": note} for note in verdict.violations])

    try:
        content = pdf_builder.build_comparison(result)
    except ImportError as exc:  # ReportLab missing in this environment
        raise UpstreamUnavailableError(f"PDF rendering is unavailable: {exc}") from exc

    blob_path = await blob.upload_generated_pdf(current_user.user_id, content)
    share_id, expires_at = await share_links.create_share_link(blob_path)

    await cosmos_repo.record_run(
        current_user.user_id,
        f"run-{uuid.uuid4().hex[:12]}",
        {
            "type": "pdf",
            "sourceRunId": body.run_id,
            "blobPath": blob_path,
            "toolCalls": ["generate_pdf", "create_share_link"],
            "safety": {"pass": True, "violations": []},
            "createdAt": datetime.now(UTC).isoformat(),
        },
    )

    data = PdfGenerateResponse(
        pdfBlobUrl=blob_path,
        shareId=share_id,
        shareUrl=f"/api/v1/share/{share_id}",
        expiresAt=expires_at,
    )
    return ApiResponse(
        request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
        generated_at=datetime.now(UTC),
        safety=SafetyBlock(pass_=True, notes=[], reviewer_version="safety-1.0.0"),
        data=data,
    )
