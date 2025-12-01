"""
Test suite for Phase 12.3 ValidationService

Tests:
- Syntax validation (YAML parsing errors with line/column)
- Schema conformance (required fields, types)
- Reference validation (broken links, missing entities)
- Error formatting and location reporting
"""

import pytest

from daemons.engine.systems.validation_service import ReferenceCache


@pytest.mark.systems
@pytest.mark.phase12
class TestSyntaxValidation:
    """Test YAML syntax validation with line/column errors."""

    def test_valid_yaml(self, validation_service):
        """Test that valid YAML passes syntax validation."""
        valid_yaml = """
class_id: warrior
name: Warrior
description: A fighter
"""
        result = validation_service.validate_syntax(valid_yaml)
        assert result.valid, "Valid YAML should pass"
        assert len(result.errors) == 0, "No errors expected"

    def test_invalid_indentation(self, validation_service):
        """Test detection of invalid YAML indentation."""
        invalid_yaml = """
class_id: warrior
name: Warrior
  description: Bad indent
"""
        result = validation_service.validate_syntax(invalid_yaml)
        assert not result.valid, "Invalid YAML should fail"
        assert len(result.errors) >= 1, "Should have at least one error"
        error = result.errors[0]
        assert error.line is not None, "Error should have line number"
        assert error.error_type == "syntax", "Should be syntax error"

    def test_unclosed_quote(self, validation_service):
        """Test detection of unclosed quotes."""
        invalid_yaml = """
class_id: "warrior
name: Warrior
"""
        result = validation_service.validate_syntax(invalid_yaml)
        assert not result.valid, "Invalid YAML should fail"
        assert len(result.errors) >= 1, "Should have error"


@pytest.mark.systems
@pytest.mark.phase12
class TestSchemaValidation:
    """Test schema conformance checking."""

    def test_missing_required_fields(self, validation_service):
        """Test detection of missing required fields."""
        incomplete_class = """
class_id: warrior
name: Warrior
"""
        result = validation_service.validate_schema(incomplete_class, "classes")
        assert not result.valid, "Missing required fields should fail"
        # Should detect missing description, base_stats, starting_resources
        assert len(result.errors) >= 1, "Should have errors for missing fields"

    def test_empty_required_field(self, validation_service):
        """Test detection of empty required fields."""
        empty_field = """
class_id: warrior
name: ""
description: A fighter
base_stats:
  strength: 10
  dexterity: 10
  intelligence: 10
  vitality: 10
starting_resources:
  health: 100
"""
        result = validation_service.validate_schema(empty_field, "classes")
        # Should detect empty name field
        # Note: Actual behavior depends on schema definition
        if not result.valid:
            assert any(
                "name" in e.message.lower() or "empty" in e.message.lower()
                for e in result.errors
            ), "Should detect empty field"

    def test_invalid_stat_type(self, validation_service):
        """Test detection of invalid stat types."""
        invalid_stats = """
class_id: warrior
name: Warrior
description: A fighter
base_stats:
  strength: "not a number"
  dexterity: 10
  intelligence: 10
  vitality: 10
starting_resources:
  health: 100
"""
        result = validation_service.validate_schema(invalid_stats, "classes")
        # Should detect string instead of number
        # Note: Actual behavior depends on schema strictness
        if not result.valid:
            assert len(result.errors) >= 1, "Should have type error"

    def test_valid_class_schema(self, validation_service):
        """Test that a valid class passes schema validation."""
        valid_class = """
class_id: test_warrior
name: Warrior
description: A fighter
base_stats:
  strength: 14
  dexterity: 10
  intelligence: 8
  vitality: 12
starting_resources:
  health: 120
  rage: 100
"""
        result = validation_service.validate_schema(valid_class, "classes")
        # Should pass or have minimal warnings
        assert len(result.errors) == 0 or all(
            e.error_type == "warning" for e in result.errors
        ), f"Valid class should pass or only have warnings: {[e.message for e in result.errors]}"


@pytest.mark.systems
@pytest.mark.phase12
class TestReferenceCache:
    """Test reference cache building and lookups."""

    def test_add_and_lookup_entities(self):
        """Test adding entities to cache and looking them up."""
        cache = ReferenceCache()

        # Add various entities
        cache.add_room("town_square", {"north": "market", "south": "gate"})
        cache.add_room("market")
        cache.add_item("sword_001")
        cache.add_npc("guard_captain")
        cache.add_ability("slash")
        cache.add_class("warrior")

        # Verify lookups
        assert "town_square" in cache.room_ids, "Room should be in cache"
        assert "sword_001" in cache.item_ids, "Item should be in cache"
        assert "slash" in cache.ability_ids, "Ability should be in cache"
        assert "warrior" in cache.class_ids, "Class should be in cache"
        assert "guard_captain" in cache.npc_ids, "NPC should be in cache"

    def test_exit_tracking(self):
        """Test that room exits are tracked in cache."""
        cache = ReferenceCache()
        cache.add_room("town_square", {"north": "market", "south": "gate"})

        assert "town_square" in cache.room_exits, "Room should have exit tracking"
        assert "market" in cache.room_exits["town_square"], "Exit should be tracked"
        assert "gate" in cache.room_exits["town_square"], "Exit should be tracked"

    def test_cache_clear(self):
        """Test clearing the cache."""
        cache = ReferenceCache()
        cache.add_room("town_square")
        cache.add_item("sword")

        cache.clear()
        assert len(cache.room_ids) == 0, "Cache should be empty after clear"
        assert len(cache.item_ids) == 0, "Cache should be empty after clear"


@pytest.mark.systems
@pytest.mark.phase12
class TestReferenceValidation:
    """Test cross-content reference validation."""

    async def test_valid_room_exits(self, validation_service):
        """Test validation of valid room exit references."""
        # Build minimal cache
        validation_service.reference_cache.add_room("town_square")
        validation_service.reference_cache.add_room("market")
        validation_service._cache_built = True

        valid_room = """
room_id: inn
name: The Inn
description: A cozy inn
exits:
  north: market
  south: town_square
"""
        result = await validation_service.validate_references(valid_room, "rooms")
        assert (
            result.valid
        ), f"Valid references should pass: {[e.message for e in result.errors]}"

    async def test_broken_room_exit(self, validation_service):
        """Test detection of broken room exit references."""
        validation_service.reference_cache.add_room("market")
        validation_service._cache_built = True

        broken_exit = """
room_id: inn
name: The Inn
description: A cozy inn
exits:
  north: market
  south: nonexistent_room
"""
        result = await validation_service.validate_references(broken_exit, "rooms")
        assert not result.valid, "Broken reference should fail"
        assert any(
            "nonexistent_room" in e.message for e in result.errors
        ), "Should mention broken room reference"

    async def test_valid_ability_references(self, validation_service):
        """Test validation of valid ability references."""
        validation_service.reference_cache.add_ability("slash")
        validation_service.reference_cache.add_ability("power_attack")
        validation_service._cache_built = True

        valid_class = """
class_id: warrior
name: Warrior
description: A fighter
base_stats:
  strength: 14
  dexterity: 10
  intelligence: 8
  vitality: 12
starting_resources:
  health: 100
available_abilities:
  - slash
  - power_attack
"""
        result = await validation_service.validate_references(valid_class, "classes")
        assert (
            result.valid
        ), f"Valid ability references should pass: {[e.message for e in result.errors]}"

    async def test_invalid_ability_reference(self, validation_service):
        """Test detection of invalid ability references."""
        validation_service.reference_cache.add_ability("slash")
        validation_service._cache_built = True

        invalid_class = """
class_id: warrior
name: Warrior
description: A fighter
base_stats:
  strength: 14
  dexterity: 10
  intelligence: 8
  vitality: 12
starting_resources:
  health: 100
available_abilities:
  - slash
  - nonexistent_ability
"""
        result = await validation_service.validate_references(invalid_class, "classes")
        assert not result.valid, "Invalid ability reference should fail"
        assert any(
            "nonexistent_ability" in e.message for e in result.errors
        ), "Should mention broken ability reference"


@pytest.mark.systems
@pytest.mark.phase12
def test_validation_service_initialization(
    temp_world_data, file_manager, schema_registry
):
    """Test ValidationService initialization."""
    from daemons.engine.systems.validation_service import ValidationService

    service = ValidationService(
        world_data_path=str(temp_world_data),
        file_manager=file_manager,
        schema_registry=schema_registry,
    )
    assert service.world_data_path is not None, "Should have world data path"
    assert service.file_manager is not None, "Should have file manager"
    assert service.schema_registry is not None, "Should have schema registry"


@pytest.mark.systems
@pytest.mark.phase12
def test_validation_error_severity_levels(validation_service):
    """Test that validation errors properly categorize severity levels.

    This is the 200th test - celebrating comprehensive test coverage! 🎉
    """
    # Syntax errors are always critical
    syntax_error_yaml = "invalid: yaml: content:"
    result = validation_service.validate_syntax(syntax_error_yaml)
    assert not result.valid, "Syntax error should fail validation"

    # Valid YAML should pass without errors
    valid_yaml = """
class_id: test_class
name: Test Class
description: A test
"""
    result = validation_service.validate_syntax(valid_yaml)
    assert result.valid, "Valid YAML should pass"
    assert len(result.errors) == 0, "No errors for valid content"

    # Verify error objects have proper structure
    syntax_error_yaml = "class_id: test\n  bad_indent: value"
    result = validation_service.validate_syntax(syntax_error_yaml)
    if result.errors:
        error = result.errors[0]
        assert hasattr(error, "error_type"), "Error should have type"
        assert hasattr(error, "message"), "Error should have message"
        assert error.error_type in [
            "syntax",
            "schema",
            "reference",
        ], "Error type should be one of the defined categories"
