"""Cosmos DB repository (backend.instructions.md). Owner: D1/D4.

All persistence for `profiles`, `reports`, `runs` (partition key `/userId`) goes through this
module - no Cosmos queries anywhere else. Every query is scoped by `userId`; owner-mismatch
reads must be impossible by construction (filter in the query, then assert ownership).

Demo/dev fallback: when `Settings.demo_mode` is true or no Cosmos endpoint is configured, `runs`
documents are kept in an in-process dict instead of Cosmos DB, so the analyze -> confirm flow
stays testable without deployed infra. Never log PHI content.
"""

import json
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.errors import ForbiddenError, NotFoundError
from app.models.profile import Profile
from app.models.report import StoredReport

_DEMO_RUNS_STORE: dict[str, dict] = {}
_DEMO_SAVED_REPORTS: dict[str, StoredReport] = {}
_DEMO_REPORTS_PATH = Path(__file__).resolve().parents[3] / "data" / "samples" / "demo_lab_reports.json"


@lru_cache
def load_demo_reports() -> list[StoredReport]:
    """Recorded demo report history (`DEMO_MODE=true`), sorted oldest first."""
    raw = json.loads(_DEMO_REPORTS_PATH.read_text(encoding="utf-8"))
    reports = [StoredReport.model_validate(document) for document in raw["reports"]]
    return sorted(reports, key=lambda report: report.report_date)


def _demo_reports() -> list[StoredReport]:
    """Seeded history plus anything analyzed during this session."""
    return sorted([*load_demo_reports(), *_DEMO_SAVED_REPORTS.values()], key=lambda report: report.report_date)


def _use_demo_store() -> bool:
    settings = get_settings()
    return settings.demo_mode or not settings.azure_cosmos_endpoint


def _reports_container():
    from app.deps import get_cosmos_client

    settings = get_settings()
    database = get_cosmos_client().get_database_client(settings.azure_cosmos_database_name)
    return database.get_container_client("reports")


async def get_profile(user_id: str) -> Profile:
    raise NotImplementedError


async def save_report(report: StoredReport) -> StoredReport:
    """Persist an analyzed report snapshot so comparisons stay stable if ranges change later."""
    if _use_demo_store():
        _DEMO_SAVED_REPORTS[report.id] = report
        return report

    await _reports_container().upsert_item(report.model_dump(by_alias=True))
    return report


async def list_reports(user_id: str) -> list[StoredReport]:
    """Every stored report for one user, oldest first - backs the two-report picker (FR3.1)."""
    if _use_demo_store():
        return [report for report in _demo_reports() if report.user_id == user_id]

    query = "SELECT * FROM c WHERE c.userId = @userId ORDER BY c.reportDate ASC"
    documents = _reports_container().query_items(
        query=query, parameters=[{"name": "@userId", "value": user_id}], partition_key=user_id
    )
    return [StoredReport.model_validate(document) async for document in documents]


async def get_report(user_id: str, report_id: str) -> StoredReport:
    """Filter by `userId` in the query, then assert ownership as defense in depth."""
    if _use_demo_store():
        report = next((item for item in _demo_reports() if item.id == report_id), None)
    else:
        query = "SELECT * FROM c WHERE c.userId = @userId AND c.id = @reportId"
        documents = _reports_container().query_items(
            query=query,
            parameters=[{"name": "@userId", "value": user_id}, {"name": "@reportId", "value": report_id}],
            partition_key=user_id,
        )
        report = next(
            iter([StoredReport.model_validate(document) async for document in documents]),
            None,
        )

    if report is None:
        raise NotFoundError(f"Report {report_id!r} not found")
    if report.user_id != user_id:
        raise ForbiddenError(f"Report {report_id!r} does not belong to the caller")
    return report


async def record_run(user_id: str, run_id: str, audit: dict) -> None:
    """Write an audit record to `runs`: input hash, tool calls, agent versions, safety verdict.

    Never log PHI content.
    """
    settings = get_settings()
    document = {"id": run_id, "userId": user_id, **audit}

    if settings.demo_mode or not settings.azure_cosmos_endpoint:
        _DEMO_RUNS_STORE[run_id] = document
        return

    from app.deps import get_cosmos_client

    client = get_cosmos_client()
    database = client.get_database_client(settings.azure_cosmos_database_name)
    container = database.get_container_client("runs")
    await container.upsert_item(document)


async def get_run(user_id: str, run_id: str) -> dict:
    """Fetch one `runs` document, scoped by `userId`; raises `NotFoundError`/`ForbiddenError`."""
    settings = get_settings()

    if settings.demo_mode or not settings.azure_cosmos_endpoint:
        document = _DEMO_RUNS_STORE.get(run_id)
    else:
        from app.deps import get_cosmos_client

        client = get_cosmos_client()
        database = client.get_database_client(settings.azure_cosmos_database_name)
        container = database.get_container_client("runs")
        try:
            document = await container.read_item(item=run_id, partition_key=user_id)
        except Exception:  # noqa: BLE001 - SDK raises a generic CosmosResourceNotFoundError
            document = None

    if document is None:
        raise NotFoundError(f"Run {run_id!r} not found")
    if document["userId"] != user_id:
        raise ForbiddenError(f"Run {run_id!r} does not belong to the caller")
    return document
