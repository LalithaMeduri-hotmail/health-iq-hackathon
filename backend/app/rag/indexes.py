"""Azure AI Search index definitions (implementation-plan.md Section 3.1). Owner: D2.

4 indexes, all `text-embedding-3-large` (3072 dims), HNSW profile, semantic configuration with
title/content fields: `idx-medicines`, `idx-reference-ranges`, `idx-specialists`, `idx-nutrition`.
"""

INDEX_NAMES = (
    "idx-medicines",
    "idx-reference-ranges",
    "idx-specialists",
    "idx-nutrition",
)


def create_or_update_indexes() -> None:
    """Create/update all 4 indexes against the Search service from `Settings.azure_search_endpoint`."""
    raise NotImplementedError
