"""Cosmos DB repository (backend.instructions.md). Owner: D1/D4.

All persistence for `profiles`, `reports`, `runs` (partition key `/userId`) goes through this
module - no Cosmos queries anywhere else. Every query is scoped by `userId`; owner-mismatch
reads must be impossible by construction (filter in the query, then assert ownership).

Demo/dev fallback: when `Settings.demo_mode` is true or no Cosmos endpoint is configured, `runs`
documents are kept in an in-process dict instead of Cosmos DB, so the analyze -> confirm flow
stays testable without deployed infra. Never log PHI content.
"""

from app.config import get_settings
from app.errors import ForbiddenError, NotFoundError
from app.models.profile import Profile
from app.models.report import ReportSummary

_DEMO_RUNS_STORE: dict[str, dict] = {}


async def get_profile(user_id: str) -> Profile:
    raise NotImplementedError


async def get_report(user_id: str, report_id: str) -> ReportSummary:
    """Filter by `userId` in the query, then assert ownership as defense in depth."""
    raise NotImplementedError


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
