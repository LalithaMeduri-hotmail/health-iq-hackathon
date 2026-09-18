"""Dependency-injection wiring: shared Azure clients and the current-user resolver.

Cross-cutting clients (OpenAI, Search, Blob, Cosmos, SQL) must be constructed once here and
injected via `Depends()` - never instantiated inside request handlers or services
(.github/instructions/backend.instructions.md). Provider functions are plain `lru_cache`
callables (not FastAPI `Depends` markers) so both routers (`Depends(get_blob_service_client)`)
and lower layers (direct call, e.g. `from app.deps import get_blob_service_client`) can reuse the
same cached client instance.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from azure.identity.aio import DefaultAzureCredential
from fastapi import Header, Request

from app.config import Settings, get_settings
from app.errors import UnauthenticatedError

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


@lru_cache
def get_azure_credential() -> DefaultAzureCredential:
    """Single shared async `DefaultAzureCredential` for every Azure SDK client."""
    return DefaultAzureCredential()


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
def get_chat_client():
    """Cached `OpenAIChatClient` (Microsoft Agent Framework) in Azure OpenAI mode for all feature agents."""
    from agent_framework.openai import OpenAIChatClient

    settings: Settings = get_settings()
    return OpenAIChatClient(
        azure_endpoint=settings.azure_openai_endpoint,
        model=settings.azure_openai_chat_deployment,
        credential=get_azure_credential(),
    )

