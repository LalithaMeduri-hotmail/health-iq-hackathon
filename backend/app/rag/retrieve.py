"""RAG retrieval (implementation-plan.md Section 3.3). Owner: D2.

Contract frozen for D3 consumption: `search(index, query) -> list[RetrievedChunk]`. Hybrid
(BM25 `search_text` + `vector_queries`) with `query_type=semantic`, `top=5`.

Returns `[]` rather than raising when Search is unconfigured or errors: agents are prompt-bound
to drop any claim they cannot cite, so an empty result degrades the answer instead of the
request. Never fabricate a source.
"""

import logging
from dataclasses import dataclass

from app.rag import embeddings
from app.rag.indexes import SEMANTIC_CONFIG

logger = logging.getLogger(__name__)

DEFAULT_TOP = 5

# The indexed corpus is seeded reference data that only changes on re-ingest, and agents re-ask the
# same questions constantly ("fasting glucose" on every report). Caching the answer removes an
# embedding round-trip plus a Search query per tool call. Bounded so a long-lived process cannot
# grow without limit; only non-empty results are stored, so a transient failure is retried.
_CACHE_MAX_ENTRIES = 512
_cache: dict[tuple[str, str, int, str | None], list["RetrievedChunk"]] = {}


def clear_cache() -> None:
    """Drop memoized results - call after re-ingesting an index."""
    _cache.clear()


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    score: float
    source_name: str
    source_url: str
    source_date: str


def _chunk(result: dict) -> RetrievedChunk:
    return RetrievedChunk(
        content=result.get("content", ""),
        # Semantic reranker score when present, otherwise the hybrid RRF score.
        score=float(result.get("@search.reranker_score") or result.get("@search.score") or 0.0),
        source_name=result.get("sourceName", ""),
        source_url=result.get("sourceUrl", ""),
        source_date=result.get("sourceDate", ""),
    )


async def search(
    index: str, query: str, *, top: int = DEFAULT_TOP, tag_filter: str | None = None
) -> list[RetrievedChunk]:
    """Hybrid + semantic search against `index`. Returns `[]` if nothing relevant."""
    if not query or not query.strip() or not embeddings.is_enabled():
        return []

    cache_key = (index, query.strip().casefold(), top, tag_filter)
    if (cached := _cache.get(cache_key)) is not None:
        return cached

    from azure.search.documents.models import VectorizedQuery

    from app.deps import get_search_client

    try:
        vector = await embeddings.embed_one(query)
        client = get_search_client(index)
        results = await client.search(
            search_text=query,
            vector_queries=[
                VectorizedQuery(vector=vector, k_nearest_neighbors=top, fields="contentVector")
            ],
            query_type="semantic",
            semantic_configuration_name=SEMANTIC_CONFIG,
            filter=f"tags eq '{tag_filter}'" if tag_filter else None,
            select=["content", "title", "sourceName", "sourceUrl", "sourceDate"],
            top=top,
        )
        chunks = [_chunk(result) async for result in results]
    except Exception:  # noqa: BLE001 - retrieval failure must not fail the user's request
        logger.warning("retrieval failed for %s: dropping grounding", index, exc_info=True)
        return []

    if chunks:
        if len(_cache) >= _CACHE_MAX_ENTRIES:
            _cache.clear()
        _cache[cache_key] = chunks
    return chunks


def as_citations(chunks: list[RetrievedChunk]) -> str:
    """Render chunks for a prompt, each with its citation so the model can attribute claims."""
    return "\n\n".join(
        f"[{position}] {chunk.content}\n    (source: {chunk.source_name}, {chunk.source_date})"
        for position, chunk in enumerate(chunks, start=1)
    )
