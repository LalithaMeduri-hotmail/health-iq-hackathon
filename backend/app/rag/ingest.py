"""RAG ingestion pipeline (implementation-plan.md Section 3.2). Owner: D2.

Read CSV/MD sources under `data/` -> chunk (500 tokens, 60 overlap for prose; one row per doc
for tabular) -> embed -> upload in batches of 100 -> verify document counts. Idempotent via
deterministic doc IDs (`sha1(source + row_key)`).
"""


def ingest_all() -> None:
    """Ingest every source in `data/` into its corresponding index. Safe to re-run."""
    raise NotImplementedError
