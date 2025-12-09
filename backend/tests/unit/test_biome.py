"""
Unit tests for the Biome and Season System (Phase 17.3).

Tests BiomeSystem loading, season progression, seasonal modifiers,
trigger conditions, and integration with temperature/weather.
"""

import pytest

from daemons.engine.systems.biome import (
    BiomeDefinition,
    BiomeSystem,
    Season,
    SeasonState,
    SeasonSystem,
    SEASON_ORDER,
    SEASON_IMMUNE_BIOMES,
    DEFAULT_SEASONAL_TEMPERATURE_MODIFIERS,
)
from daemons.engine.world import World, WorldArea, WorldRoom, WorldTime


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_world_time() -> WorldTime:
    """Create a mock WorldTime for testing."""
    return WorldTime(day=1, hour=12, minute=0)


@pytest.fixture
def mock_world_with_biomes(mock_world_time: WorldTime) -> World:
    """Create World with areas using various biomes for testing."""
    world = World(rooms={}, players={})

    # Create test areas with different biomes and seasons
    forest_area = WorldArea(
        id="area_forest",
        name="Whispering Woods",
        description="A temperate forest",
        area_time=mock_world_time,
        biome="temperate",
        base_temperature=70,
        current_season="spring",
        days_per_season=7,
        season_day=1,
        season_locked=False,
    )

    desert_area = WorldArea(
        id="area_desert",
        name="Scorching Sands",
        description="A harsh desert",
        area_time=mock_world_time,
        biome="desert",
        base_temperature=95,
        current_season="summer",
        days_per_season=7,
        season_day=3,
        season_locked=False,
    )

    arctic_area = WorldArea(
        id="area_arctic",
        name="Frozen Wastes",
        description="A frozen tundra",
        area_time=mock_world_time,
        biome="arctic",
        base_temperature=10,
        current_season="winter",
        days_per_season=10,
        season_day=5,
        season_locked=False,
    )

    underground_area = WorldArea(
        id="area_underground",
        name="Deep Caverns",
        description="Underground tunnels",
        area_time=mock_world_time,
        biome="underground",
        base_temperature=55,
        current_season="spring",  # Seasons have minimal effect underground
        days_per_season=7,
        season_day=1,
        season_locked=False,
    )

    locked_area = WorldArea(
        id="area_locked",
        name="Eternal Summer",
        description="A magical place of eternal summer",
        area_time=mock_world_time,
        biome="temperate",
        base_temperature=75,
        current_season="summer",
        days_per_season=7,
        season_day=1,
        season_locked=True,
    )

    world.areas = {
        "area_forest": forest_area,
        "area_desert": desert_area,
        "area_arctic": arctic_area,
        "area_underground": underground_area,
        "area_locked": locked_area,
    }

    # Create rooms in each area
    world.rooms["room_forest"] = WorldRoom(
        id="room_forest",
        name="Forest Clearing",
        description="A peaceful clearing",
        room_type="forest",
        area_id="area_forest",
    )

    world.rooms["room_desert"] = WorldRoom(
        id="room_desert",
        name="Sand Dunes",
        description="Endless sand dunes",
        room_type="desert",
        area_id="area_desert",
    )

    world.rooms["room_arctic"] = WorldRoom(
        id="room_arctic",
        name="Frozen Plain",
        description="A windswept frozen plain",
        room_type="arctic",
        area_id="area_arctic",
    )

    world.rooms["room_underground"] = WorldRoom(
        id="room_underground",
        name="Deep Cavern",
        description="A cavern deep underground",
        room_type="cave",
        area_id="area_underground",
    )

    return world


@pytest.fixture
def biome_system(mock_world_with_biomes: World) -> BiomeSystem:
    """Create a BiomeSystem with the mock world."""
    return BiomeSystem(mock_world_with_biomes)


@pytest.fixture
def season_system(mock_world_with_biomes: World, biome_system: BiomeSystem) -> SeasonSystem:
    """Create a SeasonSystem with the mock world and biome system."""
    return SeasonSystem(mock_world_with_biomes, biome_system)


# ============================================================================
# Season Enum Tests
# ============================================================================


class TestSeasonEnum:
    """Tests for the Season enumeration."""

    def test_season_values(self):
        """Verify all expected season values exist."""
        assert Season.SPRING.value == "spring"
        assert Season.SUMMER.value == "summer"
        assert Season.FALL.value == "fall"
        assert Season.WINTER.value == "winter"

    def test_season_count(self):
        """Verify exactly 4 seasons exist."""
        assert len(Season) == 4

    def test_season_order(self):
        """Verify season order is correct."""
        assert SEASON_ORDER == [
            Season.SPRING,
            Season.SUMMER,
            Season.FALL,
            Season.WINTER,
        ]


# ============================================================================
# BiomeDefinition Tests
# ============================================================================


class TestBiomeDefinition:
    """Tests for BiomeDefinition dataclass."""

    def test_biome_definition_creation(self):
        """Test creating a BiomeDefinition."""
        biome = BiomeDefinition(
            id="test_forest",
            name="Test Forest",
            description="A test forest biome",
            temperature_range=(40, 85),
        )
        assert biome.id == "test_forest"
        assert biome.name == "Test Forest"
        assert biome.temperature_range == (40, 85)

    def test_biome_definition_defaults(self):
        """Test BiomeDefinition default values."""
        biome = BiomeDefinition(
            id="test",
            name="Test",
            description="Test description",
        )
        assert biome.temperature_range == (50, 80)
        assert biome.movement_modifier == 1.0
        assert biome.visibility_modifier == 1.0
        assert biome.danger_modifier == 0
        assert biome.flora_tags == []
        assert biome.fauna_tags == []


# ============================================================================
# SeasonState Tests
# ============================================================================


class TestSeasonState:
    """Tests for SeasonState dataclass."""

    def test_season_state_creation(self):
        """Test creating a SeasonState."""
        state = SeasonState(
            season=Season.SUMMER,
            season_day=3,
            days_per_season=7,
            is_locked=False,
            days_until_change=4,
        )
        assert state.season == Season.SUMMER
        assert state.season_day == 3
        assert state.days_per_season == 7
        assert state.is_locked is False
        assert state.days_until_change == 4

    def test_progress_percent(self):
        """Test progress_percent calculation."""
        state = SeasonState(
            season=Season.SPRING,
            season_day=5,
            days_per_season=10,
            is_locked=False,
            days_until_change=5,
        )
        assert state.progress_percent == 0.5

    def test_progress_percent_start(self):
        """Test progress_percent at season start."""
        state = SeasonState(
            season=Season.SPRING,
            season_day=1,
            days_per_season=10,
            is_locked=False,
            days_until_change=9,
        )
        assert state.progress_percent == 0.1


# ============================================================================
# SeasonSystem Tests
# ============================================================================


class TestSeasonSystem:
    """Tests for the SeasonSystem class."""

    def test_get_season(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test getting current season for an area."""
        area = mock_world_with_biomes.areas["area_forest"]
        season = season_system.get_season(area)
        assert season == Season.SPRING

    def test_get_season_summer(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test getting summer season."""
        area = mock_world_with_biomes.areas["area_desert"]
        season = season_system.get_season(area)
        assert season == Season.SUMMER

    def test_get_season_winter(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test getting winter season."""
        area = mock_world_with_biomes.areas["area_arctic"]
        season = season_system.get_season(area)
        assert season == Season.WINTER

    def test_get_season_state(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test getting full season state."""
        area = mock_world_with_biomes.areas["area_forest"]
        state = season_system.get_season_state(area)
        assert state.season == Season.SPRING
        assert state.season_day == 1
        assert state.days_per_season == 7
        assert state.is_locked is False

    def test_get_next_season(self, season_system: SeasonSystem):
        """Test getting next season in cycle."""
        assert season_system.get_next_season(Season.SPRING) == Season.SUMMER
        assert season_system.get_next_season(Season.SUMMER) == Season.FALL
        assert season_system.get_next_season(Season.FALL) == Season.WINTER
        assert season_system.get_next_season(Season.WINTER) == Season.SPRING

    def test_advance_day_no_change(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test advancing day without season change."""
        area = mock_world_with_biomes.areas["area_forest"]
        initial_day = area.season_day
        initial_season = area.current_season

        changed = season_system.advance_day(area)

        assert changed is False
        assert area.season_day == initial_day + 1
        assert area.current_season == initial_season

    def test_advance_day_season_change(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test advancing day with season change."""
        area = mock_world_with_biomes.areas["area_forest"]
        area.season_day = 7  # Last day of season

        changed = season_system.advance_day(area)

        assert changed is True
        assert area.season_day == 1
        assert area.current_season == "summer"

    def test_advance_day_locked(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test advancing day in locked area."""
        area = mock_world_with_biomes.areas["area_locked"]
        initial_day = area.season_day
        initial_season = area.current_season

        changed = season_system.advance_day(area)

        assert changed is False
        assert area.season_day == initial_day
        assert area.current_season == initial_season

    def test_advance_day_underground(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test advancing day in season-immune biome."""
        area = mock_world_with_biomes.areas["area_underground"]
        initial_day = area.season_day

        changed = season_system.advance_day(area)

        assert changed is False
        assert area.season_day == initial_day  # Should not advance

    def test_temperature_modifier(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test getting temperature modifier."""
        area = mock_world_with_biomes.areas["area_forest"]
        modifier = season_system.get_temperature_modifier(area)

        # Spring should have a negative modifier
        assert modifier == DEFAULT_SEASONAL_TEMPERATURE_MODIFIERS[Season.SPRING]

    def test_temperature_modifier_winter(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test winter temperature modifier is coldest."""
        area = mock_world_with_biomes.areas["area_arctic"]
        modifier = season_system.get_temperature_modifier(area)

        assert modifier == DEFAULT_SEASONAL_TEMPERATURE_MODIFIERS[Season.WINTER]
        assert modifier < 0

    def test_weather_modifiers(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test getting weather modifiers."""
        area = mock_world_with_biomes.areas["area_arctic"]
        modifiers = season_system.get_weather_modifiers(area)

        # Winter should have snow modifier
        assert "snow" in modifiers
        assert modifiers["snow"] > 0

    def test_check_season_condition(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test checking season conditions."""
        area = mock_world_with_biomes.areas["area_forest"]

        assert season_system.check_season_condition(area, "spring") is True
        assert season_system.check_season_condition(area, "summer") is False
        assert season_system.check_season_condition(area, "winter") is False

    def test_is_season_transition(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test checking if season is about to change."""
        area = mock_world_with_biomes.areas["area_forest"]
        area.season_day = 5  # 2 days until change (7 - 5 = 2)

        assert season_system.is_season_transition(area, days_remaining=3) is True
        assert season_system.is_season_transition(area, days_remaining=1) is False

    def test_format_season_display(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test season display formatting."""
        area = mock_world_with_biomes.areas["area_forest"]
        display = season_system.format_season_display(area)

        assert "Spring" in display
        assert "Day 1/7" in display

    def test_format_season_display_locked(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test locked season display formatting."""
        area = mock_world_with_biomes.areas["area_locked"]
        display = season_system.format_season_display(area)

        assert "Eternal" in display
        assert "Summer" in display

    def test_should_show_season_regular(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test should_show_season for regular area."""
        area = mock_world_with_biomes.areas["area_forest"]
        assert season_system.should_show_season(area) is True

    def test_should_show_season_underground(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test should_show_season for underground area."""
        area = mock_world_with_biomes.areas["area_underground"]
        assert season_system.should_show_season(area) is False


# ============================================================================
# BiomeSystem Tests
# ============================================================================


class TestBiomeSystem:
    """Tests for the BiomeSystem class."""

    def test_initialization(self, biome_system: BiomeSystem):
        """Test BiomeSystem initializes correctly."""
        assert biome_system is not None
        assert biome_system.world is not None

    def test_get_all_biomes(self, biome_system: BiomeSystem):
        """Test getting all loaded biomes."""
        biomes = biome_system.get_all_biomes()
        # Should have loaded at least some biomes from YAML
        assert isinstance(biomes, list)

    def test_get_biome_none(self, biome_system: BiomeSystem):
        """Test getting nonexistent biome returns None."""
        biome = biome_system.get_biome("nonexistent_biome_xyz")
        assert biome is None

    def test_get_biome_for_area(
        self, biome_system: BiomeSystem, mock_world_with_biomes: World
    ):
        """Test getting biome for an area."""
        area = mock_world_with_biomes.areas["area_forest"]
        biome = biome_system.get_biome_for_area(area)
        # May or may not find it depending on YAML files
        # Just verify no error is raised

    def test_validate_area(
        self, biome_system: BiomeSystem, mock_world_with_biomes: World
    ):
        """Test validating an area against its biome."""
        area = mock_world_with_biomes.areas["area_forest"]
        warnings = biome_system.validate_area(area)
        assert isinstance(warnings, list)

    def test_validate_all_areas(
        self, biome_system: BiomeSystem
    ):
        """Test validating all areas."""
        results = biome_system.validate_all_areas()
        assert isinstance(results, dict)

    def test_get_movement_modifier(
        self, biome_system: BiomeSystem, mock_world_with_biomes: World
    ):
        """Test getting movement modifier."""
        area = mock_world_with_biomes.areas["area_forest"]
        modifier = biome_system.get_movement_modifier(area)
        assert modifier >= 0.0

    def test_get_visibility_modifier(
        self, biome_system: BiomeSystem, mock_world_with_biomes: World
    ):
        """Test getting visibility modifier."""
        area = mock_world_with_biomes.areas["area_forest"]
        modifier = biome_system.get_visibility_modifier(area)
        assert modifier >= 0.0

    def test_get_danger_modifier(
        self, biome_system: BiomeSystem, mock_world_with_biomes: World
    ):
        """Test getting danger modifier."""
        area = mock_world_with_biomes.areas["area_forest"]
        modifier = biome_system.get_danger_modifier(area)
        assert isinstance(modifier, int)

    def test_get_spawn_modifier(
        self, biome_system: BiomeSystem, mock_world_with_biomes: World
    ):
        """Test getting spawn modifier."""
        area = mock_world_with_biomes.areas["area_forest"]
        modifier = biome_system.get_spawn_modifier(area, "fauna_spawn_multiplier")
        assert modifier >= 0.0

    def test_get_compatible_flora_tags(
        self, biome_system: BiomeSystem, mock_world_with_biomes: World
    ):
        """Test getting compatible flora tags."""
        area = mock_world_with_biomes.areas["area_forest"]
        tags = biome_system.get_compatible_flora_tags(area)
        assert isinstance(tags, set)

    def test_get_compatible_fauna_tags(
        self, biome_system: BiomeSystem, mock_world_with_biomes: World
    ):
        """Test getting compatible fauna tags."""
        area = mock_world_with_biomes.areas["area_forest"]
        tags = biome_system.get_compatible_fauna_tags(area)
        assert isinstance(tags, set)

    def test_is_flora_compatible_empty(
        self, biome_system: BiomeSystem, mock_world_with_biomes: World
    ):
        """Test flora compatibility with no requirements."""
        area = mock_world_with_biomes.areas["area_forest"]
        assert biome_system.is_flora_compatible(area, []) is True

    def test_is_fauna_compatible_empty(
        self, biome_system: BiomeSystem, mock_world_with_biomes: World
    ):
        """Test fauna compatibility with no requirements."""
        area = mock_world_with_biomes.areas["area_forest"]
        assert biome_system.is_fauna_compatible(area, []) is True


# ============================================================================
# Constant Tests
# ============================================================================


class TestBiomeConstants:
    """Tests for biome-related constants."""

    def test_season_immune_biomes(self):
        """Test season immune biomes list."""
        assert "underground" in SEASON_IMMUNE_BIOMES
        assert "cave" in SEASON_IMMUNE_BIOMES
        assert "void" in SEASON_IMMUNE_BIOMES

    def test_default_temperature_modifiers(self):
        """Test default seasonal temperature modifiers."""
        assert Season.WINTER in DEFAULT_SEASONAL_TEMPERATURE_MODIFIERS
        assert Season.SUMMER in DEFAULT_SEASONAL_TEMPERATURE_MODIFIERS

        # Winter should be coldest
        assert DEFAULT_SEASONAL_TEMPERATURE_MODIFIERS[Season.WINTER] < 0
        # Summer should be warmest
        assert DEFAULT_SEASONAL_TEMPERATURE_MODIFIERS[Season.SUMMER] > 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestBiomeSeasonIntegration:
    """Tests for biome-season system integration."""

    def test_seasonal_cycle_complete(
        self, season_system: SeasonSystem, mock_world_with_biomes: World
    ):
        """Test completing a full seasonal cycle."""
        area = mock_world_with_biomes.areas["area_forest"]
        area.current_season = "spring"
        area.season_day = 1

        seasons_seen = []

        # Advance through all seasons
        for _ in range(4 * 7):  # 4 seasons * 7 days each
            current = season_system.get_season(area)
            if current not in seasons_seen:
                seasons_seen.append(current)
            season_system.advance_day(area)

        # Should have seen all 4 seasons
        assert len(seasons_seen) == 4
        assert Season.SPRING in seasons_seen
        assert Season.SUMMER in seasons_seen
        assert Season.FALL in seasons_seen
        assert Season.WINTER in seasons_seen
