"""Shared pytest fixtures. No live Azure calls in unit/contract tests - use recorded fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
