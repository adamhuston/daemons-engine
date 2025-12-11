"""
API Test for Phase 12.1 - Schema Registry Endpoints

Tests the REST API endpoints for the schema registry.
These are integration tests that require the server to be running.

Tests:
1. GET /api/admin/schemas - Fetch all schemas
2. GET /api/admin/schemas?content_type=classes - Filter by content type
3. GET /api/admin/schemas/version - Get version info
4. POST /api/admin/schemas/reload - Reload schemas (requires GAME_MASTER token)
"""

import pytest


@pytest.mark.api
@pytest.mark.phase12
@pytest.mark.skip(reason="Requires running server - manual test only")
class TestSchemaAPIEndpoints:
    """Test the schema API endpoints.

    Note: These tests are skipped by default. To run them:
    1. Start the server: daemons run
    2. Run with: pytest -m api --runxfail
    """

    def test_get_all_schemas(self, test_client, admin_headers):
        """Test GET /api/admin/schemas - fetch all schemas."""
        response = test_client.get("/api/admin/schemas", headers=admin_headers)
        assert (
            response.status_code == 200
        ), f"Should return 200, got {response.status_code}"

        data = response.json()
        assert "count" in data, "Response should have count"
        assert "schemas" in data, "Response should have schemas"
        assert data["count"] > 0, "Should have schemas"

        # Verify schema structure
        if data["schemas"]:
            schema = data["schemas"][0]
            assert "content_type" in schema, "Schema should have content_type"
            assert "checksum" in schema, "Schema should have checksum"
            assert "size_bytes" in schema, "Schema should have size_bytes"

    def test_filter_by_content_type(self, test_client, admin_headers):
        """Test GET /api/admin/schemas?content_type=classes."""
        response = test_client.get(
            "/api/admin/schemas",
            params={"content_type": "classes"},
            headers=admin_headers,
        )
        assert (
            response.status_code == 200
        ), f"Should return 200, got {response.status_code}"

        data = response.json()
        assert "schemas" in data, "Response should have schemas"

        # All returned schemas should be classes
        for schema in data["schemas"]:
            assert (
                schema["content_type"] == "classes"
            ), "All schemas should match filter"

    def test_get_schema_version(self, test_client, admin_headers):
        """Test GET /api/admin/schemas/version."""
        response = test_client.get("/api/admin/schemas/version", headers=admin_headers)
        assert (
            response.status_code == 200
        ), f"Should return 200, got {response.status_code}"

        data = response.json()
        assert "version" in data, "Should have version"
        assert "engine_version" in data, "Should have engine_version"
        assert "schema_count" in data, "Should have schema_count"
        assert "last_modified" in data, "Should have last_modified"

        assert data["schema_count"] > 0, "Should have schemas"

    def test_reload_schemas(self, test_client, admin_headers):
        """Test POST /api/admin/schemas/reload (requires GAME_MASTER)."""
        response = test_client.post("/api/admin/schemas/reload", headers=admin_headers)

        # Might be 200 (success) or 403 (permission denied)
        assert response.status_code in [
            200,
            403,
        ], f"Should return 200 or 403, got {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            assert "schemas_loaded" in data, "Should have schemas_loaded count"
            assert "version" in data, "Should have version info"
            assert data["schemas_loaded"] > 0, "Should reload schemas"

    def test_get_schemas_unauthorized(self, test_client):
        """Test that schemas endpoint requires authentication."""
        response = test_client.get("/api/admin/schemas")
        assert response.status_code == 401, "Should require authentication"


@pytest.mark.api
@pytest.mark.phase12
def test_schema_api_documentation():
    """Document how to manually test the schema API endpoints.

    This is a documentation test that always passes but provides
    instructions for manual API testing.
    """
    instructions = """
    Manual API Testing Instructions:

    1. Start the server:
       daemons run

    2. Get an access token:
       POST http://localhost:8000/auth/login
       {
         "username": "your_username",
         "password": "your_password"
       }

    3. Test endpoints with the token:

       GET /api/admin/schemas
       Headers: Authorization: Bearer <your_token>

       GET /api/admin/schemas?content_type=classes
       Headers: Authorization: Bearer <your_token>

       GET /api/admin/schemas/version
       Headers: Authorization: Bearer <your_token>

       POST /api/admin/schemas/reload
       Headers: Authorization: Bearer <your_token>
       (Requires GAME_MASTER permission)

    4. Or use the Python requests library:

       import requests

       BASE_URL = "http://localhost:8000"
       headers = {"Authorization": f"Bearer {token}"}

       response = requests.get(f"{BASE_URL}/api/admin/schemas", headers=headers)
       print(response.json())
    """
    assert True, instructions
