"""Shared embedding access for the RAG pipeline.

One module so the deployment name, vector width and batching rules live in a single place, and
so ingestion and retrieval can never disagree about how a chunk was embedded.
"""

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

# `text-embedding-3-large` native width; must match the index vector field dimensions.
EMBEDDING_DIMENSIONS = 3072

# Azure OpenAI accepts far larger batches, but small batches keep one bad row from failing a whole
# ingest run and stay well under the per-request token cap for long guidance text.
BATCH_SIZE = 16


def is_enabled() -> bool:
    """True when both an OpenAI endpoint and a Search endpoint are configured."""
    settings = get_settings()
    return bool(settings.azure_openai_endpoint and settings.azure_search_endpoint)


async def embed(texts: list[str]) -> list[list[float]]:
    """Embed `texts` in order. Raises on failure - callers decide whether that is fatal."""
    if not texts:
        return []

    from app.deps import get_embedding_client

    settings = get_settings()
    client = get_embedding_client()

    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        response = await client.embeddings.create(
            model=settings.azure_openai_embedding_deployment, input=batch
        )
        vectors.extend(item.embedding for item in sorted(response.data, key=lambda d: d.index))
    return vectors


async def embed_one(text: str) -> list[float]:
    """Embed a single query string."""
    return (await embed([text]))[0]
