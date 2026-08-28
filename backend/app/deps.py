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
from fastapi import Header

from app.config import Settings, get_settings


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated caller, scoped by `user_id` for every repository read/write."""

    user_id: str


async def get_current_user(x_demo_user_id: Annotated[str | None, Header()] = None) -> CurrentUser:
    """Local/demo stub trusting an `X-Demo-User-Id` header.

    TODO(D4): replace with Entra JWT validation (`oid` claim) before any non-demo use; see
    docs/lld/1-low-level-design-overview.md Section 0 (auth flow) and cut-list item 1 in
    docs/team-plan.md if Entra login is descoped for the demo.
    """
    return CurrentUser(user_id=x_demo_user_id or "demo-user")


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
    """Cached `AzureOpenAIChatClient` (Microsoft Agent Framework) for all feature agents."""
    from agent_framework.azure import AzureOpenAIChatClient

    settings: Settings = get_settings()
    return AzureOpenAIChatClient(
        endpoint=settings.azure_openai_endpoint,
        model=settings.azure_openai_chat_deployment,
        credential=get_azure_credential(),
    )

