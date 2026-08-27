"""RAG retrieval (implementation-plan.md Section 3.3). Owner: D2.

Contract frozen for D3 consumption: `search(index, query) -> list[RetrievedChunk]`. Hybrid
(`search` + `vectorQueries`) with `queryType=semantic`, `top=5`. Agents are prompt-bound: no
claim may appear in output without at least one attached `RetrievedChunk`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    score: float
    source_name: str
    source_url: str
    source_date: str


async def search(index: str, query: str, *, top: int = 5) -> list[RetrievedChunk]:
    """Hybrid + semantic search against `index`. Returns `[]` if nothing relevant - never fabricate."""
    raise NotImplementedError
