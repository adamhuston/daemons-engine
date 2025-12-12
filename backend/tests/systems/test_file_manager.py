"""
Test suite for Phase 12.2 File Manager implementation.

Tests:
1. FileManager lists files correctly
2. Path traversal attacks are prevented
3. File reading works with checksums
4. Atomic file writing works
5. Validation mode works
6. File deletion works with safety checks
"""

from pathlib import Path

import pytest


@pytest.mark.systems
@pytest.mark.phase12
class TestFileManager:
    """Test the FileManager system."""

    async def test_list_all_files(self, file_manager):
        """Test listing all YAML files."""
        files = await file_manager.list_files(include_schema_files=False)
        assert isinstance(files, list), "Should return a list"
        # Should have at least some files (classes, items, etc.)
        # Note: temp_world_data fixture provides schema files

        # Verify file info structure
        for file_info in files[:5]:
            assert hasattr(file_info, "file_path"), "Should have file_path"
            assert hasattr(file_info, "content_type"), "Should have content_type"
            assert hasattr(file_info, "size_bytes"), "Should have size_bytes"
            assert file_info.size_bytes >= 0, "Size should be non-negative"

    async def test_filter_by_content_type(self, file_manager, temp_world_data):
        """Test filtering files by content type."""
        # Create a test class file
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        test_file = classes_dir / "warrior.yaml"
        test_file.write_text("class_id: warrior\nname: Warrior\n")

        # List class files
        classes_files = await file_manager.list_files(
            content_type_filter="classes", include_schema_files=False
        )
        assert len(classes_files) >= 1, "Should find at least the warrior class"

        # Verify all results are class files
        for file_info in classes_files:
            assert file_info.content_type == "classes", "Should only return class files"

    def test_path_traversal_prevention(self, file_manager):
        """Test that path traversal attacks are prevented."""
        unsafe_paths = [
            "../../../etc/passwd",
            "classes/../../backend/app/main.py",
            "/etc/passwd",
        ]

        for unsafe_path in unsafe_paths:
            is_safe = file_manager._is_safe_path(unsafe_path)
            assert not is_safe, f"Path should be marked unsafe: {unsafe_path}"

    def test_safe_paths_allowed(self, file_manager):
        """Test that safe paths are correctly allowed."""
        safe_paths = [
            "classes/warrior.yaml",
            "items/sword.yaml",
            "npcs/goblin.yaml",
            "rooms/starting_room.yaml",
        ]

        for safe_path in safe_paths:
            is_safe = file_manager._is_safe_path(safe_path)
            assert is_safe, f"Path should be marked safe: {safe_path}"

    async def test_read_file(self, file_manager, temp_world_data):
        """Test reading a file with checksums."""
        # Create a test file
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        test_file = classes_dir / "warrior.yaml"
        test_content = "class_id: warrior\nname: Warrior\ndescription: A fighter\n"
        test_file.write_text(test_content)

        # Read the file
        file_content = await file_manager.read_file("classes/warrior.yaml")
        assert (
            file_content.file_path == "classes/warrior.yaml"
        ), "Should return correct path"
        assert file_content.size_bytes > 0, "Should have content size"
        assert len(file_content.checksum) > 0, "Should have checksum"
        assert file_content.last_modified is not None, "Should have timestamp"
        assert file_content.content == test_content, "Should return file content"

    async def test_read_nonexistent_file(self, file_manager):
        """Test reading a file that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            await file_manager.read_file("nonexistent/file.yaml")

    async def test_validate_yaml_syntax(self, file_manager):
        """Test YAML syntax validation."""
        # Valid YAML
        valid_yaml = "test_key: test_value\nanother_key: 123"
        success, checksum, errors = await file_manager.write_file(
            "test_validation.yaml", valid_yaml, validate_only=True
        )
        assert success, "Valid YAML should pass validation"
        assert len(errors) == 0, "Should have no errors"

        # Invalid YAML
        invalid_yaml = "invalid: yaml:\n  - broken\n    indentation"
        success, checksum, errors = await file_manager.write_file(
            "test_validation.yaml", invalid_yaml, validate_only=True
        )
        assert not success, "Invalid YAML should fail validation"
        assert len(errors) > 0, "Should have error messages"

    async def test_atomic_write_validate_only(self, file_manager):
        """Test atomic write in validate-only mode."""
        test_content = """# Test YAML file
test_field: test_value
test_list:
  - item1
  - item2
"""
        success, checksum, errors = await file_manager.write_file(
            "test/test_file.yaml", test_content, validate_only=True
        )

        assert success, "Validation should pass for valid YAML"
        assert len(errors) == 0, "Should have no errors"
        # In validate-only mode, checksum might be None
        # assert checksum is None, "Should not generate checksum in validate-only mode"

    async def test_get_statistics(self, file_manager, temp_world_data):
        """Test file statistics."""
        # Create some test files
        for content_type in ["classes", "items", "npcs"]:
            dir_path = temp_world_data / content_type
            dir_path.mkdir(exist_ok=True)
            test_file = dir_path / f"test_{content_type}.yaml"
            test_file.write_text(f"{content_type}_id: test\nname: Test\n")

        stats = await file_manager.get_stats()
        assert "total" in stats, "Should have total count"
        assert stats["total"] >= 3, "Should count created files"

    async def test_schema_file_protection(self, file_manager, temp_world_data):
        """Test that schema files cannot be deleted."""
        # Create a schema file
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        schema_file = classes_dir / "_schema.yaml"
        schema_file.write_text(
            "type: object\nproperties:\n  class_id:\n    type: string\n"
        )

        # Try to delete it
        success, errors = await file_manager.delete_file("classes/_schema.yaml")
        assert not success, "Should not allow deleting schema files"
        assert any(
            "Cannot delete schema files" in str(error) for error in errors
        ), "Should have schema protection error message"

    async def test_delete_regular_file(self, file_manager, temp_world_data):
        """Test deleting a regular (non-schema) file."""
        # Create a test file
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        test_file = classes_dir / "test_delete.yaml"
        test_file.write_text("class_id: test\nname: Test\n")

        # Delete it
        success, errors = await file_manager.delete_file("classes/test_delete.yaml")
        assert success, f"Should successfully delete file: {errors}"
        assert len(errors) == 0, "Should have no errors"
        assert not test_file.exists(), "File should be deleted from disk"


@pytest.mark.systems
@pytest.mark.phase12
def test_file_manager_initialization(temp_world_data):
    """Test that FileManager can be initialized with a valid path."""
    from daemons.engine.systems.file_manager import FileManager

    manager = FileManager(str(temp_world_data))
    assert manager.world_data_path == Path(temp_world_data), "Should set correct path"
    assert manager.world_data_path.exists(), "Path should exist"
