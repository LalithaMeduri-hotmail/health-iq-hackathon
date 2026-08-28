"""Document Intelligence wrapper (implementation-plan.md M1, Section 1.3-1.4). Owner: D1.

Contract frozen for D2/D3 consumption: `extract(file) -> OcrEnvelope`.
"""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.errors import UpstreamTimeoutError, UpstreamUnavailableError

_DEMO_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ocr" / "sample_prescription.json"
_POLL_TIMEOUT_SECONDS = 60.0


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


def _load_demo_envelope() -> OcrEnvelope:
    """Replay a recorded OCR envelope (A2: `DEMO_MODE=true` avoids live-demo flakiness)."""
    raw = json.loads(_DEMO_FIXTURE_PATH.read_text(encoding="utf-8"))
    lines = [OcrLine(text=line["text"], confidence=line["confidence"], bbox=line["bbox"]) for line in raw["lines"]]
    return OcrEnvelope(
        pages=raw["pages"], lines=lines, tables=raw.get("tables", []), handwritten_ratio=raw["handwrittenRatio"]
    )


async def _extract_read_live(file: bytes) -> OcrEnvelope:
    """Real `prebuilt-read` call via Document Intelligence, polled with backoff to 60s."""
    from app.deps import get_docintel_client

    client = get_docintel_client()
    try:
        async with asyncio.timeout(_POLL_TIMEOUT_SECONDS):
            poller = await client.begin_analyze_document("prebuilt-read", body=file, content_type="application/octet-stream")
            result = await poller.result()
    except TimeoutError as exc:
        raise UpstreamTimeoutError("Document Intelligence did not complete within 60s") from exc
    except Exception as exc:  # noqa: BLE001 - any SDK failure surfaces as a typed upstream error
        raise UpstreamUnavailableError(f"Document Intelligence request failed: {exc}") from exc

    lines: list[OcrLine] = []
    handwritten_count = 0
    total_count = 0
    for page in result.pages or []:
        for line in page.lines or []:
            confidence = min((word.confidence for word in (line.words or [])), default=1.0)
            polygon = getattr(line, "polygon", None) or []
            lines.append(OcrLine(text=line.content, confidence=confidence, bbox=[float(p) for p in polygon]))
            total_count += 1
            if getattr(line, "kind", None) == "handwriting":
                handwritten_count += 1

    tables: list[list[list[str]]] = []
    for table in result.tables or []:
        grid: list[list[str]] = [["" for _ in range(table.column_count)] for _ in range(table.row_count)]
        for cell in table.cells:
            grid[cell.row_index][cell.column_index] = cell.content
        tables.append(grid)

    handwritten_ratio = (handwritten_count / total_count) if total_count else 0.0
    return OcrEnvelope(pages=len(result.pages or []), lines=lines, tables=tables, handwritten_ratio=handwritten_ratio)


async def extract(file: bytes, *, mode: str) -> OcrEnvelope:
    """Run OCR on `file`.

    `mode` is `"read"` (prescriptions/tablet strips, `prebuilt-read`) or `"layout"` (lab reports
    with tables, `prebuilt-layout`). Poll async operations with retry/backoff, 60s timeout.
    """
    settings = get_settings()
    if settings.demo_mode:
        return _load_demo_envelope()
    if mode == "read":
        return await _extract_read_live(file)
    raise NotImplementedError(f"OCR mode {mode!r} not yet implemented; only 'read' is wired for live calls")
