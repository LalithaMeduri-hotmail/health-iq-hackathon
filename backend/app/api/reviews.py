"""Doctor review-by-email routes (docs/lld/6-low-level-design-doctor-review-pdf-secure-share.md).

`GET /reviews/{token}` renders a confirm page and changes nothing - mail scanners prefetch links,
and an auto-approved medication change would be unacceptable. The verdict is only written by the
explicit `POST /reviews/{token}/decision` that page submits.
"""

import html
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse

from app.deps import CurrentUser, get_current_user
from app.models.common import ApiResponse, SafetyBlock
from app.models.review import (
    DoctorListResponse,
    ReviewListResponse,
    ReviewRequestBody,
    ReviewRequestResponse,
)
from app.repositories import cosmos_repo
from app.services import doctor_pdf, doctors, reviews

router = APIRouter(prefix="/api/v1", tags=["reviews"])

_STATUS_COPY = {
    "approved": ("Approved", "#166534", "#dcfce7"),
    "changes_requested": ("Changes requested", "#b45309", "#fef3c7"),
    "rejected": ("Not approved", "#b91c1c", "#fee2e2"),
    "pending": ("Awaiting your decision", "#1d4ed8", "#dbeafe"),
}


def _envelope(request: Request, data):
    return ApiResponse(
        request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
        generated_at=datetime.now(UTC),
        safety=SafetyBlock(pass_=True, notes=[], reviewer_version="safety-1.0.0"),
        data=data,
    )


@router.get("/doctors")
async def registered_doctors(
    request: Request,
    _: CurrentUser = Depends(get_current_user),
) -> ApiResponse[DoctorListResponse]:
    """Clinicians the patient can send a review request to. Addresses are masked."""
    return _envelope(request, DoctorListResponse(doctors=doctors.list_doctors()))


@router.post("/reviews/request")
async def request_review(
    request: Request,
    body: ReviewRequestBody,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[ReviewRequestResponse]:
    """`{ runId, doctorIds[] }` -> emails each clinician the PDF plus a tokenised approval link."""
    run = await cosmos_repo.get_run(current_user.user_id, body.run_id)
    filename, content = doctor_pdf.build_for_run(run)

    summaries = await reviews.request_reviews(
        user_id=current_user.user_id,
        run_id=body.run_id,
        doctor_ids=body.doctor_ids,
        medicines=doctor_pdf.medicine_names(run),
        pdf_filename=filename,
        pdf_bytes=content,
    )
    return _envelope(request, ReviewRequestResponse(reviews=summaries))


@router.get("/reviews")
async def review_status(
    request: Request,
    runId: str,  # noqa: N803 - query parameters use the JSON camelCase contract
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse[ReviewListResponse]:
    """Review status for one run, so the app can show what the doctor decided."""
    summaries = await reviews.list_for_run(current_user.user_id, runId)
    approved = any(summary.status == "approved" for summary in summaries)
    return _envelope(request, ReviewListResponse(runId=runId, reviews=summaries, approved=approved))


@router.get("/reviews/{token}/document")
async def review_document(token: str) -> Response:
    """Serve the PDF behind the review token so the clinician can read it before deciding."""
    record = await reviews.get_review(token)
    run = await cosmos_repo.get_run(record["userId"], record["runId"])
    filename, content = doctor_pdf.build_for_run(run)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/reviews/{token}", response_class=HTMLResponse)
async def review_page(token: str) -> HTMLResponse:
    """Anonymous confirm page. Reading it records nothing."""
    record = await reviews.get_review(token)
    return HTMLResponse(_page(token, record))


@router.post("/reviews/{token}/decision", response_class=HTMLResponse)
async def submit_decision(
    token: str,
    decision: str = Form(...),
    notes: str = Form(""),
) -> HTMLResponse:
    """The confirm page's form target: the only route that writes a verdict."""
    record = await reviews.record_decision(token, decision=decision, notes=notes)
    return HTMLResponse(_page(token, record))


def _page(token: str, record: dict) -> str:
    """Self-contained HTML: a clinician's mail client should not need the SPA to load."""
    status = record["status"]
    label, ink, wash = _STATUS_COPY.get(status, _STATUS_COPY["pending"])
    doctor = html.escape(record["doctorName"])
    medicines = "".join(f"<li>{html.escape(name)}</li>" for name in record.get("medicines", []))
    document_url = f"/api/v1/reviews/{html.escape(token)}/document"

    if status == "pending":
        action = f"""
        <form method="post" action="/api/v1/reviews/{html.escape(token)}/decision">
          <label for="notes">Notes for the patient (optional)</label>
          <textarea id="notes" name="notes" rows="4"
                    placeholder="e.g. Continue the current brand for now; we will review at the next visit."></textarea>
          <div class="row">
            <button class="primary" type="submit" name="decision" value="approved">Approve</button>
            <button type="submit" name="decision" value="changes_requested">Request changes</button>
            <button class="danger" type="submit" name="decision" value="rejected">Do not approve</button>
          </div>
          <p class="fine">Nothing is recorded until you choose one of the buttons above.</p>
        </form>"""
    else:
        decided = html.escape((record.get("decidedAt") or "")[:16].replace("T", " "))
        note = html.escape(record.get("notes") or "")
        action = f"""
        <p class="done">Recorded on {decided} UTC. The patient can now see this in their app.</p>
        {f'<blockquote>{note}</blockquote>' if note else ''}"""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Health IQ - medicine review</title>
<style>
 body {{ font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; background:#f4f7fb;
        margin:0; padding:32px 16px; color:#0b1220; line-height:1.55; }}
 .card {{ max-width:680px; margin:0 auto; background:#fff; border-radius:14px; padding:32px;
        box-shadow:0 10px 30px -12px rgba(11,18,32,.25); }}
 h1 {{ font-size:1.4rem; margin:0 0 4px; }}
 .sub {{ color:#64748b; margin:0 0 20px; }}
 .pill {{ display:inline-block; padding:4px 12px; border-radius:999px; font-size:.8rem;
        font-weight:600; color:{ink}; background:{wash}; }}
 ul {{ padding-left:20px; }}
 a.doc {{ display:inline-block; margin:14px 0 22px; padding:10px 16px; border-radius:8px;
        background:#0f766e; color:#fff; text-decoration:none; font-weight:600; }}
 textarea {{ width:100%; padding:10px; border:1px solid #cbd5e1; border-radius:8px;
        font:inherit; box-sizing:border-box; }}
 label {{ display:block; font-weight:600; margin:18px 0 6px; }}
 .row {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }}
 button {{ padding:10px 18px; border-radius:8px; border:1px solid #cbd5e1; background:#fff;
        font:inherit; font-weight:600; cursor:pointer; }}
 button.primary {{ background:#16a34a; border-color:#16a34a; color:#fff; }}
 button.danger {{ color:#b91c1c; border-color:#fca5a5; }}
 .fine, footer {{ color:#64748b; font-size:.85rem; }}
 .done {{ font-weight:600; }}
 blockquote {{ border-left:3px solid #cbd5e1; margin:12px 0; padding-left:12px; color:#334155; }}
 footer {{ margin-top:26px; border-top:1px solid #e2e8f0; padding-top:14px; }}
</style></head>
<body><div class="card">
  <span class="pill">{label}</span>
  <h1>Medicine review request</h1>
  <p class="sub">For {doctor}. This is a request for your opinion, not a prescription change.</p>
  <p><strong>Medicines the patient uploaded:</strong></p>
  <ul>{medicines or '<li>See the attached document.</li>'}</ul>
  <a class="doc" href="{document_url}" target="_blank" rel="noopener">Open the full review PDF</a>
  {action}
  <footer>Health IQ does not diagnose or prescribe. Any lower-cost equivalent shown in the PDF is
  an estimate from curated public price data and is only presented to the patient as approved once
  you confirm it here.</footer>
</div></body></html>"""
