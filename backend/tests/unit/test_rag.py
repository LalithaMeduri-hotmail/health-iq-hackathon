"""Unit tests for the RAG pipeline: document building, offline degradation, and citations.

Ingestion shape is asserted offline (no Search, no embeddings) because every chunk must carry
provenance - agents are prompt-bound to drop any claim they cannot cite.
"""

import pytest

from app.rag import embeddings, ingest, retrieve
from app.rag.indexes import INDEX_NAMES


def test_every_index_has_a_document_builder() -> None:
    assert set(ingest._BUILDERS) == set(INDEX_NAMES)


@pytest.mark.parametrize("builder", list(ingest._BUILDERS.values()))
def test_every_chunk_carries_provenance(builder) -> None:
    docs = builder()

    assert docs, "a source produced no chunks"
    for doc in docs:
        assert doc["content"].strip(), "a chunk has no content to retrieve"
        assert doc["sourceName"], f"{doc['title']} has no source name"
        assert doc["sourceUrl"], f"{doc['title']} has no source url"


@pytest.mark.parametrize("builder", list(ingest._BUILDERS.values()))
def test_document_ids_are_stable_and_unique(builder) -> None:
    first = builder()
    second = builder()

    ids = [doc["id"] for doc in first]
    assert len(ids) == len(set(ids)), "duplicate ids would overwrite chunks"
    # Deterministic ids are what make re-ingestion idempotent rather than duplicating rows.
    assert ids == [doc["id"] for doc in second]


def test_medicine_chunks_name_the_ingredient_and_price_source() -> None:
    docs = ingest.build_medicine_docs()

    glycomet = next(doc for doc in docs if doc["title"].startswith("Glycomet"))
    assert "Metformin" in glycomet["content"]
    assert glycomet["sourceName"] == "NPPA"


async def test_search_returns_nothing_when_search_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(embeddings, "is_enabled", lambda: False)

    assert await retrieve.search("idx-medicines", "metformin") == []


async def test_search_returns_nothing_for_an_empty_query() -> None:
    assert await retrieve.search("idx-medicines", "   ") == []


async def test_search_degrades_instead_of_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(_text: str):
        raise RuntimeError("search is down")

    monkeypatch.setattr(embeddings, "is_enabled", lambda: True)
    monkeypatch.setattr(embeddings, "embed_one", boom)

    # A retrieval outage must weaken the answer, not fail the user's request.
    assert await retrieve.search("idx-medicines", "metformin") == []


def test_citations_render_with_source_and_date() -> None:
    chunks = [
        retrieve.RetrievedChunk(
            content="hba1c: typical range 4.0-5.6 %",
            score=3.3,
            source_name="MedlinePlus",
            source_url="https://medlineplus.gov/",
            source_date="2026-06-01",
        )
    ]

    rendered = retrieve.as_citations(chunks)

    assert "[1]" in rendered
    assert "MedlinePlus" in rendered
    assert "2026-06-01" in rendered
