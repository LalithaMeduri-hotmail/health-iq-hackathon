"""`@ai_function` tool definitions (agents.instructions.md). Owner: D3.

Tools are thin adapters that call `services/`, `rag/`, or `repositories/` - no business logic in
the tool body. Give each tool a precise docstring and fully typed parameters/return; the model
routes on these signatures. Tools must be idempotent and side-effect-explicit.

Only the Prescription Analyzer tools are wired so far; the remaining TODOs (`normalize_lab`,
`reference_ranges`, `comparison`, `pdf_builder`, `share_links`) belong to the other feature
agents and are out of scope for this module until those agents are implemented.
"""

from typing import Annotated

from agent_framework import ai_function

from app.models.medicine import MedicineEntity
from app.rag.retrieve import RetrievedChunk
from app.rag.retrieve import search as rag_search
from app.services.normalize_medicine import find_alternatives as _find_alternatives
from app.services.ocr import OcrEnvelope
from app.services.ocr import extract as _ocr_extract


@ai_function
async def ocr_extract(
    file_base64: Annotated[str, "Base64-encoded prescription/tablet-strip image or PDF bytes."],
    mode: Annotated[str, "'read' for prescriptions/tablet strips, 'layout' for lab report tables."] = "read",
) -> OcrEnvelope:
    """Run Document Intelligence OCR and return the structured envelope (lines/confidence/tables)."""
    import base64

    return await _ocr_extract(base64.b64decode(file_base64), mode=mode)


@ai_function
def find_alternatives(item: Annotated[MedicineEntity, "One normalized medicine line to find alternatives for."]) -> list[dict]:
    """Find safety-gated cheaper/generic alternatives for `item` (deterministic SQL match, never fabricated)."""
    return _find_alternatives(item)


@ai_function
async def search_medicines(
    query: Annotated[str, "Free-text brand/ingredient/composition query, e.g. 'Amlodipine 5mg tablet'."],
) -> list[RetrievedChunk]:
    """Hybrid + semantic search against `idx-medicines` for brand/composition recall grounding."""
    return await rag_search("idx-medicines", query)
