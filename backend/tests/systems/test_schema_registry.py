"""
Test suite for Phase 12.1 Schema Registry implementation.

Tests:
1. SchemaRegistry loads schemas correctly
2. Checksums are computed properly
3. Filtering works
4. Version info is correct
"""

from pathlib import Path

import pytest


@pytest.mark.systems
@pytest.mark.phase12
class TestSchemaRegistry:
    """Test the SchemaRegistry system."""

    def test_load_all_schemas(self, schema_registry):
        """Test loading all schemas."""
        assert len(schema_registry.schemas) > 0, "Should load at least one schema"
        assert "classes" in schema_registry.schemas, "Should load classes schema"

    def test_list_schema_types(self, schema_registry):
        """Test listing all schema types."""
        schema_list = schema_registry.get_schema_list()
        assert len(schema_list) > 0, "Should have schema types"
        assert "classes" in schema_list, "Should include classes schema"

        # Verify each schema has proper metadata
        for schema_type in schema_list:
            schema = schema_registry.schemas[schema_type]
            assert schema.size_bytes > 0, f"{schema_type} should have size"
            assert len(schema.checksum) > 0, f"{schema_type} should have checksum"

    def test_get_specific_schema(self, schema_registry):
        """Test retrieving a specific schema."""
        classes_schema = schema_registry.get_schema("classes")
        assert classes_schema is not None, "Should find classes schema"
        assert classes_schema.file_path.endswith(
            "_schema.yaml"
        ), "Should be schema file"
        assert classes_schema.size_bytes > 0, "Should have content"
        assert len(classes_schema.checksum) > 0, "Should have checksum"
        assert classes_schema.last_modified is not None, "Should have timestamp"

    def test_get_nonexistent_schema(self, schema_registry):
        """Test retrieving a schema that doesn't exist."""
        result = schema_registry.get_schema("nonexistent_content_type")
        assert result is None, "Should return None for nonexistent schema"

    def test_filter_by_content_type(self, schema_registry):
        """Test filtering schemas by content type."""
        # Get all schemas
        all_schemas = schema_registry.get_all_schemas()
        assert len(all_schemas) > 0, "Should have schemas"

        # Filter by specific content type
        classes_schemas = schema_registry.get_all_schemas(content_type_filter="classes")
        assert len(classes_schemas) >= 1, "Should find classes schema"

        # Verify all returned schemas match filter
        for schema in classes_schemas:
            assert schema.content_type == "classes", "All results should match filter"

    def test_version_info(self, schema_registry):
        """Test schema version information."""
        version = schema_registry.get_version()
        assert version.version is not None, "Should have version"
        assert version.engine_version is not None, "Should have engine version"
        assert version.last_modified is not None, "Should have last modified timestamp"
        assert version.schema_count > 0, "Should have schema count"
        assert version.schema_count == len(
            schema_registry.schemas
        ), "Count should match actual schemas"

    def test_reload_schemas(self, schema_registry):
        """Test reloading schemas."""
        initial_count = len(schema_registry.schemas)
        count = schema_registry.reload_schemas()
        assert count == initial_count, "Reload should return same count"
        assert (
            len(schema_registry.schemas) == initial_count
        ), "Should have same schemas after reload"

    def test_schema_content(self, schema_registry):
        """Test that schema content is properly loaded."""
        classes_schema = schema_registry.get_schema("classes")
        assert classes_schema is not None, "Should have classes schema"
        assert len(classes_schema.content) > 0, "Schema should have content"
        # Schema files contain metadata about fields, not the fields themselves
        assert (
            "required_fields" in classes_schema.content
            or "properties" in classes_schema.content
        ), "Schema should contain field definitions"

    def test_schema_checksums_stable(self, schema_registry):
        """Test that schema checksums are stable across reloads."""
        # Get initial checksums
        initial_checksums = {
            schema_type: schema.checksum
            for schema_type, schema in schema_registry.schemas.items()
        }

        # Reload
        schema_registry.reload_schemas()

        # Verify checksums haven't changed
        for schema_type, initial_checksum in initial_checksums.items():
            current_checksum = schema_registry.schemas[schema_type].checksum
            assert (
                current_checksum == initial_checksum
            ), f"{schema_type} checksum changed after reload"


@pytest.mark.systems
@pytest.mark.phase12
def test_schema_registry_initialization(temp_world_data):
    """Test that SchemaRegistry can be initialized with a valid path."""
    from app.engine.systems.schema_registry import SchemaRegistry

    registry = SchemaRegistry(str(temp_world_data))
    assert registry.world_data_path == Path(temp_world_data), "Should set correct path"
    assert len(registry.schemas) == 0, "Should start empty before loading"

    # Load schemas
    registry.load_all_schemas()
    assert len(registry.schemas) > 0, "Should load schemas"
