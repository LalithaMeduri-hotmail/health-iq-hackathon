"""Shared pytest fixtures. No live Azure calls in unit/contract tests - use recorded fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def force_demo_mode(monkeypatch: pytest.MonkeyPatch):
    """Pin every test to replayed fixtures, even when the repo `.env` points at real resources."""
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
