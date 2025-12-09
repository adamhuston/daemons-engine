"""
Unit tests for the Weather System (Phase 17.2).

Tests WeatherSystem calculations, weather transitions,
weather effects, and trigger conditions.
"""

import pytest
import time

from daemons.engine.systems.weather import (
    WEATHER_EFFECTS,
    WEATHER_TRANSITIONS,
    INTENSITY_MULTIPLIERS,
    WEATHER_IMMUNE_BIOMES,
    WeatherIntensity,
    WeatherSystem,
    WeatherType,
    WeatherState,
    WeatherForecast,
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
    """Create World with areas for weather testing."""
    world = World(rooms={}, players={})

    # Create test areas with different biomes
    forest_area = WorldArea(
        id="area_forest",
        name="Forest",
        description="A temperate forest",
        area_time=mock_world_time,
        biome="temperate",
        base_temperature=70,
    )

    desert_area = WorldArea(
        id="area_desert",
        name="Desert",
        description="A scorching desert",
        area_time=mock_world_time,
        biome="desert",
        base_temperature=95,
    )

    arctic_area = WorldArea(
        id="area_arctic",
        name="Arctic Tundra",
        description="A frozen wasteland",
        area_time=mock_world_time,
        biome="arctic",
        base_temperature=30,
    )

    # Underground area (weather immune)
    cave_area = WorldArea(
        id="area_cave",
        name="Deep Cave",
        description="An underground cave system",
        area_time=mock_world_time,
        biome="cave",
        base_temperature=55,
    )

    # Ethereal area (weather immune)
    ethereal_area = WorldArea(
        id="area_ethereal",
        name="Ethereal Realm",
        description="A mystical dimension",
        area_time=mock_world_time,
        biome="ethereal",
        base_temperature=70,
    )

    world.areas = {
        "area_forest": forest_area,
        "area_desert": desert_area,
        "area_arctic": arctic_area,
        "area_cave": cave_area,
        "area_ethereal": ethereal_area,
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

    world.rooms["room_cave"] = WorldRoom(
        id="room_cave",
        name="Cavern",
        description="A dark cavern",
        room_type="cave",
        area_id="area_cave",
    )

    return world


@pytest.fixture
def weather_system(mock_world_with_areas: World) -> WeatherSystem:
    """Create a WeatherSystem with the mock world."""
    return WeatherSystem(mock_world_with_areas)


# ============================================================================
# WeatherType Enum Tests
# ============================================================================


@pytest.mark.unit
class TestWeatherType:
    """Tests for WeatherType enum."""

    def test_all_weather_types_exist(self):
        """Test that all expected weather types are defined."""
        expected = ["CLEAR", "CLOUDY", "OVERCAST", "RAIN", "STORM", "SNOW", "FOG", "WIND"]
        for type_name in expected:
            assert hasattr(WeatherType, type_name)

    def test_weather_type_values(self):
        """Test that weather types have distinct values."""
        types = list(WeatherType)
        values = [wt.value for wt in types]
        assert len(values) == len(set(values))  # All unique

    def test_weather_type_string_values(self):
        """Test that weather type values are strings."""
        assert WeatherType.CLEAR.value == "clear"
        assert WeatherType.STORM.value == "storm"
        assert WeatherType.SNOW.value == "snow"


# ============================================================================
# WeatherIntensity Enum Tests
# ============================================================================


@pytest.mark.unit
class TestWeatherIntensity:
    """Tests for WeatherIntensity enum."""

    def test_all_intensities_exist(self):
        """Test that all expected intensities are defined."""
        expected = ["LIGHT", "MODERATE", "HEAVY"]
        for intensity_name in expected:
            assert hasattr(WeatherIntensity, intensity_name)

    def test_intensity_values(self):
        """Test that intensities have distinct values."""
        intensities = list(WeatherIntensity)
        values = [i.value for i in intensities]
        assert len(values) == len(set(values))

    def test_intensity_string_values(self):
        """Test that intensity values are strings."""
        assert WeatherIntensity.LIGHT.value == "light"
        assert WeatherIntensity.MODERATE.value == "moderate"
        assert WeatherIntensity.HEAVY.value == "heavy"


# ============================================================================
# Weather Effects Tests
# ============================================================================


@pytest.mark.unit
class TestWeatherEffects:
    """Tests for weather effect definitions."""

    def test_all_weather_types_have_effects(self):
        """Test that all weather types have defined effects."""
        for weather_type in WeatherType:
            assert weather_type.value in WEATHER_EFFECTS, f"Missing effects for {weather_type}"

    def test_effects_have_required_keys(self):
        """Test that each weather effect has required keys."""
        required_keys = [
            "visibility_modifier",
            "temperature_modifier",
            "movement_modifier",
            "ranged_penalty",
            "casting_penalty",
        ]
        for weather_type_str, effects in WEATHER_EFFECTS.items():
            for key in required_keys:
                assert key in effects, f"Missing {key} for {weather_type_str}"

    def test_clear_weather_no_penalties(self):
        """Test that clear weather has minimal effects."""
        clear_effects = WEATHER_EFFECTS["clear"]
        assert clear_effects["visibility_modifier"] == 0
        assert clear_effects["movement_modifier"] == 1.0
        assert clear_effects["ranged_penalty"] == 0

    def test_storm_has_significant_penalties(self):
        """Test that storm weather has significant penalties."""
        storm_effects = WEATHER_EFFECTS["storm"]
        assert storm_effects["visibility_modifier"] < 0
        assert storm_effects["movement_modifier"] < 1.0
        assert storm_effects["ranged_penalty"] > 0
        assert storm_effects["temperature_modifier"] < 0

    def test_fog_reduces_visibility(self):
        """Test that fog significantly reduces visibility."""
        fog_effects = WEATHER_EFFECTS["fog"]
        assert fog_effects["visibility_modifier"] < -15


# ============================================================================
# Weather Transitions Tests
# ============================================================================


@pytest.mark.unit
class TestWeatherTransitions:
    """Tests for weather transition definitions."""

    def test_all_weather_types_have_transitions(self):
        """Test that all weather types have transition probabilities."""
        for weather_type in WeatherType:
            assert weather_type.value in WEATHER_TRANSITIONS, f"Missing transitions for {weather_type}"

    def test_transition_probabilities_sum_to_one(self):
        """Test that transition probabilities are valid."""
        for weather_type, transitions in WEATHER_TRANSITIONS.items():
            total = sum(transitions.values())
            # Allow small floating point tolerance
            assert 0.99 <= total <= 1.01, f"Invalid transition sum for {weather_type}: {total}"

    def test_clear_can_transition_to_cloudy(self):
        """Test that clear weather can become cloudy."""
        clear_transitions = WEATHER_TRANSITIONS["clear"]
        assert "cloudy" in clear_transitions
        assert clear_transitions["cloudy"] > 0


# ============================================================================
# Intensity Multipliers Tests
# ============================================================================


@pytest.mark.unit
class TestIntensityMultipliers:
    """Tests for intensity multiplier definitions."""

    def test_all_intensities_have_multipliers(self):
        """Test that all intensities have multipliers."""
        for intensity in WeatherIntensity:
            assert intensity in INTENSITY_MULTIPLIERS

    def test_multiplier_ordering(self):
        """Test that multipliers increase with intensity."""
        assert INTENSITY_MULTIPLIERS[WeatherIntensity.LIGHT] < INTENSITY_MULTIPLIERS[WeatherIntensity.MODERATE]
        assert INTENSITY_MULTIPLIERS[WeatherIntensity.MODERATE] < INTENSITY_MULTIPLIERS[WeatherIntensity.HEAVY]

    def test_moderate_is_baseline(self):
        """Test that moderate intensity is baseline (1.0)."""
        assert INTENSITY_MULTIPLIERS[WeatherIntensity.MODERATE] == 1.0


# ============================================================================
# WeatherState Dataclass Tests
# ============================================================================


@pytest.mark.unit
class TestWeatherState:
    """Tests for WeatherState dataclass."""

    def test_weather_state_creation(self):
        """Test creating a WeatherState instance."""
        state = WeatherState(
            weather_type=WeatherType.RAIN,
            intensity=WeatherIntensity.MODERATE,
            started_at=time.time(),
            duration=1800,  # 30 minutes
            next_change_at=time.time() + 1800,
        )
        assert state.weather_type == WeatherType.RAIN
        assert state.intensity == WeatherIntensity.MODERATE
        assert state.duration == 1800

    def test_time_remaining_property(self):
        """Test WeatherState time_remaining calculation."""
        current = time.time()
        state = WeatherState(
            weather_type=WeatherType.CLEAR,
            intensity=WeatherIntensity.MODERATE,
            started_at=current,
            duration=3600,
            next_change_at=current + 3600,
        )
        # Time remaining should be approximately 3600
        assert 3590 <= state.time_remaining <= 3600

    def test_time_remaining_expired(self):
        """Test time_remaining when weather should have changed."""
        past = time.time() - 100  # 100 seconds ago
        state = WeatherState(
            weather_type=WeatherType.RAIN,
            intensity=WeatherIntensity.LIGHT,
            started_at=past - 1800,
            duration=1800,
            next_change_at=past,
        )
        assert state.time_remaining == 0


# ============================================================================
# WeatherSystem Core Tests
# ============================================================================


@pytest.mark.unit
class TestWeatherSystemCore:
    """Tests for WeatherSystem core functionality."""

    def test_system_initialization(self, weather_system: WeatherSystem):
        """Test that WeatherSystem initializes correctly."""
        assert weather_system.world is not None
        assert hasattr(weather_system, "_weather_cache")

    def test_get_current_weather(
        self, weather_system: WeatherSystem, mock_world_with_areas: World
    ):
        """Test getting weather for an area."""
        weather = weather_system.get_current_weather("area_forest")

        assert isinstance(weather, WeatherState)
        assert isinstance(weather.weather_type, WeatherType)
        assert isinstance(weather.intensity, WeatherIntensity)

    def test_weather_cached(
        self, weather_system: WeatherSystem
    ):
        """Test that weather is cached between calls."""
        weather1 = weather_system.get_current_weather("area_forest")
        weather2 = weather_system.get_current_weather("area_forest")

        # Should be same state object or same values
        assert weather1.weather_type == weather2.weather_type
        assert weather1.intensity == weather2.intensity
        assert weather1.started_at == weather2.started_at

    def test_different_areas_independent(
        self, weather_system: WeatherSystem
    ):
        """Test that different areas have independent weather."""
        # Get weather for different areas
        forest = weather_system.get_current_weather("area_forest")
        desert = weather_system.get_current_weather("area_desert")

        # Both should be valid states
        assert isinstance(forest, WeatherState)
        assert isinstance(desert, WeatherState)


# ============================================================================
# Weather Immune Area Tests
# ============================================================================


@pytest.mark.unit
class TestWeatherImmuneAreas:
    """Tests for weather-immune areas."""

    def test_weather_immune_biomes_defined(self):
        """Test that weather-immune biomes are defined."""
        assert "cave" in WEATHER_IMMUNE_BIOMES
        assert "underground" in WEATHER_IMMUNE_BIOMES
        assert "ethereal" in WEATHER_IMMUNE_BIOMES

    def test_cave_always_clear(
        self, weather_system: WeatherSystem
    ):
        """Test that cave areas are always clear."""
        weather = weather_system.get_current_weather("area_cave")
        assert weather.weather_type == WeatherType.CLEAR

    def test_ethereal_always_clear(
        self, weather_system: WeatherSystem
    ):
        """Test that ethereal areas are always clear."""
        weather = weather_system.get_current_weather("area_ethereal")
        assert weather.weather_type == WeatherType.CLEAR

    def test_immune_area_never_changes(
        self, weather_system: WeatherSystem
    ):
        """Test that immune areas don't get weather changes scheduled."""
        weather = weather_system.get_current_weather("area_cave")
        assert weather.next_change_at is None


# ============================================================================
# Weather Effects Retrieval Tests
# ============================================================================


@pytest.mark.unit
class TestWeatherEffectsRetrieval:
    """Tests for getting weather effects."""

    def test_get_weather_effects(self, weather_system: WeatherSystem):
        """Test getting effects for an area."""
        effects = weather_system.get_weather_effects("area_forest")

        assert "visibility_modifier" in effects
        assert "temperature_modifier" in effects
        assert "movement_modifier" in effects
        assert "ranged_penalty" in effects
        assert "casting_penalty" in effects
        assert "weather_type" in effects
        assert "intensity" in effects

    def test_effects_include_weather_info(self, weather_system: WeatherSystem):
        """Test that effects include current weather info."""
        effects = weather_system.get_weather_effects("area_forest")

        # Should include current weather type
        assert effects["weather_type"] in [wt.value for wt in WeatherType]
        assert effects["intensity"] in [i.value for i in WeatherIntensity]


# ============================================================================
# Weather Display Tests
# ============================================================================


@pytest.mark.unit
class TestWeatherDisplay:
    """Tests for weather display formatting."""

    def test_format_weather_display(self, weather_system: WeatherSystem):
        """Test formatting weather for display."""
        display = weather_system.format_weather_display("area_forest")

        assert isinstance(display, str)
        assert len(display) > 0

    def test_format_weather_with_effects(self, weather_system: WeatherSystem):
        """Test formatting with effects included."""
        display = weather_system.format_weather_display("area_forest", include_effects=True)

        assert isinstance(display, str)

    def test_should_show_weather_clear(self, weather_system: WeatherSystem):
        """Test should_show_weather returns False for clear."""
        # Cave area is always clear
        result = weather_system.should_show_weather("area_cave")
        assert result is False


# ============================================================================
# Weather Forecast Tests
# ============================================================================


@pytest.mark.unit
class TestWeatherForecast:
    """Tests for weather forecasting."""

    def test_get_forecast(self, weather_system: WeatherSystem):
        """Test getting a weather forecast."""
        forecast = weather_system.get_forecast("area_forest")

        assert isinstance(forecast, WeatherForecast)
        assert isinstance(forecast.current, WeatherState)
        assert isinstance(forecast.likely_next, WeatherType)
        assert isinstance(forecast.change_in_minutes, int)
        assert forecast.change_in_minutes >= 0


# ============================================================================
# Weather Transition Tests
# ============================================================================


@pytest.mark.unit
class TestWeatherTransitionMechanics:
    """Tests for weather transition mechanics."""

    def test_advance_weather(self, weather_system: WeatherSystem):
        """Test advancing weather to next state."""
        # Get initial weather
        initial = weather_system.get_current_weather("area_forest")

        # Force advance
        new_state = weather_system.advance_weather("area_forest")

        # Should return a valid state
        assert isinstance(new_state, WeatherState)
        assert isinstance(new_state.weather_type, WeatherType)

    def test_advance_weather_immune_area(self, weather_system: WeatherSystem):
        """Test that immune areas stay clear when advanced."""
        weather_system.advance_weather("area_cave")
        weather = weather_system.get_current_weather("area_cave")
        assert weather.weather_type == WeatherType.CLEAR


# ============================================================================
# Weather Condition Checks Tests
# ============================================================================


@pytest.mark.unit
class TestWeatherConditionChecks:
    """Tests for weather condition checking (for triggers)."""

    def test_check_weather_condition_exists(self, weather_system: WeatherSystem):
        """Test that check_weather_condition method exists."""
        assert hasattr(weather_system, "check_weather_condition")

    def test_check_weather_condition_type(self, weather_system: WeatherSystem):
        """Test checking weather type condition."""
        # Get current weather type
        state = weather_system.get_current_weather("area_forest")

        # Check condition
        result = weather_system.check_weather_condition(
            "area_forest",
            condition_type="is",
            weather_type=state.weather_type.value,
        )
        assert result is True

    def test_check_weather_condition_wrong_type(self, weather_system: WeatherSystem):
        """Test checking weather condition with wrong type."""
        # Cave is always clear, so check for storm
        result = weather_system.check_weather_condition(
            "area_cave",
            condition_type="is",
            weather_type="storm",
        )
        assert result is False


# ============================================================================
# Edge Case Tests
# ============================================================================


@pytest.mark.unit
class TestWeatherEdgeCases:
    """Tests for edge cases and error handling."""

    def test_nonexistent_area(self, weather_system: WeatherSystem):
        """Test handling of nonexistent area."""
        # Should not crash, may return default weather
        weather = weather_system.get_current_weather("area_nonexistent")
        assert isinstance(weather, WeatherState)

    def test_area_without_biome(self, weather_system: WeatherSystem, mock_world_with_areas: World):
        """Test area with default/missing biome."""
        # Create area without biome
        mock_world_with_areas.areas["area_plain"] = WorldArea(
            id="area_plain",
            name="Plain",
            description="A plain",
            area_time=WorldTime(day=1, hour=12, minute=0),
        )

        weather = weather_system.get_current_weather("area_plain")
        assert isinstance(weather, WeatherState)

