"""Create/populate the 4 Azure AI Search indexes (implementation-plan.md Section 3.1/3.2). Owner: D2.

Run from the `backend/` directory so the `app` package is importable, e.g.:

    uv run --project backend python ../scripts/build_search_indexes.py

Idempotent via deterministic doc IDs (`sha1(source + row_key)`) - safe to re-run.
"""

import argparse
import asyncio
import logging
import sys

from app.config import get_settings
from app.rag import ingest
from app.rag.indexes import create_or_update_indexes


async def _run(skip_ingest: bool) -> int:
    settings = get_settings()
    if not settings.azure_search_endpoint:
        print("AZURE_SEARCH_ENDPOINT is not set; nothing to do.", file=sys.stderr)
        return 1
    if not settings.azure_openai_endpoint:
        print("AZURE_OPENAI_ENDPOINT is not set; embeddings are required to ingest.", file=sys.stderr)
        return 1

    print(f"Search endpoint: {settings.azure_search_endpoint}")
    for name in await create_or_update_indexes():
        print(f"  index ready: {name}")

    if skip_ingest:
        return 0

    print("Embedding and uploading documents...")
    for name, count in (await ingest.ingest_all()).items():
        print(f"  {name}: {count} documents")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--indexes-only", action="store_true", help="Create/update index definitions without ingesting."
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(asyncio.run(_run(args.indexes_only)))


if __name__ == "__main__":
    main()
