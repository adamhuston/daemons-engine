"""
Phase 17.3: Biome Coherence and Season System

Manages biome definitions, seasonal progression, and environmental coherence.

Biomes define:
- Temperature ranges and seasonal modifiers
- Weather patterns and seasonal variations
- Flora/fauna compatibility tags (for Phase 17.4-17.5)
- Gameplay modifiers (danger, movement, visibility)

Seasons cycle through:
- SPRING: Warming temperatures, increased rain, new growth
- SUMMER: Peak temperatures, stable weather, active fauna
- FALL: Cooling temperatures, harvest time, migration begins
- WINTER: Cold temperatures, snow/frost, reduced activity

The system is designed for extensibility:
- Flora spawning uses flora_tags for compatibility
- Fauna spawning uses fauna_tags for compatibility
- Predator/prey dynamics use fauna_tags["predator"/"prey"]
- Seasonal spawning uses spawn_modifiers and season checks
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from daemons.engine.world import AreaId, World, WorldArea

logger = logging.getLogger(__name__)


class Season(Enum):
    """Four seasons that cycle throughout the year."""

    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"
    WINTER = "winter"


# Season order for cycling
SEASON_ORDER = [Season.SPRING, Season.SUMMER, Season.FALL, Season.WINTER]

# Default seasonal temperature modifiers (Fahrenheit)
DEFAULT_SEASONAL_TEMPERATURE_MODIFIERS = {
    Season.SPRING: -5,
    Season.SUMMER: +10,
    Season.FALL: -5,
    Season.WINTER: -25,
}

# Default seasonal weather modifiers (adjustments to base probabilities)
DEFAULT_SEASONAL_WEATHER_MODIFIERS = {
    Season.SPRING: {"rain": +0.10, "clear": -0.05},
    Season.SUMMER: {"clear": +0.15, "rain": -0.05},
    Season.FALL: {"fog": +0.10, "cloudy": +0.05, "clear": -0.10},
    Season.WINTER: {"snow": +0.25, "rain": -0.15, "clear": -0.05},
}

# Biomes that are season-immune (always the same season)
SEASON_IMMUNE_BIOMES = {
    "underground",
    "cave",
    "ethereal",
    "void",
    "planar",
}


@dataclass
class BiomeDefinition:
    """
    Complete definition of a biome loaded from YAML.

    This is the central data structure for biome coherence.
    All environmental systems reference this for compatibility.
    """

    id: str
    name: str
    description: str

    # Environmental ranges
    temperature_range: tuple[int, int] = (50, 80)  # (min, max) Fahrenheit
    climate_types: list[str] = field(default_factory=lambda: ["temperate"])

    # Weather configuration
    weather_patterns: dict[str, float] = field(
        default_factory=lambda: {"clear": 0.4, "cloudy": 0.3, "rain": 0.2, "storm": 0.1}
    )
    seasonal_weather_modifiers: dict[str, dict[str, float]] = field(
        default_factory=dict
    )

    # Seasonal modifiers
    seasonal_temperature_modifiers: dict[str, int] = field(default_factory=dict)
    seasonal_descriptions: dict[str, str] = field(default_factory=dict)

    # Flora/fauna compatibility (Phase 17.4-17.5)
    flora_tags: list[str] = field(default_factory=list)
    fauna_tags: list[str] = field(default_factory=list)

    # Spawn modifiers (Phase 17.5-17.6)
    spawn_modifiers: dict[str, Any] = field(default_factory=dict)

    # Gameplay modifiers
    danger_modifier: int = 0
    magic_affinity: str = "low"
    movement_modifier: float = 1.0
    visibility_modifier: float = 1.0

    # Transition rules
    adjacent_biomes: list[str] = field(default_factory=list)
    transition_zones: dict[str, dict] = field(default_factory=dict)


@dataclass
class SeasonState:
    """Current season state for an area."""

    season: Season
    season_day: int  # Day within current season (1 to days_per_season)
    days_per_season: int
    is_locked: bool  # If True, season never changes
    days_until_change: int  # Days until next season

    @property
    def progress_percent(self) -> float:
        """Percentage through current season (0.0 to 1.0)."""
        return self.season_day / self.days_per_season


class BiomeSystem:
    """
    Manages biome definitions and area-biome coherence.

    Responsibilities:
    - Load biome definitions from YAML files
    - Validate area configurations against biome requirements
    - Provide biome-specific modifiers to other systems
    - Support flora/fauna compatibility queries
    """

    def __init__(self, world: "World", world_data_path: str | None = None):
        self.world = world
        self._biomes: dict[str, BiomeDefinition] = {}

        # Determine world_data path
        if world_data_path is None:
            # Go up from systems/ to engine/ to daemons/, then into world_data/
            world_data_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "world_data"
            )
        self._biome_path = os.path.join(world_data_path, "biomes")

        # Load biome definitions
        self._load_biomes()
        logger.info(f"BiomeSystem initialized with {len(self._biomes)} biomes")

    def _load_biomes(self) -> None:
        """Load all biome definitions from YAML files."""
        if not os.path.isdir(self._biome_path):
            logger.warning(f"Biome directory not found: {self._biome_path}")
            return

        for filename in os.listdir(self._biome_path):
            if filename.endswith(".yaml") and not filename.startswith("_"):
                filepath = os.path.join(self._biome_path, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    # Support both "id" and "biome_id" keys
                    if data and ("id" in data or "biome_id" in data):
                        biome = self._parse_biome(data)
                        self._biomes[biome.id] = biome
                        logger.debug(f"Loaded biome: {biome.id}")
                except Exception as e:
                    logger.error(f"Failed to load biome from {filename}: {e}")

    def _parse_biome(self, data: dict) -> BiomeDefinition:
        """Parse a biome definition from YAML data."""
        # Support both "id" and "biome_id" keys
        biome_id = data.get("id") or data.get("biome_id")
        temp_data = data.get("temperature", {})
        temp_range = data.get("temperature_range", [
            temp_data.get("base_min", 50),
            temp_data.get("base_max", 80)
        ])
        return BiomeDefinition(
            id=biome_id,
            name=data.get("name", biome_id),
            description=data.get("description", ""),
            temperature_range=(temp_range[0], temp_range[1]),
            climate_types=data.get("climate_types", ["temperate"]),
            weather_patterns=data.get(
                "weather_patterns",
                {"clear": 0.4, "cloudy": 0.3, "rain": 0.2, "storm": 0.1},
            ),
            seasonal_weather_modifiers=data.get("seasonal_weather_modifiers", {}),
            seasonal_temperature_modifiers=data.get(
                "seasonal_temperature_modifiers", {}
            ),
            seasonal_descriptions=data.get("seasonal_descriptions", {}),
            flora_tags=data.get("flora_tags", []),
            fauna_tags=data.get("fauna_tags", []),
            spawn_modifiers=data.get("spawn_modifiers", {}),
            danger_modifier=data.get("danger_modifier", 0),
            magic_affinity=data.get("magic_affinity", "low"),
            movement_modifier=data.get("movement_modifier", 1.0),
            visibility_modifier=data.get("visibility_modifier", 1.0),
            adjacent_biomes=data.get("adjacent_biomes", []),
            transition_zones=data.get("transition_zones", {}),
        )

    def get_biome(self, biome_id: str) -> BiomeDefinition | None:
        """Get a biome definition by ID."""
        # Try exact match first
        if biome_id in self._biomes:
            return self._biomes[biome_id]
        # Try with biome_ prefix
        prefixed = f"biome_{biome_id}"
        if prefixed in self._biomes:
            return self._biomes[prefixed]
        return None

    def get_biome_for_area(self, area: "WorldArea") -> BiomeDefinition | None:
        """Get the biome definition for an area based on its biome field."""
        if not area.biome:
            return None
        return self.get_biome(area.biome)

    def get_all_biomes(self) -> list[BiomeDefinition]:
        """Get all loaded biome definitions."""
        return list(self._biomes.values())

    # ========== Validation Methods ==========

    def validate_area(self, area: "WorldArea") -> list[str]:
        """
        Validate an area's configuration against its biome.

        Returns list of warning messages (empty if valid).
        """
        warnings = []
        biome = self.get_biome_for_area(area)

        if not biome:
            # No biome defined or biome not found
            if area.biome and area.biome not in SEASON_IMMUNE_BIOMES:
                warnings.append(
                    f"Unknown biome '{area.biome}' for area '{area.id}'"
                )
            return warnings

        # Check temperature range
        if hasattr(area, "base_temperature"):
            min_temp, max_temp = biome.temperature_range
            if area.base_temperature < min_temp - 20:
                warnings.append(
                    f"Area '{area.id}' base_temperature ({area.base_temperature}°F) "
                    f"is very low for biome '{biome.name}' (expected {min_temp}-{max_temp}°F)"
                )
            elif area.base_temperature > max_temp + 20:
                warnings.append(
                    f"Area '{area.id}' base_temperature ({area.base_temperature}°F) "
                    f"is very high for biome '{biome.name}' (expected {min_temp}-{max_temp}°F)"
                )

        # Check climate compatibility
        if hasattr(area, "climate") and area.climate:
            if area.climate.lower() not in [c.lower() for c in biome.climate_types]:
                warnings.append(
                    f"Area '{area.id}' climate '{area.climate}' "
                    f"is unusual for biome '{biome.name}' (expected: {biome.climate_types})"
                )

        return warnings

    def validate_all_areas(self) -> dict[str, list[str]]:
        """Validate all areas in the world. Returns dict of area_id -> warnings."""
        results = {}
        for area_id, area in self.world.areas.items():
            warnings = self.validate_area(area)
            if warnings:
                results[area_id] = warnings
        return results

    # ========== Flora/Fauna Compatibility (Phase 17.4-17.5) ==========

    def get_compatible_flora_tags(self, area: "WorldArea") -> set[str]:
        """
        Get all flora tags compatible with an area.

        Combines:
        1. Area's explicit flora_tags
        2. Biome's default flora_tags
        """
        tags = set(area.flora_tags or [])

        biome = self.get_biome_for_area(area)
        if biome:
            tags.update(biome.flora_tags)

        return tags

    def get_compatible_fauna_tags(self, area: "WorldArea") -> set[str]:
        """
        Get all fauna tags compatible with an area.

        Combines:
        1. Area's explicit fauna_tags
        2. Biome's default fauna_tags
        """
        tags = set(area.fauna_tags or [])

        biome = self.get_biome_for_area(area)
        if biome:
            tags.update(biome.fauna_tags)

        return tags

    def is_flora_compatible(
        self, area: "WorldArea", flora_tags: list[str]
    ) -> bool:
        """Check if a flora item is compatible with an area."""
        if not flora_tags:
            return True  # No requirements = compatible everywhere

        area_tags = self.get_compatible_flora_tags(area)
        return bool(set(flora_tags) & area_tags)

    def is_fauna_compatible(
        self, area: "WorldArea", fauna_tags: list[str]
    ) -> bool:
        """Check if a fauna NPC is compatible with an area."""
        if not fauna_tags:
            return True  # No requirements = compatible everywhere

        area_tags = self.get_compatible_fauna_tags(area)
        return bool(set(fauna_tags) & area_tags)

    # ========== Spawn Modifiers (Phase 17.5-17.6) ==========

    def get_spawn_modifier(
        self, area: "WorldArea", modifier_key: str, season: Season | None = None
    ) -> float:
        """
        Get a spawn modifier for an area, optionally for a specific season.

        Args:
            area: The area to check
            modifier_key: Key like "fauna_spawn_multiplier", "flora_growth_rate"
            season: Optional season for seasonal modifiers

        Returns:
            Modifier value (default 1.0 if not specified)
        """
        biome = self.get_biome_for_area(area)
        if not biome or not biome.spawn_modifiers:
            return 1.0

        # Check for season-specific modifier first
        if season:
            season_key = season.value
            if season_key in biome.spawn_modifiers:
                season_mods = biome.spawn_modifiers[season_key]
                if isinstance(season_mods, dict) and modifier_key in season_mods:
                    return float(season_mods[modifier_key])

        # Fall back to base modifier
        if modifier_key in biome.spawn_modifiers:
            return float(biome.spawn_modifiers[modifier_key])

        return 1.0

    # ========== Gameplay Modifiers ==========

    def get_movement_modifier(self, area: "WorldArea") -> float:
        """Get movement speed modifier for an area."""
        biome = self.get_biome_for_area(area)
        if biome:
            return biome.movement_modifier
        return 1.0

    def get_visibility_modifier(self, area: "WorldArea") -> float:
        """Get visibility range modifier for an area."""
        biome = self.get_biome_for_area(area)
        if biome:
            return biome.visibility_modifier
        return 1.0

    def get_danger_modifier(self, area: "WorldArea") -> int:
        """Get danger level modifier for an area."""
        biome = self.get_biome_for_area(area)
        if biome:
            return biome.danger_modifier
        return 0


class SeasonSystem:
    """
    Manages seasonal progression and seasonal effects.

    Responsibilities:
    - Track current season per area
    - Advance seasons as game time passes
    - Provide seasonal modifiers to temperature/weather
    - Support season-based spawn conditions
    """

    def __init__(self, world: "World", biome_system: BiomeSystem | None = None):
        self.world = world
        self.biome_system = biome_system
        logger.info("SeasonSystem initialized")

    def get_season(self, area: "WorldArea") -> Season:
        """Get the current season for an area."""
        season_str = area.current_season.lower()
        try:
            return Season(season_str)
        except ValueError:
            return Season.SUMMER  # Default fallback

    def get_season_state(self, area: "WorldArea") -> SeasonState:
        """Get full season state for an area."""
        season = self.get_season(area)
        days_per_season = area.days_per_season
        season_day = min(area.season_day, days_per_season)
        days_until_change = days_per_season - season_day

        return SeasonState(
            season=season,
            season_day=season_day,
            days_per_season=days_per_season,
            is_locked=area.season_locked,
            days_until_change=days_until_change,
        )

    def get_next_season(self, current: Season) -> Season:
        """Get the next season in the cycle."""
        idx = SEASON_ORDER.index(current)
        return SEASON_ORDER[(idx + 1) % len(SEASON_ORDER)]

    def advance_day(self, area: "WorldArea") -> bool:
        """
        Advance the season day for an area.

        Called when a game day passes.
        Returns True if season changed.
        """
        if area.season_locked:
            return False

        # Check for season-immune biomes
        if area.biome and area.biome.lower() in SEASON_IMMUNE_BIOMES:
            return False

        area.season_day += 1

        if area.season_day > area.days_per_season:
            # Advance to next season
            current = self.get_season(area)
            next_season = self.get_next_season(current)
            area.current_season = next_season.value
            area.season_day = 1
            logger.info(
                f"Season changed in {area.id}: {current.value} -> {next_season.value}"
            )
            return True

        return False

    # ========== Seasonal Temperature Modifiers ==========

    def get_temperature_modifier(self, area: "WorldArea") -> int:
        """
        Get temperature modifier for the current season.

        Checks biome-specific modifiers first, falls back to defaults.
        """
        season = self.get_season(area)

        # Check for biome-specific seasonal modifiers
        if self.biome_system:
            biome = self.biome_system.get_biome_for_area(area)
            if biome and biome.seasonal_temperature_modifiers:
                if season.value in biome.seasonal_temperature_modifiers:
                    return biome.seasonal_temperature_modifiers[season.value]

        # Fall back to defaults
        return DEFAULT_SEASONAL_TEMPERATURE_MODIFIERS.get(season, 0)

    # ========== Seasonal Weather Modifiers ==========

    def get_weather_modifiers(self, area: "WorldArea") -> dict[str, float]:
        """
        Get weather probability modifiers for the current season.

        Returns dict of weather_type -> adjustment (+/- probability).
        """
        season = self.get_season(area)

        # Check for biome-specific seasonal weather modifiers
        if self.biome_system:
            biome = self.biome_system.get_biome_for_area(area)
            if biome and biome.seasonal_weather_modifiers:
                if season.value in biome.seasonal_weather_modifiers:
                    return biome.seasonal_weather_modifiers[season.value]

        # Fall back to defaults
        return DEFAULT_SEASONAL_WEATHER_MODIFIERS.get(season, {})

    # ========== Seasonal Descriptions ==========

    def get_seasonal_description(self, area: "WorldArea") -> str | None:
        """Get seasonal flavor text for an area's biome."""
        if not self.biome_system:
            return None

        biome = self.biome_system.get_biome_for_area(area)
        if not biome or not biome.seasonal_descriptions:
            return None

        season = self.get_season(area)
        return biome.seasonal_descriptions.get(season.value)

    # ========== Condition Checks (for triggers) ==========

    def check_season_condition(
        self, area: "WorldArea", expected_season: str
    ) -> bool:
        """Check if area's current season matches expected."""
        current = self.get_season(area)
        return current.value == expected_season.lower()

    def is_season_transition(self, area: "WorldArea", days_remaining: int = 3) -> bool:
        """Check if season is about to change (within N days)."""
        state = self.get_season_state(area)
        if state.is_locked:
            return False
        return state.days_until_change <= days_remaining

    # ========== Display Formatting ==========

    def format_season_display(self, area: "WorldArea") -> str:
        """Format season for display to players."""
        state = self.get_season_state(area)

        # Season icons
        icons = {
            Season.SPRING: "🌱",
            Season.SUMMER: "☀️",
            Season.FALL: "🍂",
            Season.WINTER: "❄️",
        }

        icon = icons.get(state.season, "🌍")
        name = state.season.value.title()

        if state.is_locked:
            return f"{icon} Eternal {name}"

        return f"{icon} {name} (Day {state.season_day}/{state.days_per_season})"

    def should_show_season(self, area: "WorldArea") -> bool:
        """Determine if season should be shown in area description."""
        # Don't show for season-immune biomes
        if area.biome and area.biome.lower() in SEASON_IMMUNE_BIOMES:
            return False
        return True
