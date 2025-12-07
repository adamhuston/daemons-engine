"""
Phase 17.1: Temperature System

Manages dynamic temperature in rooms based on multiple sources:
- Area base temperature
- Time-of-day modifiers (cooler at night, warmer at midday)
- Biome modifiers (arctic = cold, desert = hot)
- Room overrides (forges, ice caves, etc.)

Temperature in Fahrenheit:
- < 32°F: FREEZING (cold damage, movement penalty)
- 32-50°F: COLD (stamina regen reduced)
- 50-80°F: COMFORTABLE (no effects)
- 80-100°F: HOT (stamina regen reduced)
- > 100°F: SCORCHING (heat damage, movement penalty)
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from daemons.engine.world import RoomId, World, WorldArea, WorldRoom

logger = logging.getLogger(__name__)


class TemperatureLevel(Enum):
    """Temperature threshold categories."""

    FREEZING = "freezing"  # < 32°F
    COLD = "cold"  # 32-50°F
    COMFORTABLE = "comfortable"  # 50-80°F
    HOT = "hot"  # 80-100°F
    SCORCHING = "scorching"  # > 100°F


# Temperature thresholds in Fahrenheit
TEMPERATURE_THRESHOLDS = {
    "freezing_max": 32,
    "cold_max": 50,
    "comfortable_max": 80,
    "hot_max": 100,
}

# Time-of-day temperature modifiers (relative to base)
# Game time periods: dawn, morning, afternoon, dusk, evening, night
TIME_TEMPERATURE_MODIFIERS: dict[str, int] = {
    "dawn": -10,  # Cool morning
    "morning": -5,  # Warming up
    "afternoon": +5,  # Warmest part of day
    "dusk": 0,  # Cooling down
    "evening": -5,  # Getting cooler
    "night": -15,  # Coldest part of day
}

# Biome base temperature modifiers (added to area base_temperature)
# These represent the inherent temperature characteristics of biomes
BIOME_TEMPERATURE_MODIFIERS: dict[str, int] = {
    "arctic": -40,  # Extremely cold
    "tundra": -30,  # Very cold
    "boreal": -15,  # Cold
    "temperate": 0,  # Neutral
    "grassland": +5,  # Slightly warm
    "desert": +30,  # Hot
    "tropical": +15,  # Warm and humid
    "swamp": +10,  # Warm and humid
    "mountain": -20,  # Cold due to altitude
    "underground": 0,  # Special: constant temperature
    "ethereal": 0,  # Special: immune to temperature
    "void": 0,  # Special: immune to temperature
    "planar": 0,  # Special: immune to temperature
    "forest": 0,  # Neutral (shaded)
    "cave": 0,  # Special: constant temperature
}

# Biomes that maintain constant temperature (ignore time-of-day)
TEMPERATURE_IMMUNE_BIOMES: set[str] = {
    "underground",
    "ethereal",
    "void",
    "planar",
    "cave",
}

# Player effects configuration
TEMPERATURE_EFFECTS = {
    "freezing": {
        "damage_per_tick": 2,  # HP damage per regen tick
        "movement_penalty": 0.25,  # 25% slower movement
        "stamina_regen_modifier": 0.5,  # 50% reduced regen
        "message": "The bitter cold bites into your flesh!",
        "icon": "🥶",
    },
    "cold": {
        "damage_per_tick": 0,
        "movement_penalty": 0.0,
        "stamina_regen_modifier": 0.75,  # 25% reduced regen
        "message": "You shiver in the cold.",
        "icon": "❄️",
    },
    "comfortable": {
        "damage_per_tick": 0,
        "movement_penalty": 0.0,
        "stamina_regen_modifier": 1.0,  # Normal regen
        "message": "",
        "icon": "",
    },
    "hot": {
        "damage_per_tick": 0,
        "movement_penalty": 0.0,
        "stamina_regen_modifier": 0.75,  # 25% reduced regen
        "message": "The heat is oppressive.",
        "icon": "🌡️",
    },
    "scorching": {
        "damage_per_tick": 2,  # HP damage per regen tick
        "movement_penalty": 0.25,  # 25% slower movement
        "stamina_regen_modifier": 0.5,  # 50% reduced regen
        "message": "The scorching heat sears your skin!",
        "icon": "🔥",
    },
}


@dataclass
class TemperatureState:
    """Current temperature state for a room."""

    temperature: int  # Current temperature in Fahrenheit
    level: TemperatureLevel  # Category (freezing, cold, comfortable, hot, scorching)
    base_temperature: int  # Area base before modifiers
    time_modifier: int  # Time-of-day adjustment
    biome_modifier: int  # Biome-based adjustment
    is_override: bool  # True if room override was applied


class TemperatureSystem:
    """
    Manages temperature calculations throughout the world.

    Provides temperature effects for players and NPCs,
    and conditions for trigger evaluation.
    """

    def __init__(self, world: "World"):
        self.world = world
        logger.info("TemperatureSystem initialized")

    def get_temperature_level(self, temperature: int) -> TemperatureLevel:
        """
        Convert numeric temperature to a category.

        Args:
            temperature: Temperature in Fahrenheit

        Returns:
            TemperatureLevel enum value
        """
        if temperature < TEMPERATURE_THRESHOLDS["freezing_max"]:
            return TemperatureLevel.FREEZING
        elif temperature < TEMPERATURE_THRESHOLDS["cold_max"]:
            return TemperatureLevel.COLD
        elif temperature < TEMPERATURE_THRESHOLDS["comfortable_max"]:
            return TemperatureLevel.COMFORTABLE
        elif temperature < TEMPERATURE_THRESHOLDS["hot_max"]:
            return TemperatureLevel.HOT
        else:
            return TemperatureLevel.SCORCHING

    def calculate_room_temperature(
        self,
        room: "WorldRoom",
        current_time: float,
    ) -> TemperatureState:
        """
        Calculate effective temperature for a room.

        Resolution order:
        1. Room temperature_override (if set) - ignores all other calculations
        2. Area base_temperature + time modifier + biome modifier

        Args:
            room: The WorldRoom to calculate temperature for
            current_time: Current Unix timestamp

        Returns:
            TemperatureState with full calculation breakdown
        """
        # Check for room override first
        if hasattr(room, "temperature_override") and room.temperature_override is not None:
            temp = room.temperature_override
            return TemperatureState(
                temperature=temp,
                level=self.get_temperature_level(temp),
                base_temperature=temp,
                time_modifier=0,
                biome_modifier=0,
                is_override=True,
            )

        # Get area for this room
        area = self.world.areas.get(room.area_id) if room.area_id else None

        # Start with area base temperature (or default 70°F)
        base_temp = 70  # Default comfortable temperature
        biome = "temperate"  # Default biome

        if area:
            base_temp = getattr(area, "base_temperature", 70)
            biome = getattr(area, "biome", "temperate")

        # Calculate biome modifier
        biome_modifier = BIOME_TEMPERATURE_MODIFIERS.get(biome.lower(), 0)

        # Calculate time-of-day modifier (unless biome is immune)
        time_modifier = 0
        if biome.lower() not in TEMPERATURE_IMMUNE_BIOMES:
            time_period = self._get_time_period(area, current_time)
            time_modifier = TIME_TEMPERATURE_MODIFIERS.get(time_period, 0)

        # Calculate final temperature
        final_temp = base_temp + biome_modifier + time_modifier

        return TemperatureState(
            temperature=final_temp,
            level=self.get_temperature_level(final_temp),
            base_temperature=base_temp,
            time_modifier=time_modifier,
            biome_modifier=biome_modifier,
            is_override=False,
        )

    def calculate_room_temperature_by_id(self, room_id: "RoomId") -> TemperatureState:
        """
        Calculate room temperature by room ID (convenience wrapper).

        Args:
            room_id: ID of the room

        Returns:
            TemperatureState or default comfortable state if room not found
        """
        import time

        room = self.world.rooms.get(room_id)
        if not room:
            return TemperatureState(
                temperature=70,
                level=TemperatureLevel.COMFORTABLE,
                base_temperature=70,
                time_modifier=0,
                biome_modifier=0,
                is_override=False,
            )
        return self.calculate_room_temperature(room, time.time())

    def _get_time_period(
        self,
        area: "WorldArea | None",
        current_time: float,
    ) -> str:
        """
        Get the current time period for an area.

        Args:
            area: The WorldArea (may be None)
            current_time: Unix timestamp

        Returns:
            Time period string: dawn, morning, afternoon, dusk, evening, night
        """
        if area and hasattr(area, "area_time"):
            # Use area's local time
            hour = area.area_time.hour
        else:
            # Fall back to real-world time mapping
            import datetime

            dt = datetime.datetime.fromtimestamp(current_time)
            hour = dt.hour

        # Map hours to time periods
        if 5 <= hour < 7:
            return "dawn"
        elif 7 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 19:
            return "dusk"
        elif 19 <= hour < 22:
            return "evening"
        else:
            return "night"

    def get_temperature_effects(self, temperature: int) -> dict:
        """
        Get the gameplay effects for a given temperature.

        Args:
            temperature: Temperature in Fahrenheit

        Returns:
            Dict with damage_per_tick, movement_penalty, stamina_regen_modifier, message, icon
        """
        level = self.get_temperature_level(temperature)
        return TEMPERATURE_EFFECTS.get(level.value, TEMPERATURE_EFFECTS["comfortable"])

    def format_temperature_display(
        self,
        temperature: int,
        include_effects: bool = True,
    ) -> str:
        """
        Format temperature for display to players.

        Args:
            temperature: Temperature in Fahrenheit
            include_effects: Whether to include effect description

        Returns:
            Formatted string like "52°F (Cool) ❄️"
        """
        level = self.get_temperature_level(temperature)
        effects = TEMPERATURE_EFFECTS[level.value]
        icon = effects["icon"]

        # Level display names
        level_names = {
            TemperatureLevel.FREEZING: "Freezing",
            TemperatureLevel.COLD: "Cold",
            TemperatureLevel.COMFORTABLE: "Comfortable",
            TemperatureLevel.HOT: "Hot",
            TemperatureLevel.SCORCHING: "Scorching",
        }

        result = f"{temperature}°F ({level_names[level]})"
        if icon:
            result += f" {icon}"

        if include_effects and effects["message"]:
            result += f"\n{effects['message']}"

        return result

    def should_show_temperature(self, temperature: int) -> bool:
        """
        Determine if temperature should be shown in room description.

        Only show for extreme temperatures (freezing/cold or hot/scorching).

        Args:
            temperature: Temperature in Fahrenheit

        Returns:
            True if temperature should be displayed
        """
        level = self.get_temperature_level(temperature)
        return level != TemperatureLevel.COMFORTABLE

    def check_temperature_condition(
        self,
        room_id: "RoomId",
        condition_type: str,
        threshold: int | None = None,
        min_temp: int | None = None,
        max_temp: int | None = None,
    ) -> bool:
        """
        Check temperature conditions for triggers.

        Supports:
        - temperature_above: temp > threshold
        - temperature_below: temp < threshold
        - temperature_range: min_temp <= temp <= max_temp

        Args:
            room_id: Room to check
            condition_type: One of "above", "below", "range"
            threshold: Temperature threshold for above/below
            min_temp: Minimum for range check
            max_temp: Maximum for range check

        Returns:
            True if condition is met
        """
        state = self.calculate_room_temperature_by_id(room_id)
        temp = state.temperature

        if condition_type == "above" and threshold is not None:
            return temp > threshold
        elif condition_type == "below" and threshold is not None:
            return temp < threshold
        elif condition_type == "range" and min_temp is not None and max_temp is not None:
            return min_temp <= temp <= max_temp

        return False
