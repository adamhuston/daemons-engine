"""
Phase 9: Character Classes & Abilities System - ClassSystem Runtime Manager

The ClassSystem manages:
1. Class templates (loaded from YAML)
2. Ability templates (loaded from YAML)
3. Behavior registration and retrieval
4. Hot-reload of content

This is the central hub for all class/ability data at runtime.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from daemons.engine.systems.abilities import (
    AbilityTemplate,
    ClassTemplate,
    load_abilities_from_yaml,
    load_classes_from_yaml,
)
from daemons.engine.systems.context import GameContext

logger = logging.getLogger(__name__)


class ClassSystem:
    """
    Runtime manager for character classes and abilities.

    Manages:
    - Class templates (in-memory cache of YAML definitions)
    - Ability templates (in-memory cache of YAML definitions)
    - Behavior registration (Python functions implementing ability logic)
    - Content hot-reload (re-import YAML without server restart)

    Single instance per game session, accessed via GameContext.
    """

    def __init__(self, context: GameContext):
        """
        Initialize ClassSystem.

        Args:
            context: GameContext providing access to world and other systems
        """
        self.context = context

        # Runtime caches
        self.class_templates: dict[str, ClassTemplate] = {}
        self.ability_templates: dict[str, AbilityTemplate] = {}

        # Behavior registry: behavior_id -> callable
        self.behavior_registry: dict[str, Callable] = {}

        logger.info("ClassSystem initialized")

    async def load_content(self, world_data_path: Path) -> None:
        """
        Load all class and ability definitions from YAML files.

        Called during engine startup. Reads YAML files and populates
        class_templates and ability_templates caches.

        Also calls _register_core_behaviors() to register built-in behaviors.

        Args:
            world_data_path: Path to world_data directory

        Raises:
            ValueError: If YAML is invalid or required fields are missing
        """
        logger.info(f"Loading class and ability content from {world_data_path}")

        # Load classes and abilities from YAML
        try:
            self.class_templates = await load_classes_from_yaml(
                world_data_path / "classes"
            )
            logger.info(f"Loaded {len(self.class_templates)} classes")
        except Exception as e:
            logger.error(f"Failed to load classes: {str(e)}")
            raise

        try:
            self.ability_templates = await load_abilities_from_yaml(
                world_data_path / "abilities"
            )
            logger.info(f"Loaded {len(self.ability_templates)} abilities")
        except Exception as e:
            logger.error(f"Failed to load abilities: {str(e)}")
            raise

        # Register built-in behaviors
        self._register_core_behaviors()

    def get_class(self, class_id: str) -> ClassTemplate | None:
        """
        Retrieve a class template by ID.

        Args:
            class_id: The class identifier (e.g., "warrior", "mage")

        Returns:
            ClassTemplate if found, None otherwise
        """
        return self.class_templates.get(class_id)

    def get_ability(self, ability_id: str) -> AbilityTemplate | None:
        """
        Retrieve an ability template by ID.

        Args:
            ability_id: The ability identifier (e.g., "slash", "fireball")

        Returns:
            AbilityTemplate if found, None otherwise
        """
        return self.ability_templates.get(ability_id)

    def register_behavior(self, behavior_id: str, handler: Callable) -> None:
        """
        Register a behavior function.

        Behaviors are Python functions that implement ability logic.
        They can be registered at startup (via _register_core_behaviors)
        or dynamically added later (via admin API or hot-reload).

        Args:
            behavior_id: Unique identifier for this behavior
            handler: Async callable that executes the behavior
        """
        self.behavior_registry[behavior_id] = handler
        logger.info(f"Registered behavior: {behavior_id}")

    def get_behavior(self, behavior_id: str) -> Callable | None:
        """
        Retrieve a registered behavior function by ID.

        Args:
            behavior_id: The behavior identifier

        Returns:
            Callable if found, None otherwise
        """
        return self.behavior_registry.get(behavior_id)

    def _register_core_behaviors(self) -> None:
        """
        Register built-in ability behaviors.

        Auto-discovers and registers all behaviors from the ability_behaviors package.
        Behaviors are discovered by inspecting all *_behavior functions in:
        - ability_behaviors.core
        - ability_behaviors.custom
        - ability_behaviors.utility

        This allows adding new behaviors without modifying this registration code.
        Just add a new async function ending in '_behavior' to any of those modules.
        """
        import inspect

        # Discover behaviors from all submodules
        behavior_count = 0

        # Import submodules
        from daemons.engine.systems.ability_behaviors import core, custom, utility

        for module in [core, custom, utility]:
            # Get all functions ending with '_behavior'
            for name, func in inspect.getmembers(module, inspect.isfunction):
                if name.endswith("_behavior") and inspect.iscoroutinefunction(func):
                    # Convert function name to behavior ID: "arcane_bolt_behavior" -> "arcane_bolt"
                    behavior_id = name.replace("_behavior", "")
                    self.register_behavior(behavior_id, func)
                    behavior_count += 1

        logger.info(f"Auto-registered {behavior_count} ability behaviors")

    def reload_behaviors(self) -> None:
        """
        Reload custom behaviors from custom.py module.

        Called by Phase 8 hot-reload system to update ability behaviors
        without restarting the server. This re-imports the custom behavior
        module and re-registers all custom behaviors.

        Used for iterating on custom ability implementations.

        Implementation details:
        - Unload old custom behaviors
        - Re-import ability_behaviors.custom module
        - Register new custom behaviors

        Deferred to Phase 9d.
        """
        # TODO Phase 9d: Implement custom behavior hot-reload
        logger.info("Custom behavior reload deferred to Phase 9d")

    # =========================================================================
    # Query Methods for Systems
    # =========================================================================

    def get_available_classes(self) -> dict[str, ClassTemplate]:
        """Get all loaded classes."""
        return dict(self.class_templates)

    def get_available_abilities(self) -> dict[str, AbilityTemplate]:
        """Get all loaded abilities."""
        return dict(self.ability_templates)

    def get_classes_for_player(self) -> list[str]:
        """
        Get list of playable classes.

        Returns:
            List of class IDs available for character creation
        """
        return sorted(self.class_templates.keys())

    def get_abilities_for_class(self, class_id: str) -> list[str]:
        """
        Get abilities available to a specific class.

        Args:
            class_id: The class identifier

        Returns:
            List of ability IDs available to this class
        """
        class_template = self.get_class(class_id)
        if not class_template:
            return []
        return class_template.available_abilities

    def get_abilities_at_level(self, class_id: str, level: int) -> list[str]:
        """
        Get abilities unlocked at a specific level.

        Returns abilities with required_level <= level.

        Args:
            class_id: The class identifier
            level: The character level

        Returns:
            List of ability IDs available at this level
        """
        class_template = self.get_class(class_id)
        if not class_template:
            return []

        abilities = []
        for ability_id in class_template.available_abilities:
            ability = self.get_ability(ability_id)
            if ability and ability.required_level <= level:
                abilities.append(ability_id)

        return sorted(abilities, key=lambda aid: self.get_ability(aid).required_level)

    def get_ability_slots_for_level(self, class_id: str, level: int) -> int:
        """
        Get number of equipped ability slots at a specific level.

        Args:
            class_id: The class identifier
            level: The character level

        Returns:
            Number of ability slots available at this level
        """
        class_template = self.get_class(class_id)
        if not class_template:
            return 0

        # ability_slots dict is {level: count}
        # Find the highest level slot count that applies
        available_slots = 0
        for slot_level in sorted(class_template.ability_slots.keys()):
            if slot_level <= level:
                available_slots = class_template.ability_slots[slot_level]

        return available_slots

    def validate_ability_for_class(self, ability_id: str, class_id: str) -> bool:
        """
        Check if an ability is valid for a class.

        Args:
            ability_id: The ability identifier
            class_id: The class identifier

        Returns:
            True if ability is available to class, False otherwise
        """
        ability = self.get_ability(ability_id)
        if not ability:
            return False

        class_template = self.get_class(class_id)
        if not class_template:
            return False

        # Check if ability is in this class's available list
        if ability_id not in class_template.available_abilities:
            return False

        # Check if ability is restricted to a different class
        if ability.required_class and ability.required_class != class_id:
            return False

        return True
