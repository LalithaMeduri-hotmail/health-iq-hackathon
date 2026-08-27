"""Create/populate the 4 Azure AI Search indexes (implementation-plan.md Section 3.1/3.2). Owner: D2.

Run from the `backend/` directory so the `app` package is importable, e.g.:

    uv run --project backend python ../scripts/build_search_indexes.py

Idempotent via deterministic doc IDs (`sha1(source + row_key)`) - safe to re-run.
"""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    # TODO(D2): call app.rag.indexes.create_or_update_indexes() then app.rag.ingest.ingest_all().
    raise NotImplementedError


if __name__ == "__main__":
    main()
