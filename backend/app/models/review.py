"""Doctor-review request contracts (docs/lld/6-low-level-design-doctor-review-pdf-secure-share.md).

`models/` is a pure leaf: no imports from services, repositories, or SDK clients here.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReviewDecision = Literal["approved", "changes_requested", "rejected"]
ReviewState = Literal["pending", "approved", "changes_requested", "rejected", "expired"]

# Which of the two outcome documents a decided review produces.
PrescriptionKind = Literal["approved", "followup"]


class RegisteredDoctor(BaseModel):
    """One clinician from the curated Health IQ registry (`data/doctors/registered_doctors.csv`)."""

    model_config = ConfigDict(populate_by_name=True)

    doctor_id: str = Field(alias="doctorId")
    name: str
    specialty: str
    registration_no: str = Field(alias="registrationNo")
    # Masked for display (`d***@gmail.com`); the raw address never leaves the mailer.
    email_masked: str = Field(alias="emailMasked")


class DoctorListResponse(BaseModel):
    doctors: list[RegisteredDoctor]


class ReviewRequestBody(BaseModel):
    """`POST /api/v1/reviews/request` body."""

    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    doctor_ids: list[str] = Field(alias="doctorIds", min_length=1)
    # As printed on the patient's own prescription; it names the document the clinician signs.
    patient_name: str | None = Field(alias="patientName", default=None, max_length=80)


class MedicineVerdict(BaseModel):
    """The clinician's verdict on one medicine line; every line gets its own."""

    model_config = ConfigDict(populate_by_name=True)

    line_id: str = Field(alias="lineId")
    label: str
    decision: ReviewDecision


class ReviewSummary(BaseModel):
    """One outstanding or completed review, as the patient's app sees it."""

    model_config = ConfigDict(populate_by_name=True)

    review_id: str = Field(alias="reviewId")
    run_id: str = Field(alias="runId")
    doctor_name: str = Field(alias="doctorName")
    doctor_specialty: str = Field(alias="doctorSpecialty")
    doctor_email_masked: str = Field(alias="doctorEmailMasked")
    status: ReviewState
    requested_at: str = Field(alias="requestedAt")
    decided_at: str | None = Field(alias="decidedAt", default=None)
    notes: str | None = None
    delivery: str = "sent"
    decisions: list[MedicineVerdict] = Field(default_factory=list)


class ReviewRequestResponse(BaseModel):
    reviews: list[ReviewSummary]


class ReviewListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    reviews: list[ReviewSummary]
    approved: bool = False


class ReviewDecisionBody(BaseModel):
    """Body of the doctor's confirm-page POST."""

    decision: ReviewDecision
    notes: str = ""


class PrescriptionLine(BaseModel):
    """One medicine row of a Health IQ outcome document."""

    model_config = ConfigDict(populate_by_name=True)

    label: str
    maker: str = ""
    generic: str = ""
    form: str = ""
    strength: str = "-"
    frequency: str = "-"
    duration: str = "-"
    decision: ReviewDecision
    note: str = "-"


class PrescriptionDocument(BaseModel):
    """Everything the Health IQ prescription/follow-up PDF renders. Built after a doctor decides."""

    model_config = ConfigDict(populate_by_name=True)

    kind: PrescriptionKind
    patient_name: str = Field(alias="patientName")
    doctor_name: str = Field(alias="doctorName")
    doctor_specialty: str = Field(alias="doctorSpecialty")
    doctor_registration_no: str = Field(alias="doctorRegistrationNo")
    reviewed_at: str = Field(alias="reviewedAt")
    reference: str
    notes: str = ""
    lines: list[PrescriptionLine]
