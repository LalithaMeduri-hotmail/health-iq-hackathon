"""`@tool` function-tool definitions (agents.instructions.md). Owner: D3.

Tools are thin adapters that call `services/`, `rag/`, or `repositories/` - no business logic in
the tool body. Give each tool a precise docstring and fully typed parameters/return; the model
routes on these signatures. Tools must be idempotent and side-effect-explicit.

The `search_*` tools are the grounding surface: each returns chunks carrying
`sourceName`/`sourceUrl`/`sourceDate`, so an agent can satisfy "no claim without a citation".
"""

from typing import Annotated

from agent_framework import tool

from app.models.medicine import MedicineEntity
from app.models.profile import DoctorLink
from app.rag.retrieve import RetrievedChunk
from app.rag.retrieve import search as rag_search
from app.services.normalize_medicine import find_alternatives as _find_alternatives
from app.services.ocr import OcrEnvelope
from app.services.ocr import extract as _ocr_extract
from app.services.specialist_mapping import get_doctor_link as _get_doctor_link
from app.services.specialist_mapping import get_mapping as _get_specialist_mapping
from app.services.specialist_mapping import get_source as _get_specialist_source


def _as_dict(chunk: RetrievedChunk) -> dict:
    """Flatten a chunk for the model; plain dicts route far more reliably than dataclasses."""
    return {
        "content": chunk.content,
        "sourceName": chunk.source_name,
        "sourceUrl": chunk.source_url,
        "sourceDate": chunk.source_date,
    }


@tool
async def ocr_extract(
    file_base64: Annotated[str, "Base64-encoded prescription/tablet-strip image or PDF bytes."],
    mode: Annotated[str, "'read' for prescriptions/tablet strips, 'layout' for lab report tables."] = "read",
) -> OcrEnvelope:
    """Run Document Intelligence OCR and return the structured envelope (lines/confidence/tables)."""
    import base64

    return await _ocr_extract(base64.b64decode(file_base64), mode=mode)


@tool
def find_alternatives(item: Annotated[MedicineEntity, "One normalized medicine line to find alternatives for."]) -> list[dict]:
    """Find safety-gated cheaper/generic alternatives for `item` (deterministic SQL match, never fabricated)."""
    return _find_alternatives(item)


@tool
async def search_medicines(
    query: Annotated[str, "Free-text brand/ingredient/composition query, e.g. 'Amlodipine 5mg tablet'."],
) -> list[dict]:
    """Hybrid + semantic search against `idx-medicines` for brand/composition recall grounding."""
    return [_as_dict(chunk) for chunk in await rag_search("idx-medicines", query)]


@tool
async def search_reference_ranges(
    query: Annotated[str, "Lab parameter to explain, e.g. 'HbA1c' or 'fasting blood sugar range'."],
) -> list[dict]:
    """Retrieve curated reference ranges and plain-language explanations, each with its source.

    Use this before explaining what any lab value means. Every returned chunk carries
    `sourceName`/`sourceUrl`/`sourceDate` - cite one, or do not make the claim.
    """
    return [_as_dict(chunk) for chunk in await rag_search("idx-reference-ranges", query)]


@tool
async def search_specialist_guidance(
    query: Annotated[str, "What the patient's abnormal results are about, e.g. 'thyroid TSH high'."],
) -> list[dict]:
    """Retrieve curated guidance on which specialty category discusses which parameters, with sources."""
    return [_as_dict(chunk) for chunk in await rag_search("idx-specialists", query)]


@tool
async def search_nutrition_rules(
    query: Annotated[str, "Meal need, e.g. 'low-cost vegetarian dinner for elevated glucose'."],
) -> list[dict]:
    """Retrieve curated, sourced nutrition guidance from `idx-nutrition`."""
    return [_as_dict(chunk) for chunk in await rag_search("idx-nutrition", query)]


@tool
def search_specialist_mapping(
    parameter_group: Annotated[str, "Curated parameter group, e.g. 'metabolic', 'lipids', 'thyroid'."],
) -> dict:
    """Look up the curated specialty category and consult guidance for one parameter group.

    Returns `{ specialtyCategory, whenToConsult, disclaimer, source }`. Categories only - the
    mapping never names or endorses an individual practitioner.
    """
    mapping = _get_specialist_mapping(parameter_group)
    return {**mapping, "source": _get_specialist_source(parameter_group).model_dump(by_alias=True)}


@tool
def get_doctor_links(
    parameter_group: Annotated[str, "Curated parameter group a category was already resolved for."],
) -> list[DoctorLink]:
    """Return the public/demo directory links for one parameter group, flagged `provenance`."""
    return [_get_doctor_link(parameter_group)]

