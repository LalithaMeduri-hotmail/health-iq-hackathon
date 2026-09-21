"""Doctor-review request contracts (docs/lld/6-low-level-design-doctor-review-pdf-secure-share.md).

`models/` is a pure leaf: no imports from services, repositories, or SDK clients here.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReviewDecision = Literal["approved", "changes_requested", "rejected"]
ReviewState = Literal["pending", "approved", "changes_requested", "rejected", "expired"]


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
    # `lineId -> cheaperBrand` the patient picked. An unlisted line falls back to the best-value
    # match, so the clinician is never asked about a switch nobody chose.
    selections: dict[str, str] = Field(default_factory=dict)


class MedicineVerdict(BaseModel):
    """The clinician's verdict on one medicine line, with the switch it was a verdict about."""

    model_config = ConfigDict(populate_by_name=True)

    line_id: str = Field(alias="lineId")
    label: str
    decision: ReviewDecision
    maker: str = ""
    alternative: str = ""
    alternative_maker: str = Field(alias="alternativeMaker", default="")
    savings_pct: int = Field(alias="savingsPct", default=0)
    original_mrp_inr: float = Field(alias="originalMrpInr", default=0.0)
    cheaper_mrp_inr: float = Field(alias="cheaperMrpInr", default=0.0)


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
    """One medicine row of the Health IQ review summary: what was prescribed, what Health IQ
    proposed instead, and the clinician's verdict on that switch."""

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
    alternative: str = ""
    alternative_maker: str = Field(alias="alternativeMaker", default="")
    alternative_generic: str = Field(alias="alternativeGeneric", default="")
    savings_pct: int = Field(alias="savingsPct", default=0)
    original_mrp_inr: float = Field(alias="originalMrpInr", default=0.0)
    cheaper_mrp_inr: float = Field(alias="cheaperMrpInr", default=0.0)


class PrescriptionDocument(BaseModel):
    """Everything the single Health IQ review-summary PDF renders. Built after a doctor decides."""

    model_config = ConfigDict(populate_by_name=True)

    patient_name: str = Field(alias="patientName")
    doctor_name: str = Field(alias="doctorName")
    doctor_specialty: str = Field(alias="doctorSpecialty")
    doctor_registration_no: str = Field(alias="doctorRegistrationNo")
    reviewed_at: str = Field(alias="reviewedAt")
    reference: str
    notes: str = ""
    lines: list[PrescriptionLine]
