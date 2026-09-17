"""Document triage: is this upload a prescription or a lab report?

The model reads the OCR text and decides, because the keyword counting it replaces cannot cope
with layouts it has never seen (a lab report that lists current medications, a prescription
quoting one lab value). `services/document_type.py` remains the offline fallback so demo mode
and the test suite still route correctly without a model.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.agents import llm
from app.services import document_type

_LOW_CONFIDENCE = 0.6


class DocumentVerdict(BaseModel):
    """What the triage agent returns; `reason` is recorded for audit, never shown as advice."""

    kind: Literal["prescription", "lab_report", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reason: str = ""


async def classify(text: str) -> DocumentVerdict:
    """Classify `text`, falling back to keyword scoring when no model is available."""
    if not text or not text.strip():
        return DocumentVerdict(kind="unknown", reason="no readable text")

    verdict = await llm.structured(
        instructions=llm.prompt("document_agent"),
        task="Classify this uploaded health document.",
        data=text[:6000],
        schema=DocumentVerdict,
        name="DocumentTriageAgent",
    )
    if verdict is None:
        return DocumentVerdict(
            kind=document_type.classify(text), confidence=0.5, reason="keyword fallback (no model)"
        )

    # A hesitant model is treated as undecided rather than trusted into the wrong feature.
    if verdict.confidence < _LOW_CONFIDENCE:
        return DocumentVerdict(kind="unknown", confidence=verdict.confidence, reason=verdict.reason)
    return verdict
