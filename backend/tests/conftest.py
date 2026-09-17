"""Shared pytest fixtures. No live Azure calls in unit/contract tests - use recorded fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

# Services pick a live client whenever its endpoint is configured, so `DEMO_MODE` alone does not
# keep the suite offline once `.env` points at provisioned resources.
_LIVE_ENDPOINT_VARS = (
    "AZURE_DOCINTEL_ENDPOINT",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_STORAGE_ACCOUNT_NAME",
    "AZURE_COSMOS_ENDPOINT",
    "AZURE_SQL_SERVER_FQDN",
    "AZURE_KEY_VAULT_URI",
    "APPLICATIONINSIGHTS_CONNECTION_STRING",
)


@pytest.fixture(autouse=True)
def force_demo_mode(monkeypatch: pytest.MonkeyPatch):
    """Pin every test to replayed fixtures, even when the repo `.env` points at real resources."""
    monkeypatch.setenv("DEMO_MODE", "true")
    for name in _LIVE_ENDPOINT_VARS:
        monkeypatch.setenv(name, "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
