"""Doctor review-by-email routes (docs/lld/6-low-level-design-doctor-review-pdf-secure-share.md).

`GET /reviews/{token}` renders a confirm page and changes nothing - mail scanners prefetch links,
and an auto-approved medication change would be unacceptable. The verdict is only written by the
explicit `POST /reviews/{token}/decision` that page submits.
"""

import html
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.deps import CurrentUser, get_current_user
from app.errors import UnauthenticatedError, ValidationError
from app.models.common import ApiResponse, SafetyBlock
from app.models.review import (
    DoctorListResponse,
    ReviewListResponse,
    ReviewRequestBody,
    ReviewRequestResponse,
)
from app.repositories import cosmos_repo
from app.services import doctor_pdf, doctors, patients, reviews

router = APIRouter(prefix="/api/v1", tags=["reviews"])

_STATUS_COPY = {
    "approved": ("Approved", "#166534", "#dcfce7"),
    "changes_requested": ("Changes requested", "#b45309", "#fef3c7"),
    "rejected": ("Not approved", "#b91c1c", "#fee2e2"),
    "pending": ("Awaiting your decision", "#1d4ed8", "#dbeafe"),
}

# (value, full wording shown on hover/for screen readers, symbol on the button)
_DECISION_OPTIONS = (
    ("approved", "Approve", "&#10003;"),
    ("changes_requested", "Request change", "&#9998;"),
    ("rejected", "Do not approve", "&#10007;"),
)

_DECISION_LABELS = {value: label for value, label, _ in _DECISION_OPTIONS}
_DECISION_SYMBOLS = {value: symbol for value, _, symbol in _DECISION_OPTIONS}

# The buttons are imperative ("Approve"); a recorded verdict must read as already decided, and
# must match what the summary PDF and the patient's app show for the same decision.
_VERDICT_LABELS = {
    "approved": "Approved",
    "changes_requested": "Change requested",
    "rejected": "Not approved",
}

_DOCUMENT_COPY = "Health IQ review summary (PDF)"


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
    """`{ runId, doctorIds[], patientName }` -> emails each clinician the PDF plus an approval link."""
    run = await cosmos_repo.get_run(current_user.user_id, body.run_id)
    filename, content = doctor_pdf.build_for_run(run)

    summaries = await reviews.request_reviews(
        user_id=current_user.user_id,
        run_id=body.run_id,
        doctor_ids=body.doctor_ids,
        medicines=doctor_pdf.medicine_names(run),
        lines=doctor_pdf.medicine_lines(run, body.selections),
        patient_name=body.patient_name or await patients.display_name(current_user.user_id),
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


def _pdf_response(filename: str, content: bytes) -> Response:
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


UNLOCK_COOKIE_NAME = "hiq_review_unlock"


def _require_unlock(request: Request, token: str) -> None:
    """Possession of the link is not authorisation; the emailed PIN is."""
    if not reviews.is_unlocked(token, request.cookies.get(UNLOCK_COOKIE_NAME)):
        raise UnauthenticatedError("Enter the PIN from your email to open this review")


@router.get("/reviews/{token}/document")
async def review_document(token: str, request: Request) -> Response:
    """Serve the PDF behind the review token so the clinician can read it before deciding."""
    _require_unlock(request, token)
    record = await reviews.get_review(token)
    run = await cosmos_repo.get_run(record["userId"], record["runId"])
    filename, content = doctor_pdf.build_for_run(run)
    return _pdf_response(filename, content)


@router.get("/reviews/{token}/prescription")
async def review_outcome_document(token: str, request: Request) -> Response:
    """The clinician's copy of what they just signed: every medicine, alternative and verdict."""
    _require_unlock(request, token)
    record = await reviews.get_review(token)
    return _pdf_response(*await _build_outcome(record))


@router.get("/reviews/{review_id}/documents")
async def patient_outcome_document(
    review_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """The patient's copy of the same document, addressed by review id rather than the token."""
    record = await reviews.get_review_for_patient(current_user.user_id, review_id)
    return _pdf_response(*await _build_outcome(record))


async def _build_outcome(record: dict) -> tuple[str, bytes]:
    run = await cosmos_repo.get_run(record["userId"], record["runId"])
    patient_name = record.get("patientName") or await patients.display_name(record["userId"])
    return doctor_pdf.build_outcome_document(run, record, patient_name)


@router.get("/reviews/{token}", response_class=HTMLResponse)
async def review_page(token: str, request: Request) -> HTMLResponse:
    """Anonymous confirm page. Reading it records nothing.

    Until the emailed PIN is entered this shows only the PIN prompt - no patient name, no
    medicines - so a leaked link discloses nothing.
    """
    record = await reviews.get_review(token)
    if not reviews.is_unlocked(token, request.cookies.get(UNLOCK_COOKIE_NAME)):
        return _html_response(_pin_page(token, record))
    return _html_response(_page(token, record))


@router.post("/reviews/{token}/unlock", response_class=HTMLResponse)
async def unlock_review_page(token: str, request: Request) -> HTMLResponse:
    """Exchange the emailed PIN for a short-lived cookie scoped to this one review."""
    form = await request.form()
    try:
        record = await reviews.unlock_review(token, str(form.get("pin", "")))
    except ValidationError as exc:
        record = await reviews.get_review(token)
        return _html_response(_pin_page(token, record, error=exc.detail))

    value, max_age = reviews.issue_unlock_cookie(token)
    response = _html_response(_page(token, record))
    response.set_cookie(
        UNLOCK_COOKIE_NAME,
        value,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=get_settings().session_cookie_secure,
        path=f"/api/v1/reviews/{token}",
    )
    return response


@router.post("/reviews/{token}/decision", response_class=HTMLResponse)
async def submit_decision(token: str, request: Request) -> HTMLResponse:
    """The confirm page's form target: the only route that writes a verdict.

    Field names are `decision-<lineId>`, one per medicine, so the clinician answers each line
    individually instead of accepting or rejecting the whole summary.
    """
    _require_unlock(request, token)
    form = await request.form()
    decisions = {
        key[len("decision-") :]: str(value)
        for key, value in form.items()
        if key.startswith("decision-")
    }
    record = await reviews.record_decision(
        token, decisions=decisions, notes=str(form.get("notes", ""))
    )
    return _html_response(_page(token, record))


def _html_response(markup: str) -> HTMLResponse:
    """Never cached: a clinician revisiting the link must see the decision state as it is now."""
    return HTMLResponse(
        markup, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    )


def _named(name: str, maker: str) -> str:
    """Medicine name first, its maker in brackets after it - the name is what gets dispensed."""
    suffix = f' <span class="maker">({html.escape(maker)})</span>' if maker else ""
    return f"<strong>{html.escape(name)}</strong>{suffix}"


def _alternative_cell(line: dict) -> str:
    """What the clinician is actually being asked about: the switch, priced and sourced."""
    alternative = line.get("alternative")
    if not alternative:
        return '<span class="none">No equivalent found - confirm as read</span>'

    savings = line.get("savingsPct") or 0
    price = ""
    if line.get("originalMrpInr") and line.get("cheaperMrpInr"):
        price = (
            f'<span class="price">&#8377;{line["originalMrpInr"]:.2f} &rarr; '
            f'&#8377;{line["cheaperMrpInr"]:.2f}'
            f'{f" &middot; about {savings}% less" if savings else ""}</span>'
        )
    return _named(alternative, line.get("alternativeMaker", "")) + price


def _decide_form(token: str, lines: list[dict]) -> str:
    """One radio group per medicine. Nothing defaults to approved - every line is an explicit choice."""
    rows = ""
    for line in lines:
        line_id = html.escape(line["lineId"])
        # `title` carries the full wording the icon stands for, since the icon alone is ambiguous.
        picks = "".join(
            f'<label class="pick c-{value}" title="{label}"><input type="radio" required '
            f'name="decision-{line_id}" value="{value}" aria-label="{label} {html.escape(line["label"])}">'
            f'<span aria-hidden="true">{symbol}</span></label>'
            for value, label, symbol in _DECISION_OPTIONS
        )
        rows += (
            f'<tr><td class="medName">{_named(line["label"], line.get("maker", ""))}</td>'
            f"<td>{_alternative_cell(line)}</td>"
            f'<td class="picks">{picks}</td></tr>'
        )

    return f"""
    <form method="post" action="/api/v1/reviews/{html.escape(token)}/decision">
      <p class="lead">Choose one option for each medicine.</p>
      <div class="scroll">
        <table class="meds">
          <thead><tr><th>Current medicine</th><th>Health IQ alternative</th><th>Decision</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
      <p class="key">
        <span class="chip c-approved">&#10003;</span> Approve
        <span class="chip c-changes_requested">&#9998;</span> Request change
        <span class="chip c-rejected">&#10007;</span> Do not approve
      </p>
      <label for="notes">Notes for the patient (optional)</label>
      <textarea id="notes" name="notes" rows="3"
                placeholder="e.g. Continue the current brand for now; we will review at the next visit."></textarea>
      <div class="row"><button class="primary" type="submit">Record my decision</button></div>
      <p class="fine">Nothing is recorded until you submit this form.</p>
    </form>"""


def _outcome_links(token: str, record: dict) -> str:
    if not record.get("decisions"):
        return ""
    link = (
        f'<a class="doc" href="/api/v1/reviews/{html.escape(token)}/prescription" '
        f'target="_blank" rel="noopener">{_DOCUMENT_COPY}</a>'
    )
    return f"<p><strong>Document generated for the patient:</strong></p><p>{link}</p>"


def _decided_summary(record: dict) -> str:
    proposals = {entry["lineId"]: entry for entry in record.get("lines", [])}
    rows = ""
    for entry in record.get("decisions", []):
        decision = entry["decision"]
        label = _VERDICT_LABELS.get(decision, decision)
        proposal = proposals.get(entry["lineId"], {})
        rows += (
            f'<tr><td class="medName">{_named(entry["label"], proposal.get("maker", ""))}</td>'
            f"<td>{_alternative_cell(proposal)}</td>"
            f'<td class="picks"><span class="verdict c-{html.escape(decision)}" title="{label}">'
            f'<span aria-hidden="true">{_DECISION_SYMBOLS.get(decision, "")}</span> {label}</span></td></tr>'
        )
    if not rows:
        return ""
    return (
        '<div class="scroll"><table class="meds">'
        "<thead><tr><th>Current medicine</th><th>Health IQ alternative</th><th>Your decision</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )


def _page(token: str, record: dict) -> str:
    """Self-contained HTML: a clinician's mail client should not need the SPA to load."""
    status = record["status"]
    label, ink, wash = _STATUS_COPY.get(status, _STATUS_COPY["pending"])
    doctor = html.escape(record["doctorName"])
    patient = html.escape(record.get("patientName") or "not given")
    lines = record.get("lines") or []
    document_url = f"/api/v1/reviews/{html.escape(token)}/document"

    if status == "pending":
        body = (
            f'<p class="who">Patient: <strong>{patient}</strong></p>'
            "<p><strong>Medicines the patient uploaded:</strong></p>"
            f'<ul>{"".join(f"<li>{html.escape(name)}</li>" for name in record.get("medicines", []))}</ul>'
            f'<a class="doc" href="{document_url}" target="_blank" rel="noopener">Open the full review PDF</a>'
            f"{_decide_form(token, lines)}"
        )
    else:
        decided = html.escape((record.get("decidedAt") or "")[:16].replace("T", " "))
        note = html.escape(record.get("notes") or "")
        body = (
            f'<p class="who">Patient: <strong>{patient}</strong></p>'
            "<p><strong>Your decision:</strong></p>"
            f"{_decided_summary(record)}"
            f'<p class="done">Recorded on {decided} UTC. The patient can now see this in their app.</p>'
            f"{f'<blockquote>{note}</blockquote>' if note else ''}"
            f"{_outcome_links(token, record)}"
        )

    return _shell(label, ink, wash, doctor, body)


def _pin_page(token: str, record: dict, error: str = "") -> str:
    """Shown until the emailed PIN is entered. Deliberately carries no patient or medicine data."""
    doctor = html.escape(record["doctorName"])
    banner = (
        f'<p class="pinError">{html.escape(error)}</p>' if error else ""
    )
    body = (
        '<p class="who">This review is protected. Enter the 6-digit PIN from the Health IQ '
        "email sent to your inbox.</p>"
        f"{banner}"
        f'<form method="post" action="/api/v1/reviews/{html.escape(token)}/unlock">'
        '<label for="pin">Verification PIN</label>'
        '<input id="pin" name="pin" inputmode="numeric" autocomplete="one-time-code" '
        'pattern="[0-9]{6}" maxlength="6" required autofocus class="pinInput">'
        '<div class="row"><button class="primary" type="submit">Open the review</button></div>'
        '<p class="fine">The PIN is in the same email as this link. Without it nothing about the '
        "patient is shown.</p></form>"
    )
    return _shell("PIN required", "#1d4ed8", "#dbeafe", doctor, body)


def _shell(label: str, ink: str, wash: str, doctor: str, body: str) -> str:
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
 .who {{ color:#334155; margin:0 0 14px; }}
 a.doc {{ display:inline-block; margin:14px 8px 22px 0; padding:10px 16px; border-radius:8px;
        background:#0f766e; color:#fff; text-decoration:none; font-weight:600; }}
 textarea {{ width:100%; padding:10px; border:1px solid #cbd5e1; border-radius:8px;
        font:inherit; box-sizing:border-box; }}
 label {{ display:block; font-weight:600; margin:18px 0 6px; }}
 .lead {{ font-weight:600; margin:18px 0 8px; }}
 .scroll {{ overflow-x:auto; }}
 table.meds {{ width:100%; border-collapse:collapse; font-size:.85rem; }}
 table.meds th {{ text-align:left; font-size:.75rem; text-transform:uppercase; letter-spacing:.04em;
        color:#64748b; border-bottom:1px solid #e2e8f0; padding:0 10px 6px 0; white-space:nowrap; }}
 table.meds td {{ border-bottom:1px solid #f1f5f9; padding:10px 10px 10px 0; vertical-align:middle; }}
 table.meds td:last-child, table.meds th:last-child {{ padding-right:0; text-align:right;
        white-space:nowrap; }}
 .medName {{ font-weight:600; }}
 .maker {{ font-weight:400; color:#64748b; }}
 .price {{ display:block; color:#64748b; font-size:.78rem; }}
 .none {{ color:#94a3b8; }}
 .picks {{ white-space:nowrap; }}
 .picks label.pick + label.pick {{ margin-left:6px; }}
 label.pick {{ position:relative; display:inline-flex; align-items:center; justify-content:center;
        margin:0; width:30px; height:30px; border:1px solid #cbd5e1; border-radius:50%;
        cursor:pointer; font-size:.9rem; line-height:1; color:#475569; }}
 label.pick input {{ position:absolute; opacity:0; width:0; height:0; }}
 label.pick:hover {{ border-color:#94a3b8; background:#f8fafc; }}
 label.pick:has(input:focus-visible) {{ outline:2px solid #1d4ed8; outline-offset:2px; }}
 label.pick:has(input:checked) {{ color:#fff; }}
 .c-approved:has(input:checked) {{ background:#16a34a; border-color:#16a34a; }}
 .c-changes_requested:has(input:checked) {{ background:#d97706; border-color:#d97706; }}
 .c-rejected:has(input:checked) {{ background:#dc2626; border-color:#dc2626; }}
 .key {{ display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin:10px 0 0;
        color:#64748b; font-size:.8rem; }}
 .key .chip {{ display:inline-flex; align-items:center; justify-content:center; width:20px;
        height:20px; border-radius:50%; color:#fff; font-size:.75rem; margin-left:10px; }}
 .key .chip:first-child {{ margin-left:0; }}
 .chip.c-approved {{ background:#16a34a; }}
 .chip.c-changes_requested {{ background:#d97706; }}
 .chip.c-rejected {{ background:#dc2626; }}
 .verdict {{ display:inline-flex; align-items:center; gap:6px; padding:3px 10px;
        border-radius:999px; font-size:.78rem; font-weight:600; background:#e2e8f0; }}
 .verdict.c-approved {{ color:#166534; background:#dcfce7; }}
 .verdict.c-changes_requested {{ color:#b45309; background:#fef3c7; }}
 .verdict.c-rejected {{ color:#b91c1c; background:#fee2e2; }}
 .row {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }}
 button {{ padding:10px 18px; border-radius:8px; border:1px solid #cbd5e1; background:#fff;
        font:inherit; font-weight:600; cursor:pointer; }}
 button.primary {{ background:#16a34a; border-color:#16a34a; color:#fff; }}
 .fine, footer {{ color:#64748b; font-size:.85rem; }}
 .pinInput {{ font-size:1.6rem; letter-spacing:.5rem; width:9ch; padding:10px 12px;
        border:1px solid #cbd5e1; border-radius:8px; font-family:inherit; }}
 .pinError {{ background:#fee2e2; color:#b91c1c; border-radius:8px; padding:10px 14px;
        font-size:.9rem; font-weight:600; }}
 .done {{ font-weight:600; }}
 blockquote {{ border-left:3px solid #cbd5e1; margin:12px 0; padding-left:12px; color:#334155; }}
 footer {{ margin-top:26px; border-top:1px solid #e2e8f0; padding-top:14px; }}
</style></head>
<body><div class="card">
  <span class="pill">{label}</span>
  <h1>Medicine review request</h1>
  <p class="sub">For {doctor}. This is a request for your opinion, not a prescription change.</p>
  {body}
  <footer>Health IQ does not diagnose or prescribe. Any lower-cost equivalent shown in the PDF is
  an estimate from curated public price data and is only presented to the patient as approved once
  you confirm it here.</footer>
</div></body></html>"""
