"""Document Intelligence wrapper (implementation-plan.md M1, Section 1.3-1.4). Owner: D1.

Contract frozen for D2/D3 consumption: `extract(file) -> OcrEnvelope`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    bbox: list[float]


@dataclass(frozen=True)
class OcrEnvelope:
    """`{ pages, lines[{text, confidence, bbox}], tables[], handwrittenRatio }`."""

    pages: int
    lines: list[OcrLine]
    tables: list[list[list[str]]]
    handwritten_ratio: float


async def extract(file: bytes, *, mode: str) -> OcrEnvelope:
    """Run OCR on `file`.

    `mode` is `"read"` (prescriptions/tablet strips, `prebuilt-read`) or `"layout"` (lab reports
    with tables, `prebuilt-layout`). Poll async operations with retry/backoff, 60s timeout.
    """
    raise NotImplementedError
