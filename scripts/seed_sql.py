"""Seed Azure SQL `Medicine`, `MedicinePrice`, `LabMetric`, `ShareLink` tables (implementation-plan.md M0/M2). Owner: D1/D2.

Run from the `backend/` directory so the `app` package is importable, e.g.:

    uv run --project backend python ../scripts/seed_sql.py

Reads `data/medicines/medicine_catalog.csv` and `data/reference_ranges/lab_reference_ranges.csv`.
Must be idempotent (safe to re-run) per docs/lld/8-low-level-design-cross-cutting-platform.md
Section 7.4 (Rollback Strategy).
"""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    # TODO(D1/D2): create tables if missing, then upsert rows from data/*.csv using
    # app.repositories.sql_repo (AAD auth, parameterized queries only).
    raise NotImplementedError


if __name__ == "__main__":
    main()
