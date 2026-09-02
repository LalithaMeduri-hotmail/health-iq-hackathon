"""Secure share links (implementation-plan.md Section 5.2). Owner: D3.

`shareId` is a 128-bit URL-safe random token, stored hashed (SHA-256) in SQL `ShareLink`. Backend
issues a user-delegation SAS valid 24h, read-only, single blob. Rate limit 20 req/min/IP; log
every access with timestamp + `ipHash`. No PHI in the URL; the token is opaque and revocable.
"""


import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.errors import ForbiddenError, NotFoundError, RateLimitedError
from app.repositories import sql_repo

SHARE_TTL_HOURS = 24
RATE_LIMIT_PER_MINUTE = 20
_TOKEN_BYTES = 16  # 128-bit URL-safe token

_ACCESS_LOG: dict[str, deque[float]] = defaultdict(deque)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _enforce_rate_limit(ip_hash: str) -> None:
    """20 req/min/IP on the public share route (implementation-plan.md Section 5.2).

    In-process only; a multi-replica deployment needs a shared counter (Redis/Front Door).
    """
    now = time.monotonic()
    hits = _ACCESS_LOG[ip_hash]
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= RATE_LIMIT_PER_MINUTE:
        raise RateLimitedError("Too many requests for this share link; please retry in a minute")
    hits.append(now)


async def create_share_link(blob_path: str) -> tuple[str, str]:
    """Create a new share token. Returns `(shareId, expiresAt)`; only its hash is persisted."""
    share_id = secrets.token_urlsafe(_TOKEN_BYTES)
    expires_at = (datetime.now(UTC) + timedelta(hours=SHARE_TTL_HOURS)).isoformat()
    await sql_repo.create_share_link(_hash(share_id), blob_path, expires_at)
    return share_id, expires_at


async def resolve_share_link(share_id: str, *, client_ip: str) -> str:
    """Validate the token, enforce rate limiting, log access, and return the blob path to serve."""
    _enforce_rate_limit(_hash(client_ip))

    record = await sql_repo.get_share_link(_hash(share_id))
    if record is None:
        raise NotFoundError("This share link is not valid")
    if datetime.fromisoformat(record["expiresAt"]) < datetime.now(UTC):
        raise ForbiddenError("This share link has expired")

    record["accessCount"] = record.get("accessCount", 0) + 1
    record["lastAccessAt"] = datetime.now(UTC).isoformat()
    record["lastAccessIpHash"] = _hash(client_ip)
    return record["blobPath"]


async def build_sas_url(blob_path: str) -> str:
    """Read-only, single-blob user-delegation SAS valid for `SHARE_TTL_HOURS`."""
    from azure.storage.blob import BlobSasPermissions, generate_blob_sas

    from app.deps import get_blob_service_client

    settings = get_settings()
    container_name, _, blob_name = blob_path.partition("/")
    client = get_blob_service_client()

    starts_on = datetime.now(UTC)
    expires_on = starts_on + timedelta(hours=SHARE_TTL_HOURS)
    delegation_key = await client.get_user_delegation_key(key_start_time=starts_on, key_expiry_time=expires_on)

    token = generate_blob_sas(
        account_name=settings.azure_storage_account_name,
        container_name=container_name,
        blob_name=blob_name,
        user_delegation_key=delegation_key,
        permission=BlobSasPermissions(read=True),
        expiry=expires_on,
    )
    # The SDK builds the blob URL; string-joining the account URL drops or doubles the separator.
    blob_url = client.get_blob_client(container=container_name, blob=blob_name).url
    return f"{blob_url}?{token}"
