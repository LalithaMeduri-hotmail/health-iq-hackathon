"""Cosmos DB repository (backend.instructions.md). Owner: D1/D4.

All persistence for `profiles`, `reports`, `runs` (partition key `/userId`) goes through this
module - no Cosmos queries anywhere else. Every query is scoped by `userId`; owner-mismatch
reads must be impossible by construction (filter in the query, then assert ownership).

Demo/dev fallback: when `Settings.demo_mode` is true or no Cosmos endpoint is configured, `runs`
documents are kept in an in-process dict instead of Cosmos DB, so the analyze -> confirm flow
stays testable without deployed infra. Never log PHI content.
"""

import hashlib
import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.audit import AuditEvent, ConsentRecord
from app.models.medical_document import MedicalDocument
from app.models.patient_profile import PatientProfile
from app.models.profile import CONSENT_PURPOSES, Consent, Profile
from app.models.report import StoredReport
from app.models.review import IssuedPrescription

_DEMO_RUNS_STORE: dict[str, dict] = {}
_DEMO_SAVED_REPORTS: dict[str, StoredReport] = {}
_DEMO_PROFILES: dict[str, dict] = {}
_DEMO_PROFILES_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "samples" / "demo_profiles.json"
)
_DEMO_ACCOUNTS: dict[str, dict] = {}
_DEMO_ACCOUNT_INDEX: dict[str, str] = {}  # casefolded username/mobile/email -> userId
_DEMO_REPORTS_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "samples" / "demo_lab_reports.json"
)


@lru_cache
def load_demo_profiles() -> dict[str, dict]:
    """Synthetic demo profiles keyed by `userId`; in-memory writes override these baselines."""
    raw = json.loads(_DEMO_PROFILES_PATH.read_text(encoding="utf-8"))
    profiles = {
        document["userId"]: document
        for document in raw["profiles"]
    }
    for user_id, document in profiles.items():
        if document["id"] != user_id:
            raise ValueError(
                f"Demo profile id {document['id']!r} must match userId {user_id!r}"
            )
        Profile.model_validate(document)
    return profiles


@lru_cache
def load_demo_reports() -> list[StoredReport]:
    """Recorded demo report history (`DEMO_MODE=true`), sorted oldest first."""
    raw = json.loads(_DEMO_REPORTS_PATH.read_text(encoding="utf-8"))
    reports = [StoredReport.model_validate(document) for document in raw["reports"]]
    return sorted(reports, key=lambda report: report.report_date)


def _demo_reports() -> list[StoredReport]:
    """Seeded history plus anything analyzed during this session."""
    return sorted(
        [*load_demo_reports(), *_DEMO_SAVED_REPORTS.values()],
        key=lambda report: report.report_date,
    )


def _use_demo_store() -> bool:
    settings = get_settings()
    return settings.demo_mode or not settings.azure_cosmos_endpoint


def _reports_container():
    from app.deps import get_cosmos_client

    settings = get_settings()
    database = get_cosmos_client().get_database_client(settings.azure_cosmos_database_name)
    return database.get_container_client("reports")


def _profiles_container():
    from app.deps import get_cosmos_client

    settings = get_settings()
    database = get_cosmos_client().get_database_client(settings.azure_cosmos_database_name)
    return database.get_container_client("profiles")


def _demo_etag(document: dict) -> str:
    """Content-derived `_etag` stand-in that enforces demo-store concurrency."""
    payload = {key: value for key, value in document.items() if key not in {"etag", "_etag"}}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _to_profile(document: dict) -> Profile:
    """Map a `profiles` document to the domain model, normalizing Cosmos `_etag` onto `etag`."""
    return Profile.model_validate(
        {**document, "etag": document.get("_etag") or document.get("etag")}
    )


async def get_profile(user_id: str) -> Profile:
    """Read one profile, or return an empty default so a first-time user still has a profile.

    Returning a default (rather than raising) keeps `GET /profile` a safe read for a brand-new
    caller, per LLD Section 2.3.2.
    """
    if _use_demo_store():
        document = _DEMO_PROFILES.get(user_id) or load_demo_profiles().get(user_id)
    else:
        try:
            document = await _profiles_container().read_item(item=user_id, partition_key=user_id)
        except Exception:  # noqa: BLE001 - SDK raises a generic CosmosResourceNotFoundError
            document = None

    if document is None:
        return Profile(userId=user_id)
    if document["userId"] != user_id:
        raise ForbiddenError(f"Profile {user_id!r} does not belong to the caller")
    return _to_profile(document)


async def save_profile(profile: Profile, *, if_match: str | None = None) -> Profile:
    """Upsert one profile under optimistic concurrency (LLD Section 2.3.3).

    `if_match` is the caller-supplied `etag`; when present and stale the write is rejected with
    `ConflictError` instead of silently overwriting a concurrent edit.
    """
    current = await get_profile(profile.user_id)
    if if_match is not None and current.etag is not None and if_match != current.etag:
        raise ConflictError("Profile was modified by another request; re-read it and retry")

    document = profile.model_dump(by_alias=True, exclude={"etag"})
    document["id"] = profile.user_id

    if _use_demo_store():
        document["etag"] = _demo_etag(document)
        _DEMO_PROFILES[profile.user_id] = document
        return _to_profile(document)

    from azure.core import MatchConditions

    kwargs = (
        {"etag": if_match, "match_condition": MatchConditions.IfNotModified} if if_match else {}
    )
    saved = await _profiles_container().upsert_item(document, **kwargs)
    return _to_profile(saved)


async def record_report_analysis(user_id: str, report_id: str, consent_version: str) -> Profile:
    """Stamp the accepted consent and point `latestSummaryId` at the newest analyzed report.

    Both happen at the same moment in the analyze flow (LLD Section 2.11 steps 1 and 9), so they
    share one read-modify-write instead of two.
    """
    profile = await get_profile(user_id)
    profile.latest_summary_id = report_id
    profile.consent = Consent(
        version=consent_version,
        acceptedAt=datetime.now(UTC).isoformat(),
        purposes=list(CONSENT_PURPOSES),
    )
    return await save_profile(profile)


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
            parameters=[
                {"name": "@userId", "value": user_id},
                {"name": "@reportId", "value": report_id},
            ],
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


def _accounts_container():
    from app.deps import get_cosmos_client

    settings = get_settings()
    database = get_cosmos_client().get_database_client(settings.azure_cosmos_database_name)
    return database.get_container_client("accounts")


async def find_account_by_identifier(identifier: str) -> dict | None:
    """Look up an account document by username, mobile, or email (case-insensitive).

    Used only for pre-authentication lookups (register uniqueness check, login) - there is no
    `userId` to scope by yet, so this is intentionally a cross-partition read at this small
    (accounts) scale, not a pattern to replicate for PHI-bearing containers.
    """
    key = identifier.strip().casefold()
    if _use_demo_store():
        user_id = _DEMO_ACCOUNT_INDEX.get(key)
        return _DEMO_ACCOUNTS.get(user_id) if user_id else None

    # No `partition_key` means the async SDK fans out across partitions on its own. Passing
    # `enable_cross_partition_query` (the sync-SDK spelling) is forwarded to the HTTP transport as
    # an unknown kwarg and raises `TypeError`, which surfaced as a 500 on every register/login.
    query = "SELECT * FROM c WHERE c.usernameKey = @key OR c.mobileKey = @key OR c.emailKey = @key"
    documents = _accounts_container().query_items(
        query=query, parameters=[{"name": "@key", "value": key}]
    )
    async for document in documents:
        return document
    return None


async def get_account(user_id: str) -> dict | None:
    if _use_demo_store():
        return _DEMO_ACCOUNTS.get(user_id)
    try:
        return await _accounts_container().read_item(item=user_id, partition_key=user_id)
    except Exception:  # noqa: BLE001 - SDK raises a generic CosmosResourceNotFoundError
        return None


async def create_account(document: dict) -> None:
    """Insert a brand-new account; caller must already have checked identifier uniqueness."""
    if _use_demo_store():
        user_id = document["id"]
        _DEMO_ACCOUNTS[user_id] = document
        index_keys = (
            document.get("usernameKey"),
            document.get("mobileKey"),
            document.get("emailKey"),
        )
        for key in index_keys:
            if key:
                _DEMO_ACCOUNT_INDEX[key] = user_id
        return
    await _accounts_container().create_item(document)


async def save_account(document: dict) -> None:
    """Upsert an existing account (e.g. failed-PIN-attempt counters, lockout timestamp)."""
    if _use_demo_store():
        _DEMO_ACCOUNTS[document["id"]] = document
        return
    await _accounts_container().upsert_item(document)


# --------------------------------------------------------------------------------------
# Patient profiles, medical documents, consent, audit.
#
# Patient profiles live in the existing `profiles` container (partition `/userId` = account id)
# under an `id` prefixed `pp-`, which keeps them in the account's partition without colliding
# with the legacy account-level profile document whose `id` equals the account id. The prefix
# avoids `:` so the id can be used verbatim in a blob path and a local filesystem path.
# --------------------------------------------------------------------------------------

PATIENT_PROFILE_ID_PREFIX = "pp-"

_DEMO_PATIENT_PROFILES: dict[str, dict] = {}
_DEMO_DOCUMENTS: dict[str, dict] = {}
_DEMO_PRESCRIPTIONS: dict[str, dict] = {}
_DEMO_AUDIT: list[dict] = []
_DEMO_CONSENTS: list[dict] = []


def _container(name: str):
    from app.deps import get_cosmos_client

    settings = get_settings()
    database = get_cosmos_client().get_database_client(settings.azure_cosmos_database_name)
    return database.get_container_client(name)


def _to_patient_profile(document: dict) -> PatientProfile:
    return PatientProfile.model_validate(
        {**document, "etag": document.get("_etag") or document.get("etag")}
    )


async def list_patient_profiles(account_id: str) -> list[PatientProfile]:
    """Every patient profile owned by one account, oldest first.

    The `accountId` filter is part of the query and the partition key, so a profile belonging to
    another account cannot be returned even if an `id` were guessed.
    """
    if _use_demo_store():
        documents = [
            document
            for document in _DEMO_PATIENT_PROFILES.values()
            if document["accountId"] == account_id
        ]
    else:
        query = (
            "SELECT * FROM c WHERE c.accountId = @accountId "
            "AND STARTSWITH(c.id, @prefix) ORDER BY c.createdAt ASC"
        )
        results = _profiles_container().query_items(
            query=query,
            parameters=[
                {"name": "@accountId", "value": account_id},
                {"name": "@prefix", "value": PATIENT_PROFILE_ID_PREFIX},
            ],
            partition_key=account_id,
        )
        documents = [document async for document in results]

    profiles = [_to_patient_profile(document) for document in documents]
    return sorted(profiles, key=lambda profile: profile.created_at)


async def get_patient_profile(account_id: str, profile_id: str) -> PatientProfile | None:
    """Read one patient profile, or `None` when it does not exist *or* is not this account's.

    Both cases collapse to `None` on purpose: the caller turns it into a single `404`, so the
    response never reveals that another account's profile exists.
    """
    if _use_demo_store():
        document = _DEMO_PATIENT_PROFILES.get(profile_id)
    else:
        try:
            document = await _profiles_container().read_item(
                item=profile_id, partition_key=account_id
            )
        except Exception:  # noqa: BLE001 - SDK raises a generic CosmosResourceNotFoundError
            document = None

    if document is None or document.get("accountId") != account_id:
        return None
    return _to_patient_profile(document)


async def save_patient_profile(
    profile: PatientProfile, *, if_match: str | None = None
) -> PatientProfile:
    """Upsert one patient profile under optimistic concurrency."""
    existing = await get_patient_profile(profile.account_id, profile.id)
    if if_match is not None and existing is not None and existing.etag is not None:
        if if_match != existing.etag:
            raise ConflictError("Profile was modified by another request; re-read it and retry")

    document = json.loads(profile.model_dump_json(by_alias=True, exclude={"etag"}))
    document["id"] = profile.id
    # The container partitions on `/userId`; patient profiles carry both so either key works.
    document["userId"] = profile.account_id

    if _use_demo_store():
        document["etag"] = _demo_etag(document)
        _DEMO_PATIENT_PROFILES[profile.id] = document
        return _to_patient_profile(document)

    saved = await _profiles_container().upsert_item(document)
    return _to_patient_profile(saved)


async def save_document(document_model: MedicalDocument) -> MedicalDocument:
    """Upsert a medical-document record (pending or confirmed)."""
    document = json.loads(document_model.model_dump_json(by_alias=True))
    if _use_demo_store():
        _DEMO_DOCUMENTS[document_model.id] = document
        return document_model
    await _container("documents").upsert_item(document)
    return document_model


async def get_document(account_id: str, document_id: str) -> MedicalDocument | None:
    """Read one document scoped to the account; `None` when absent or owned by another account."""
    if _use_demo_store():
        document = _DEMO_DOCUMENTS.get(document_id)
    else:
        try:
            document = await _container("documents").read_item(
                item=document_id, partition_key=account_id
            )
        except Exception:  # noqa: BLE001 - SDK raises a generic CosmosResourceNotFoundError
            document = None

    if document is None or document.get("accountId") != account_id:
        return None
    return MedicalDocument.model_validate(document)


async def list_documents(account_id: str, profile_id: str) -> list[MedicalDocument]:
    """Documents belonging to one patient profile, newest first."""
    if _use_demo_store():
        documents = [
            document
            for document in _DEMO_DOCUMENTS.values()
            if document["accountId"] == account_id and document["profileId"] == profile_id
        ]
    else:
        query = "SELECT * FROM c WHERE c.accountId = @accountId AND c.profileId = @profileId"
        results = _container("documents").query_items(
            query=query,
            parameters=[
                {"name": "@accountId", "value": account_id},
                {"name": "@profileId", "value": profile_id},
            ],
            partition_key=account_id,
        )
        documents = [document async for document in results]

    models = [MedicalDocument.model_validate(document) for document in documents]
    return sorted(models, key=lambda item: item.created_at, reverse=True)


async def delete_document(account_id: str, document_id: str) -> None:
    """Hard-delete a document record after its ownership has already been verified."""
    if _use_demo_store():
        stored = _DEMO_DOCUMENTS.get(document_id)
        if stored and stored.get("accountId") == account_id:
            _DEMO_DOCUMENTS.pop(document_id, None)
        return
    await _container("documents").delete_item(item=document_id, partition_key=account_id)


async def save_prescription(prescription: IssuedPrescription) -> IssuedPrescription:
    """Persist one issued Health IQ prescription as the profile's permanent history."""
    document = json.loads(prescription.model_dump_json(by_alias=True))
    if _use_demo_store():
        _DEMO_PRESCRIPTIONS[prescription.id] = document
        return prescription
    await _container("prescriptions").upsert_item(document)
    return prescription


async def list_prescriptions(account_id: str, profile_id: str) -> list[IssuedPrescription]:
    """Issued prescriptions for one patient profile, newest first."""
    if _use_demo_store():
        documents = [
            document
            for document in _DEMO_PRESCRIPTIONS.values()
            if document["accountId"] == account_id and document["profileId"] == profile_id
        ]
    else:
        query = "SELECT * FROM c WHERE c.accountId = @accountId AND c.profileId = @profileId"
        results = _container("prescriptions").query_items(
            query=query,
            parameters=[
                {"name": "@accountId", "value": account_id},
                {"name": "@profileId", "value": profile_id},
            ],
            partition_key=account_id,
        )
        documents = [document async for document in results]

    models = [IssuedPrescription.model_validate(document) for document in documents]
    return sorted(models, key=lambda item: item.issued_at, reverse=True)


async def get_prescription(
    account_id: str, profile_id: str, prescription_id: str
) -> IssuedPrescription | None:
    """One issued prescription, scoped to the account *and* the profile it belongs to."""
    if _use_demo_store():
        document = _DEMO_PRESCRIPTIONS.get(prescription_id)
    else:
        try:
            document = await _container("prescriptions").read_item(
                item=prescription_id, partition_key=account_id
            )
        except Exception:  # noqa: BLE001 - SDK raises a generic CosmosResourceNotFoundError
            document = None

    if document is None:
        return None
    # Scoping on both keys keeps one family member's prescription out of another's history.
    if document.get("accountId") != account_id or document.get("profileId") != profile_id:
        return None
    return IssuedPrescription.model_validate(document)


async def record_audit_event(event: AuditEvent) -> None:
    """Append one audit event. Callers must pass structural facts only, never medical content."""
    document = json.loads(event.model_dump_json(by_alias=True))
    if _use_demo_store():
        _DEMO_AUDIT.append(document)
        return
    await _container("audit").create_item(document)


async def list_audit_events(account_id: str, profile_id: str | None = None) -> list[dict]:
    """Audit trail for one account, optionally narrowed to a single profile."""
    if _use_demo_store():
        documents = [event for event in _DEMO_AUDIT if event["accountId"] == account_id]
    else:
        query = "SELECT * FROM c WHERE c.accountId = @accountId"
        results = _container("audit").query_items(
            query=query,
            parameters=[{"name": "@accountId", "value": account_id}],
            partition_key=account_id,
        )
        documents = [document async for document in results]

    if profile_id is not None:
        documents = [event for event in documents if event.get("profileId") == profile_id]
    return sorted(documents, key=lambda event: event["timestamp"], reverse=True)


async def record_consent(record: ConsentRecord) -> None:
    """Append one immutable consent decision."""
    document = json.loads(record.model_dump_json(by_alias=True))
    if _use_demo_store():
        _DEMO_CONSENTS.append(document)
        return
    await _container("consents").create_item(document)


async def list_consents(account_id: str, profile_id: str) -> list[dict]:
    if _use_demo_store():
        return [
            record
            for record in _DEMO_CONSENTS
            if record["accountId"] == account_id and record["profileId"] == profile_id
        ]

    query = "SELECT * FROM c WHERE c.accountId = @accountId AND c.profileId = @profileId"
    results = _container("consents").query_items(
        query=query,
        parameters=[
            {"name": "@accountId", "value": account_id},
            {"name": "@profileId", "value": profile_id},
        ],
        partition_key=account_id,
    )
    return [document async for document in results]


def owning_profile_id(report: StoredReport, owner_profile_id: str) -> str:
    """Profile a stored report belongs to, resolving pre-profile records to the owner profile."""
    return report.profile_id or owner_profile_id


async def list_reports_for_profile(
    account_id: str, profile_id: str, *, owner_profile_id: str
) -> list[StoredReport]:
    """Reports belonging to exactly one patient profile, oldest first."""
    reports = await list_reports(account_id)
    return [
        report
        for report in reports
        if owning_profile_id(report, owner_profile_id) == profile_id
    ]


async def get_report_for_profile(
    account_id: str, profile_id: str, report_id: str, *, owner_profile_id: str
) -> StoredReport:
    """Read one report and assert it belongs to this profile, else `404` (never `403`)."""
    reports = await list_reports_for_profile(
        account_id, profile_id, owner_profile_id=owner_profile_id
    )
    report = next((item for item in reports if item.id == report_id), None)
    if report is None:
        raise NotFoundError("Report not found")
    return report


def reset_demo_state() -> None:
    """Clear the in-process patient-profile stores so each test starts from a clean account.

    Only the containers introduced with patient profiles are cleared. The older report/run demo
    stores are left alone on purpose: existing tests build state across cases against them.
    """
    _DEMO_PATIENT_PROFILES.clear()
    _DEMO_DOCUMENTS.clear()
    _DEMO_PRESCRIPTIONS.clear()
    _DEMO_AUDIT.clear()
    _DEMO_CONSENTS.clear()
