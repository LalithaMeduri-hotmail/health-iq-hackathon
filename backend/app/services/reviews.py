"""Doctor-review requests: tokenised approval links, email dispatch, and decision capture.

Security model mirrors `share_links.py`: a 128-bit URL-safe token is emailed to the clinician
and only its SHA-256 is persisted. `GET` on the link is side-effect free (mail scanners routinely
prefetch links, and an auto-approved medication change would be unacceptable); the verdict is
only recorded by an explicit `POST` from the confirm page.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.errors import GoneError, NotFoundError, ValidationError
from app.models.review import MedicineVerdict, ReviewSummary
from app.repositories import sql_repo
from app.services import doctors, email

_TOKEN_BYTES = 16  # 128-bit URL-safe token
_DECISIONS = {"approved", "changes_requested", "rejected"}


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
        decisions=[MedicineVerdict.model_validate(entry) for entry in record.get("decisions", [])],
    )


def _body(doctor_name: str, patient_ref: str, medicines: list[str], approval_url: str) -> str:
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

The page shows the same details and asks you to confirm before anything is saved. Nothing is
recorded by opening this link. It expires in {get_settings().review_link_ttl_hours // 24} days.

Health IQ does not diagnose or prescribe. No change is shown to the user as approved until you
confirm it here.
"""


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

        delivery = await email.send(
            address,
            f"Health IQ - medicine review request for {doctor.name}",
            _body(doctor.name, user_id, medicines, approval_url),
            attachment=(pdf_filename, pdf_bytes),
        )

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
    return await sql_repo.get_doctor_review(_hash(token)) or record


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
