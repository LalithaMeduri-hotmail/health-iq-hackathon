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
from app.services import blob, doctor_pdf, share_links

router = APIRouter(prefix="/api/v1/pdf", tags=["pdf"])


@router.post("/generate")
async def generate(
    request: Request,
    body: PdfGenerateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[PdfGenerateResponse]:
    """`{ runId }` -> a doctor-review PDF plus a revocable 24h share link."""
    run = await cosmos_repo.get_run(current_user.user_id, body.run_id)
    run_type = run.get("type")

    if run_type == "comparison":
        payload = ComparisonResult.model_validate(run["comparison"]).model_dump(by_alias=True)
    elif run_type == "prescription":
        payload = {"items": run.get("items", [])}
    else:
        raise ValidationError(f"Run {body.run_id!r} cannot be rendered as a doctor-review PDF")

    verdict = safety_agent.review(payload)
    if not verdict.passed:
        raise ValidationError(
            "Safety review blocked this document",
            errors=[{"field": "safety", "issue": note} for note in verdict.violations],
        )

    # Rendering is the expensive step, so an unchanged run reuses its stored PDF (LLD Section 5.8).
    # The token itself is always minted fresh: only its hash is persisted, so it cannot be re-read.
    blob_path = None if body.regenerate else run.get("pdfBlobPath")
    if blob_path is None:
        try:
            filename, content = doctor_pdf.build_for_run(run)
        except ImportError as exc:  # ReportLab missing in this environment
            raise UpstreamUnavailableError(f"PDF rendering is unavailable: {exc}") from exc

        blob_path = await blob.upload_generated_pdf(current_user.user_id, content)
        run["pdfBlobPath"] = blob_path
        run["pdfFilename"] = filename
        await cosmos_repo.record_run(current_user.user_id, body.run_id, run)

    share_id, expires_at = await share_links.create_share_link(
        blob_path,
        user_id=current_user.user_id,
        run_id=body.run_id,
        filename=run.get("pdfFilename", ""),
    )

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

