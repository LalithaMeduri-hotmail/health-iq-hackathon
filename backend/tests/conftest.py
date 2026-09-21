"""Shared pytest fixtures. No live Azure calls in unit/contract tests - use recorded fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.repositories import cosmos_repo


@pytest.fixture(autouse=True)
def force_demo_mode(monkeypatch: pytest.MonkeyPatch):
    """Pin every test to replayed fixtures, even when the repo `.env` points at real resources."""
    monkeypatch.setenv("DEMO_MODE", "true")
    # A configured mail transport would make the suite email real doctors from the demo registry.
    monkeypatch.setenv("AZURE_COMMUNICATION_ENDPOINT", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_demo_stores():
    """Isolate the in-process patient-profile stores; without this, profiles created by one test
    collide by display name with the next one's (`409 already exists`)."""
    cosmos_repo.reset_demo_state()
    yield
    cosmos_repo.reset_demo_state()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
