"""
Utility ability behaviors - non-combat abilities for exploration and interaction.

These behaviors implement common utility patterns:
- Creating light/darkness effects
- Unlocking doors and containers
- Opening passages and secret areas
- Environmental manipulation
- Detection and sense enhancement
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class UtilityResult:
    """
    Result of executing a utility ability.

    Used by AbilityExecutor to determine what happened when a utility ability was cast.
    """

    success: bool  # Whether the ability executed successfully
    message: str  # Human-readable result message
    state_changes: Dict[str, Any] = None  # Environmental/object state changes
    affected_targets: List[str] = None  # IDs of affected objects/entities
    duration: Optional[float] = None  # Duration of effect (None = permanent)
    error: Optional[str] = None  # Error message if unsuccessful

    def __post_init__(self):
        if self.state_changes is None:
            self.state_changes = {}
        if self.affected_targets is None:
            self.affected_targets = []


# =============================================================================
# Light/Visibility Behaviors
# =============================================================================


async def create_light_behavior(
    caster,  # WorldPlayer or WorldEntity
    target,  # Can be caster or a room/area
    ability_template,
    combat_system,
    **context,
) -> UtilityResult:
    """
    Creates light in an area (personal aura or room-wide).

    Effects:
    - Reveals dark areas
    - Grants light source buff
    - Duration-based effect (can expire)

    Args:
        caster: The entity casting the ability
        target: Target (self or room)
        ability_template: AbilityTemplate from ClassSystem
        combat_system: CombatSystem instance (has .context with lighting_system)
        **context: Additional context

    Returns:
        UtilityResult indicating light created
    """
    try:
        light_level = ability_template.metadata.get(
            "light_level", 50
        )  # 0-100 brightness
        duration = ability_template.metadata.get("duration", 300.0)  # 5 minutes default
        effect_radius = ability_template.metadata.get("radius", 1)  # Room radius

        # Get the lighting system from combat_system context
        lighting_system = getattr(combat_system, "context", None)
        if lighting_system:
            lighting_system = getattr(lighting_system, "lighting_system", None)

        # Get caster's room
        room_id = getattr(caster, "room_id", None)

        # For personal light (e.g., light orb), track on caster
        if ability_template.target_type == "self":
            if not hasattr(caster, "active_effects"):
                caster.active_effects = {}

            caster.active_effects["light_aura"] = {
                "level": light_level,
                "duration": duration,
                "start_time": context.get("current_time", 0),
            }

            # Update lighting system if available
            if lighting_system and room_id:
                import time

                expires_at = time.time() + duration
                lighting_system.update_light_source(
                    room_id=room_id,
                    source_id=f"spell_light_{caster.id}",
                    source_type="spell",
                    intensity=light_level,
                    expires_at=expires_at,
                )

            return UtilityResult(
                success=True,
                message=f"{caster.name} creates a sphere of light!",
                state_changes={"light_aura": light_level},
                affected_targets=[caster.id],
                duration=duration,
            )

        # For room-wide light (e.g., daylight), track on room/area
        elif ability_template.target_type == "room":
            if not hasattr(caster, "last_used_light_effects"):
                caster.last_used_light_effects = {}

            room_key = room_id if room_id else "unknown"
            caster.last_used_light_effects[room_key] = {
                "level": light_level,
                "duration": duration,
                "caster": caster.id,
                "radius": effect_radius,
            }

            # Update lighting system if available
            if lighting_system and room_id:
                import time

                expires_at = time.time() + duration
                lighting_system.update_light_source(
                    room_id=room_id,
                    source_id=f"spell_daylight_{caster.id}_{int(time.time())}",
                    source_type="spell",
                    intensity=light_level,
                    expires_at=expires_at,
                )

            return UtilityResult(
                success=True,
                message=f"Light fills the area around {caster.name}!",
                state_changes={"room_light": light_level, "radius": effect_radius},
                affected_targets=[room_key],
                duration=duration,
            )

        return UtilityResult(
            success=False,
            message="Light spell targeting failed",
            error="Invalid target type for light",
        )

    except Exception as e:
        logger.error(f"create_light_behavior failed: {e}", exc_info=True)
        return UtilityResult(success=False, message="Light spell failed", error=str(e))


async def darkness_behavior(
    caster, target, ability_template, combat_system, **context
) -> UtilityResult:
    """
    Creates darkness or obscures light sources.

    Effects:
    - Darkens an area
    - Reduces visibility
    - Can negate light effects

    Args:
        caster: The entity casting the ability
        target: Target area
        ability_template: AbilityTemplate from ClassSystem
        combat_system: CombatSystem instance (has .context with lighting_system)
        **context: Additional context

    Returns:
        UtilityResult indicating darkness applied
    """
    try:
        darkness_level = ability_template.metadata.get(
            "darkness_level", 75
        )  # 0-100 opacity
        duration = ability_template.metadata.get("duration", 180.0)  # 3 minutes default

        # Get the lighting system from combat_system context
        lighting_system = getattr(combat_system, "context", None)
        if lighting_system:
            lighting_system = getattr(lighting_system, "lighting_system", None)

        # Get caster's room
        room_id = getattr(caster, "room_id", None)

        if not hasattr(caster, "active_effects"):
            caster.active_effects = {}

        caster.active_effects["darkness_veil"] = {
            "level": darkness_level,
            "duration": duration,
            "start_time": context.get("current_time", 0),
        }

        # Update lighting system if available - darkness uses negative intensity
        if lighting_system and room_id:
            import time

            expires_at = time.time() + duration
            # Use the dedicated method for darkness effects
            lighting_system.update_light_source(
                room_id=room_id,
                source_id=f"spell_darkness_{caster.id}",
                source_type="spell",
                intensity=-darkness_level,  # Negative intensity for darkness
                expires_at=expires_at,
            )

        return UtilityResult(
            success=True,
            message=f"Darkness envelops {caster.name}!",
            state_changes={"darkness_veil": darkness_level},
            affected_targets=[caster.id],
            duration=duration,
        )

    except Exception as e:
        logger.error(f"darkness_behavior failed: {e}", exc_info=True)
        return UtilityResult(
            success=False, message="Darkness spell failed", error=str(e)
        )


# =============================================================================
# Unlock/Opening Behaviors
# =============================================================================


async def unlock_door_behavior(
    caster,
    target,  # The door/container object
    ability_template,
    combat_system,
    **context,
) -> UtilityResult:
    """
    Magically unlocks a locked door or container.

    Requirements:
    - Target must be locked
    - No level requirements on the lock
    - Can potentially bypass magical locks with sufficient caster power

    Args:
        caster: The entity casting the ability
        target: The door or container to unlock
        ability_template: AbilityTemplate from ClassSystem
        combat_system: CombatSystem instance
        **context: Additional context (may include target_object)

    Returns:
        UtilityResult indicating unlock success/failure
    """
    try:
        target_object = context.get("target_object")

        # Validate target
        if not target_object:
            return UtilityResult(
                success=False,
                message="No valid target to unlock",
                error="Target object not found",
            )

        # Check if already unlocked
        if not getattr(target_object, "is_locked", False):
            return UtilityResult(
                success=False,
                message=f"{target_object.name if hasattr(target_object, 'name') else 'Target'} is not locked",
                error="Target is not locked",
            )

        # Check lock difficulty against caster level
        lock_difficulty = getattr(target_object, "lock_difficulty", 1)
        if caster.level < lock_difficulty:
            return UtilityResult(
                success=False,
                message=f"The lock is too complex for your level ({lock_difficulty})",
                error="Insufficient skill level",
            )

        # Perform the unlock
        target_object.is_locked = False
        target_name = getattr(target_object, "name", "the door")

        return UtilityResult(
            success=True,
            message=f"{caster.name} magically unlocks {target_name}!",
            state_changes={"is_locked": False},
            affected_targets=[getattr(target_object, "id", "unknown")],
            duration=None,  # Permanent unlock
        )

    except Exception as e:
        logger.error(f"unlock_door_behavior failed: {e}", exc_info=True)
        return UtilityResult(success=False, message="Unlock spell failed", error=str(e))


async def unlock_container_behavior(
    caster, target, ability_template, combat_system, **context
) -> UtilityResult:
    """
    Magically opens a locked container without a key.

    Similar to unlock_door but specifically for chests, boxes, etc.

    Args:
        caster: The entity casting the ability
        target: The container to open
        ability_template: AbilityTemplate from ClassSystem
        combat_system: CombatSystem instance
        **context: Additional context

    Returns:
        UtilityResult indicating container open success/failure
    """
    try:
        target_object = context.get("target_object")

        if not target_object:
            return UtilityResult(
                success=False,
                message="No container to open",
                error="Target object not found",
            )

        # Check if sealed/trapped
        is_trapped = getattr(target_object, "is_trapped", False)
        if is_trapped:
            caster_perception = getattr(caster, "perception", 10)
            trap_difficulty = getattr(target_object, "trap_difficulty", 15)

            if caster_perception < trap_difficulty:
                return UtilityResult(
                    success=False,
                    message=f"You trigger a trap on {target_object.name}!",
                    error="Trap triggered",
                    state_changes={"trap_triggered": True},
                )

        # Open the container
        target_object.is_open = True
        target_object.is_locked = False

        return UtilityResult(
            success=True,
            message=f"{caster.name} opens {target_object.name}!",
            state_changes={"is_open": True, "is_locked": False},
            affected_targets=[getattr(target_object, "id", "unknown")],
            duration=None,
        )

    except Exception as e:
        logger.error(f"unlock_container_behavior failed: {e}", exc_info=True)
        return UtilityResult(
            success=False, message="Container unlock spell failed", error=str(e)
        )


# =============================================================================
# Detection/Sensing Behaviors
# =============================================================================


async def detect_magic_behavior(
    caster, target, ability_template, combat_system, **context
) -> UtilityResult:
    """
    Detects magical auras and enchantments in an area.

    Effects:
    - Reveals magical items and effects
    - Shows magical auras of creatures
    - Duration-based detection range

    Args:
        caster: The entity casting the ability
        target: Usually caster (self-targeted)
        ability_template: AbilityTemplate from ClassSystem
        combat_system: CombatSystem instance
        **context: Additional context (world_engine, etc.)

    Returns:
        UtilityResult with detected magical objects
    """
    try:
        duration = ability_template.metadata.get("duration", 60.0)  # 1 minute
        radius = ability_template.metadata.get("radius", 3)  # Room range

        # In a full implementation, this would scan the area for magical auras
        # For now, we track that detection is active
        if not hasattr(caster, "active_effects"):
            caster.active_effects = {}

        caster.active_effects["detect_magic"] = {
            "radius": radius,
            "duration": duration,
            "start_time": context.get("current_time", 0),
            "detected": [],  # Would be filled by game loop
        }

        return UtilityResult(
            success=True,
            message=f"{caster.name} is now attuned to magical energies!",
            state_changes={"detect_magic_active": True, "radius": radius},
            affected_targets=[caster.id],
            duration=duration,
        )

    except Exception as e:
        logger.error(f"detect_magic_behavior failed: {e}", exc_info=True)
        return UtilityResult(
            success=False, message="Detection spell failed", error=str(e)
        )


async def true_sight_behavior(
    caster, target, ability_template, combat_system, **context
) -> UtilityResult:
    """
    Penetrates illusions and reveals hidden objects.

    Effects:
    - Sees through invisibility
    - Detects hidden creatures/objects
    - Short duration, high cost

    Args:
        caster: The entity casting the ability
        target: Target area (usually self)
        ability_template: AbilityTemplate from ClassSystem
        combat_system: CombatSystem instance
        **context: Additional context

    Returns:
        UtilityResult indicating true sight activated
    """
    try:
        duration = ability_template.metadata.get("duration", 30.0)  # 30 seconds

        if not hasattr(caster, "active_effects"):
            caster.active_effects = {}

        caster.active_effects["true_sight"] = {
            "duration": duration,
            "start_time": context.get("current_time", 0),
        }

        return UtilityResult(
            success=True,
            message=f"{caster.name}'s vision penetrates all illusions!",
            state_changes={"true_sight_active": True},
            affected_targets=[caster.id],
            duration=duration,
        )

    except Exception as e:
        logger.error(f"true_sight_behavior failed: {e}", exc_info=True)
        return UtilityResult(
            success=False, message="True sight spell failed", error=str(e)
        )


# =============================================================================
# Environmental Manipulation
# =============================================================================


async def teleport_behavior(
    caster, target, ability_template, combat_system, **context
) -> UtilityResult:
    """
    Teleports caster to a location or waypoint.

    Requirements:
    - Must know the destination (learned location)
    - Cannot teleport into occupied spaces
    - Can have memory/attunement requirements

    Args:
        caster: The entity casting the ability
        target: Destination (encoded in context or as target_id)
        ability_template: AbilityTemplate from ClassSystem
        combat_system: CombatSystem instance
        **context: Additional context (destination, etc.)

    Returns:
        UtilityResult indicating teleport success/failure
    """
    try:
        destination = context.get("destination")

        if not destination:
            return UtilityResult(
                success=False,
                message="No destination specified",
                error="Missing destination",
            )

        # Check if caster knows this location
        known_locations = getattr(caster, "known_locations", [])
        if destination not in known_locations:
            return UtilityResult(
                success=False,
                message=f"You are not attuned to {destination}",
                error="Unknown destination",
            )

        # In full implementation, would check destination occupancy
        # For now, just track the teleport
        old_location = getattr(caster, "location", "unknown")
        caster.location = destination

        return UtilityResult(
            success=True,
            message=f"{caster.name} vanishes in a flash and reappears at {destination}!",
            state_changes={"location": destination, "previous_location": old_location},
            affected_targets=[caster.id],
            duration=None,  # Teleport is instantaneous
        )

    except Exception as e:
        logger.error(f"teleport_behavior failed: {e}", exc_info=True)
        return UtilityResult(
            success=False, message="Teleport spell failed", error=str(e)
        )


async def create_passage_behavior(
    caster, target, ability_template, combat_system, **context
) -> UtilityResult:
    """
    Opens a temporary passage through walls or sealed areas.

    Effects:
    - Creates temporary doorway
    - Time-limited access (duration)
    - Cannot be used on certain barriers

    Args:
        caster: The entity casting the ability
        target: The wall/barrier to open
        ability_template: AbilityTemplate from ClassSystem
        combat_system: CombatSystem instance
        **context: Additional context (wall_id, etc.)

    Returns:
        UtilityResult indicating passage created
    """
    try:
        duration = ability_template.metadata.get("duration", 120.0)  # 2 minutes
        wall_id = context.get("wall_id")

        if not wall_id:
            return UtilityResult(
                success=False, message="No wall to open", error="Wall not found"
            )

        # Create temporary passage
        if not hasattr(caster, "created_passages"):
            caster.created_passages = {}

        caster.created_passages[wall_id] = {
            "creator": caster.id,
            "duration": duration,
            "created_at": context.get("current_time", 0),
        }

        return UtilityResult(
            success=True,
            message=f"{caster.name} opens a passage through the wall!",
            state_changes={"passage_open": True},
            affected_targets=[wall_id],
            duration=duration,
        )

    except Exception as e:
        logger.error(f"create_passage_behavior failed: {e}", exc_info=True)
        return UtilityResult(
            success=False, message="Passage spell failed", error=str(e)
        )


# =============================================================================
# Conversion to Combat-Compatible Results
# =============================================================================


def utility_result_to_behavior_result(utility_result: UtilityResult):
    """
    Convert UtilityResult to BehaviorResult for compatibility with AbilityExecutor.

    This allows utility abilities to use the same execution pipeline as combat abilities.

    Args:
        utility_result: The UtilityResult from a utility behavior

    Returns:
        dict: Compatible with AbilityExecutor's expected result format
    """
    # Import here to avoid circular imports
    from app.engine.systems.ability_behaviors.core import BehaviorResult

    return BehaviorResult(
        success=utility_result.success,
        message=utility_result.message,
        targets_hit=utility_result.affected_targets,
        effects_applied=list(utility_result.state_changes.keys()),
        error=utility_result.error,
    )
