"""Azure AI Search index definitions (implementation-plan.md Section 3.1). Owner: D2.

4 indexes sharing one schema, all `text-embedding-3-large` (3072 dims), HNSW profile, and a
semantic configuration over title/content: `idx-medicines`, `idx-reference-ranges`,
`idx-specialists`, `idx-nutrition`.

The schema is deliberately uniform so `retrieve.search()` can query any index the same way, and
so provenance (`sourceName`/`sourceUrl`/`sourceDate`) is a required part of every document -
agents.instructions.md forbids a claim without a citation, which is only enforceable if every
chunk carries one.
"""

import logging

from app.rag.embeddings import EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)

INDEX_NAMES = (
    "idx-medicines",
    "idx-reference-ranges",
    "idx-specialists",
    "idx-nutrition",
)

_VECTOR_PROFILE = "hnsw-profile"
_VECTOR_ALGORITHM = "hnsw-config"
SEMANTIC_CONFIG = "semantic-config"


def _build_index(name: str):
    """One `SearchIndex` definition; imports stay local so `INDEX_NAMES` is importable offline."""
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SemanticConfiguration,
        SemanticField,
        SemanticPrioritizedFields,
        SemanticSearch,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        # Filterable so an agent can narrow to one canonical key / parameter group / meal type.
        SearchableField(name="tags", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="sourceName", type=SearchFieldDataType.String),
        SimpleField(name="sourceUrl", type=SearchFieldDataType.String),
        SimpleField(name="sourceDate", type=SearchFieldDataType.String),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name=_VECTOR_PROFILE,
        ),
    ]

    return SearchIndex(
        name=name,
        fields=fields,
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name=_VECTOR_ALGORITHM)],
            profiles=[
                VectorSearchProfile(
                    name=_VECTOR_PROFILE, algorithm_configuration_name=_VECTOR_ALGORITHM
                )
            ],
        ),
        semantic_search=SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name=SEMANTIC_CONFIG,
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="title"),
                        content_fields=[SemanticField(field_name="content")],
                    ),
                )
            ]
        ),
    )


async def create_or_update_indexes() -> list[str]:
    """Create/update all 4 indexes against `Settings.azure_search_endpoint`. Idempotent."""
    from app.deps import get_search_index_client

    client = get_search_index_client()
    created: list[str] = []
    for name in INDEX_NAMES:
        await client.create_or_update_index(_build_index(name))
        logger.info("index ready: %s", name)
        created.append(name)
    return created
