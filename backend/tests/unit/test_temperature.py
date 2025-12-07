"""
Unit tests for the Temperature System.

Tests TemperatureSystem calculations, biome modifiers, time-of-day variations,
trigger conditions, and edge cases.
"""

import pytest

from daemons.engine.systems.temperature import (
    BIOME_TEMPERATURE_MODIFIERS,
    TEMPERATURE_EFFECTS,
    TEMPERATURE_IMMUNE_BIOMES,
    TEMPERATURE_THRESHOLDS,
    TIME_TEMPERATURE_MODIFIERS,
    TemperatureLevel,
    TemperatureState,
    TemperatureSystem,
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
def mock_world_with_areas(mock_world_time: WorldTime) -> World:
    """Create World with areas and rooms for temperature testing."""
    world = World(rooms={}, players={})

    # Create test areas with different biomes
    forest_area = WorldArea(
        id="area_forest",
        name="Forest",
        description="A temperate forest",
        area_time=mock_world_time,
        biome="forest",
        base_temperature=70,
        temperature_variation=20,
    )

    desert_area = WorldArea(
        id="area_desert",
        name="Desert",
        description="A scorching desert",
        area_time=mock_world_time,
        biome="desert",
        base_temperature=95,
        temperature_variation=30,
    )

    arctic_area = WorldArea(
        id="area_arctic",
        name="Arctic Tundra",
        description="A frozen wasteland",
        area_time=mock_world_time,
        biome="arctic",
        base_temperature=30,
        temperature_variation=15,
    )

    underground_area = WorldArea(
        id="area_underground",
        name="Cave System",
        description="A deep underground cave",
        area_time=mock_world_time,
        biome="underground",
        base_temperature=55,
        temperature_variation=5,
    )

    world.areas = {
        "area_forest": forest_area,
        "area_desert": desert_area,
        "area_arctic": arctic_area,
        "area_underground": underground_area,
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

    # Room with temperature override
    world.rooms["room_forge"] = WorldRoom(
        id="room_forge",
        name="Blacksmith's Forge",
        description="An extremely hot forge",
        room_type="urban",
        area_id="area_forest",
        temperature_override=120,
    )

    # Room with cold override
    world.rooms["room_ice_cave"] = WorldRoom(
        id="room_ice_cave",
        name="Ice Cave",
        description="A magically frozen cave",
        room_type="cave",
        area_id="area_forest",
        temperature_override=15,
    )

    return world


@pytest.fixture
def temperature_system(mock_world_with_areas: World) -> TemperatureSystem:
    """Create a TemperatureSystem with the mock world."""
    return TemperatureSystem(mock_world_with_areas)


# ============================================================================
# TemperatureLevel Enum Tests
# ============================================================================


@pytest.mark.unit
class TestTemperatureLevel:
    """Tests for TemperatureLevel enum."""

    def test_all_levels_exist(self):
        """Test that all expected temperature levels are defined."""
        expected = ["FREEZING", "COLD", "COMFORTABLE", "HOT", "SCORCHING"]
        for level_name in expected:
            assert hasattr(TemperatureLevel, level_name)

    def test_level_values(self):
        """Test that levels have distinct values."""
        levels = list(TemperatureLevel)
        values = [level.value for level in levels]
        assert len(values) == len(set(values))  # All unique

    def test_level_ordering(self):
        """Test that levels can be compared logically."""
        assert TemperatureLevel.FREEZING.value == "freezing"
        assert TemperatureLevel.SCORCHING.value == "scorching"


# ============================================================================
# Temperature Thresholds Tests
# ============================================================================


@pytest.mark.unit
class TestTemperatureThresholds:
    """Tests for temperature threshold definitions."""

    def test_thresholds_defined(self):
        """Test that threshold keys are defined."""
        assert "freezing_max" in TEMPERATURE_THRESHOLDS
        assert "cold_max" in TEMPERATURE_THRESHOLDS
        assert "comfortable_max" in TEMPERATURE_THRESHOLDS
        assert "hot_max" in TEMPERATURE_THRESHOLDS

    def test_threshold_ranges(self):
        """Test that threshold ranges make sense."""
        freezing_max = TEMPERATURE_THRESHOLDS["freezing_max"]
        cold_max = TEMPERATURE_THRESHOLDS["cold_max"]
        comfortable_max = TEMPERATURE_THRESHOLDS["comfortable_max"]
        hot_max = TEMPERATURE_THRESHOLDS["hot_max"]

        # Freezing ends before cold
        assert freezing_max < cold_max
        # Cold ends before comfortable
        assert cold_max < comfortable_max
        # Comfortable ends before hot
        assert comfortable_max < hot_max


# ============================================================================
# Biome Modifier Tests
# ============================================================================


@pytest.mark.unit
class TestBiomeModifiers:
    """Tests for biome temperature modifiers."""

    def test_arctic_modifier_is_negative(self):
        """Test that arctic biome has significant cold modifier."""
        assert "arctic" in BIOME_TEMPERATURE_MODIFIERS
        assert BIOME_TEMPERATURE_MODIFIERS["arctic"] < 0
        assert BIOME_TEMPERATURE_MODIFIERS["arctic"] <= -30

    def test_desert_modifier_is_positive(self):
        """Test that desert biome has significant heat modifier."""
        assert "desert" in BIOME_TEMPERATURE_MODIFIERS
        assert BIOME_TEMPERATURE_MODIFIERS["desert"] > 0
        assert BIOME_TEMPERATURE_MODIFIERS["desert"] >= 20

    def test_underground_is_immune(self):
        """Test that underground areas are temperature-immune."""
        assert "underground" in TEMPERATURE_IMMUNE_BIOMES

    def test_ethereal_is_immune(self):
        """Test that ethereal areas are temperature-immune."""
        assert "ethereal" in TEMPERATURE_IMMUNE_BIOMES

    def test_default_modifier(self):
        """Test that unknown biomes get default modifier."""
        assert BIOME_TEMPERATURE_MODIFIERS.get("unknown_biome", 0) == 0


# ============================================================================
# Time-of-Day Modifier Tests
# ============================================================================


@pytest.mark.unit
class TestTimeModifiers:
    """Tests for time-of-day temperature modifiers."""

    def test_night_is_coldest(self):
        """Test that night has the coldest modifier."""
        night_mod = TIME_TEMPERATURE_MODIFIERS.get("night", 0)
        for time_phase, modifier in TIME_TEMPERATURE_MODIFIERS.items():
            if time_phase != "night":
                assert modifier >= night_mod

    def test_afternoon_is_warmest(self):
        """Test that afternoon has the warmest modifier."""
        afternoon_mod = TIME_TEMPERATURE_MODIFIERS.get("afternoon", 0)
        for time_phase, modifier in TIME_TEMPERATURE_MODIFIERS.items():
            assert modifier <= afternoon_mod

    def test_all_phases_defined(self):
        """Test that all time phases have modifiers."""
        expected_phases = ["dawn", "morning", "afternoon", "dusk", "evening", "night"]
        for phase in expected_phases:
            assert phase in TIME_TEMPERATURE_MODIFIERS


# ============================================================================
# TemperatureSystem Core Tests
# ============================================================================


@pytest.mark.unit
class TestTemperatureSystemCalculations:
    """Tests for TemperatureSystem calculation methods."""

    def test_calculate_base_temperature(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test basic temperature calculation."""
        import time

        room = mock_world_with_areas.rooms["room_forest"]

        # Calculate temperature
        state = temperature_system.calculate_room_temperature(room, time.time())

        # Forest has base 70, no biome modifier (0)
        # Result depends on time of day
        assert isinstance(state.temperature, int)
        assert state.base_temperature == 70
        assert state.biome_modifier == BIOME_TEMPERATURE_MODIFIERS.get("forest", 0)

    def test_temperature_override(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test that room temperature override is used."""
        import time

        room = mock_world_with_areas.rooms["room_forge"]

        state = temperature_system.calculate_room_temperature(room, time.time())

        # Override should be exact value
        assert state.temperature == 120
        assert state.is_override is True

    def test_desert_high_temperature(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test that desert has higher temperature due to biome modifier."""
        import time

        room = mock_world_with_areas.rooms["room_desert"]

        state = temperature_system.calculate_room_temperature(room, time.time())

        # Desert has base 95 + biome modifier (+30)
        # Should be very hot
        assert state.biome_modifier == 30  # desert modifier
        assert state.level in [TemperatureLevel.HOT, TemperatureLevel.SCORCHING]

    def test_arctic_low_temperature(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test that arctic has lower temperature due to biome modifier."""
        import time

        room = mock_world_with_areas.rooms["room_arctic"]

        state = temperature_system.calculate_room_temperature(room, time.time())

        # Arctic has base 30 + biome modifier (-40)
        assert state.biome_modifier == -40  # arctic modifier
        assert state.level in [TemperatureLevel.FREEZING, TemperatureLevel.COLD]

    def test_underground_no_time_modifier(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test that underground areas ignore time modifiers."""
        import time

        room = mock_world_with_areas.rooms["room_underground"]

        state = temperature_system.calculate_room_temperature(room, time.time())

        # Underground is immune - should have 0 time modifier
        assert state.time_modifier == 0


# ============================================================================
# Temperature Level Classification Tests
# ============================================================================


@pytest.mark.unit
class TestTemperatureLevelClassification:
    """Tests for get_temperature_level method."""

    def test_freezing_temperatures(self, temperature_system: TemperatureSystem):
        """Test that very cold temperatures are classified as FREEZING."""
        assert (
            temperature_system.get_temperature_level(-20) == TemperatureLevel.FREEZING
        )
        assert temperature_system.get_temperature_level(0) == TemperatureLevel.FREEZING
        assert temperature_system.get_temperature_level(31) == TemperatureLevel.FREEZING

    def test_cold_temperatures(self, temperature_system: TemperatureSystem):
        """Test that cold temperatures are classified as COLD."""
        assert temperature_system.get_temperature_level(35) == TemperatureLevel.COLD
        assert temperature_system.get_temperature_level(45) == TemperatureLevel.COLD

    def test_comfortable_temperatures(self, temperature_system: TemperatureSystem):
        """Test that moderate temperatures are classified as COMFORTABLE."""
        assert (
            temperature_system.get_temperature_level(60) == TemperatureLevel.COMFORTABLE
        )
        assert (
            temperature_system.get_temperature_level(70) == TemperatureLevel.COMFORTABLE
        )

    def test_hot_temperatures(self, temperature_system: TemperatureSystem):
        """Test that warm temperatures are classified as HOT."""
        assert temperature_system.get_temperature_level(85) == TemperatureLevel.HOT
        assert temperature_system.get_temperature_level(95) == TemperatureLevel.HOT

    def test_scorching_temperatures(self, temperature_system: TemperatureSystem):
        """Test that very hot temperatures are classified as SCORCHING."""
        assert (
            temperature_system.get_temperature_level(105) == TemperatureLevel.SCORCHING
        )
        assert (
            temperature_system.get_temperature_level(150) == TemperatureLevel.SCORCHING
        )


# ============================================================================
# Temperature Display Tests
# ============================================================================


@pytest.mark.unit
class TestTemperatureDisplay:
    """Tests for format_temperature_display method."""

    def test_display_includes_temperature(self, temperature_system: TemperatureSystem):
        """Test that display includes the temperature value."""
        display = temperature_system.format_temperature_display(72)
        assert "72" in display

    def test_display_includes_level(self, temperature_system: TemperatureSystem):
        """Test that display includes the temperature level description."""
        display = temperature_system.format_temperature_display(72)
        # Should mention comfortable or similar
        assert "Comfortable" in display

    def test_freezing_display_is_descriptive(
        self, temperature_system: TemperatureSystem
    ):
        """Test that freezing temperatures have appropriate description."""
        display = temperature_system.format_temperature_display(10)
        # Should indicate freezing
        assert "Freezing" in display

    def test_scorching_display_is_descriptive(
        self, temperature_system: TemperatureSystem
    ):
        """Test that scorching temperatures have appropriate description."""
        display = temperature_system.format_temperature_display(115)
        assert "Scorching" in display


# ============================================================================
# should_show_temperature Tests
# ============================================================================


@pytest.mark.unit
class TestShouldShowTemperature:
    """Tests for should_show_temperature method."""

    def test_shows_for_freezing(self, temperature_system: TemperatureSystem):
        """Test that freezing temperatures are shown."""
        assert temperature_system.should_show_temperature(10) is True

    def test_shows_for_scorching(self, temperature_system: TemperatureSystem):
        """Test that scorching temperatures are shown."""
        assert temperature_system.should_show_temperature(115) is True

    def test_hides_for_comfortable(self, temperature_system: TemperatureSystem):
        """Test that comfortable temperatures are not shown."""
        assert temperature_system.should_show_temperature(70) is False

    def test_shows_for_cold(self, temperature_system: TemperatureSystem):
        """Test that cold temperatures are shown."""
        assert temperature_system.should_show_temperature(40) is True

    def test_shows_for_hot(self, temperature_system: TemperatureSystem):
        """Test that hot temperatures are shown."""
        assert temperature_system.should_show_temperature(90) is True


# ============================================================================
# Trigger Condition Tests
# ============================================================================


@pytest.mark.unit
class TestTemperatureTriggerConditions:
    """Tests for check_temperature_condition method."""

    def test_temperature_above_true(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test temperature_above condition when met (using forge room)."""
        # Forge has override temp of 120
        result = temperature_system.check_temperature_condition(
            "room_forge", "above", threshold=100
        )
        assert result is True

    def test_temperature_above_false(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test temperature_above condition when not met (using ice cave)."""
        # Ice cave has override temp of 15
        result = temperature_system.check_temperature_condition(
            "room_ice_cave", "above", threshold=50
        )
        assert result is False

    def test_temperature_below_true(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test temperature_below condition when met (using ice cave)."""
        # Ice cave has override temp of 15
        result = temperature_system.check_temperature_condition(
            "room_ice_cave", "below", threshold=40
        )
        assert result is True

    def test_temperature_below_false(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test temperature_below condition when not met (using forge)."""
        # Forge has override temp of 120
        result = temperature_system.check_temperature_condition(
            "room_forge", "below", threshold=100
        )
        assert result is False

    def test_temperature_range_inside(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test temperature_range condition when inside range."""
        # Forge has override temp of 120
        result = temperature_system.check_temperature_condition(
            "room_forge", "range", min_temp=100, max_temp=150
        )
        assert result is True

    def test_temperature_range_outside(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test temperature_range condition when outside range."""
        # Forge has override temp of 120
        result = temperature_system.check_temperature_condition(
            "room_forge", "range", min_temp=50, max_temp=70
        )
        assert result is False

    def test_unknown_room_returns_false(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test that unknown rooms use default temperature."""
        result = temperature_system.check_temperature_condition(
            "unknown_room", "above", threshold=75
        )
        # Default temp is 70, so > 75 should be false
        assert result is False


# ============================================================================
# TemperatureState Dataclass Tests
# ============================================================================


@pytest.mark.unit
class TestTemperatureState:
    """Tests for TemperatureState dataclass."""

    def test_create_temperature_state(self):
        """Test creating a TemperatureState."""
        state = TemperatureState(
            temperature=72,
            level=TemperatureLevel.COMFORTABLE,
            is_override=False,
            base_temperature=70,
            biome_modifier=2,
            time_modifier=0,
        )

        assert state.temperature == 72
        assert state.level == TemperatureLevel.COMFORTABLE
        assert state.is_override is False

    def test_temperature_state_with_override(self):
        """Test TemperatureState with override flag."""
        state = TemperatureState(
            temperature=120,
            level=TemperatureLevel.SCORCHING,
            is_override=True,
            base_temperature=70,
            biome_modifier=0,
            time_modifier=0,
        )

        assert state.is_override is True
        assert state.temperature == 120


# ============================================================================
# Temperature Effects Tests
# ============================================================================


@pytest.mark.unit
class TestTemperatureEffects:
    """Tests for temperature effect definitions."""

    def test_effects_defined_for_all_levels(self):
        """Test that effects are defined for all temperature levels."""
        for level in TemperatureLevel:
            assert level.value in TEMPERATURE_EFFECTS

    def test_comfortable_has_no_penalties(self):
        """Test that comfortable temperature has no negative effects."""
        effects = TEMPERATURE_EFFECTS["comfortable"]
        assert effects.get("damage_per_tick", 0) == 0
        assert effects.get("movement_penalty", 0) == 0

    def test_extreme_temperatures_have_damage(self):
        """Test that extreme temperatures cause damage."""
        freezing = TEMPERATURE_EFFECTS["freezing"]
        scorching = TEMPERATURE_EFFECTS["scorching"]

        assert freezing.get("damage_per_tick", 0) > 0
        assert scorching.get("damage_per_tick", 0) > 0


# ============================================================================
# Edge Case Tests
# ============================================================================


@pytest.mark.unit
class TestTemperatureEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_orphan_room_uses_defaults(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test handling when room has no area."""
        import time

        room = WorldRoom(
            id="room_orphan",
            name="Orphan Room",
            description="A room with no area",
            room_type="test",
        )
        mock_world_with_areas.rooms["room_orphan"] = room

        # Should not crash, should return default (70)
        state = temperature_system.calculate_room_temperature(room, time.time())
        assert isinstance(state.temperature, int)
        # Default base is 70
        assert state.base_temperature == 70

    def test_very_extreme_temperatures(self, temperature_system: TemperatureSystem):
        """Test classification of extremely high/low temperatures."""
        assert (
            temperature_system.get_temperature_level(-100) == TemperatureLevel.FREEZING
        )
        assert (
            temperature_system.get_temperature_level(200) == TemperatureLevel.SCORCHING
        )

    def test_boundary_temperatures(self, temperature_system: TemperatureSystem):
        """Test temperatures at threshold boundaries."""
        # Test at exact threshold boundaries
        level_32 = temperature_system.get_temperature_level(32)
        level_50 = temperature_system.get_temperature_level(50)
        level_80 = temperature_system.get_temperature_level(80)
        level_100 = temperature_system.get_temperature_level(100)

        # Just verify they return valid levels
        assert level_32 in list(TemperatureLevel)
        assert level_50 in list(TemperatureLevel)
        assert level_80 in list(TemperatureLevel)
        assert level_100 in list(TemperatureLevel)

    def test_missing_room_returns_default(
        self, temperature_system: TemperatureSystem, mock_world_with_areas: World
    ):
        """Test that missing room returns default state."""
        state = temperature_system.calculate_room_temperature_by_id("nonexistent_room")
        assert state.temperature == 70
        assert state.level == TemperatureLevel.COMFORTABLE
