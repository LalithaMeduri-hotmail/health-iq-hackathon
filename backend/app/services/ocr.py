"""Document Intelligence wrapper (implementation-plan.md M1, Section 1.3-1.4). Owner: D1.

Contract frozen for D2/D3 consumption: `extract(file) -> OcrEnvelope`.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.errors import UpstreamTimeoutError, UpstreamUnavailableError

logger = logging.getLogger(__name__)

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ocr"
_DEMO_FIXTURE_PATH = _FIXTURE_DIR / "sample_prescription.json"
_DEMO_READ_FIXTURES = ("sample_prescription.json", "sample_prescription_02.json")
_DEMO_LAYOUT_FIXTURES = ("sample_lab_report_older.json", "sample_lab_report_newer.json")
_POLL_TIMEOUT_SECONDS = 60.0

_demo_read_calls = 0
_demo_layout_calls = 0


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    bbox: list[float]


@dataclass(frozen=True)
class OcrEnvelope:
    """`{ pages, lines[{text, confidence, bbox}], tables[], handwrittenRatio }`.

    `source` records what produced this: `docintel`, `pdf-text`, `image-ocr`, or `fixture`. Only
    the first three actually read the uploaded bytes, so only they can be trusted to say what the
    document is.
    """

    pages: int
    lines: list[OcrLine]
    tables: list[list[list[str]]]
    handwritten_ratio: float
    source: str = "fixture"

    @property
    def was_read(self) -> bool:
        """True when the uploaded bytes were genuinely read rather than replayed."""
        return self.source != "fixture"


def _load_demo_envelope(path: Path = _DEMO_FIXTURE_PATH) -> OcrEnvelope:
    """Replay a recorded OCR envelope (A2: `DEMO_MODE=true` avoids live-demo flakiness)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    lines = [OcrLine(text=line["text"], confidence=line["confidence"], bbox=line["bbox"]) for line in raw["lines"]]
    return OcrEnvelope(
        pages=raw["pages"], lines=lines, tables=raw.get("tables", []), handwritten_ratio=raw["handwrittenRatio"]
    )


def _demo_read_envelope() -> OcrEnvelope:
    """Replay the recorded prescription fixtures in rotation.

    Mirrors `_demo_layout_envelope`: consecutive image uploads replay *different* prescriptions,
    so each sample photo has a fixture that matches what it shows.
    """
    global _demo_read_calls
    fixture = _DEMO_READ_FIXTURES[_demo_read_calls % len(_DEMO_READ_FIXTURES)]
    _demo_read_calls += 1
    return _load_demo_envelope(_FIXTURE_DIR / fixture)


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
    return OcrEnvelope(
        pages=len(result.pages or []),
        lines=lines,
        tables=tables,
        handwritten_ratio=handwritten_ratio,
        source="docintel",
    )


def _is_pdf(file: bytes) -> bool:
    return file.startswith(b"%PDF")


_TABLE_HEADER_ALIASES = frozenset(
    {
        "test", "tests", "parameter", "parameters", "analyte", "investigation",
        "result", "results", "value", "observed value", "observation",
        "unit", "units",
        "reference range", "range", "normal range", "reference interval", "bio. ref. range",
    }
)


def _is_numeric(cell: str) -> bool:
    try:
        float(cell.strip().replace(",", ""))
    except ValueError:
        return False
    return True


def _reconstruct_tables(texts: list[str]) -> list[list[list[str]]]:
    """Regroup a lab table that PDF text extraction flattened to one cell per line.

    Finds a run of consecutive column headers, then chunks the following lines by that column
    count for as long as each chunk still carries a numeric result - which stops cleanly at the
    footer text below the table.
    """
    for start, _ in enumerate(texts):
        width = 0
        while (
            start + width < len(texts)
            and texts[start + width].strip().casefold() in _TABLE_HEADER_ALIASES
        ):
            width += 1
        if width < 3:
            continue

        header = [texts[start + offset].strip() for offset in range(width)]
        rows: list[list[str]] = []
        cursor = start + width
        while cursor + width <= len(texts):
            chunk = [texts[cursor + offset].strip() for offset in range(width)]
            if not any(_is_numeric(cell) for cell in chunk):
                break
            rows.append(chunk)
            cursor += width

        if rows:
            return [[header, *rows]]
    return []


def _extract_pdf_text(file: bytes) -> OcrEnvelope | None:
    """Read a digital PDF's embedded text locally.

    Returns `None` when there is no text to take - a scanned/image-only PDF, or one this parser
    cannot open - so the caller falls through to real OCR. Text drawn into a PDF is exact, so
    confidence is 1.0: there is no character-recognition guesswork to be unsure about.
    """
    from io import BytesIO

    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(file))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # noqa: BLE001 - any parse failure just means "no text here"
        logger.info("local PDF text extraction skipped: %s", type(exc).__name__)
        return None

    texts = [stripped for page in pages for raw in page.splitlines() if (stripped := raw.strip())]
    if not texts:
        return None

    lines = [OcrLine(text=text, confidence=1.0, bbox=[]) for text in texts]
    return OcrEnvelope(
        pages=len(pages),
        lines=lines,
        tables=_reconstruct_tables(texts),
        handwritten_ratio=0.0,
        source="pdf-text",
    )


def _extract_image_text(file: bytes) -> OcrEnvelope | None:
    """Recognise text in an uploaded photo with a local Tesseract install.

    Returns `None` when Tesseract is not available, so the caller falls back. Per-word confidence
    is averaged into a per-line score, which is what drives the confirmation gate: a smudged or
    handwritten line scores low and the user is asked to check it.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None

    from io import BytesIO

    try:
        with Image.open(BytesIO(file)) as image:
            data = pytesseract.image_to_data(
                image.convert("RGB"), output_type=pytesseract.Output.DICT
            )
    except Exception as exc:  # noqa: BLE001 - a missing binary or odd image just means "no text"
        logger.info("local image OCR skipped: %s", type(exc).__name__)
        return None

    # Tesseract emits one row per word; regroup by (block, paragraph, line) to rebuild lines.
    grouped: dict[tuple[int, int, int], list[tuple[str, float]]] = {}
    for index, word in enumerate(data["text"]):
        stripped = word.strip()
        confidence = float(data["conf"][index])
        if not stripped or confidence < 0:
            continue
        key = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
        grouped.setdefault(key, []).append((stripped, confidence / 100.0))

    lines = [
        OcrLine(
            text=" ".join(word for word, _ in words),
            confidence=sum(score for _, score in words) / len(words),
            bbox=[],
        )
        for _, words in sorted(grouped.items())
        if words
    ]
    if not lines:
        return None

    return OcrEnvelope(
        pages=1,
        lines=lines,
        tables=_reconstruct_tables([line.text for line in lines]),
        handwritten_ratio=0.0,
        source="image-ocr",
    )


async def extract(file: bytes, *, mode: str) -> OcrEnvelope:
    """Run OCR on `file`.

    `mode` is `"read"` (prescriptions/tablet strips, `prebuilt-read`) or `"layout"` (lab reports
    with tables, `prebuilt-layout`). Poll async operations with retry/backoff, 60s timeout.

    Resolution order, first that can actually read the bytes wins: Document Intelligence, then a
    digital PDF's embedded text, then local Tesseract for photos. Only when none of those is
    available does an image fall back to the recorded fixtures.
    """
    if mode not in ("read", "layout"):
        raise NotImplementedError(f"Unknown OCR mode {mode!r}; expected 'read' or 'layout'")

    settings = get_settings()
    if not settings.demo_mode and settings.azure_docintel_endpoint:
        return await _extract_live(file, mode=mode)

    if _is_pdf(file):
        envelope = await asyncio.to_thread(_extract_pdf_text, file)
        if envelope is not None:
            return envelope
    else:
        envelope = await asyncio.to_thread(_extract_image_text, file)
        if envelope is not None:
            return envelope

    if not settings.demo_mode:
        raise UpstreamUnavailableError(
            "Reading this file needs an OCR engine; set AZURE_DOCINTEL_ENDPOINT or "
            "install Tesseract."
        )
    logger.warning("no OCR engine available for this upload; replaying a recorded fixture")
    return _demo_layout_envelope() if mode == "layout" else _demo_read_envelope()
