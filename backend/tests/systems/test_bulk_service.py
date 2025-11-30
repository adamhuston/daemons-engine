"""
Test suite for Phase 12.5 - Bulk Operations API

Tests BulkService functionality:
- Bulk import with validation
- Bulk export to ZIP
- Batch validation
- Rollback mechanisms
- Error handling
"""

import zipfile
from pathlib import Path

import pytest

from app.engine.systems.bulk_service import (BatchValidationRequest,
                                             BulkExportRequest,
                                             BulkImportRequest, BulkService)
from app.engine.systems.file_manager import FileManager
from app.engine.systems.schema_registry import SchemaRegistry
from app.engine.systems.validation_service import ValidationService


@pytest.fixture
def temp_world_data(tmp_path):
    """Create temporary world_data directory with test content"""
    world_data = tmp_path / "world_data"

    # Create subdirectories
    rooms_dir = world_data / "rooms"
    items_dir = world_data / "items"
    npcs_dir = world_data / "npcs"

    rooms_dir.mkdir(parents=True)
    items_dir.mkdir(parents=True)
    npcs_dir.mkdir(parents=True)

    # Create schema files
    room_schema = rooms_dir / "_schema.yaml"
    room_schema.write_text(
        """
required_fields:
  - room_id
  - name
  - description
optional_fields:
  - exits
  - lighting_override
  - room_type
"""
    )

    item_schema = items_dir / "_schema.yaml"
    item_schema.write_text(
        """
required_fields:
  - item_id
  - name
  - description
  - type
optional_fields:
  - weight
  - value
"""
    )

    npc_schema = npcs_dir / "_schema.yaml"
    npc_schema.write_text(
        """
required_fields:
  - npc_id
  - name
  - description
optional_fields:
  - level
  - faction_id
"""
    )

    # Create some test content
    room1 = rooms_dir / "room1.yaml"
    room1.write_text(
        """
room_id: room_1
name: Test Room
description: A test room for validation
"""
    )

    item1 = items_dir / "item1.yaml"
    item1.write_text(
        """
item_id: test_sword
name: Test Sword
description: A basic sword for testing
type: weapon
"""
    )

    return world_data


@pytest.fixture
def file_manager(temp_world_data):
    """Create FileManager instance"""
    return FileManager(temp_world_data)


@pytest.fixture
def schema_registry(temp_world_data):
    """Create SchemaRegistry instance"""
    registry = SchemaRegistry(temp_world_data)
    registry.load_all_schemas()
    return registry


@pytest.fixture
def validation_service(temp_world_data, file_manager, schema_registry):
    """Create ValidationService instance"""
    return ValidationService(
        world_data_path=str(temp_world_data),
        file_manager=file_manager,
        schema_registry=schema_registry,
    )


@pytest.fixture
def bulk_service(file_manager, validation_service, schema_registry):
    """Create BulkService instance"""
    return BulkService(
        file_manager=file_manager,
        validation_service=validation_service,
        schema_registry=schema_registry,
    )


# ============================================================================
# Bulk Import Tests
# ============================================================================


@pytest.mark.asyncio
async def test_bulk_import_valid_files(bulk_service):
    """Test importing multiple valid YAML files"""
    files = {
        "rooms/room2.yaml": """
room_id: room_2
name: Second Room
description: Another test room
""",
        "items/item2.yaml": """
item_id: test_shield
name: Test Shield
description: A protective shield
type: armor
""",
    }

    request = BulkImportRequest(
        files=files, validate_only=False, rollback_on_error=True
    )

    response = await bulk_service.bulk_import(request)

    assert response.success is True
    assert response.total_files == 2
    assert response.files_validated == 2
    assert response.files_written == 2
    assert response.files_failed == 0
    assert response.rolled_back is False

    # Verify files were written
    for result in response.results:
        assert result.success is True
        assert result.written is True
        assert result.checksum is not None


@pytest.mark.asyncio
async def test_bulk_import_validate_only(bulk_service):
    """Test validation without writing files"""
    files = {
        "rooms/room3.yaml": """
room_id: room_3
name: Third Room
description: Validation test
"""
    }

    request = BulkImportRequest(files=files, validate_only=True)

    response = await bulk_service.bulk_import(request)

    assert response.success is True
    assert response.files_validated == 1
    assert response.files_written == 0  # Not written in validate-only mode

    # Verify file was not written
    for result in response.results:
        assert result.success is True
        assert result.written is False


@pytest.mark.asyncio
async def test_bulk_import_invalid_yaml(bulk_service):
    """Test importing files with invalid YAML syntax"""
    files = {
        "rooms/bad_room.yaml": """
id: bad_room
name: Bad Room
  invalid indentation:
description: This will fail
"""
    }

    request = BulkImportRequest(
        files=files, validate_only=False, rollback_on_error=True
    )

    response = await bulk_service.bulk_import(request)

    assert response.success is False
    assert response.files_failed > 0
    assert response.files_written == 0  # Rollback prevented write

    # Verify error details
    for result in response.results:
        if not result.success:
            assert result.validation_result is not None
            assert not result.validation_result.valid


@pytest.mark.asyncio
async def test_bulk_import_missing_required_fields(bulk_service):
    """Test importing files with missing required fields"""
    files = {
        "rooms/incomplete_room.yaml": """
id: incomplete_room
name: Incomplete Room
# Missing description field
"""
    }

    request = BulkImportRequest(files=files, rollback_on_error=True)

    response = await bulk_service.bulk_import(request)

    assert response.success is False
    assert response.files_failed > 0

    # Check validation result
    result = response.results[0]
    assert not result.success
    assert result.validation_result is not None
    assert len(result.validation_result.errors) > 0


@pytest.mark.asyncio
async def test_bulk_import_rollback_on_error(bulk_service):
    """Test rollback when some files are invalid"""
    files = {
        "rooms/good_room.yaml": """
id: good_room
name: Good Room
description: This is valid
""",
        "rooms/bad_room.yaml": """
id: bad_room
# Missing required fields
""",
    }

    request = BulkImportRequest(files=files, rollback_on_error=True)

    response = await bulk_service.bulk_import(request)

    # Should fail because one file is invalid
    assert response.success is False
    assert response.files_written == 0  # Nothing written due to rollback
    assert response.error is not None


@pytest.mark.asyncio
async def test_bulk_import_no_rollback(bulk_service):
    """Test importing with rollback disabled (partial success)"""
    files = {
        "rooms/valid_room.yaml": """
room_id: valid_room
name: Valid Room
description: This will succeed
""",
        "rooms/invalid_room.yaml": """
room_id: invalid_room
# Missing name and description fields
""",
    }

    request = BulkImportRequest(
        files=files, rollback_on_error=False  # Allow partial success
    )

    response = await bulk_service.bulk_import(request)

    # Some files written despite errors
    assert response.files_written > 0
    assert response.files_failed > 0

    # Check individual results
    valid_result = next(r for r in response.results if "valid_room" in r.file_path)
    assert valid_result.success is True
    assert valid_result.written is True


# ============================================================================
# Bulk Export Tests
# ============================================================================


@pytest.mark.asyncio
async def test_bulk_export_all_files(bulk_service, temp_world_data):
    """Test exporting all content to ZIP"""
    request = BulkExportRequest(
        content_types=None, include_schema_files=False  # All types
    )

    response = await bulk_service.bulk_export(request)

    assert response.success is True
    assert response.total_files > 0
    assert Path(response.zip_path).exists()

    # Verify ZIP contains files
    with zipfile.ZipFile(response.zip_path, "r") as zipf:
        namelist = zipf.namelist()
        assert "manifest.json" in namelist
        assert any("room1.yaml" in name for name in namelist)
        assert any("item1.yaml" in name for name in namelist)

    # Verify manifest
    assert "export_timestamp" in response.manifest
    assert "total_files" in response.manifest
    assert response.manifest["total_files"] == response.total_files


@pytest.mark.asyncio
async def test_bulk_export_filtered_by_type(bulk_service):
    """Test exporting specific content types"""
    request = BulkExportRequest(content_types=["rooms"], include_schema_files=False)

    response = await bulk_service.bulk_export(request)

    assert response.success is True
    assert response.total_files > 0

    # Verify only rooms exported
    with zipfile.ZipFile(response.zip_path, "r") as zipf:
        namelist = zipf.namelist()
        assert any("rooms" in name for name in namelist)
        assert not any("items" in name and ".yaml" in name for name in namelist)


@pytest.mark.asyncio
async def test_bulk_export_with_schema_files(bulk_service):
    """Test exporting with schema files included"""
    request = BulkExportRequest(content_types=["rooms"], include_schema_files=True)

    response = await bulk_service.bulk_export(request)

    assert response.success is True

    # Verify schema files included
    with zipfile.ZipFile(response.zip_path, "r") as zipf:
        namelist = zipf.namelist()
        assert any("_schema.yaml" in name for name in namelist)


@pytest.mark.asyncio
async def test_bulk_export_specific_files(bulk_service):
    """Test exporting specific file paths"""
    request = BulkExportRequest(file_paths=["rooms/room1.yaml"])

    response = await bulk_service.bulk_export(request)

    assert response.success is True
    assert response.total_files == 1

    # Verify only specified file exported
    with zipfile.ZipFile(response.zip_path, "r") as zipf:
        namelist = zipf.namelist()
        assert "rooms/room1.yaml" in namelist
        assert len([n for n in namelist if n.endswith(".yaml")]) == 1


@pytest.mark.asyncio
async def test_bulk_export_empty_filter(bulk_service):
    """Test export with filter that matches no files"""
    request = BulkExportRequest(content_types=["nonexistent_type"])

    response = await bulk_service.bulk_export(request)

    assert response.success is False
    assert response.total_files == 0
    assert "No files matched" in response.error


# ============================================================================
# Batch Validation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_batch_validate_all_valid(bulk_service):
    """Test batch validation with all valid files"""
    files = {
        "rooms/new_room1.yaml": """
room_id: new_room1
name: New Room 1
description: Valid test room
""",
        "rooms/new_room2.yaml": """
room_id: new_room2
name: New Room 2
description: Another valid room
""",
    }

    request = BatchValidationRequest(files=files)
    response = await bulk_service.batch_validate(request)

    assert response.success is True
    assert response.total_files == 2
    assert response.valid_files == 2
    assert response.invalid_files == 0

    # All results should be valid
    for result in response.results:
        assert result.valid is True
        assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_batch_validate_mixed_results(bulk_service):
    """Test batch validation with mix of valid and invalid"""
    files = {
        "rooms/valid.yaml": """
room_id: valid_room
name: Valid
description: This is valid
""",
        "rooms/invalid.yaml": """
room_id: invalid_room
# Missing name and description fields
""",
    }

    request = BatchValidationRequest(files=files)
    response = await bulk_service.batch_validate(request)

    assert response.success is True
    assert response.total_files == 2
    assert response.valid_files == 1
    assert response.invalid_files == 1


@pytest.mark.asyncio
async def test_batch_validate_syntax_errors(bulk_service):
    """Test batch validation detects YAML syntax errors"""
    files = {
        "rooms/syntax_error.yaml": """
room_id: syntax_error
name: Bad Syntax
  invalid: indentation
description: This has a syntax error
"""
    }

    request = BatchValidationRequest(files=files)
    response = await bulk_service.batch_validate(request)

    assert response.total_files == 1
    assert response.invalid_files == 1

    # Check error details
    result = response.results[0]
    assert not result.valid
    assert len(result.errors) > 0
    # ValidationError objects have error_type attribute
    assert any("syntax" in err.error_type.lower() for err in result.errors)


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_import_export_roundtrip(bulk_service, temp_world_data):
    """Test exporting and then re-importing content"""
    # Export all content
    export_request = BulkExportRequest(content_types=None, include_schema_files=False)
    export_response = await bulk_service.bulk_export(export_request)
    assert export_response.success is True

    # Extract files from ZIP
    files = {}
    with zipfile.ZipFile(export_response.zip_path, "r") as zipf:
        for name in zipf.namelist():
            if name.endswith(".yaml") and not name.endswith("_schema.yaml"):
                content = zipf.read(name).decode("utf-8")
                files[name] = content

    # Import extracted files
    import_request = BulkImportRequest(
        files=files,
        validate_only=False,
        rollback_on_error=True,
        overwrite_existing=True,
    )
    import_response = await bulk_service.bulk_import(import_request)

    assert import_response.success is True
    assert import_response.files_written == len(files)


@pytest.mark.asyncio
async def test_validate_then_import(bulk_service):
    """Test validation before import workflow"""
    files = {
        "rooms/workflow_test.yaml": """
room_id: workflow_room
name: Workflow Test
description: Testing validation workflow
"""
    }

    # Step 1: Validate
    validate_request = BatchValidationRequest(files=files)
    validate_response = await bulk_service.batch_validate(validate_request)
    assert validate_response.valid_files == 1

    # Step 2: Import
    import_request = BulkImportRequest(files=files, validate_only=False)
    import_response = await bulk_service.bulk_import(import_request)
    assert import_response.success is True
    assert import_response.files_written == 1


# ============================================================================
# Summary
# ============================================================================


def test_summary():
    """Print test suite summary"""
    print("\n" + "=" * 70)
    print("Phase 12.5 Bulk Operations Test Suite Summary")
    print("=" * 70)
    print("\nBulk Import Tests:")
    print("  ✓ Import valid files")
    print("  ✓ Validate-only mode")
    print("  ✓ Invalid YAML syntax detection")
    print("  ✓ Missing required fields detection")
    print("  ✓ Rollback on error")
    print("  ✓ Partial success (no rollback)")
    print("\nBulk Export Tests:")
    print("  ✓ Export all files to ZIP")
    print("  ✓ Filter by content type")
    print("  ✓ Include schema files")
    print("  ✓ Export specific files")
    print("  ✓ Empty filter handling")
    print("\nBatch Validation Tests:")
    print("  ✓ All valid files")
    print("  ✓ Mixed valid/invalid")
    print("  ✓ Syntax error detection")
    print("\nIntegration Tests:")
    print("  ✓ Export/import roundtrip")
    print("  ✓ Validate then import workflow")
    print("=" * 70)


if __name__ == "__main__":
    # Run tests with pytest
    import sys

    pytest.main([__file__, "-v", "--tb=short"] + sys.argv[1:])
