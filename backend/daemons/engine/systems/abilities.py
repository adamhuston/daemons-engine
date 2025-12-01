"""
Phase 9: Character Classes & Abilities System - Loaders, Templates, and Executor

This module provides:
1. ClassTemplate and AbilityTemplate dataclasses
2. YAML loaders for class and ability definitions
3. Validation and error handling for content loading
4. AbilityExecutor for ability validation, cooldown, and execution
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from daemons.engine.systems.context import GameContext
from daemons.engine.world import ResourceDef, StatGrowth, WorldEntity, WorldNpc

logger = logging.getLogger(__name__)


# =============================================================================
# Domain Models (ClassTemplate and AbilityTemplate)
# =============================================================================


@dataclass
class ClassTemplate:
    """
    Defines a playable character class.

    Loaded from YAML files in world_data/classes/
    """

    class_id: str  # "warrior", "mage", "rogue"
    name: str  # Display name
    description: str  # Flavor text

    # Base stats at level 1
    base_stats: dict[str, int]  # {"strength": 12, "dexterity": 10, ...}

    # Stat growth per level
    stat_growth: dict[str, StatGrowth]  # How each stat progresses

    # Starting resources at level 1
    starting_resources: dict[str, int]  # {"health": 100, "mana": 50}

    # Resource definitions for this class (regen rates, modifiers, etc.)
    resources: dict[str, ResourceDef]  # Overrides/adds resources

    # Abilities available to this class
    available_abilities: list[str]  # ["slash", "power_attack", "rally"]

    # Ability slots unlock per level
    ability_slots: dict[int, int]  # {1: 2, 5: 3, 10: 4} = slots at levels

    # Global cooldown (GCD) configuration per ability category
    gcd_config: dict[str, float] = field(default_factory=dict)
    # {"melee": 1.0, "spell": 1.5, "shared": 1.0}

    # Flavor/metadata
    icon: str | None = None
    keywords: list[str] = field(default_factory=list)


@dataclass
class AbilityTemplate:
    """
    Defines a usable ability.

    Loaded from YAML files in world_data/abilities/
    """

    ability_id: str  # "slash", "fireball", "heal"
    name: str  # Display name
    description: str  # Flavor text

    # Classification
    ability_type: str  # "active", "passive", "reactive"
    ability_category: str  # "melee", "ranged", "magic", "utility"

    # Cooldown mechanics
    cooldown: float  # Seconds between uses (personal cooldown)

    # Effect execution - supports behavior chaining!
    # Legacy: behavior_id for single behavior (backward compatible)
    # New: behaviors list for chaining multiple behaviors
    behavior_id: str | None = (
        None  # Legacy single behavior (converted to behaviors list)
    )
    behaviors: list[str] = field(
        default_factory=list
    )  # Behavior chain: ["melee_attack", "stun_effect"]

    # Targeting (base defaults)
    target_type: str = "self"  # "self", "enemy", "ally", "room"
    target_range: int = 0  # 0 = self, 1+ = distance (rooms)

    # Resource costs (e.g., {"mana": 30} or {"rage": 25})
    costs: dict[str, int] = field(default_factory=dict)

    # Execution requirements
    requires_target: bool = False
    requires_los: bool = False  # Line of sight
    can_use_while_moving: bool = False

    # Unlock condition
    required_level: int = 1  # Minimum level to learn
    required_class: str | None = None  # Restricted to specific class, or None for any

    # GCD category
    gcd_category: str | None = None  # GCD category: "melee", "spell", "shared"

    # Effects and scaling
    effects: list[str] = field(default_factory=list)  # Effect template IDs
    scaling: dict[str, float] = field(default_factory=dict)
    # {"strength": 1.2, "intelligence": 0.5, "level": 0.1}

    # UI/flavor
    icon: str | None = None
    animation: str | None = None
    sound: str | None = None
    keywords: list[str] = field(default_factory=list)

    # Ability-specific metadata (used by behaviors)
    metadata: dict[str, Any] = field(default_factory=dict)
    # For utility abilities: {"duration": 300.0, "light_level": 50, "radius": 1}
    # For combat: {"stun_duration": 2.0, "damage_boost": 1.5}

    # Spellcasting requirements (optional, for games with magic systems)
    # Example: {"requires_focus": true, "requires_incantation": true, "focus_item": "wand"}
    # Future: validation logic can check these before allowing execution
    spellcasting_requirements: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# YAML Loaders
# =============================================================================


async def load_classes_from_yaml(path: Path) -> dict[str, ClassTemplate]:
    """
    Load all class definitions from YAML files.

    Args:
        path: Path to directory containing class YAML files (e.g., world_data/classes/)

    Returns:
        Dict mapping class_id -> ClassTemplate

    Raises:
        FileNotFoundError: If path doesn't exist
        yaml.YAMLError: If YAML is malformed
        ValueError: If class data is invalid
    """
    classes = {}

    if not path.exists():
        logger.warning(f"Classes directory does not exist: {path}")
        return classes

    for yaml_file in sorted(path.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            # Skip schema/documentation files
            continue

        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)

            if not data:
                logger.warning(f"Empty YAML file: {yaml_file}")
                continue

            # Convert stat_growth dicts to StatGrowth objects
            if "stat_growth" in data:
                stat_growth = {}
                for stat_name, growth_data in data["stat_growth"].items():
                    stat_growth[stat_name] = StatGrowth(
                        per_level=growth_data.get("per_level", 0),
                        per_milestone=growth_data.get("per_milestone", {}),
                    )
                data["stat_growth"] = stat_growth

            # Convert resources dicts to ResourceDef objects
            if "resources" in data:
                resources = {}
                for resource_id, resource_data in data["resources"].items():
                    resources[resource_id] = ResourceDef(
                        resource_id=resource_data.get("resource_id", resource_id),
                        name=resource_data.get("name", resource_id.title()),
                        description=resource_data.get("description", ""),
                        max_amount=resource_data.get("max_amount", 100),
                        regen_rate=resource_data.get("regen_rate", 1.0),
                        regen_type=resource_data.get("regen_type", "passive"),
                        regen_modifiers=resource_data.get("regen_modifiers", {}),
                        color=resource_data.get("color", "#FFFFFF"),
                    )
                data["resources"] = resources

            class_template = ClassTemplate(**data)
            classes[class_template.class_id] = class_template
            logger.info(
                f"Loaded class: {class_template.class_id} ({class_template.name})"
            )

        except (yaml.YAMLError, KeyError, TypeError) as e:
            logger.error(f"Error loading class from {yaml_file}: {str(e)}")
            raise ValueError(f"Invalid class definition in {yaml_file.name}: {str(e)}")

    if not classes:
        logger.warning(f"No classes loaded from {path}")

    return classes


async def load_abilities_from_yaml(path: Path) -> dict[str, AbilityTemplate]:
    """
    Load all ability definitions from YAML files.

    Each YAML file can contain multiple abilities under an "abilities" key.

    Args:
        path: Path to directory containing ability YAML files (e.g., world_data/abilities/)

    Returns:
        Dict mapping ability_id -> AbilityTemplate

    Raises:
        FileNotFoundError: If path doesn't exist
        yaml.YAMLError: If YAML is malformed
        ValueError: If ability data is invalid
    """
    abilities = {}

    if not path.exists():
        logger.warning(f"Abilities directory does not exist: {path}")
        return abilities

    for yaml_file in sorted(path.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            # Skip schema/documentation files
            continue

        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)

            if not data:
                logger.warning(f"Empty YAML file: {yaml_file}")
                continue

            # Each YAML file contains an "abilities" list
            ability_list = data.get("abilities", [])

            if not ability_list:
                logger.warning(f"No abilities defined in {yaml_file.name}")
                continue

            for ability_data in ability_list:
                try:
                    # Handle backward compatibility: convert behavior_id to behaviors list
                    if (
                        "behavior_id" in ability_data
                        and "behaviors" not in ability_data
                    ):
                        # Legacy format: single behavior_id
                        behavior_id = ability_data.pop("behavior_id")
                        ability_data["behaviors"] = [behavior_id]
                        logger.debug(
                            f"Converting legacy behavior_id '{behavior_id}' to behaviors list "
                            f"for {ability_data.get('ability_id', 'unknown')}"
                        )
                    elif "behaviors" in ability_data:
                        # New format: behaviors list already present
                        # Remove behavior_id if present to avoid confusion
                        ability_data.pop("behavior_id", None)

                    ability = AbilityTemplate(**ability_data)

                    # Validate that behaviors list is not empty
                    if not ability.behaviors:
                        logger.error(
                            f"Ability {ability.ability_id} has no behaviors defined. "
                            f"Must have either behavior_id or behaviors field."
                        )
                        continue

                    # Check for duplicate IDs
                    if ability.ability_id in abilities:
                        logger.warning(
                            f"Duplicate ability ID: {ability.ability_id} "
                            f"(in {yaml_file.name}, also exists elsewhere)"
                        )

                    abilities[ability.ability_id] = ability
                    behavior_info = (
                        " -> ".join(ability.behaviors)
                        if len(ability.behaviors) > 1
                        else ability.behaviors[0]
                    )
                    logger.info(
                        f"Loaded ability: {ability.ability_id} ({ability.name}) - behaviors: {behavior_info}"
                    )

                except (KeyError, TypeError) as e:
                    logger.error(
                        f"Error loading ability from {yaml_file.name}: {str(e)}"
                    )
                    raise ValueError(
                        f"Invalid ability definition in {yaml_file.name}: {str(e)}"
                    )

        except yaml.YAMLError as e:
            logger.error(f"YAML error in {yaml_file}: {str(e)}")
            raise ValueError(f"Invalid YAML in {yaml_file.name}: {str(e)}")

    if not abilities:
        logger.warning(f"No abilities loaded from {path}")

    return abilities


# =============================================================================
# AbilityExecutor - Validates and Executes Abilities
# =============================================================================


@dataclass
class AbilityExecutionResult:
    """Result of executing an ability."""

    success: bool
    ability_id: str
    caster_id: str
    message: str
    error: str | None = None
    damage_dealt: int = 0
    targets_hit: list[str] = field(default_factory=list)
    effects_applied: list[str] = field(default_factory=list)
    cooldown_applied: float = 0.0


class AbilityExecutor:
    """
    Validates and executes abilities.

    Responsibilities:
    1. Validate ability use (learned, level, resources, cooldown)
    2. Resolve targets based on ability's target_type
    3. Apply cooldowns (personal + GCD)
    4. Retrieve and call behavior function
    5. Return standardized result

    Single instance per game session, accessed via GameContext.
    """

    def __init__(self, context: GameContext):
        """
        Initialize AbilityExecutor.

        Args:
            context: GameContext providing access to world, class_system, etc.
        """
        self.context = context

        # Cooldown tracking: {player_id: {ability_id: (cooldown_end_time, is_personal)}}
        self.cooldowns: dict[str, dict[str, tuple[float, bool]]] = {}

        # GCD tracking: {player_id: (gcd_end_time, category)}
        self.gcd_state: dict[str, tuple[float, str]] = {}

        logger.info("AbilityExecutor initialized")

    async def execute_ability(
        self,
        caster: WorldEntity,
        ability_id: str,
        target_id: str | None = None,
        target_entity: WorldEntity | None = None,
    ) -> AbilityExecutionResult:
        """
        Execute an ability.

        Main entry point for ability execution. Validates, resolves targets,
        applies cooldowns, and calls the behavior function.

        Phase 14.2: Now accepts any WorldEntity (players, NPCs, items) as caster.

        Args:
            caster: The entity casting the ability (player, NPC, or item)
            ability_id: The ability to cast
            target_id: Optional target ID (overrides target resolution)
            target_entity: Optional target entity (for passed-in targets)

        Returns:
            AbilityExecutionResult with success status and details
        """
        try:
            # 1. Validate ability use
            validation_error = self._validate_ability_use(caster, ability_id)
            if validation_error:
                # Emit ability_error event
                error_event = self.context.event_dispatcher.ability_error(
                    caster.id, ability_id, ability_id, validation_error
                )
                await self.context.event_dispatcher.dispatch([error_event])

                return AbilityExecutionResult(
                    success=False,
                    ability_id=ability_id,
                    caster_id=caster.id,
                    message="",
                    error=validation_error,
                )

            # Get ability template from ClassSystem
            ability = self.context.class_system.get_ability(ability_id)
            if not ability:
                error_msg = f"Unknown ability: {ability_id}"
                error_event = self.context.event_dispatcher.ability_error(
                    caster.id, ability_id, ability_id, error_msg
                )
                await self.context.event_dispatcher.dispatch([error_event])

                return AbilityExecutionResult(
                    success=False,
                    ability_id=ability_id,
                    caster_id=caster.id,
                    message="",
                    error=error_msg,
                )

            # 2. Resolve targets
            targets = self._resolve_targets(caster, ability, target_id, target_entity)
            if ability.requires_target and not targets:
                error_msg = "No valid target found"
                error_event = self.context.event_dispatcher.ability_error(
                    caster.id, ability_id, ability.name, error_msg
                )
                await self.context.event_dispatcher.dispatch([error_event])

                return AbilityExecutionResult(
                    success=False,
                    ability_id=ability_id,
                    caster_id=caster.id,
                    message="",
                    error=error_msg,
                )

            # Emit ability_cast event (cast has started)
            target_ids = [t.id for t in targets] if targets else []
            entity_type = "npc" if isinstance(caster, WorldNpc) else "player"
            cast_event = self.context.event_dispatcher.ability_cast(
                caster.id, ability_id, ability.name, target_ids, entity_type=entity_type
            )
            await self.context.event_dispatcher.dispatch([cast_event])

            # 3. Apply resource costs
            if ability.costs:
                resource_events = []
                for resource_id, cost in ability.costs.items():
                    pool = caster.get_resource_pool(resource_id)
                    if pool:
                        pool.current -= cost
                        logger.info(
                            f"{caster.name} spent {cost} {resource_id} "
                            f"({pool.current} remaining)"
                        )
                        # Create resource_update event
                        resources_payload = {}
                        for rid in (
                            caster.character_sheet.resource_pools.keys()
                            if caster.character_sheet
                            else []
                        ):
                            rpool = caster.get_resource_pool(rid)
                            if rpool:
                                resources_payload[rid] = {
                                    "current": rpool.current,
                                    "max": rpool.max,
                                    "percent": (
                                        (rpool.current / rpool.max * 100)
                                        if rpool.max > 0
                                        else 0
                                    ),
                                }
                        if resources_payload:
                            resource_event = (
                                self.context.event_dispatcher.resource_update(
                                    caster.id, resources_payload
                                )
                            )
                            resource_events.append(resource_event)

                if resource_events:
                    await self.context.event_dispatcher.dispatch(resource_events)

            # 4. Execute behavior chain
            # Support both single behavior and multi-behavior chains
            behavior_results = []
            combined_targets_hit = set()
            combined_damage = 0
            combined_effects = []
            combined_messages = []

            for behavior_id in ability.behaviors:
                behavior_fn = self.context.class_system.get_behavior(behavior_id)
                if not behavior_fn:
                    error_msg = f"No behavior found in chain: {behavior_id}"
                    logger.error(f"Behavior chain error for {ability_id}: {error_msg}")
                    error_event = self.context.event_dispatcher.ability_error(
                        caster.id, ability_id, ability.name, error_msg
                    )
                    await self.context.event_dispatcher.dispatch([error_event])

                    return AbilityExecutionResult(
                        success=False,
                        ability_id=ability_id,
                        caster_id=caster.id,
                        message="",
                        error=error_msg,
                    )

                # Execute this behavior in the chain
                if targets:
                    # Pass multiple targets for AoE, single target otherwise
                    if len(targets) > 1 or ability.target_type == "room":
                        behavior_result = await behavior_fn(
                            caster, targets, ability, self.context.combat_system
                        )
                    else:
                        behavior_result = await behavior_fn(
                            caster, targets[0], ability, self.context.combat_system
                        )
                else:
                    # No targets (self or area effect)
                    behavior_result = await behavior_fn(
                        caster, caster, ability, self.context.combat_system
                    )

                # Collect results from this behavior
                if not behavior_result.success:
                    # If any behavior in the chain fails, abort
                    logger.warning(
                        f"Behavior {behavior_id} failed in chain for {ability_id}: {behavior_result.error}"
                    )
                    error_event = self.context.event_dispatcher.ability_error(
                        caster.id,
                        ability_id,
                        ability.name,
                        behavior_result.error or "Behavior failed",
                    )
                    await self.context.event_dispatcher.dispatch([error_event])

                    return AbilityExecutionResult(
                        success=False,
                        ability_id=ability_id,
                        caster_id=caster.id,
                        message="",
                        error=behavior_result.error,
                    )

                behavior_results.append(behavior_result)

                # Aggregate results from all behaviors in chain
                if behavior_result.targets_hit:
                    combined_targets_hit.update(behavior_result.targets_hit)
                if behavior_result.damage_dealt:
                    combined_damage += behavior_result.damage_dealt
                if behavior_result.effects_applied:
                    combined_effects.extend(behavior_result.effects_applied)
                if behavior_result.message:
                    combined_messages.append(behavior_result.message)

            # Combine all behavior results into final result
            behavior_result = behavior_results[0]  # Use first result as base
            behavior_result.targets_hit = list(combined_targets_hit)
            behavior_result.damage_dealt = combined_damage
            behavior_result.effects_applied = combined_effects
            behavior_result.message = (
                " ".join(combined_messages)
                if combined_messages
                else behavior_result.message
            )

            # 5. Check for target deaths and trigger retaliation after behavior chain execution
            death_events = []
            if targets and combined_damage > 0:
                for target in targets if isinstance(targets, list) else [targets]:
                    if not target.is_alive():
                        logger.info(
                            f"Target {target.name} killed by {ability_id} from {caster.name}"
                        )
                        target_death_events = (
                            await self.context.combat_system.handle_death(
                                target.id, caster.id
                            )
                        )
                        death_events.extend(target_death_events)

                        # Clear caster's combat state if target was their combat target
                        if (
                            hasattr(caster, "combat")
                            and caster.combat.target_id == target.id
                        ):
                            caster.combat.clear_combat()
                    else:
                        # Target survived - trigger retaliation/combat engagement
                        world = self.context.world

                        # If target is a player, make them auto-retaliate (if not already in combat)
                        if target.id in world.players:
                            if (
                                hasattr(target, "combat")
                                and not target.combat.is_in_combat()
                            ):
                                try:
                                    retaliation_events = (
                                        self.context.combat_system.start_attack_entity(
                                            target.id, caster.id
                                        )
                                    )
                                    if retaliation_events:
                                        await self.context.event_dispatcher.dispatch(
                                            retaliation_events
                                        )
                                except Exception as e:
                                    logger.warning(f"Player retaliation failed: {e}")

                        # If target is an NPC, trigger engine hooks so AI behaviors can respond
                        elif target.id in world.npcs and self.context.engine:
                            await self.context.engine._trigger_npc_combat_start(
                                target.id, caster.id
                            )

            # 6. Apply cooldowns
            self._apply_cooldowns(caster, ability)

            # Emit cooldown_update event
            cooldown_remaining = self.get_ability_cooldown(caster.id, ability_id)
            cooldown_event = self.context.event_dispatcher.cooldown_update(
                caster.id, ability_id, cooldown_remaining
            )

            # Emit ability_cast_complete event
            complete_event = self.context.event_dispatcher.ability_cast_complete(
                caster.id,
                ability_id,
                ability.name,
                True,
                behavior_result.message,
                damage_dealt=behavior_result.damage_dealt,
                targets_hit=behavior_result.targets_hit,
                entity_type=entity_type,
            )

            # Dispatch ability completion events FIRST, then death events
            # This ensures the hit message appears before the death message
            await self.context.event_dispatcher.dispatch(
                [cooldown_event, complete_event]
            )

            # Dispatch death events after ability completion
            if death_events:
                await self.context.event_dispatcher.dispatch(death_events)

            logger.info(f"{caster.name} cast {ability_id}: {behavior_result.message}")

            return AbilityExecutionResult(
                success=True,
                ability_id=ability_id,
                caster_id=caster.id,
                message=behavior_result.message,
                damage_dealt=behavior_result.damage_dealt,
                targets_hit=behavior_result.targets_hit,
                effects_applied=behavior_result.effects_applied,
                cooldown_applied=behavior_result.cooldown_applied,
            )

        except Exception as e:
            logger.error(f"Error executing ability {ability_id}: {e}", exc_info=True)
            error_msg = f"Ability execution failed: {str(e)}"
            error_event = self.context.event_dispatcher.ability_error(
                caster.id, ability_id, ability_id, error_msg
            )
            try:
                await self.context.event_dispatcher.dispatch([error_event])
            except Exception as dispatch_err:
                logger.error(f"Failed to dispatch error event: {dispatch_err}")

            return AbilityExecutionResult(
                success=False,
                ability_id=ability_id,
                caster_id=caster.id,
                message="",
                error=error_msg,
            )

    def _validate_ability_use(self, caster: WorldEntity, ability_id: str) -> str | None:
        """
        Validate that an entity can use an ability.

        Phase 14.2: Now works with any WorldEntity (players, NPCs, items).

        Checks:
        - Entity has a character sheet (class chosen)
        - Ability is learned
        - Entity is high enough level
        - Entity has enough resources
        - Personal cooldown is ready
        - GCD is ready

        Args:
            caster: The entity attempting to cast (player, NPC, or item)
            ability_id: The ability ID

        Returns:
            Error message if validation fails, None if valid
        """
        # Check character sheet
        if not caster.has_character_sheet():
            return "You must choose a class first"

        # Check ability learned
        if ability_id not in caster.get_learned_abilities():
            return f"You haven't learned {ability_id}"

        # Get ability template
        ability = self.context.class_system.get_ability(ability_id)
        if not ability:
            return f"Unknown ability: {ability_id}"

        # Check level
        if caster.level < ability.required_level:
            return f"You must be level {ability.required_level} to use {ability_id}"

        # Check resources
        if ability.costs:
            for resource_id, cost in ability.costs.items():
                pool = caster.get_resource_pool(resource_id)
                if not pool or pool.current < cost:
                    return f"Not enough {resource_id} (need {cost}, have {pool.current if pool else 0})"

        # Check personal cooldown
        current_time = time.time()
        if caster.id in self.cooldowns:
            if ability_id in self.cooldowns[caster.id]:
                cooldown_end, is_personal = self.cooldowns[caster.id][ability_id]
                if current_time < cooldown_end:
                    remaining = cooldown_end - current_time
                    return f"{ability_id} is on cooldown for {remaining:.1f}s"

        # Check GCD
        if caster.id in self.gcd_state:
            gcd_end, category = self.gcd_state[caster.id]
            if current_time < gcd_end:
                # Check if this ability is in the same GCD category
                if ability.gcd_category == category:
                    remaining = gcd_end - current_time
                    return f"Global cooldown active for {remaining:.1f}s"

        # Check spellcasting requirements (hook for future magic systems)
        # Games can define requirements like focus items, incantations, etc.
        spellcasting_error = self._validate_spellcasting_requirements(caster, ability)
        if spellcasting_error:
            return spellcasting_error

        return None

    def _validate_spellcasting_requirements(
        self, caster: WorldEntity, ability: AbilityTemplate
    ) -> str | None:
        """
        Validate spellcasting-specific requirements for an ability.

        This hook allows game designers to define custom requirements for abilities
        that need special conditions beyond basic resource/cooldown checks.

        Possible requirements (defined in ability YAML):
        - requires_focus: bool - Requires a focus item equipped
        - focus_item: str - Specific item type required (e.g., "wand", "staff")
        - requires_incantation: bool - Requires verbal component (future: silence effects)
        - requires_somatic: bool - Requires hand gestures (future: restrained effects)
        - requires_material: str - Requires specific consumable item

        Args:
            caster: The entity attempting to cast
            ability: The ability template with spellcasting_requirements

        Returns:
            Error message if requirements not met, None if valid
        """
        requirements = ability.spellcasting_requirements
        if not requirements:
            return None

        # Future implementation examples:
        # if requirements.get("requires_focus"):
        #     focus_type = requirements.get("focus_item")
        #     if not self._has_focus_equipped(caster, focus_type):
        #         return f"You need a {focus_type or 'focus'} equipped to cast {ability.name}"
        #
        # if requirements.get("requires_incantation"):
        #     if caster.has_status_effect("silenced"):
        #         return f"You cannot speak the incantation while silenced"

        # Currently a no-op hook - extend this method to implement specific checks
        return None

    def _resolve_targets(
        self,
        caster: WorldEntity,
        ability: AbilityTemplate,
        target_id: str | None,
        target_entity: WorldEntity | None,
    ) -> list[WorldEntity]:
        """
        Resolve targets for an ability based on its target_type.

        Phase 14.2: Now works with any WorldEntity (players, NPCs, items) as caster.

        Target types:
        - "self": The caster
        - "enemy": A single enemy (requires target_id or target_entity)
        - "ally": A single ally (requires target_id or target_entity)
        - "room": All entities in the room

        Args:
            caster: The casting entity (player, NPC, or item)
            ability: The ability template
            target_id: Optional explicit target ID
            target_entity: Optional explicit target entity

        Returns:
            List of target entities (empty if no valid targets)
        """
        world = self.context.world
        caster_room = world.rooms.get(caster.room_id)
        if not caster_room:
            return []

        target_type = ability.target_type or "self"

        if target_type == "self":
            return [caster]

        elif target_type == "enemy":
            # Single enemy target
            if target_entity:
                return [target_entity]
            elif target_id:
                target = world.get_entity(target_id)
                if target and target.room_id == caster.room_id:
                    return [target]
            return []

        elif target_type == "ally":
            # Single ally target (including self)
            if target_entity:
                return [target_entity]
            elif target_id:
                target = world.get_entity(target_id)
                if target and target.room_id == caster.room_id:
                    return [target]
            return []

        elif target_type == "room":
            # All entities in room (typically enemies for combat abilities)
            targets = []
            for entity_id in caster_room.entity_ids:
                entity = world.get_entity(entity_id)
                if entity and entity.id != caster.id:
                    targets.append(entity)
            return targets

        return []

    def _apply_cooldowns(self, caster: WorldEntity, ability: AbilityTemplate) -> None:
        """
        Apply personal cooldown and GCD after ability execution.

        Phase 14.2: Now works with any WorldEntity (players, NPCs, items) as caster.

        Args:
            caster: The casting entity (player, NPC, or item)
            ability: The ability template
        """
        current_time = time.time()

        # Initialize cooldown tracking for this player if needed
        if caster.id not in self.cooldowns:
            self.cooldowns[caster.id] = {}

        # Apply personal cooldown
        if ability.cooldown > 0:
            cooldown_end = current_time + ability.cooldown
            self.cooldowns[caster.id][ability.ability_id] = (cooldown_end, True)
            logger.info(
                f"{caster.name} ability {ability.ability_id} on cooldown "
                f"for {ability.cooldown}s"
            )

        # Apply GCD
        if ability.gcd_category:
            # Get GCD duration from class template
            class_id = caster.get_class_id()
            if class_id:
                class_template = self.context.class_system.get_class(class_id)
                if class_template and ability.gcd_category in class_template.gcd_config:
                    gcd_duration = class_template.gcd_config[ability.gcd_category]
                    gcd_end = current_time + gcd_duration
                    self.gcd_state[caster.id] = (gcd_end, ability.gcd_category)
                    logger.info(
                        f"{caster.name} GCD ({ability.gcd_category}) "
                        f"for {gcd_duration}s"
                    )

    def clear_cooldown(self, caster_id: str, ability_id: str) -> None:
        """
        Manually clear a cooldown (for admin/debug).

        Args:
            caster_id: The player ID
            ability_id: The ability ID
        """
        if caster_id in self.cooldowns and ability_id in self.cooldowns[caster_id]:
            del self.cooldowns[caster_id][ability_id]
            logger.info(f"Cleared cooldown for {ability_id}")

    def clear_gcd(self, caster_id: str) -> None:
        """
        Manually clear GCD (for admin/debug).

        Args:
            caster_id: The player ID
        """
        if caster_id in self.gcd_state:
            del self.gcd_state[caster_id]
            logger.info(f"Cleared GCD for player {caster_id}")

    def get_ability_cooldown(self, caster_id: str, ability_id: str) -> float:
        """
        Get remaining cooldown time in seconds.

        Args:
            caster_id: The player ID
            ability_id: The ability ID

        Returns:
            Seconds remaining (0 if not on cooldown)
        """
        if (
            caster_id not in self.cooldowns
            or ability_id not in self.cooldowns[caster_id]
        ):
            return 0.0

        cooldown_end, _ = self.cooldowns[caster_id][ability_id]
        remaining = max(0.0, cooldown_end - time.time())
        return remaining

    def get_gcd_remaining(self, caster_id: str) -> float:
        """
        Get remaining GCD time in seconds.

        Args:
            caster_id: The player ID

        Returns:
            Seconds remaining (0 if not on GCD)
        """
        if caster_id not in self.gcd_state:
            return 0.0

        gcd_end, _ = self.gcd_state[caster_id]
        remaining = max(0.0, gcd_end - time.time())
        return remaining
