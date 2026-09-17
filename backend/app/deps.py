"""Dependency-injection wiring: shared Azure clients and the current-user resolver.

Cross-cutting clients (OpenAI, Search, Blob, Cosmos, SQL) must be constructed once here and
injected via `Depends()` - never instantiated inside request handlers or services
(.github/instructions/backend.instructions.md). Provider functions are plain `lru_cache`
callables (not FastAPI `Depends` markers) so both routers (`Depends(get_blob_service_client)`)
and lower layers (direct call, e.g. `from app.deps import get_blob_service_client`) can reuse the
same cached client instance.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated
from urllib.parse import urlsplit

from azure.identity.aio import DefaultAzureCredential
from fastapi import Header, Request

from app.config import Settings, get_settings
from app.errors import UnauthenticatedError

logger = logging.getLogger(__name__)

# Refresh this far before real expiry so a token never dies mid-request.
_TOKEN_EXPIRY_SKEW_SECONDS = 300

# Name of the HttpOnly session cookie set by `api/auth.py` on register/login. Kept here (not in
# auth.py) so both the cookie writer and this reader agree on one name without a circular import.
SESSION_COOKIE_NAME = "hiq_session"


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated caller, scoped by `user_id` for every repository read/write."""

    user_id: str


async def get_current_user(
    request: Request, x_demo_user_id: Annotated[str | None, Header()] = None
) -> CurrentUser:
    """Resolve the caller from the account-module session (cookie or bearer token).

    Falls back to the `X-Demo-User-Id` header stub only when `DEMO_MODE=true` and no session is
    present, so existing demo flows keep working without forcing a login. A present-but-invalid/
    expired token is always rejected (never silently downgraded to the demo stub).
    """
    settings = get_settings()
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer ") :]

    if token:
        from app.services.security import decode_session_token

        user_id = decode_session_token(token)
        if user_id is None:
            raise UnauthenticatedError("Session expired or invalid; please sign in again")
        return CurrentUser(user_id=user_id)

    if settings.demo_mode:
        return CurrentUser(user_id=x_demo_user_id or "demo-user")

    raise UnauthenticatedError("Sign in required")


class _CachingCredential:
    """Wraps a credential so each scope's token is fetched once per hour, not once per call.

    `AzureCliCredential` shells out to `az account get-access-token` on *every* `get_token` and
    caches nothing - measured at ~5s per call locally. Azure SDK clients hold their own token
    cache, but hand-rolled providers (the embedding client, the agent framework) call straight
    through, so the RAG path paid that cost on every retrieval. The cache lives here so every
    consumer shares one entry per scope.

    A request carrying `claims` is a CAE re-auth challenge and must never be served from cache.
    """

    def __init__(self, inner: DefaultAzureCredential) -> None:
        self._inner = inner
        self._entries: dict[tuple, object] = {}
        self._locks: dict[tuple, asyncio.Lock] = {}

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def _fresh(self, key: tuple):
        entry = self._entries.get(key)
        if entry is not None and entry.expires_on - _TOKEN_EXPIRY_SKEW_SECONDS > time.time():
            return entry
        return None

    async def _cached(self, key: tuple, fetch):
        if (entry := self._fresh(key)) is not None:
            return entry
        # One lock per scope: without it, parallel tool calls each spawn their own `az`.
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            if (entry := self._fresh(key)) is not None:
                return entry
            entry = await fetch()
            self._entries[key] = entry
            return entry

    async def get_token(self, *scopes: str, **kwargs):
        if kwargs.get("claims"):
            return await self._inner.get_token(*scopes, **kwargs)
        key = ("token", scopes, kwargs.get("tenant_id"), kwargs.get("enable_cae", False))
        return await self._cached(key, lambda: self._inner.get_token(*scopes, **kwargs))

    async def get_token_info(self, *scopes: str, **kwargs):
        options = kwargs.get("options") or {}
        if options.get("claims"):
            return await self._inner.get_token_info(*scopes, **kwargs)
        key = ("info", scopes, options.get("tenant_id"), options.get("enable_cae", False))
        return await self._cached(
            key, lambda: self._inner.get_token_info(*scopes, **kwargs)
        )

    async def close(self) -> None:
        await self._inner.close()

    async def __aenter__(self):
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self._inner.__aexit__(*exc_info)


@lru_cache
def get_azure_credential() -> DefaultAzureCredential:
    """Single shared async credential for every Azure SDK client, with an in-process token cache.

    `process_timeout` is raised above the 10s default because `az account get-access-token` is
    slow on developer machines whose CLI profile spans many subscriptions, and a timeout there
    surfaces as an opaque "Failed to invoke the Azure CLI".

    The credentials we never authenticate with are excluded rather than left to fail: each one
    that is merely *unavailable* still costs wall-clock time to probe, and `AzurePowerShell` in
    particular spawns a shell that can hit the full `process_timeout` before giving up. What
    remains is what actually signs us in - environment/workload/managed identity in Azure, the
    Azure CLI locally.
    """
    return _CachingCredential(
        DefaultAzureCredential(
            process_timeout=30,
            exclude_shared_token_cache_credential=True,
            exclude_visual_studio_code_credential=True,
            exclude_powershell_credential=True,
            exclude_developer_cli_credential=True,
        )
    )


# Data-plane scopes the app authenticates against. Cosmos is per-account, so it is derived.
_WARMUP_SCOPES = (
    "https://cognitiveservices.azure.com/.default",  # Azure OpenAI + Document Intelligence
    "https://search.azure.com/.default",
    "https://storage.azure.com/.default",
)


async def warm_token_cache() -> None:
    """Pre-acquire one token per scope at startup so no user request pays the `az` shell-out.

    Sequential on purpose: several `az account get-access-token` processes at once contend badly
    enough on a developer machine to hit `process_timeout` and fail the whole chain. Every failure
    is swallowed - a warm cache is an optimization, and the app must still boot offline.
    """
    settings = get_settings()
    if settings.demo_mode or not settings.azure_openai_endpoint:
        return

    scopes = list(_WARMUP_SCOPES)
    if settings.azure_cosmos_endpoint:
        host = urlsplit(settings.azure_cosmos_endpoint).hostname
        if host:
            scopes.append(f"https://{host}/.default")

    credential = get_azure_credential()
    for scope in scopes:
        try:
            await credential.get_token(scope)
        except Exception:  # noqa: BLE001 - warm-up must never block startup
            logger.warning("token warm-up failed for %s; first request will be slow", scope)


@lru_cache
def get_blob_service_client():
    """Cached async `BlobServiceClient` for `raw-uploads`/`generated-pdfs`/`thumbnails`."""
    from azure.storage.blob.aio import BlobServiceClient

    settings: Settings = get_settings()
    account_url = f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
    return BlobServiceClient(account_url=account_url, credential=get_azure_credential())


@lru_cache
def get_cosmos_client():
    """Cached async `CosmosClient` for the `healthiq` database (`profiles`/`reports`/`runs`)."""
    from azure.cosmos.aio import CosmosClient

    settings: Settings = get_settings()
    return CosmosClient(url=settings.azure_cosmos_endpoint, credential=get_azure_credential())


@lru_cache
def get_docintel_client():
    """Cached async Document Intelligence client (`prebuilt-read`/`prebuilt-layout`)."""
    from azure.ai.documentintelligence.aio import DocumentIntelligenceClient

    settings: Settings = get_settings()
    return DocumentIntelligenceClient(endpoint=settings.azure_docintel_endpoint, credential=get_azure_credential())


@lru_cache
def get_search_client(index_name: str):
    """Cached async `SearchClient` bound to one index (e.g. `idx-medicines`)."""
    from azure.search.documents.aio import SearchClient

    settings: Settings = get_settings()
    return SearchClient(
        endpoint=settings.azure_search_endpoint, index_name=index_name, credential=get_azure_credential()
    )


@lru_cache
def get_search_index_client():
    """Cached async `SearchIndexClient` for creating/updating index definitions."""
    from azure.search.documents.indexes.aio import SearchIndexClient

    settings: Settings = get_settings()
    return SearchIndexClient(
        endpoint=settings.azure_search_endpoint, credential=get_azure_credential()
    )


@lru_cache
def get_embedding_client():
    """Cached `AsyncAzureOpenAI` bound to the `text-embedding-3-large` deployment."""
    from openai.lib.azure import AsyncAzureOpenAI

    settings: Settings = get_settings()
    credential = get_azure_credential()

    async def token_provider() -> str:
        token = await credential.get_token("https://cognitiveservices.azure.com/.default")
        return token.token

    return AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2024-10-21",
    )


@lru_cache
def get_chat_client():
    """Cached Agent Framework chat client for all feature agents.

    Agent Framework 1.x dropped the separate `AzureOpenAIChatClient`; Azure is now reached by
    handing `OpenAIChatClient` an `azure_endpoint` plus an Entra credential.
    """
    from agent_framework_openai import OpenAIChatClient

    settings: Settings = get_settings()
    return OpenAIChatClient(
        azure_endpoint=settings.azure_openai_endpoint,
        model=settings.azure_openai_chat_deployment,
        credential=get_azure_credential(),
    )

