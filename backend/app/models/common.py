"""Shared response envelope and error contracts (docs/lld/1-low-level-design-overview.md Section 0.3/0.4).

`models/` is a pure leaf: no imports from services, repositories, or SDK clients here.
"""

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DISCLAIMER_TEXT = (
    "This is a health information and doctor-collaboration assistant. It does not diagnose, "
    "prescribe, or replace clinical judgment. Any medicine alternative or health action must be "
    "reviewed by a qualified healthcare professional."
)


class SafetyBlock(BaseModel):
    """Mandatory safety verdict attached to every response by `SafetyReviewerAgent`."""

    model_config = ConfigDict(populate_by_name=True)

    pass_: bool = Field(alias="pass")
    notes: list[str] = Field(default_factory=list)
    reviewer_version: str = Field(alias="reviewerVersion", default="safety-1.0.0")


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Canonical success envelope every `api/` endpoint returns; never return a bare domain object."""

    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(alias="requestId")
    generated_at: datetime = Field(alias="generatedAt")
    api_version: str = Field(alias="apiVersion", default="v1")
    disclaimer: str = DISCLAIMER_TEXT
    safety: SafetyBlock
    data: T


class ProblemDetails(BaseModel):
    """RFC 7807 problem details, returned by the centralized exception handlers in `main.py`."""

    type: str
    title: str
    status: int
    detail: str
    instance: str
    errors: list[dict] = Field(default_factory=list)


class SourceRef(BaseModel):
    """Provenance for any medical/nutritional claim - required by SafetyReviewerAgent rule R2."""

    model_config = ConfigDict(populate_by_name=True)

    source_name: str = Field(alias="sourceName")
    source_url: str = Field(alias="sourceUrl")
    source_date: str = Field(alias="sourceDate")
