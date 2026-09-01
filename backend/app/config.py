"""Typed application settings, bound to Key Vault (docs/lld/8-low-level-design-cross-cutting-platform.md Section 7.4)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Environment/Key-Vault-backed configuration. Never hardcode endpoints, keys, or thresholds elsewhere."""

    # Absolute paths: the server runs from `backend/`, so a relative `.env` would miss the repo-root file.
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _REPO_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    azure_tenant_id: str = ""
    azure_key_vault_uri: str = ""

    azure_storage_account_name: str = ""
    azure_cosmos_endpoint: str = ""
    azure_cosmos_database_name: str = "healthiq"
    azure_sql_server_fqdn: str = ""
    azure_sql_database_name: str = "healthiq"
    azure_search_endpoint: str = ""
    azure_docintel_endpoint: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_chat_deployment: str = "gpt-5.4"
    azure_openai_embedding_deployment: str = "text-embedding-3-large"
    applicationinsights_connection_string: str = ""

    demo_mode: bool = True
    ocr_confidence_threshold: float = 0.75
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance.

    TODO(D1): once `azure_key_vault_uri` is set, overlay any unset fields from Key Vault secrets
    (AZURE-STORAGE-ACCOUNT-NAME, AZURE-COSMOS-ENDPOINT, ... - see infra/main.bicep outputs) using
    `DefaultAzureCredential` + `SecretClient`.
    """
    return Settings()
