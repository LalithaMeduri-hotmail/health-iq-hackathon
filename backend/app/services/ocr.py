"""Document Intelligence wrapper (implementation-plan.md M1, Section 1.3-1.4). Owner: D1.

Contract frozen for D2/D3 consumption: `extract(file) -> OcrEnvelope`.
"""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.errors import UpstreamTimeoutError, UpstreamUnavailableError

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ocr"
_DEMO_FIXTURE_PATH = _FIXTURE_DIR / "sample_prescription.json"
_DEMO_LAYOUT_FIXTURES = ("sample_lab_report_older.json", "sample_lab_report_newer.json")
_POLL_TIMEOUT_SECONDS = 60.0

_demo_layout_calls = 0


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


def _load_demo_envelope(path: Path = _DEMO_FIXTURE_PATH) -> OcrEnvelope:
    """Replay a recorded OCR envelope (A2: `DEMO_MODE=true` avoids live-demo flakiness)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    lines = [OcrLine(text=line["text"], confidence=line["confidence"], bbox=line["bbox"]) for line in raw["lines"]]
    return OcrEnvelope(
        pages=raw["pages"], lines=lines, tables=raw.get("tables", []), handwritten_ratio=raw["handwrittenRatio"]
    )


def _demo_layout_envelope() -> OcrEnvelope:
    """Replay the recorded lab-report fixtures in rotation.

    Consecutive uploads therefore replay *different* reports, which keeps the two-report
    comparison flow demonstrable without a live Document Intelligence resource.
    """
    global _demo_layout_calls
    fixture = _DEMO_LAYOUT_FIXTURES[_demo_layout_calls % len(_DEMO_LAYOUT_FIXTURES)]
    _demo_layout_calls += 1
    return _load_demo_envelope(_FIXTURE_DIR / fixture)


async def _extract_live(file: bytes, *, mode: str) -> OcrEnvelope:
    """Real `prebuilt-read`/`prebuilt-layout` call via Document Intelligence, polled with backoff to 60s."""
    from app.deps import get_docintel_client

    model_id = "prebuilt-layout" if mode == "layout" else "prebuilt-read"
    client = get_docintel_client()
    try:
        async with asyncio.timeout(_POLL_TIMEOUT_SECONDS):
            poller = await client.begin_analyze_document(model_id, body=file, content_type="application/octet-stream")
            result = await poller.result()
    except TimeoutError as exc:
        raise UpstreamTimeoutError("Document Intelligence did not complete within 60s") from exc
    except Exception as exc:  # noqa: BLE001 - any SDK failure surfaces as a typed upstream error
        raise UpstreamUnavailableError(f"Document Intelligence request failed: {exc}") from exc

    lines: list[OcrLine] = []
    for page in result.pages or []:
        page_words = page.words or []
        for line in page.lines or []:
            # Confidence lives on page words, not on the line itself.
            line_spans = [(span.offset, span.offset + span.length) for span in (line.spans or [])]
            word_confidences = [
                word.confidence
                for word in page_words
                if any(start <= word.span.offset < end for start, end in line_spans)
            ]
            confidence = min(word_confidences) if word_confidences else 1.0
            polygon = line.polygon or []
            lines.append(OcrLine(text=line.content, confidence=confidence, bbox=[float(p) for p in polygon]))

    tables: list[list[list[str]]] = []
    for table in result.tables or []:
        grid: list[list[str]] = [["" for _ in range(table.column_count)] for _ in range(table.row_count)]
        for cell in table.cells:
            grid[cell.row_index][cell.column_index] = cell.content
        tables.append(grid)

    content_length = len(result.content or "")
    handwritten_length = sum(
        span.length for style in (result.styles or []) if style.is_handwritten for span in (style.spans or [])
    )
    handwritten_ratio = (handwritten_length / content_length) if content_length else 0.0
    return OcrEnvelope(pages=len(result.pages or []), lines=lines, tables=tables, handwritten_ratio=handwritten_ratio)


async def extract(file: bytes, *, mode: str) -> OcrEnvelope:
    """Run OCR on `file`.

    `mode` is `"read"` (prescriptions/tablet strips, `prebuilt-read`) or `"layout"` (lab reports
    with tables, `prebuilt-layout`). Poll async operations with retry/backoff, 60s timeout.
    """
    settings = get_settings()
    if settings.demo_mode:
        return _demo_layout_envelope() if mode == "layout" else _load_demo_envelope()
    if mode in ("read", "layout"):
        return await _extract_live(file, mode=mode)
    raise NotImplementedError(f"Unknown OCR mode {mode!r}; expected 'read' or 'layout'")
