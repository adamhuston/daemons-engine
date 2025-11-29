"""
Phase 11: Lighting and Vision System

Manages dynamic light levels in rooms based on multiple sources:
- Area ambient lighting (base level)
- Time-of-day modifiers
- Player light spells (light, daylight)
- Darkness effects
- Item-based light sources (torches, lanterns)

Light levels range from 0-100:
- 0-10: Pitch black (no visibility)
- 11-25: Very dark (minimal visibility)
- 26-50: Dim (partial visibility)
- 51-75: Normal (full visibility)
- 76-100: Bright (enhanced visibility, reveals secrets)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from app.engine.world import World, WorldRoom, WorldArea, WorldPlayer, RoomId
    from app.engine.systems.time_manager import TimeEventManager

logger = logging.getLogger(__name__)


class LightLevel(Enum):
    """Light level categories for easy reference."""
    PITCH_BLACK = 0
    VERY_DARK = 15
    DARK = 30
    DIM = 45
    NORMAL = 60
    BRIGHT = 75
    BRILLIANT = 90


class VisibilityLevel(Enum):
    """Visibility categories based on light level."""
    NONE = "none"          # 0-10: Can't see anything
    MINIMAL = "minimal"    # 11-25: Abbreviated description, names only
    PARTIAL = "partial"    # 26-50: Full description, limited details
    NORMAL = "normal"      # 51-75: Full visibility
    ENHANCED = "enhanced"  # 76-100: Reveals hidden content


# Mapping of ambient_lighting string values to numeric light levels
AMBIENT_LIGHTING_VALUES: Dict[str, int] = {
    "pitch_black": 0,
    "very_dark": 15,
    "dark": 30,
    "dim": 45,
    "normal": 60,
    "bright": 75,
    "brilliant": 90,
    "prismatic": 60,  # Special: immune to time modifiers
}

# Biomes that ignore time-of-day modifiers
TIME_IMMUNE_BIOMES: Set[str] = {
    "underground",
    "ethereal",
    "void",
    "planar",
}


@dataclass
class LightSource:
    """
    Represents an active light source in a room.
    
    Can be from spells (light, daylight), items (torches), or other effects.
    """
    source_id: str  # e.g., "player_uuid" or "global_daylight" or "item_torch_123"
    source_type: str  # "spell", "item", "environmental"
    intensity: int  # Light contribution (0-100)
    expires_at: Optional[float] = None  # Unix timestamp, None = permanent
    event_id: Optional[str] = None  # TimeEvent ID for expiration tracking


@dataclass
class RoomLightState:
    """Runtime light state for a room."""
    current_light_level: int = 60  # Cached effective light level
    active_light_sources: Dict[str, LightSource] = field(default_factory=dict)
    last_calculated: float = 0.0  # Unix timestamp of last calculation


class LightingSystem:
    """
    Manages lighting and visibility throughout the world.
    
    Calculates effective light levels from multiple sources and provides
    visibility filtering for room descriptions, entities, and items.
    """
    
    def __init__(self, world: "World", time_manager: "TimeEventManager"):
        self.world = world
        self.time_manager = time_manager
        
        # Room light states: room_id -> RoomLightState
        self.room_light_states: Dict["RoomId", RoomLightState] = {}
        
        logger.info("LightingSystem initialized")
    
    def get_or_create_light_state(self, room_id: "RoomId") -> RoomLightState:
        """Get existing light state or create new one for a room."""
        if room_id not in self.room_light_states:
            self.room_light_states[room_id] = RoomLightState()
        return self.room_light_states[room_id]
    
    def calculate_room_light_by_id(self, room_id: "RoomId") -> int:
        """
        Calculate room light level by room ID (convenience wrapper).
        
        Args:
            room_id: ID of the room
            
        Returns:
            Light level (0-100) or 60 (default) if room not found
        """
        import time
        room = self.world.rooms.get(room_id)
        if not room:
            return 60  # Default normal light if room not found
        return self.calculate_room_light(room, time.time())
    
    def calculate_room_light(self, room: "WorldRoom", current_time: float) -> int:
        """
        Calculate effective light level for a room.
        
        Sources (additive, clamped to 0-100):
        - Room lighting_override (if set): Replaces ambient + time calculation
        - Area ambient_lighting (base): 0-90
        - Time-of-day modifier: -20 to +0
        - Player light spells: +0 to +50
        - Darkness effects: -50 to -100
        - Item light sources: +10 to +35
        
        Args:
            room: The WorldRoom to calculate light for
            current_time: Current Unix timestamp
            
        Returns:
            Effective light level (0-100)
        """
        light_level = 0
        override_applied = False
        
        # Check for room lighting_override first
        if hasattr(room, 'lighting_override') and room.lighting_override is not None:
            try:
                # lighting_override completely replaces ambient + time calculation
                override_value = int(room.lighting_override)
                light_level = override_value
                override_applied = True
            except (ValueError, TypeError):
                # Fall through to normal calculation if override is invalid
                pass
        
        # If no override (or invalid override), calculate normally
        if not override_applied:
            # 1. Base ambient lighting from area
            area = self.world.areas.get(room.area_id) if room.area_id else None
            if area:
                ambient_str = getattr(area, "ambient_lighting", "normal")
                light_level += AMBIENT_LIGHTING_VALUES.get(ambient_str, 60)
            else:
                # Rooms without areas default to "normal"
                light_level += 60
            
            # 2. Time-of-day modifier (unless biome is time-immune)
            if area and area.biome not in TIME_IMMUNE_BIOMES:
                time_modifier = self._calculate_time_modifier(area, current_time)
                light_level += time_modifier
        
        # 3. Active light sources (spells, items, etc.)
        light_state = self.get_or_create_light_state(room.id)
        
        # Remove expired light sources
        expired = [
            source_id for source_id, source in light_state.active_light_sources.items()
            if source.expires_at and source.expires_at <= current_time
        ]
        for source_id in expired:
            del light_state.active_light_sources[source_id]
        
        # Add remaining light sources
        for source in light_state.active_light_sources.values():
            light_level += source.intensity
        
        # 4. Check for darkness effects from players in room
        darkness_penalty = self._calculate_darkness_penalty(room)
        light_level += darkness_penalty  # Note: penalty is negative
        
        # Clamp to valid range
        return max(0, min(100, light_level))
    
    def _calculate_time_modifier(self, area: "WorldArea", current_time: float) -> int:
        """
        Calculate light modifier based on time of day.
        
        Returns:
            Modifier value (-20 to 0)
        """
        if not hasattr(area, "area_time"):
            return 0
        
        area_time = area.area_time
        hour = area_time.hour
        
        # Night (21:00-05:00): -20 light
        if hour >= 21 or hour < 5:
            return -20
        # Dawn/Dusk (05:00-07:00, 18:00-21:00): -10 light
        elif (5 <= hour < 7) or (18 <= hour < 21):
            return -10
        # Day (07:00-18:00): +0 light
        else:
            return 0
    
    def _calculate_darkness_penalty(self, room: "WorldRoom") -> int:
        """
        Calculate cumulative darkness penalty from entities with darkness effects.
        
        Returns:
            Penalty value (negative integer, -60 per darkness effect)
        """
        penalty = 0
        
        # Check players in room for darkness effects
        for player_id in room.entities:
            player = self.world.players.get(player_id)
            if player and hasattr(player, "active_effects"):
                if "darkness_veil" in player.active_effects:
                    penalty -= 60
        
        return penalty
    
    def update_light_source(
        self,
        room_id: "RoomId",
        source_id: str,
        intensity: int,
        duration: Optional[float] = None,
        source_type: str = "spell"
    ) -> None:
        """
        Add or update a light source in a room.
        
        Args:
            room_id: Room to add light to
            source_id: Unique identifier for this light source
            intensity: Light contribution (0-100)
            duration: Duration in seconds (None = permanent)
            source_type: Type of source ("spell", "item", "environmental")
        """
        import time
        current_time = time.time()
        expires_at = current_time + duration if duration else None
        
        light_state = self.get_or_create_light_state(room_id)
        
        # Create light source
        light_source = LightSource(
            source_id=source_id,
            source_type=source_type,
            intensity=intensity,
            expires_at=expires_at
        )
        
        # If temporary, schedule removal via TimeEventManager
        if expires_at:
            event_id = self.time_manager.schedule_event(
                execute_at=expires_at,
                callback=lambda: self._remove_expired_light_source(room_id, source_id),
                recurring=False
            )
            light_source.event_id = event_id
        
        light_state.active_light_sources[source_id] = light_source
        
        # Recalculate room light
        room = self.world.rooms.get(room_id)
        if room:
            new_level = self.calculate_room_light(room, current_time)
            light_state.current_light_level = new_level
            light_state.last_calculated = current_time
            
            effect_type = "darkness" if intensity < 0 else "light"
            sign = "" if intensity < 0 else "+"
            logger.info(
                f"{effect_type.title()} source '{source_id}' added to room {room_id}: "
                f"{sign}{intensity} intensity, new level: {new_level}"
            )
    
    def remove_light_source(self, room_id: "RoomId", source_id: str) -> None:
        """
        Remove a light source from a room.
        
        Args:
            room_id: Room to remove light from
            source_id: Light source identifier to remove
        """
        import time
        current_time = time.time()
        
        light_state = self.room_light_states.get(room_id)
        if not light_state:
            return
        
        source = light_state.active_light_sources.pop(source_id, None)
        if source:
            # Cancel expiration event if it exists
            if source.event_id:
                self.time_manager.cancel_event(source.event_id)
            
            # Recalculate room light
            room = self.world.rooms.get(room_id)
            if room:
                new_level = self.calculate_room_light(room, current_time)
                light_state.current_light_level = new_level
                light_state.last_calculated = current_time
                
                logger.info(
                    f"Light source '{source_id}' removed from room {room_id}, "
                    f"new level: {new_level}"
                )
    
    def recalculate_all_rooms(self) -> None:
        """
        Recalculate light levels for all rooms with active light states.
        
        Called when time-of-day changes to update lighting across the world.
        Only recalculates rooms that have been previously accessed or have
        active light sources.
        """
        import time
        current_time = time.time()
        
        recalculated_count = 0
        for room_id, light_state in self.room_light_states.items():
            room = self.world.rooms.get(room_id)
            if room:
                old_level = light_state.current_light_level
                new_level = self.calculate_room_light(room, current_time)
                
                if old_level != new_level:
                    light_state.current_light_level = new_level
                    light_state.last_calculated = current_time
                    recalculated_count += 1
        
        if recalculated_count > 0:
            logger.info(
                f"Recalculated light levels for {recalculated_count} rooms "
                f"(time-of-day change)"
            )
    
    def _remove_expired_light_source(self, room_id: "RoomId", source_id: str) -> None:
        """Internal callback for TimeEventManager when light expires."""
        self.remove_light_source(room_id, source_id)
    
    def get_room_light_level(self, room_id: "RoomId") -> int:
        """
        Get current light level for a room (cached).
        
        Recalculates if cache is stale (>60 seconds old).
        
        Args:
            room_id: Room to get light level for
            
        Returns:
            Current light level (0-100)
        """
        import time
        current_time = time.time()
        
        room = self.world.rooms.get(room_id)
        if not room:
            return 60  # Default to normal light
        
        light_state = self.get_or_create_light_state(room_id)
        
        # Recalculate if stale or never calculated
        if current_time - light_state.last_calculated > 60:
            new_level = self.calculate_room_light(room, current_time)
            light_state.current_light_level = new_level
            light_state.last_calculated = current_time
        
        return light_state.current_light_level
    
    def get_visibility_level(self, light_level: int) -> VisibilityLevel:
        """
        Convert numeric light level to visibility category.
        
        Args:
            light_level: Numeric light level (0-100)
            
        Returns:
            VisibilityLevel enum value
        """
        if light_level <= 10:
            return VisibilityLevel.NONE
        elif light_level <= 25:
            return VisibilityLevel.MINIMAL
        elif light_level <= 50:
            return VisibilityLevel.PARTIAL
        elif light_level <= 75:
            return VisibilityLevel.NORMAL
        else:
            return VisibilityLevel.ENHANCED
    
    def get_visible_description(
        self,
        room: "WorldRoom",
        light_level: int
    ) -> Optional[str]:
        """
        Get appropriate room description based on light level.
        
        Args:
            room: The room to describe
            light_level: Current light level
            
        Returns:
            Description text or None if too dark to see
        """
        visibility = self.get_visibility_level(light_level)
        
        if visibility == VisibilityLevel.NONE:
            return "It is pitch black. You can't see anything."
        elif visibility == VisibilityLevel.MINIMAL:
            # Return abbreviated description (first sentence only)
            desc = room.get_effective_description()
            first_sentence = desc.split('.')[0] + '.' if '.' in desc else desc[:50] + '...'
            return f"You can barely make out your surroundings. {first_sentence}"
        else:
            # Normal or better: return full description
            return room.get_effective_description()
    
    def filter_visible_entities(
        self,
        entities: List[any],
        light_level: int
    ) -> List[any]:
        """
        Filter entities by visibility threshold.
        
        Args:
            entities: List of WorldPlayer or WorldNpc entities
            light_level: Current light level
            
        Returns:
            Filtered list of visible entities
        """
        visibility = self.get_visibility_level(light_level)
        
        if visibility == VisibilityLevel.NONE:
            # Can't see any entities in pitch black
            return []
        elif visibility == VisibilityLevel.MINIMAL:
            # Can see entities but with minimal detail
            return entities
        else:
            # Normal visibility: see all entities
            # In ENHANCED mode, could reveal hidden entities
            return entities
    
    def can_see_item_details(self, light_level: int) -> bool:
        """
        Check if light level is sufficient to see item details.
        
        Args:
            light_level: Current light level
            
        Returns:
            True if can see item details
        """
        return light_level > 25  # Partial visibility or better
    
    def can_inspect_target(self, light_level: int) -> bool:
        """
        Check if light level allows 'look <target>' inspection.
        
        Args:
            light_level: Current light level
            
        Returns:
            True if can inspect targets
        """
        return light_level > 10  # Above pitch black
    
    def recalculate_all_rooms(self, current_time: float) -> None:
        """
        Recalculate light levels for all rooms.
        
        Called during time transitions (dawn/dusk/night) to batch-update light.
        
        Args:
            current_time: Current Unix timestamp
        """
        recalculated = 0
        for room_id, room in self.world.rooms.items():
            light_state = self.get_or_create_light_state(room_id)
            new_level = self.calculate_room_light(room, current_time)
            
            if new_level != light_state.current_light_level:
                light_state.current_light_level = new_level
                light_state.last_calculated = current_time
                recalculated += 1
        
        if recalculated > 0:
            logger.info(f"Recalculated light for {recalculated} rooms due to time change")
