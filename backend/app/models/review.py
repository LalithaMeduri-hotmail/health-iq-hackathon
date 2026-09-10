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
