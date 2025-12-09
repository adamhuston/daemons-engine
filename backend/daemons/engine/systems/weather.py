"""
Phase 17.2: Weather System

Manages dynamic weather that changes over time and affects gameplay.

Weather Types:
- CLEAR: No precipitation, good visibility
- CLOUDY: Overcast skies, slightly reduced visibility
- OVERCAST: Heavy clouds, dim conditions
- RAIN: Light, moderate, or heavy precipitation
- STORM: Thunderstorm with lightning, heavy rain
- SNOW: Flurries, moderate snow, or blizzard
- FOG: Light or dense fog reducing visibility
- WIND: Breezy to gale-force winds

Weather affects:
- Visibility (fog/rain reduce light_level)
- Temperature (rain cools, clear sun heats)
- Movement (blizzard/storm = slower travel)
- Combat (rain = ranged penalty, wind = casting penalty)
"""

import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from daemons.engine.world import AreaId, World, WorldArea

logger = logging.getLogger(__name__)


class WeatherType(Enum):
    """Types of weather conditions."""

    CLEAR = "clear"
    CLOUDY = "cloudy"
    OVERCAST = "overcast"
    RAIN = "rain"
    STORM = "storm"
    SNOW = "snow"
    FOG = "fog"
    WIND = "wind"


class WeatherIntensity(Enum):
    """Intensity levels for weather conditions."""

    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"


# Weather display names and icons
WEATHER_DISPLAY = {
    WeatherType.CLEAR: {"name": "Clear", "icon": "☀️", "desc": "clear skies"},
    WeatherType.CLOUDY: {"name": "Cloudy", "icon": "⛅", "desc": "cloudy skies"},
    WeatherType.OVERCAST: {"name": "Overcast", "icon": "☁️", "desc": "overcast skies"},
    WeatherType.RAIN: {"name": "Rain", "icon": "🌧️", "desc": "rainfall"},
    WeatherType.STORM: {"name": "Storm", "icon": "⛈️", "desc": "thunderstorm"},
    WeatherType.SNOW: {"name": "Snow", "icon": "🌨️", "desc": "snowfall"},
    WeatherType.FOG: {"name": "Fog", "icon": "🌫️", "desc": "foggy conditions"},
    WeatherType.WIND: {"name": "Wind", "icon": "💨", "desc": "strong winds"},
}

# Intensity descriptors
INTENSITY_DESCRIPTORS = {
    WeatherIntensity.LIGHT: {
        WeatherType.RAIN: "light drizzle",
        WeatherType.SNOW: "light flurries",
        WeatherType.FOG: "light mist",
        WeatherType.WIND: "a gentle breeze",
        WeatherType.STORM: "a passing storm",
    },
    WeatherIntensity.MODERATE: {
        WeatherType.RAIN: "steady rain",
        WeatherType.SNOW: "moderate snowfall",
        WeatherType.FOG: "thick fog",
        WeatherType.WIND: "strong winds",
        WeatherType.STORM: "a thunderstorm",
    },
    WeatherIntensity.HEAVY: {
        WeatherType.RAIN: "heavy downpour",
        WeatherType.SNOW: "a blizzard",
        WeatherType.FOG: "dense fog",
        WeatherType.WIND: "gale-force winds",
        WeatherType.STORM: "a violent thunderstorm",
    },
}

# Default weather patterns by climate type
CLIMATE_WEATHER_PATTERNS: dict[str, dict[str, float]] = {
    "arid": {
        "clear": 0.70,
        "wind": 0.20,
        "cloudy": 0.05,
        "storm": 0.05,
    },
    "temperate": {
        "clear": 0.35,
        "cloudy": 0.25,
        "rain": 0.20,
        "overcast": 0.10,
        "storm": 0.05,
        "fog": 0.05,
    },
    "arctic": {
        "snow": 0.40,
        "cloudy": 0.25,
        "overcast": 0.15,
        "wind": 0.10,
        "clear": 0.10,
    },
    "tropical": {
        "rain": 0.35,
        "storm": 0.20,
        "clear": 0.20,
        "cloudy": 0.15,
        "fog": 0.10,
    },
    "humid": {
        "rain": 0.30,
        "fog": 0.25,
        "cloudy": 0.20,
        "overcast": 0.15,
        "clear": 0.10,
    },
    "cold": {
        "snow": 0.30,
        "cloudy": 0.25,
        "overcast": 0.20,
        "clear": 0.15,
        "wind": 0.10,
    },
    "mild": {
        "clear": 0.40,
        "cloudy": 0.30,
        "rain": 0.15,
        "overcast": 0.10,
        "fog": 0.05,
    },
    "hot": {
        "clear": 0.50,
        "cloudy": 0.20,
        "wind": 0.15,
        "storm": 0.10,
        "rain": 0.05,
    },
}

# Weather transition probabilities (Markov chain)
# What weather is likely to follow the current weather
WEATHER_TRANSITIONS: dict[str, dict[str, float]] = {
    "clear": {"clear": 0.50, "cloudy": 0.30, "wind": 0.10, "fog": 0.10},
    "cloudy": {"cloudy": 0.30, "clear": 0.25, "overcast": 0.20, "rain": 0.15, "wind": 0.10},
    "overcast": {"overcast": 0.25, "rain": 0.30, "cloudy": 0.25, "storm": 0.10, "snow": 0.10},
    "rain": {"rain": 0.35, "overcast": 0.25, "cloudy": 0.20, "storm": 0.15, "clear": 0.05},
    "storm": {"storm": 0.20, "rain": 0.40, "overcast": 0.25, "cloudy": 0.15},
    "snow": {"snow": 0.40, "overcast": 0.25, "cloudy": 0.20, "clear": 0.10, "wind": 0.05},
    "fog": {"fog": 0.30, "cloudy": 0.30, "clear": 0.25, "overcast": 0.15},
    "wind": {"wind": 0.30, "clear": 0.30, "cloudy": 0.25, "storm": 0.10, "rain": 0.05},
}

# Weather effects on gameplay
WEATHER_EFFECTS: dict[str, dict[str, Any]] = {
    "clear": {
        "visibility_modifier": 0,
        "temperature_modifier": 5,  # Warmer in sunshine
        "movement_modifier": 1.0,
        "ranged_penalty": 0,
        "casting_penalty": 0,
        "message": "",
    },
    "cloudy": {
        "visibility_modifier": -5,
        "temperature_modifier": 0,
        "movement_modifier": 1.0,
        "ranged_penalty": 0,
        "casting_penalty": 0,
        "message": "",
    },
    "overcast": {
        "visibility_modifier": -10,
        "temperature_modifier": -5,
        "movement_modifier": 1.0,
        "ranged_penalty": 0,
        "casting_penalty": 0,
        "message": "The heavy clouds block out the sun.",
    },
    "rain": {
        "visibility_modifier": -15,
        "temperature_modifier": -10,
        "movement_modifier": 0.9,  # 10% slower
        "ranged_penalty": 10,  # -10% to ranged attacks
        "casting_penalty": 0,
        "message": "Rain falls around you.",
    },
    "storm": {
        "visibility_modifier": -25,
        "temperature_modifier": -15,
        "movement_modifier": 0.75,  # 25% slower
        "ranged_penalty": 25,  # -25% to ranged attacks
        "casting_penalty": 10,  # -10% to casting
        "message": "Thunder rumbles and lightning flashes across the sky.",
    },
    "snow": {
        "visibility_modifier": -20,
        "temperature_modifier": -20,
        "movement_modifier": 0.8,  # 20% slower
        "ranged_penalty": 15,
        "casting_penalty": 5,
        "message": "Snow falls gently from the sky.",
    },
    "fog": {
        "visibility_modifier": -30,
        "temperature_modifier": -5,
        "movement_modifier": 0.9,
        "ranged_penalty": 20,
        "casting_penalty": 0,
        "message": "A thick fog obscures your surroundings.",
    },
    "wind": {
        "visibility_modifier": -5,
        "temperature_modifier": -10,  # Wind chill
        "movement_modifier": 0.85,
        "ranged_penalty": 20,
        "casting_penalty": 15,
        "message": "Strong winds whip around you.",
    },
}

# Intensity multipliers for effects
INTENSITY_MULTIPLIERS = {
    WeatherIntensity.LIGHT: 0.5,
    WeatherIntensity.MODERATE: 1.0,
    WeatherIntensity.HEAVY: 1.5,
}

# Weather duration ranges (in game hours)
# These are converted to real seconds based on REAL_SECONDS_PER_GAME_HOUR (30 sec/game hour)
# Real-world weather typically persists for hours, so game weather should too
WEATHER_DURATION_RANGES: dict[str, tuple[int, int]] = {
    "clear": (4, 16),  # 4-16 game hours (2-8 real minutes)
    "cloudy": (2, 8),  # 2-8 game hours (1-4 real minutes)
    "overcast": (2, 6),  # 2-6 game hours (1-3 real minutes)
    "rain": (1, 4),  # 1-4 game hours (30s-2 real minutes)
    "storm": (1, 3),  # 1-3 game hours (30s-1.5 real minutes)
    "snow": (2, 8),  # 2-8 game hours (1-4 real minutes)
    "fog": (2, 6),  # 2-6 game hours (1-3 real minutes)
    "wind": (1, 4),  # 1-4 game hours (30s-2 real minutes)
}

# Chance that weather will persist (repeat) instead of transitioning
# This allows occasional extended weather patterns
WEATHER_PERSIST_CHANCE: float = 0.25  # 25% chance to repeat current weather

# Biomes that are immune to weather (always clear)
WEATHER_IMMUNE_BIOMES: set[str] = {
    "underground",
    "cave",
    "ethereal",
    "void",
    "planar",
}


@dataclass
class WeatherState:
    """Current weather state for an area."""

    weather_type: WeatherType
    intensity: WeatherIntensity
    started_at: float  # Unix timestamp
    duration: int  # Seconds
    next_change_at: float | None = None

    @property
    def time_remaining(self) -> int:
        """Seconds until weather changes."""
        if self.next_change_at is None:
            return 0
        remaining = int(self.next_change_at - time.time())
        return max(0, remaining)


@dataclass
class WeatherForecast:
    """Weather forecast information."""

    current: WeatherState
    likely_next: WeatherType
    change_in_minutes: int


class WeatherSystem:
    """
    Manages weather across all areas in the world.

    Features:
    - Climate-based weather patterns
    - Markov chain transitions for realistic progression
    - Intensity variations within weather types
    - Gameplay effects (visibility, movement, combat)
    - Integration with temperature system
    """

    def __init__(self, world: "World"):
        self.world = world
        # In-memory cache of current weather states per area
        self._weather_cache: dict[str, WeatherState] = {}
        logger.info("WeatherSystem initialized")

    def get_current_weather(self, area_id: "AreaId") -> WeatherState:
        """
        Get the current weather for an area.

        Args:
            area_id: ID of the area

        Returns:
            WeatherState with current conditions
        """
        # Check cache first
        if area_id in self._weather_cache:
            state = self._weather_cache[area_id]
            # Check if weather should have changed
            if state.next_change_at and time.time() >= state.next_change_at:
                return self.advance_weather(area_id)
            return state

        # Initialize weather for this area
        return self._initialize_area_weather(area_id)

    def _initialize_area_weather(self, area_id: "AreaId") -> WeatherState:
        """Initialize weather for an area that doesn't have cached state."""
        area = self.world.areas.get(area_id)

        # Default to clear weather for immune areas
        if area and self._is_weather_immune(area):
            state = WeatherState(
                weather_type=WeatherType.CLEAR,
                intensity=WeatherIntensity.MODERATE,
                started_at=time.time(),
                duration=86400,  # 24 hours - effectively permanent
                next_change_at=None,  # Never changes
            )
            self._weather_cache[area_id] = state
            return state

        # Select initial weather based on climate/patterns
        weather_type = self._select_weather_type(area)
        intensity = self._select_intensity(weather_type)
        duration = self._calculate_duration(weather_type)

        state = WeatherState(
            weather_type=weather_type,
            intensity=intensity,
            started_at=time.time(),
            duration=duration,
            next_change_at=time.time() + duration,
        )
        self._weather_cache[area_id] = state

        logger.debug(
            f"Initialized weather for {area_id}: {weather_type.value} ({intensity.value})"
        )
        return state

    def advance_weather(self, area_id: "AreaId") -> WeatherState:
        """
        Advance weather to the next state for an area.

        Uses Markov chain transitions combined with area weather patterns.
        Has a chance to persist (repeat) current weather instead of changing.

        Args:
            area_id: ID of the area

        Returns:
            New WeatherState
        """
        area = self.world.areas.get(area_id)

        # Immune areas stay clear
        if area and self._is_weather_immune(area):
            if area_id not in self._weather_cache:
                return self._initialize_area_weather(area_id)
            return self._weather_cache[area_id]

        current_state = self._weather_cache.get(area_id)
        current_type = current_state.weather_type if current_state else WeatherType.CLEAR
        current_intensity = current_state.intensity if current_state else WeatherIntensity.MODERATE

        # Check for weather persistence - chance to repeat current weather
        if random.random() < WEATHER_PERSIST_CHANCE:
            # Weather persists - same type, possibly different intensity/duration
            next_type = current_type
            # Slight chance to shift intensity when persisting
            if random.random() < 0.3:
                intensity = self._select_intensity(next_type)
            else:
                intensity = current_intensity
            duration = self._calculate_duration(next_type)
            
            new_state = WeatherState(
                weather_type=next_type,
                intensity=intensity,
                started_at=time.time(),
                duration=duration,
                next_change_at=time.time() + duration,
            )
            self._weather_cache[area_id] = new_state
            
            logger.debug(
                f"Weather persisted in {area_id}: {next_type.value} ({intensity.value})"
            )
            return new_state

        # Normal weather transition using Markov chain
        # Get transition probabilities
        transitions = WEATHER_TRANSITIONS.get(
            current_type.value, WEATHER_TRANSITIONS["clear"]
        )

        # Blend with area's weather patterns
        patterns = self._get_weather_patterns(area)
        blended = self._blend_probabilities(transitions, patterns)

        # Select next weather type
        next_type_str = self._weighted_random_choice(blended)
        next_type = WeatherType(next_type_str)

        # Determine intensity
        intensity = self._select_intensity(next_type)

        # Calculate duration
        duration = self._calculate_duration(next_type)

        # Create new state
        new_state = WeatherState(
            weather_type=next_type,
            intensity=intensity,
            started_at=time.time(),
            duration=duration,
            next_change_at=time.time() + duration,
        )
        self._weather_cache[area_id] = new_state

        logger.debug(
            f"Weather changed in {area_id}: {current_type.value} -> {next_type.value} ({intensity.value})"
        )
        return new_state

    def get_forecast(self, area_id: "AreaId") -> WeatherForecast:
        """
        Get a weather forecast for an area.

        Args:
            area_id: ID of the area

        Returns:
            WeatherForecast with current weather and prediction
        """
        current = self.get_current_weather(area_id)

        # Predict next weather based on transition probabilities
        area = self.world.areas.get(area_id)
        transitions = WEATHER_TRANSITIONS.get(
            current.weather_type.value, WEATHER_TRANSITIONS["clear"]
        )
        patterns = self._get_weather_patterns(area)
        blended = self._blend_probabilities(transitions, patterns)

        # Get most likely next weather
        likely_next_str = max(blended.keys(), key=lambda k: blended[k])
        likely_next = WeatherType(likely_next_str)

        # Time until change (convert to minutes)
        change_in_minutes = current.time_remaining // 60

        return WeatherForecast(
            current=current,
            likely_next=likely_next,
            change_in_minutes=change_in_minutes,
        )

    def get_weather_effects(
        self, area_id: "AreaId"
    ) -> dict[str, Any]:
        """
        Get the gameplay effects of current weather.

        Args:
            area_id: ID of the area

        Returns:
            Dict with visibility_modifier, temperature_modifier, etc.
        """
        state = self.get_current_weather(area_id)
        base_effects = WEATHER_EFFECTS.get(
            state.weather_type.value, WEATHER_EFFECTS["clear"]
        )

        # Apply intensity multiplier
        multiplier = INTENSITY_MULTIPLIERS[state.intensity]

        return {
            "visibility_modifier": int(base_effects["visibility_modifier"] * multiplier),
            "temperature_modifier": int(base_effects["temperature_modifier"] * multiplier),
            "movement_modifier": 1.0 - (1.0 - base_effects["movement_modifier"]) * multiplier,
            "ranged_penalty": int(base_effects["ranged_penalty"] * multiplier),
            "casting_penalty": int(base_effects["casting_penalty"] * multiplier),
            "message": base_effects["message"],
            "weather_type": state.weather_type.value,
            "intensity": state.intensity.value,
        }

    def format_weather_display(
        self, area_id: "AreaId", include_effects: bool = False
    ) -> str:
        """
        Format weather for display to players.

        Args:
            area_id: ID of the area
            include_effects: Whether to include gameplay effects

        Returns:
            Formatted string like "☀️ Clear skies" or "🌧️ Heavy rain"
        """
        state = self.get_current_weather(area_id)
        display = WEATHER_DISPLAY.get(
            state.weather_type, WEATHER_DISPLAY[WeatherType.CLEAR]
        )

        # Get intensity-specific description if available
        intensity_desc = INTENSITY_DESCRIPTORS.get(state.intensity, {})
        desc = intensity_desc.get(state.weather_type, display["desc"])

        # Format based on intensity
        if state.intensity == WeatherIntensity.LIGHT:
            result = f"{display['icon']} Light {display['name'].lower()}"
        elif state.intensity == WeatherIntensity.HEAVY:
            result = f"{display['icon']} {desc.capitalize()}"
        else:
            result = f"{display['icon']} {display['name']}"

        if include_effects:
            effects = self.get_weather_effects(area_id)
            if effects["message"]:
                result += f"\n{effects['message']}"

        return result

    def should_show_weather(self, area_id: "AreaId") -> bool:
        """
        Determine if weather should be shown in room description.

        Only show for non-clear weather or if effects are significant.

        Args:
            area_id: ID of the area

        Returns:
            True if weather should be displayed
        """
        state = self.get_current_weather(area_id)
        # Don't show for clear weather unless heavy wind
        if state.weather_type == WeatherType.CLEAR:
            return False
        if state.weather_type == WeatherType.CLOUDY and state.intensity == WeatherIntensity.LIGHT:
            return False
        return True

    def check_weather_condition(
        self,
        area_id: "AreaId",
        condition_type: str,
        weather_type: str | None = None,
        intensity: str | None = None,
    ) -> bool:
        """
        Check weather conditions for triggers.

        Supports:
        - weather_is: Check if current weather matches type
        - weather_intensity: Check if intensity matches

        Args:
            area_id: Area to check
            condition_type: "weather_is" or "weather_intensity"
            weather_type: Expected weather type (for weather_is)
            intensity: Expected intensity (for weather_intensity)

        Returns:
            True if condition is met
        """
        state = self.get_current_weather(area_id)

        if condition_type == "weather_is" and weather_type:
            return state.weather_type.value == weather_type.lower()
        elif condition_type == "weather_intensity" and intensity:
            return state.intensity.value == intensity.lower()
        elif condition_type == "weather_not" and weather_type:
            return state.weather_type.value != weather_type.lower()

        return False

    def set_weather(
        self,
        area_id: "AreaId",
        weather_type: str,
        intensity: str = "moderate",
        duration: int | None = None,
    ) -> WeatherState:
        """
        Manually set weather for an area (admin/trigger use).

        Args:
            area_id: ID of the area
            weather_type: Weather type to set
            intensity: Intensity level
            duration: Duration in seconds (None = use default)

        Returns:
            New WeatherState
        """
        try:
            w_type = WeatherType(weather_type.lower())
        except ValueError:
            w_type = WeatherType.CLEAR

        try:
            w_intensity = WeatherIntensity(intensity.lower())
        except ValueError:
            w_intensity = WeatherIntensity.MODERATE

        if duration is None:
            duration = self._calculate_duration(w_type)

        state = WeatherState(
            weather_type=w_type,
            intensity=w_intensity,
            started_at=time.time(),
            duration=duration,
            next_change_at=time.time() + duration,
        )
        self._weather_cache[area_id] = state

        logger.info(f"Weather manually set in {area_id}: {weather_type} ({intensity})")
        return state

    # ---------- Private Helper Methods ----------

    def _is_weather_immune(self, area: "WorldArea | None") -> bool:
        """Check if an area is immune to weather effects."""
        if area is None:
            return False

        # Check explicit immunity flag
        if getattr(area, "weather_immunity", False):
            return True

        # Check biome
        biome = getattr(area, "biome", "").lower()
        return biome in WEATHER_IMMUNE_BIOMES

    def _get_weather_patterns(self, area: "WorldArea | None") -> dict[str, float]:
        """Get weather patterns for an area, falling back to climate defaults."""
        if area is None:
            return CLIMATE_WEATHER_PATTERNS.get("mild", {})

        # Check for custom patterns
        patterns = getattr(area, "weather_patterns", None)
        if patterns and isinstance(patterns, dict):
            return patterns

        # Fall back to climate-based patterns
        climate = getattr(area, "climate", "mild").lower()
        return CLIMATE_WEATHER_PATTERNS.get(climate, CLIMATE_WEATHER_PATTERNS["mild"])

    def _select_weather_type(self, area: "WorldArea | None") -> WeatherType:
        """Select a weather type based on area patterns."""
        patterns = self._get_weather_patterns(area)
        selected = self._weighted_random_choice(patterns)
        try:
            return WeatherType(selected)
        except ValueError:
            return WeatherType.CLEAR

    def _select_intensity(self, weather_type: WeatherType) -> WeatherIntensity:
        """Select an intensity level for a weather type."""
        # Clear/cloudy/overcast are always moderate
        if weather_type in (WeatherType.CLEAR, WeatherType.CLOUDY, WeatherType.OVERCAST):
            return WeatherIntensity.MODERATE

        # Other weather types vary
        roll = random.random()
        if roll < 0.3:
            return WeatherIntensity.LIGHT
        elif roll < 0.8:
            return WeatherIntensity.MODERATE
        else:
            return WeatherIntensity.HEAVY

    def _calculate_duration(self, weather_type: WeatherType) -> int:
        """Calculate duration in seconds for a weather type."""
        duration_range = WEATHER_DURATION_RANGES.get(
            weather_type.value, (2, 6)
        )
        # Duration is in game hours, convert to real seconds
        # 1 game hour = 30 real seconds (from world.py REAL_SECONDS_PER_GAME_HOUR)
        game_hours = random.randint(duration_range[0], duration_range[1])
        real_seconds = int(game_hours * 30)
        # Minimum 30 seconds (1 game hour), no maximum - let weather persist naturally
        return max(30, real_seconds)

    def _blend_probabilities(
        self,
        transitions: dict[str, float],
        patterns: dict[str, float],
        transition_weight: float = 0.6,
    ) -> dict[str, float]:
        """
        Blend transition probabilities with area weather patterns.

        Args:
            transitions: Markov chain transition probabilities
            patterns: Area-specific weather patterns
            transition_weight: How much to weight transitions (0-1)

        Returns:
            Blended probability dict
        """
        pattern_weight = 1.0 - transition_weight
        blended: dict[str, float] = {}

        # Get all possible weather types
        all_types = set(transitions.keys()) | set(patterns.keys())

        for w_type in all_types:
            trans_prob = transitions.get(w_type, 0.0)
            pattern_prob = patterns.get(w_type, 0.0)
            blended[w_type] = trans_prob * transition_weight + pattern_prob * pattern_weight

        # Normalize
        total = sum(blended.values())
        if total > 0:
            blended = {k: v / total for k, v in blended.items()}

        return blended

    def _weighted_random_choice(self, weights: dict[str, float]) -> str:
        """Select a random item based on weights."""
        if not weights:
            return "clear"

        items = list(weights.keys())
        probs = list(weights.values())

        # Normalize probabilities
        total = sum(probs)
        if total <= 0:
            return items[0] if items else "clear"

        probs = [p / total for p in probs]

        return random.choices(items, weights=probs, k=1)[0]

    def tick_all_areas(self) -> list[tuple[str, WeatherState, WeatherState | None]]:
        """
        Check and advance weather for all areas.

        Called periodically by the game engine.

        Returns:
            List of (area_id, new_state, old_state) for areas that changed
        """
        changes: list[tuple[str, WeatherState, WeatherState | None]] = []
        current_time = time.time()

        for area_id in self.world.areas:
            if area_id not in self._weather_cache:
                new_state = self._initialize_area_weather(area_id)
                changes.append((area_id, new_state, None))
            else:
                state = self._weather_cache[area_id]
                if state.next_change_at and current_time >= state.next_change_at:
                    old_state = state
                    new_state = self.advance_weather(area_id)
                    changes.append((area_id, new_state, old_state))

        return changes
