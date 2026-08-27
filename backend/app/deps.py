"""Dependency-injection wiring: shared Azure clients and the current-user resolver.

Cross-cutting clients (OpenAI, Search, Blob, Cosmos, SQL) must be constructed once here and
injected via `Depends()` - never instantiated inside request handlers or services
(.github/instructions/backend.instructions.md).
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Header


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


# TODO(D1): add cached provider functions here for the Blob, Cosmos, SQL, Search, Document
# Intelligence, and Azure OpenAI clients, all constructed with DefaultAzureCredential and the
# endpoints from `Settings`. Example shape:
#
#     @lru_cache
#     def get_blob_service_client(settings: Annotated[Settings, Depends(get_settings)]) -> BlobServiceClient:
#         return BlobServiceClient(account_url=settings.azure_storage_blob_endpoint, credential=DefaultAzureCredential())
