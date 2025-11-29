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
from pathlib import Path
from typing import Dict, Optional, Callable, Any
import asyncio

from app.engine.systems.abilities import (
    ClassTemplate,
    AbilityTemplate,
    load_classes_from_yaml,
    load_abilities_from_yaml,
)
from app.engine.systems.context import GameContext

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
        self.class_templates: Dict[str, ClassTemplate] = {}
        self.ability_templates: Dict[str, AbilityTemplate] = {}
        
        # Behavior registry: behavior_id -> callable
        self.behavior_registry: Dict[str, Callable] = {}
        
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
    
    def get_class(self, class_id: str) -> Optional[ClassTemplate]:
        """
        Retrieve a class template by ID.
        
        Args:
            class_id: The class identifier (e.g., "warrior", "mage")
            
        Returns:
            ClassTemplate if found, None otherwise
        """
        return self.class_templates.get(class_id)
    
    def get_ability(self, ability_id: str) -> Optional[AbilityTemplate]:
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
    
    def get_behavior(self, behavior_id: str) -> Optional[Callable]:
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
        
        Core behaviors (combat):
        - melee_attack: Basic physical attack
        - power_attack: High-damage attack (costs rage)
        - rally_passive: Passive defense buff
        - aoe_attack: Area damage
        - stun_effect: Crowd control effect
        - mana_regen: Resource restoration
        - fireball: Mage AoE spell
        - polymorph: Mage crowd control
        - backstab: Rogue single-target attack
        - evasion_passive: Rogue dodge buff
        - damage_boost: Temporary damage buff
        
        Custom behaviors (class-specific variants):
        - whirlwind_attack: Warrior AoE ability
        - shield_bash: Warrior defensive ability
        - inferno: Mage ultimate spell
        - arcane_missiles: Mage rapid-fire spell
        - shadow_clone: Rogue utility ability
        
        Utility behaviors (non-combat):
        - create_light: Create light source (personal or area)
        - darkness: Create darkness/shadow effect
        - unlock_door: Magically unlock doors
        - unlock_container: Open sealed containers
        - detect_magic: Sense magical auras
        - true_sight: Penetrate illusions
        - teleport: Transport to known location
        - create_passage: Open temporary wall passages
        """
        # Import all behaviors
        from app.engine.systems.ability_behaviors import (
            # Core behaviors
            melee_attack_behavior,
            power_attack_behavior,
            rally_passive_behavior,
            aoe_attack_behavior,
            stun_effect_behavior,
            mana_regen_behavior,
            fireball_behavior,
            polymorph_behavior,
            backstab_behavior,
            evasion_passive_behavior,
            damage_boost_behavior,
            # Custom behaviors
            whirlwind_attack_behavior,
            shield_bash_behavior,
            inferno_behavior,
            arcane_missiles_behavior,
            shadow_clone_behavior,
        )
        from app.engine.systems.ability_behaviors.utility import (
            create_light_behavior,
            darkness_behavior,
            unlock_door_behavior,
            unlock_container_behavior,
            detect_magic_behavior,
            true_sight_behavior,
            teleport_behavior,
            create_passage_behavior,
        )
        
        # Register core behaviors
        self.register_behavior("melee_attack", melee_attack_behavior)
        self.register_behavior("power_attack", power_attack_behavior)
        self.register_behavior("rally_passive", rally_passive_behavior)
        self.register_behavior("aoe_attack", aoe_attack_behavior)
        self.register_behavior("stun_effect", stun_effect_behavior)
        self.register_behavior("mana_regen", mana_regen_behavior)
        self.register_behavior("fireball", fireball_behavior)
        self.register_behavior("polymorph", polymorph_behavior)
        self.register_behavior("backstab", backstab_behavior)
        self.register_behavior("evasion_passive", evasion_passive_behavior)
        self.register_behavior("damage_boost", damage_boost_behavior)
        
        # Register custom behaviors
        self.register_behavior("whirlwind_attack", whirlwind_attack_behavior)
        self.register_behavior("shield_bash", shield_bash_behavior)
        self.register_behavior("inferno", inferno_behavior)
        self.register_behavior("arcane_missiles", arcane_missiles_behavior)
        self.register_behavior("shadow_clone", shadow_clone_behavior)
        
        # Register utility behaviors
        self.register_behavior("create_light", create_light_behavior)
        self.register_behavior("darkness", darkness_behavior)
        self.register_behavior("unlock_door", unlock_door_behavior)
        self.register_behavior("unlock_container", unlock_container_behavior)
        self.register_behavior("detect_magic", detect_magic_behavior)
        self.register_behavior("true_sight", true_sight_behavior)
        self.register_behavior("teleport", teleport_behavior)
        self.register_behavior("create_passage", create_passage_behavior)
        
        logger.info(f"Registered {len(self.behavior_registry)} ability behaviors")
    
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
    
    def get_available_classes(self) -> Dict[str, ClassTemplate]:
        """Get all loaded classes."""
        return dict(self.class_templates)
    
    def get_available_abilities(self) -> Dict[str, AbilityTemplate]:
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
