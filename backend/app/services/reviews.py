"""Doctor-review requests: tokenised approval links, email dispatch, and decision capture.

Security model mirrors `share_links.py`: a 128-bit URL-safe token is emailed to the clinician
and only its SHA-256 is persisted. `GET` on the link is side-effect free (mail scanners routinely
prefetch links, and an auto-approved medication change would be unacceptable); the verdict is
only recorded by an explicit `POST` from the confirm page.
"""

import hashlib
import html
import logging
import secrets
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.errors import GoneError, NotFoundError, UpstreamUnavailableError, ValidationError
from app.models.review import IssuedPrescription, MedicineVerdict, ReviewSummary
from app.repositories import sql_repo
from app.services import doctors, email, security

logger = logging.getLogger(__name__)

_TOKEN_BYTES = 16  # 128-bit URL-safe token
_DECISIONS = {"approved", "changes_requested", "rejected"}


_PROPOSAL_FIELDS = (
    "maker",
    "alternative",
    "alternativeMaker",
    "savingsPct",
    "originalMrpInr",
    "cheaperMrpInr",
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _verdicts(record: dict) -> list[MedicineVerdict]:
    """Each verdict rejoined to the switch it answered, so the app can show both side by side."""
    proposals = {line["lineId"]: line for line in record.get("lines", [])}
    merged = []
    for entry in record.get("decisions", []):
        proposal = proposals.get(entry["lineId"], {})
        merged.append(
            MedicineVerdict.model_validate(
                entry | {key: proposal[key] for key in _PROPOSAL_FIELDS if proposal.get(key)}
            )
        )
    return merged


def _summary(record: dict, review_id: str = "") -> ReviewSummary:
    return ReviewSummary(
        reviewId=review_id or record.get("reviewId", ""),
        runId=record["runId"],
        doctorName=record["doctorName"],
        doctorSpecialty=record["doctorSpecialty"],
        doctorEmailMasked=record["doctorEmailMasked"],
        status=record["status"],
        requestedAt=record["requestedAt"],
        decidedAt=record.get("decidedAt"),
        notes=record.get("notes") or None,
        delivery=record.get("delivery", "sent"),
        decisions=_verdicts(record),
    )


def _body(
    doctor_name: str, patient_ref: str, medicines: list[str], approval_url: str, pin: str
) -> str:
    listed = "\n".join(f"  - {name}" for name in medicines) or "  - (see attached PDF)"
    return f"""Dear {doctor_name},

A Health IQ user ({patient_ref}) has asked you to review the attached medicine summary before
they act on anything in it. This is a review request, not a prescription change.

Medicines extracted from their prescription:
{listed}

The attached PDF lists each medicine as it was read, how confident the reader was, and any
lower-cost equivalent with its price source and date.

To record your decision, open:
  {approval_url}

The page will ask for this verification PIN before it shows anything:
  {pin}

The PIN is what proves it is you: anyone who only has the link cannot open the review. Please do
not forward this email. Nothing is recorded by opening the link. It expires in
{get_settings().review_link_ttl_hours // 24} days.

Health IQ does not diagnose or prescribe. No change is shown to the user as approved until you
confirm it here.
"""


def _html_body(
    doctor_name: str, patient_ref: str, medicines: list[str], approval_url: str, pin: str
) -> str:
    """Same message as `_body`, with a button. Gmail strips <style>, so every rule is inline."""
    listed = (
        "".join(f"<li>{html.escape(name)}</li>" for name in medicines)
        or "<li>(see attached PDF)</li>"
    )
    ttl_days = get_settings().review_link_ttl_hours // 24
    return f"""\
<html><body style="margin:0;padding:24px;background:#f1f5f9;
    font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0b1220;">
  <div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;padding:28px;">
    <p style="margin:0 0 4px;font-size:13px;color:#64748b;">Health IQ</p>
    <h1 style="margin:0 0 16px;font-size:20px;">Medicine review request</h1>
    <p style="margin:0 0 16px;font-size:14px;line-height:1.5;">
      Dear {html.escape(doctor_name)}, a Health IQ user ({html.escape(patient_ref)}) has asked you
      to review the attached medicine summary before they act on anything in it.
      <strong>This is a request for your opinion, not a prescription change.</strong>
    </p>
    <p style="margin:0 0 6px;font-size:14px;">
      <strong>Medicines extracted from their prescription:</strong>
    </p>
    <ul style="margin:0 0 24px;padding-left:20px;font-size:14px;line-height:1.6;">{listed}</ul>
    <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
      <tr><td style="border-radius:8px;background:#0f766e;">
        <a href="{html.escape(approval_url, quote=True)}"
           style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:600;
                  color:#ffffff;text-decoration:none;">Review &amp; record my decision</a>
      </td></tr>
    </table>
    <div style="margin:0 0 20px;padding:16px;border:1px solid #e2e8f0;border-radius:8px;
                background:#f8fafc;">
      <p style="margin:0 0 6px;font-size:13px;color:#64748b;">Your verification PIN</p>
      <p style="margin:0;font-size:28px;font-weight:700;letter-spacing:6px;color:#0b1220;">
        {html.escape(pin)}
      </p>
      <p style="margin:8px 0 0;font-size:12px;color:#64748b;line-height:1.5;">
        The page asks for this before it shows anything. The PIN is what proves it is you -
        anyone holding only the link cannot open the review. Please do not forward this email.
      </p>
    </div>
    <p style="margin:0 0 16px;font-size:12px;color:#64748b;line-height:1.5;">
      Opening the link records nothing - the page shows each medicine with the equivalent the
      patient chose and asks you to confirm before anything is saved.
      The link expires in {ttl_days} days.
    </p>
    <p style="margin:0 0 16px;font-size:12px;color:#64748b;word-break:break-all;">
      If the button does not work, paste this into your browser:<br>{html.escape(approval_url)}
    </p>
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
    <p style="margin:0;font-size:11px;color:#94a3b8;line-height:1.5;">
      Health IQ does not diagnose or prescribe. No change is shown to the patient as approved
      until you confirm it here.
    </p>
  </div>
</body></html>"""


async def request_reviews(
    *,
    user_id: str,
    run_id: str,
    doctor_ids: list[str],
    medicines: list[str],
    lines: list[dict],
    patient_name: str,
    pdf_filename: str,
    pdf_bytes: bytes,
) -> list[ReviewSummary]:
    """Create one tokenised review per clinician and email each of them the PDF."""
    if not doctor_ids:
        raise ValidationError("Pick at least one doctor to send this to")
    if not patient_name.strip():
        raise ValidationError(
            "Add the patient name exactly as it appears on the prescription",
            errors=[{"field": "patientName", "issue": "required"}],
        )

    settings = get_settings()
    expires_at = (datetime.now(UTC) + timedelta(hours=settings.review_link_ttl_hours)).isoformat()
    summaries: list[ReviewSummary] = []

    for doctor_id in dict.fromkeys(doctor_ids):
        doctor, address = doctors.get_address(doctor_id)
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        approval_url = f"{settings.public_api_base_url.rstrip('/')}/api/v1/reviews/{token}"
        pin = security.generate_review_pin()

        # One unreachable mailbox must not discard the reviews already raised for the others, so
        # the failure is recorded on the review rather than raised.
        try:
            delivery = await email.send(
                address,
                f"Health IQ - medicine review request for {doctor.name}",
                _body(doctor.name, user_id, medicines, approval_url, pin),
                attachment=(pdf_filename, pdf_bytes),
                html_body=_html_body(doctor.name, user_id, medicines, approval_url, pin),
            )
        except UpstreamUnavailableError as exc:
            # Without the reason this is undiagnosable after the fact: the request still returns
            # 200 and the only trace is this line.
            logger.warning(
                "review email could not be delivered to doctor %s: %s", doctor_id, exc.detail
            )
            delivery = "failed"

        record = {
            "reviewId": token[:8],
            "userId": user_id,
            "runId": run_id,
            "patientName": patient_name.strip(),
            "doctorId": doctor.doctor_id,
            "doctorName": doctor.name,
            "doctorSpecialty": doctor.specialty,
            "doctorRegistrationNo": doctor.registration_no,
            "doctorEmailMasked": doctor.email_masked,
            "medicines": medicines,
            "lines": lines,
            "decisions": [],
            "pdfFilename": pdf_filename,
            "status": "pending",
            "notes": "",
            "requestedAt": datetime.now(UTC).isoformat(),
            "decidedAt": None,
            "expiresAt": expires_at,
            "delivery": delivery,
            # Only the hash is stored: a database or log leak must not yield a usable PIN.
            "pinHash": security.hash_pin(pin),
            "pinFailedAttempts": 0,
            "pinLockedUntil": None,
        }
        await sql_repo.create_doctor_review(_hash(token), record)
        summaries.append(_summary(record))

    return summaries


async def get_review(token: str) -> dict:
    """Resolve an emailed token. Side-effect free, so link prefetching cannot change state."""
    record = await sql_repo.get_doctor_review(_hash(token))
    if record is None:
        raise NotFoundError("This review link is not valid")
    if datetime.fromisoformat(record["expiresAt"]) < datetime.now(UTC):
        raise GoneError("This review link has expired")
    return record


async def unlock_review(token: str, pin: str) -> dict:
    """Check the emailed PIN for one review, throttling guesses.

    The URL token alone is not enough to see or decide anything: possession of the link proves
    nothing about who is holding it, so the PIN from the doctor's own inbox is the second factor.
    """
    record = await get_review(token)
    settings = get_settings()
    now = datetime.now(UTC)

    locked_until = record.get("pinLockedUntil")
    if locked_until and datetime.fromisoformat(locked_until) > now:
        raise ValidationError("Too many incorrect PINs. Try again later.")

    pin_hash = record.get("pinHash") or ""
    if not pin_hash:
        raise ValidationError("This review link cannot be verified. Ask the patient to resend it.")

    if not security.verify_pin(pin.strip(), pin_hash):
        attempts = int(record.get("pinFailedAttempts") or 0) + 1
        lock_until = (
            (now + timedelta(minutes=settings.pin_lockout_minutes)).isoformat()
            if attempts >= settings.pin_max_failed_attempts
            else None
        )
        await sql_repo.record_review_pin_attempt(
            _hash(token), failed_attempts=attempts, locked_until=lock_until
        )
        if lock_until:
            raise ValidationError("Too many incorrect PINs. Try again later.")
        raise ValidationError("That PIN does not match. Check the email and try again.")

    await sql_repo.record_review_pin_attempt(_hash(token), failed_attempts=0, locked_until=None)
    return record


def issue_unlock_cookie(token: str) -> tuple[str, int]:
    """`(cookie value, max-age seconds)` proving this browser answered the PIN for this review."""
    return security.issue_review_unlock(_hash(token), get_settings().review_unlock_minutes)


def is_unlocked(token: str, cookie_value: str | None) -> bool:
    return bool(cookie_value) and security.review_unlock_matches(cookie_value, _hash(token))


def _overall_status(decisions: list[dict]) -> str:
    """One review-level status from the per-medicine verdicts, worst outcome first.

    A patient acting on a summary needs the weakest verdict to be the headline: any medicine the
    clinician did not approve as read means the summary as a whole is not approved.
    """
    verdicts = {entry["decision"] for entry in decisions}
    if verdicts == {"approved"}:
        return "approved"
    if verdicts == {"rejected"}:
        return "rejected"
    return "changes_requested"


async def record_decision(token: str, *, decisions: dict[str, str], notes: str) -> dict:
    """Record the clinician's per-medicine verdicts. A decided review cannot be overwritten."""
    record = await get_review(token)
    if record["status"] != "pending":
        raise ValidationError("A decision has already been recorded for this review")

    lines = record.get("lines") or []
    if not lines:
        raise ValidationError("This review has no medicines to decide on")

    resolved: list[dict] = []
    for line in lines:
        decision = decisions.get(line["lineId"])
        if decision is None:
            raise ValidationError(f"Choose an option for {line['label']}")
        if decision not in _DECISIONS:
            raise ValidationError(f"{decision!r} is not a valid decision")
        resolved.append({"lineId": line["lineId"], "label": line["label"], "decision": decision})

    decided_at = datetime.now(UTC).isoformat()
    await sql_repo.record_doctor_decision(
        _hash(token),
        status=_overall_status(resolved),
        notes=notes.strip()[:1000],
        decided_at=decided_at,
        decisions=resolved,
    )
    decided = await sql_repo.get_doctor_review(_hash(token)) or record
    await _issue_prescription(decided)
    return decided


async def _issue_prescription(review: dict) -> None:
    """Snapshot the decided review into the patient profile's prescription history.

    Written here rather than rendered on demand because the review record is transient and the
    medicine catalog moves: a recheck months later must show what the clinician approved, at the
    prices they saw. A storage failure must not lose the clinician's decision, so it is logged
    rather than raised.
    """
    from app.repositories import cosmos_repo
    from app.services import doctor_pdf, patients

    try:
        run = await cosmos_repo.get_run(review["userId"], review["runId"])
        profile_id = run.get("profileId")
        if not profile_id:
            # An uploaded prescription stays unassigned until the patient confirms whose it is.
            logger.info("review %s has no profile yet; not filed to history", review["reviewId"])
            return

        patient_name = review.get("patientName") or await patients.display_name(review["userId"])
        document = doctor_pdf.build_document_model(run, review, patient_name)
        await cosmos_repo.save_prescription(
            IssuedPrescription(
                id=f"rx-{review['reviewId']}",
                accountId=review["userId"],
                profileId=profile_id,
                runId=review["runId"],
                reviewId=review["reviewId"],
                status=review["status"],
                issuedAt=review["decidedAt"],
                document=document,
            )
        )
    except Exception:  # noqa: BLE001 - history is secondary to recording the verdict
        logger.exception("could not file the issued prescription for review %s", review["reviewId"])


async def get_review_for_patient(user_id: str, review_id: str) -> dict:
    """The patient's own copy of one review, by short id and scoped by `userId`.

    The emailed token is the clinician's credential and is never shown to the patient, so their
    app addresses a review by `reviewId` instead.
    """
    record = await sql_repo.find_doctor_review(user_id, review_id)
    if record is None:
        raise NotFoundError("No such review")
    return record


async def list_for_run(user_id: str, run_id: str) -> list[ReviewSummary]:
    """Every review raised for one run, for the patient's status panel."""
    return [_summary(record) for record in await sql_repo.list_doctor_reviews(user_id, run_id)]
