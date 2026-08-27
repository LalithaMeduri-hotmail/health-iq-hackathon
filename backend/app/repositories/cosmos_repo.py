"""Cosmos DB repository (backend.instructions.md). Owner: D1/D4.

All persistence for `profiles`, `reports`, `runs` (partition key `/userId`) goes through this
module - no Cosmos queries anywhere else. Every query is scoped by `userId`; owner-mismatch
reads must be impossible by construction (filter in the query, then assert ownership).
"""

from app.models.profile import Profile
from app.models.report import ReportSummary


async def get_profile(user_id: str) -> Profile:
    raise NotImplementedError


async def get_report(user_id: str, report_id: str) -> ReportSummary:
    """Filter by `userId` in the query, then assert ownership as defense in depth."""
    raise NotImplementedError


async def record_run(user_id: str, run_id: str, audit: dict) -> None:
    """Write an audit record to `runs`: input hash, tool calls, agent versions, safety verdict.

    Never log PHI content.
    """
    raise NotImplementedError
