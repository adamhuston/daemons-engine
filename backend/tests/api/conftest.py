"""API test specific fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def test_client():
    """Create FastAPI TestClient for API endpoint testing."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def admin_headers():
    """Headers for admin authentication (when auth is implemented)."""
    return {
        "Authorization": "Bearer test_admin_token",
        "Content-Type": "application/json",
    }
