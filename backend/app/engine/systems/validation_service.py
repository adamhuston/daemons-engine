"""
Validation Service System for Phase 12.3

Provides comprehensive YAML validation with detailed error reporting:
- Syntax validation with line/column error positions
- Schema conformance checking against _schema.yaml definitions
- Reference validation for cross-content links
- Real-time validation feedback for CMS Monaco editor
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml


@dataclass
class ValidationError:
    """A validation error with precise location information."""

    severity: str  # "error" or "warning"
    message: str  # Human-readable error description
    line: Optional[int] = None  # Line number (1-indexed)
    column: Optional[int] = None  # Column number (1-indexed)
    field_path: Optional[str] = None  # Field path (e.g., "base_stats.strength")
    error_type: str = "validation"  # "syntax", "schema", "reference", "validation"
    suggestion: Optional[str] = None  # Helpful fix suggestion


@dataclass
class ValidationWarning:
    """A validation warning (non-blocking issues)."""

    message: str  # Human-readable warning description
    line: Optional[int] = None  # Line number (1-indexed)
    column: Optional[int] = None  # Column number (1-indexed)
    field_path: Optional[str] = None  # Field path
    warning_type: str = "general"  # "deprecated", "style", "performance", "general"
    suggestion: Optional[str] = None  # Helpful improvement suggestion


@dataclass
class ValidationResult:
    """Complete validation result with errors and warnings."""

    valid: bool  # True if no errors (warnings are ok)
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)
    content_type: Optional[str] = None  # Content category
    file_path: Optional[str] = None  # File being validated

    def add_error(
        self,
        message: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
        field_path: Optional[str] = None,
        error_type: str = "validation",
        suggestion: Optional[str] = None,
    ):
        """Add a validation error."""
        self.errors.append(
            ValidationError(
                severity="error",
                message=message,
                line=line,
                column=column,
                field_path=field_path,
                error_type=error_type,
                suggestion=suggestion,
            )
        )
        self.valid = False

    def add_warning(
        self,
        message: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
        field_path: Optional[str] = None,
        warning_type: str = "general",
        suggestion: Optional[str] = None,
    ):
        """Add a validation warning."""
        self.warnings.append(
            ValidationWarning(
                message=message,
                line=line,
                column=column,
                field_path=field_path,
                warning_type=warning_type,
                suggestion=suggestion,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API-friendly dict."""
        return {
            "valid": self.valid,
            "errors": [
                {
                    "severity": e.severity,
                    "message": e.message,
                    "line": e.line,
                    "column": e.column,
                    "field_path": e.field_path,
                    "error_type": e.error_type,
                    "suggestion": e.suggestion,
                }
                for e in self.errors
            ],
            "warnings": [
                {
                    "message": w.message,
                    "line": w.line,
                    "column": w.column,
                    "field_path": w.field_path,
                    "warning_type": w.warning_type,
                    "suggestion": w.suggestion,
                }
                for w in self.warnings
            ],
            "content_type": self.content_type,
            "file_path": self.file_path,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


class ReferenceCache:
    """
    Indexes all content IDs for fast reference validation.

    Caches:
    - Room IDs, area IDs, exit destinations
    - Item IDs, NPC IDs, ability IDs
    - Quest IDs, dialogue IDs, faction IDs
    - Any other cross-content references
    """

    def __init__(self):
        self.room_ids: Set[str] = set()
        self.area_ids: Set[str] = set()
        self.item_ids: Set[str] = set()
        self.npc_ids: Set[str] = set()
        self.ability_ids: Set[str] = set()
        self.quest_ids: Set[str] = set()
        self.dialogue_ids: Set[str] = set()
        self.faction_ids: Set[str] = set()
        self.class_ids: Set[str] = set()
        self.trigger_ids: Set[str] = set()
        self.quest_chain_ids: Set[str] = set()

        # Track which rooms have which exits for bidirectional validation
        self.room_exits: Dict[str, Set[str]] = {}  # room_id -> set of exit destinations

    def add_room(self, room_id: str, exits: Optional[Dict[str, str]] = None):
        """Register a room and its exits."""
        self.room_ids.add(room_id)
        if exits:
            self.room_exits[room_id] = set(exits.values())

    def add_area(self, area_id: str):
        """Register an area."""
        self.area_ids.add(area_id)

    def add_item(self, item_id: str):
        """Register an item."""
        self.item_ids.add(item_id)

    def add_npc(self, npc_id: str):
        """Register an NPC."""
        self.npc_ids.add(npc_id)

    def add_ability(self, ability_id: str):
        """Register an ability."""
        self.ability_ids.add(ability_id)

    def add_quest(self, quest_id: str):
        """Register a quest."""
        self.quest_ids.add(quest_id)

    def add_dialogue(self, dialogue_id: str):
        """Register a dialogue."""
        self.dialogue_ids.add(dialogue_id)

    def add_faction(self, faction_id: str):
        """Register a faction."""
        self.faction_ids.add(faction_id)

    def add_class(self, class_id: str):
        """Register a class."""
        self.class_ids.add(class_id)

    def add_trigger(self, trigger_id: str):
        """Register a trigger."""
        self.trigger_ids.add(trigger_id)

    def add_quest_chain(self, quest_chain_id: str):
        """Register a quest chain."""
        self.quest_chain_ids.add(quest_chain_id)

    def clear(self):
        """Clear all cached references."""
        self.room_ids.clear()
        self.area_ids.clear()
        self.item_ids.clear()
        self.npc_ids.clear()
        self.ability_ids.clear()
        self.quest_ids.clear()
        self.dialogue_ids.clear()
        self.faction_ids.clear()
        self.class_ids.clear()
        self.trigger_ids.clear()
        self.quest_chain_ids.clear()
        self.room_exits.clear()


class ValidationService:
    """
    Comprehensive YAML validation service for CMS integration.

    Provides:
    1. Syntax validation - Parse YAML and extract line/column errors
    2. Schema conformance - Check required fields and types
    3. Reference validation - Check cross-content links (exits, items, NPCs, etc.)
    4. Real-time feedback - Return errors with precise locations for Monaco editor
    """

    def __init__(self, world_data_path: str, schema_registry=None, file_manager=None):
        """
        Initialize the validation service.

        Args:
            world_data_path: Path to world_data directory
            schema_registry: Optional SchemaRegistry instance for schema lookups
            file_manager: Optional FileManager instance for file operations
        """
        self.world_data_path = Path(world_data_path)
        self.schema_registry = schema_registry
        self.file_manager = file_manager
        self.reference_cache = ReferenceCache()
        self._cache_built = False

    def validate_syntax(self, yaml_content: str) -> ValidationResult:
        """
        Validate YAML syntax and extract precise error locations.

        Args:
            yaml_content: Raw YAML string to validate

        Returns:
            ValidationResult with syntax errors (if any)
        """
        result = ValidationResult(valid=True)

        try:
            yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            # Extract line/column from YAML error
            line = None
            column = None

            if hasattr(e, "problem_mark"):
                mark = e.problem_mark
                line = mark.line + 1  # YAML uses 0-indexed lines
                column = mark.column + 1  # YAML uses 0-indexed columns

            # Build helpful error message
            message = str(e.problem) if hasattr(e, "problem") else str(e)

            # Add context from problem_mark
            context = ""
            if hasattr(e, "context"):
                context = f" ({e.context})"

            result.add_error(
                message=f"YAML syntax error: {message}{context}",
                line=line,
                column=column,
                error_type="syntax",
                suggestion="Check YAML indentation and special characters",
            )

        return result

    def validate_schema(self, yaml_content: str, content_type: str) -> ValidationResult:
        """
        Validate YAML content against schema definition.

        Args:
            yaml_content: Raw YAML string to validate
            content_type: Content category (e.g., "classes", "items", "rooms")

        Returns:
            ValidationResult with schema conformance errors (if any)
        """
        result = ValidationResult(valid=True, content_type=content_type)

        # First check syntax
        syntax_result = self.validate_syntax(yaml_content)
        if not syntax_result.valid:
            return syntax_result

        # Parse YAML
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError:
            # Should not happen since we already validated syntax
            result.add_error("Failed to parse YAML", error_type="syntax")
            return result

        if data is None:
            result.add_error("Empty YAML file", error_type="schema")
            return result

        # Do basic required field validation regardless of schema registry
        result = self._validate_required_fields(data, content_type, result)

        # Get schema if available for additional validation
        if not self.schema_registry:
            result.add_warning(
                "Schema registry not available - using basic field validation only",
                warning_type="general",
            )
            return result

        schema_info = self.schema_registry.get_schema(content_type)
        if not schema_info:
            result.add_warning(
                f"No schema found for content type '{content_type}' - using basic field validation only",
                warning_type="general",
            )

        return result

    def _validate_required_fields(
        self, data: Dict[str, Any], content_type: str, result: ValidationResult
    ) -> ValidationResult:
        """
        Validate required fields based on content type.

        Args:
            data: Parsed YAML data
            content_type: Content category
            result: ValidationResult to append errors to

        Returns:
            Updated ValidationResult
        """
        # Define required fields per content type
        required_fields = {
            "classes": [
                "class_id",
                "name",
                "description",
                "base_stats",
                "starting_resources",
            ],
            "items": ["item_id", "name", "description", "type"],
            "rooms": ["room_id", "name", "description"],
            "npcs": ["npc_id", "name", "description"],
            "abilities": ["ability_id", "name", "description"],
            "quests": ["quest_id", "name", "description"],
            "areas": ["area_id", "name", "description"],
            "dialogues": ["dialogue_id", "name"],
            "factions": ["faction_id", "name", "description"],
            "triggers": ["trigger_id", "name", "event"],
            "quest_chains": ["quest_chain_id", "name", "quests"],
        }

        if content_type not in required_fields:
            return result

        # Check each required field
        for field_name in required_fields[content_type]:
            if field_name not in data:
                result.add_error(
                    message=f"Missing required field: '{field_name}'",
                    field_path=field_name,
                    error_type="schema",
                    suggestion=f"Add '{field_name}' field to the YAML file",
                )
            elif data[field_name] is None or (
                isinstance(data[field_name], str) and not data[field_name].strip()
            ):
                result.add_error(
                    message=f"Required field '{field_name}' is empty",
                    field_path=field_name,
                    error_type="schema",
                    suggestion=f"Provide a value for '{field_name}'",
                )

        # Type-specific validation
        if content_type == "classes":
            result = self._validate_class_fields(data, result)
        elif content_type == "rooms":
            result = self._validate_room_fields(data, result)
        elif content_type == "items":
            result = self._validate_item_fields(data, result)

        return result

    def _validate_class_fields(
        self, data: Dict[str, Any], result: ValidationResult
    ) -> ValidationResult:
        """Validate class-specific fields."""
        # Check base_stats structure
        if "base_stats" in data and isinstance(data["base_stats"], dict):
            required_stats = ["strength", "dexterity", "intelligence", "vitality"]
            for stat in required_stats:
                if stat not in data["base_stats"]:
                    result.add_error(
                        message=f"Missing required stat: '{stat}' in base_stats",
                        field_path=f"base_stats.{stat}",
                        error_type="schema",
                    )
                elif not isinstance(data["base_stats"][stat], (int, float)):
                    result.add_error(
                        message=f"Stat '{stat}' must be a number",
                        field_path=f"base_stats.{stat}",
                        error_type="schema",
                    )

        # Check starting_resources
        if "starting_resources" in data and isinstance(
            data["starting_resources"], dict
        ):
            if not data["starting_resources"]:
                result.add_error(
                    message="starting_resources cannot be empty",
                    field_path="starting_resources",
                    error_type="schema",
                )

        return result

    def _validate_room_fields(
        self, data: Dict[str, Any], result: ValidationResult
    ) -> ValidationResult:
        """Validate room-specific fields."""
        # Exits should be a dict with direction -> room_id
        if "exits" in data:
            if not isinstance(data["exits"], dict):
                result.add_error(
                    message="exits must be a dictionary",
                    field_path="exits",
                    error_type="schema",
                )

        return result

    def _validate_item_fields(
        self, data: Dict[str, Any], result: ValidationResult
    ) -> ValidationResult:
        """Validate item-specific fields."""
        # Type should be valid
        valid_types = [
            "weapon",
            "armor",
            "consumable",
            "quest_item",
            "material",
            "container",
        ]
        if "type" in data and data["type"] not in valid_types:
            result.add_warning(
                message=f"Unknown item type '{data['type']}'. Valid types: {', '.join(valid_types)}",
                field_path="type",
                warning_type="style",
            )

        return result

    async def validate_references(
        self, yaml_content: str, content_type: str
    ) -> ValidationResult:
        """
        Validate cross-content references (room exits, item IDs, NPC IDs, etc.).

        Args:
            yaml_content: Raw YAML string to validate
            content_type: Content category

        Returns:
            ValidationResult with broken reference errors (if any)
        """
        result = ValidationResult(valid=True, content_type=content_type)

        # First validate syntax and schema
        syntax_result = self.validate_syntax(yaml_content)
        if not syntax_result.valid:
            return syntax_result

        # Parse YAML
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError:
            result.add_error("Failed to parse YAML", error_type="syntax")
            return result

        if data is None:
            return result

        # Build reference cache if not already built
        if not self._cache_built:
            await self.build_reference_cache()

        # Validate references based on content type
        if content_type == "rooms":
            result = self._validate_room_references(data, result)
        elif content_type == "npcs":
            result = self._validate_npc_references(data, result)
        elif content_type == "items":
            result = self._validate_item_references(data, result)
        elif content_type == "classes":
            result = self._validate_class_references(data, result)
        elif content_type == "quests":
            result = self._validate_quest_references(data, result)

        return result

    def _validate_room_references(
        self, data: Dict[str, Any], result: ValidationResult
    ) -> ValidationResult:
        """Validate room exit references."""
        if "exits" in data and isinstance(data["exits"], dict):
            for direction, destination in data["exits"].items():
                if destination not in self.reference_cache.room_ids:
                    result.add_error(
                        message=f"Exit '{direction}' points to non-existent room '{destination}'",
                        field_path=f"exits.{direction}",
                        error_type="reference",
                        suggestion=f"Create room '{destination}' or fix the exit destination",
                    )

        if "area_id" in data and data["area_id"]:
            if data["area_id"] not in self.reference_cache.area_ids:
                result.add_warning(
                    message=f"Room references non-existent area '{data['area_id']}'",
                    field_path="area_id",
                    warning_type="general",
                )

        return result

    def _validate_npc_references(
        self, data: Dict[str, Any], result: ValidationResult
    ) -> ValidationResult:
        """Validate NPC references to factions, dialogues, etc."""
        if "faction_id" in data and data["faction_id"]:
            if data["faction_id"] not in self.reference_cache.faction_ids:
                result.add_warning(
                    message=f"NPC references non-existent faction '{data['faction_id']}'",
                    field_path="faction_id",
                    warning_type="general",
                )

        if "dialogue_id" in data and data["dialogue_id"]:
            if data["dialogue_id"] not in self.reference_cache.dialogue_ids:
                result.add_warning(
                    message=f"NPC references non-existent dialogue '{data['dialogue_id']}'",
                    field_path="dialogue_id",
                    warning_type="general",
                )

        return result

    def _validate_item_references(
        self, data: Dict[str, Any], result: ValidationResult
    ) -> ValidationResult:
        """Validate item references."""
        # Items might reference other items (crafting materials, etc.)
        # This is content-type specific and would need more schema info
        return result

    def _validate_class_references(
        self, data: Dict[str, Any], result: ValidationResult
    ) -> ValidationResult:
        """Validate class ability references."""
        if "available_abilities" in data and isinstance(
            data["available_abilities"], list
        ):
            for ability_id in data["available_abilities"]:
                if ability_id not in self.reference_cache.ability_ids:
                    result.add_error(
                        message=f"Class references non-existent ability '{ability_id}'",
                        field_path="available_abilities",
                        error_type="reference",
                        suggestion=f"Create ability '{ability_id}' or remove from available_abilities",
                    )

        return result

    def _validate_quest_references(
        self, data: Dict[str, Any], result: ValidationResult
    ) -> ValidationResult:
        """Validate quest references to NPCs, items, etc."""
        # Quest validation would check objectives, rewards, etc.
        return result

    async def build_reference_cache(self):
        """
        Build reference cache by scanning all YAML files in world_data.

        This indexes all content IDs for fast validation lookups.
        """
        if not self.file_manager:
            return

        self.reference_cache.clear()

        # Get all YAML files
        files = await self.file_manager.list_files()

        for file_info in files:
            content_type = file_info.content_type

            try:
                # Read file content
                file_content = await self.file_manager.read_file(file_info.file_path)
                data = yaml.safe_load(file_content.content)

                if data is None:
                    continue

                # Index based on content type
                if content_type == "rooms" and "room_id" in data:
                    exits = data.get("exits", {})
                    self.reference_cache.add_room(data["room_id"], exits)
                elif content_type == "areas" and "area_id" in data:
                    self.reference_cache.add_area(data["area_id"])
                elif content_type == "items" and "item_id" in data:
                    self.reference_cache.add_item(data["item_id"])
                elif content_type == "npcs" and "npc_id" in data:
                    self.reference_cache.add_npc(data["npc_id"])
                elif content_type == "abilities" and "ability_id" in data:
                    self.reference_cache.add_ability(data["ability_id"])
                elif content_type == "quests" and "quest_id" in data:
                    self.reference_cache.add_quest(data["quest_id"])
                elif content_type == "dialogues" and "dialogue_id" in data:
                    self.reference_cache.add_dialogue(data["dialogue_id"])
                elif content_type == "factions" and "faction_id" in data:
                    self.reference_cache.add_faction(data["faction_id"])
                elif content_type == "classes" and "class_id" in data:
                    self.reference_cache.add_class(data["class_id"])
                elif content_type == "triggers" and "trigger_id" in data:
                    self.reference_cache.add_trigger(data["trigger_id"])
                elif content_type == "quest_chains" and "quest_chain_id" in data:
                    self.reference_cache.add_quest_chain(data["quest_chain_id"])

            except Exception:
                # Skip files that fail to parse
                continue

        self._cache_built = True

    async def validate_full(
        self, yaml_content: str, content_type: str, check_references: bool = True
    ) -> ValidationResult:
        """
        Perform complete validation: syntax + schema + references.

        Args:
            yaml_content: Raw YAML string to validate
            content_type: Content category
            check_references: Whether to validate cross-content references

        Returns:
            Complete ValidationResult
        """
        # Start with syntax validation
        result = self.validate_syntax(yaml_content)
        if not result.valid:
            result.content_type = content_type
            return result

        # Add schema validation
        schema_result = self.validate_schema(yaml_content, content_type)
        result.errors.extend(schema_result.errors)
        result.warnings.extend(schema_result.warnings)
        result.content_type = content_type

        if schema_result.errors:
            result.valid = False

        # Add reference validation if requested
        if check_references:
            ref_result = await self.validate_references(yaml_content, content_type)
            result.errors.extend(ref_result.errors)
            result.warnings.extend(ref_result.warnings)

            if ref_result.errors:
                result.valid = False

        return result
