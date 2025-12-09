"""
Unit tests for Phase 17.6: Spawn Conditions and Population Manager

Tests spawn condition evaluation, population tracking, and ecological dynamics.
"""

import pytest
import time
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, AsyncMock, patch

from daemons.engine.systems.spawn_conditions import (
    SpawnConditions,
    SpawnConditionEvaluator,
    EvaluationResult,
)
from daemons.engine.systems.population import (
    PopulationConfig,
    PopulationManager,
    PopulationSnapshot,
    PredationResult,
    SpawnResult,
)
from daemons.engine.world import World, WorldRoom


# ============================================================================
# Test Fixtures
# ============================================================================


@dataclass
class MockNpc:
    """Mock NPC for testing."""
    id: str
    template_id: str
    room_id: str
    name: str = "Test NPC"
    hunger: int = 50


@pytest.fixture
def mock_world():
    """Create a mock World with rooms."""
    world = World(rooms={}, players={})
    world.npcs = {}
    world.npc_templates = {}
    world.areas = {}
    
    # Add test rooms
    room1 = WorldRoom(
        id="room_forest_1",
        name="Forest Clearing",
        description="A clearing in the forest",
        room_type="outdoor",
    )
    room1.area_id = "area_forest"
    room1.north_id = "room_forest_2"
    room1.npc_ids = []
    world.rooms["room_forest_1"] = room1
    
    room2 = WorldRoom(
        id="room_forest_2",
        name="Dense Forest",
        description="Deep in the forest",
        room_type="outdoor",
    )
    room2.area_id = "area_forest"
    room2.south_id = "room_forest_1"
    room2.npc_ids = []
    world.rooms["room_forest_2"] = room2
    
    return world


@pytest.fixture
def spawn_evaluator(mock_world):
    """Create SpawnConditionEvaluator with mock world."""
    return SpawnConditionEvaluator(world=mock_world)


@pytest.fixture
def population_manager(mock_world):
    """Create PopulationManager with mock world."""
    return PopulationManager(world=mock_world)


# ============================================================================
# SpawnConditions Tests
# ============================================================================


@pytest.mark.systems
class TestSpawnConditions:
    """Test SpawnConditions dataclass."""

    def test_from_dict_empty(self):
        """Test parsing empty conditions dict."""
        conditions = SpawnConditions.from_dict({})
        assert conditions.time_of_day is None
        assert conditions.temperature_range is None
        assert conditions.weather_is is None
        assert conditions.has_conditions() is False

    def test_from_dict_time_conditions(self):
        """Test parsing time conditions."""
        conditions = SpawnConditions.from_dict({
            "time_of_day": ["dawn", "dusk"],
        })
        assert conditions.time_of_day == ["dawn", "dusk"]
        assert conditions.has_conditions() is True

    def test_from_dict_temperature_range(self):
        """Test parsing temperature range."""
        conditions = SpawnConditions.from_dict({
            "temperature_range": [32, 80],
        })
        assert conditions.temperature_range == (32, 80)

    def test_from_dict_temperature_min_max(self):
        """Test parsing temperature min/max."""
        conditions = SpawnConditions.from_dict({
            "temperature_min": 40,
            "temperature_max": 90,
        })
        assert conditions.temperature_range == (40, 90)

    def test_from_dict_weather_conditions(self):
        """Test parsing weather conditions."""
        conditions = SpawnConditions.from_dict({
            "weather_is": ["clear", "cloudy"],
            "weather_not": ["storm"],
        })
        assert conditions.weather_is == ["clear", "cloudy"]
        assert conditions.weather_not == ["storm"]

    def test_from_dict_season_conditions(self):
        """Test parsing season conditions."""
        conditions = SpawnConditions.from_dict({
            "season_is": ["spring", "summer"],
            "season_not": ["winter"],
        })
        assert conditions.season_is == ["spring", "summer"]
        assert conditions.season_not == ["winter"]

    def test_from_dict_biome_conditions(self):
        """Test parsing biome conditions."""
        conditions = SpawnConditions.from_dict({
            "biome_is": ["forest", "grassland"],
            "biome_match": True,
        })
        assert conditions.biome_is == ["forest", "grassland"]
        assert conditions.biome_match is True

    def test_from_dict_population_conditions(self):
        """Test parsing population conditions."""
        conditions = SpawnConditions.from_dict({
            "max_in_room": 3,
            "max_in_area": 10,
        })
        assert conditions.max_in_room == 3
        assert conditions.max_in_area == 10

    def test_from_dict_dependency_conditions(self):
        """Test parsing dependency conditions."""
        conditions = SpawnConditions.from_dict({
            "requires_flora": ["oak_tree", "wild_berries"],
            "requires_fauna": ["npc_rabbit"],
            "excludes_fauna": ["npc_wolf"],
        })
        assert conditions.requires_flora == ["oak_tree", "wild_berries"]
        assert conditions.requires_fauna == ["npc_rabbit"]
        assert conditions.excludes_fauna == ["npc_wolf"]

    def test_has_conditions_with_various_conditions(self):
        """Test has_conditions with different condition types."""
        # Time only
        cond1 = SpawnConditions(time_of_day=["day"])
        assert cond1.has_conditions() is True
        
        # Temperature only
        cond2 = SpawnConditions(temperature_range=(30, 80))
        assert cond2.has_conditions() is True
        
        # Light level only
        cond3 = SpawnConditions(light_level_min=50)
        assert cond3.has_conditions() is True
        
        # Biome match only
        cond4 = SpawnConditions(biome_match=True)
        assert cond4.has_conditions() is True


# ============================================================================
# SpawnConditionEvaluator Tests
# ============================================================================


@pytest.mark.systems
class TestSpawnConditionEvaluator:
    """Test SpawnConditionEvaluator."""

    @pytest.mark.asyncio
    async def test_evaluate_no_conditions(self, spawn_evaluator):
        """Test evaluation with no conditions always allows spawn."""
        conditions = SpawnConditions()
        session = MagicMock()
        
        result = await spawn_evaluator.evaluate(
            conditions, "room_forest_1", "area_forest", "npc_deer", session
        )
        
        assert result.can_spawn is True
        assert len(result.failed_conditions) == 0

    @pytest.mark.asyncio
    async def test_evaluate_room_not_found(self, spawn_evaluator):
        """Test evaluation with non-existent room."""
        conditions = SpawnConditions(time_of_day=["day"])
        session = MagicMock()
        
        result = await spawn_evaluator.evaluate(
            conditions, "room_nonexistent", "area_forest", "npc_deer", session
        )
        
        assert result.can_spawn is False
        assert "room_not_found" in result.failed_conditions

    @pytest.mark.asyncio
    async def test_evaluate_time_condition_pass(self, mock_world):
        """Test time condition passes when current time matches."""
        mock_time_manager = MagicMock()
        mock_time_manager.get_hour.return_value = 12  # Noon = day
        
        evaluator = SpawnConditionEvaluator(
            world=mock_world,
            time_manager=mock_time_manager,
        )
        
        conditions = SpawnConditions(time_of_day=["day"])
        session = MagicMock()
        
        result = await evaluator.evaluate(
            conditions, "room_forest_1", "area_forest", "npc_deer", session
        )
        
        assert result.can_spawn is True

    @pytest.mark.asyncio
    async def test_evaluate_time_condition_fail(self, mock_world):
        """Test time condition fails when current time doesn't match."""
        mock_time_manager = MagicMock()
        mock_time_manager.get_hour.return_value = 23  # Night
        
        evaluator = SpawnConditionEvaluator(
            world=mock_world,
            time_manager=mock_time_manager,
        )
        
        conditions = SpawnConditions(time_of_day=["day"])
        session = MagicMock()
        
        result = await evaluator.evaluate(
            conditions, "room_forest_1", "area_forest", "npc_deer", session
        )
        
        assert result.can_spawn is False
        assert any("time_of_day" in c for c in result.failed_conditions)

    @pytest.mark.asyncio
    async def test_evaluate_temperature_condition_pass(self, mock_world):
        """Test temperature condition passes when in range."""
        mock_temp_system = MagicMock()
        mock_temp = MagicMock()
        mock_temp.effective_temperature = 70
        mock_temp_system.calculate_room_temperature.return_value = mock_temp
        
        evaluator = SpawnConditionEvaluator(
            world=mock_world,
            temperature_system=mock_temp_system,
        )
        
        conditions = SpawnConditions(temperature_range=(32, 100))
        session = MagicMock()
        
        result = await evaluator.evaluate(
            conditions, "room_forest_1", "area_forest", "npc_deer", session
        )
        
        assert result.can_spawn is True

    @pytest.mark.asyncio
    async def test_evaluate_temperature_condition_fail(self, mock_world):
        """Test temperature condition fails when out of range."""
        mock_temp_system = MagicMock()
        mock_temp = MagicMock()
        mock_temp.effective_temperature = 10  # Too cold
        mock_temp_system.calculate_room_temperature.return_value = mock_temp
        
        evaluator = SpawnConditionEvaluator(
            world=mock_world,
            temperature_system=mock_temp_system,
        )
        
        conditions = SpawnConditions(temperature_range=(32, 100))
        session = MagicMock()
        
        result = await evaluator.evaluate(
            conditions, "room_forest_1", "area_forest", "npc_deer", session
        )
        
        assert result.can_spawn is False
        assert any("temperature" in c for c in result.failed_conditions)

    @pytest.mark.asyncio
    async def test_evaluate_weather_is_condition(self, mock_world):
        """Test weather_is condition."""
        mock_weather_system = MagicMock()
        mock_weather = MagicMock()
        mock_weather_type = MagicMock()
        mock_weather_type.value = "clear"
        mock_weather.weather_type = mock_weather_type
        mock_weather_system.get_current_weather.return_value = mock_weather
        
        evaluator = SpawnConditionEvaluator(
            world=mock_world,
            weather_system=mock_weather_system,
        )
        
        # Test pass
        conditions = SpawnConditions(weather_is=["clear", "cloudy"])
        session = MagicMock()
        
        result = await evaluator.evaluate(
            conditions, "room_forest_1", "area_forest", "npc_deer", session
        )
        
        assert result.can_spawn is True

    @pytest.mark.asyncio
    async def test_evaluate_weather_not_condition(self, mock_world):
        """Test weather_not condition."""
        mock_weather_system = MagicMock()
        mock_weather = MagicMock()
        mock_weather_type = MagicMock()
        mock_weather_type.value = "storm"
        mock_weather.weather_type = mock_weather_type
        mock_weather_system.get_current_weather.return_value = mock_weather
        
        evaluator = SpawnConditionEvaluator(
            world=mock_world,
            weather_system=mock_weather_system,
        )
        
        conditions = SpawnConditions(weather_not=["storm"])
        session = MagicMock()
        
        result = await evaluator.evaluate(
            conditions, "room_forest_1", "area_forest", "npc_deer", session
        )
        
        assert result.can_spawn is False
        assert any("weather_not" in c for c in result.failed_conditions)

    @pytest.mark.asyncio
    async def test_evaluate_season_condition(self, mock_world):
        """Test season condition."""
        mock_biome_system = MagicMock()
        mock_season = MagicMock()
        mock_season.value = "summer"
        mock_biome_system.get_season.return_value = mock_season
        
        evaluator = SpawnConditionEvaluator(
            world=mock_world,
            biome_system=mock_biome_system,
        )
        
        # Test pass
        conditions = SpawnConditions(season_is=["summer", "spring"])
        session = MagicMock()
        
        result = await evaluator.evaluate(
            conditions, "room_forest_1", "area_forest", "npc_deer", session
        )
        
        assert result.can_spawn is True
        
        # Test fail
        conditions_fail = SpawnConditions(season_not=["summer"])
        
        result_fail = await evaluator.evaluate(
            conditions_fail, "room_forest_1", "area_forest", "npc_deer", session
        )
        
        assert result_fail.can_spawn is False

    @pytest.mark.asyncio
    async def test_evaluate_max_in_room_condition(self, mock_world):
        """Test max_in_room population condition."""
        # Add NPCs to room
        npc1 = MockNpc(id="deer_1", template_id="npc_deer", room_id="room_forest_1")
        npc2 = MockNpc(id="deer_2", template_id="npc_deer", room_id="room_forest_1")
        mock_world.npcs = {"deer_1": npc1, "deer_2": npc2}
        mock_world.rooms["room_forest_1"].npc_ids = ["deer_1", "deer_2"]
        
        evaluator = SpawnConditionEvaluator(world=mock_world)
        
        conditions = SpawnConditions(max_in_room=2)
        session = MagicMock()
        
        result = await evaluator.evaluate(
            conditions, "room_forest_1", "area_forest", "npc_deer", session
        )
        
        assert result.can_spawn is False
        assert any("max_in_room" in c for c in result.failed_conditions)

    @pytest.mark.asyncio
    async def test_evaluate_requires_fauna_condition(self, mock_world):
        """Test requires_fauna dependency condition."""
        # Add rabbit to room
        rabbit = MockNpc(id="rabbit_1", template_id="npc_rabbit", room_id="room_forest_1")
        mock_world.npcs = {"rabbit_1": rabbit}
        mock_world.rooms["room_forest_1"].npc_ids = ["rabbit_1"]
        
        evaluator = SpawnConditionEvaluator(world=mock_world)
        
        # Should pass - rabbit is present
        conditions = SpawnConditions(requires_fauna=["npc_rabbit"])
        session = MagicMock()
        
        result = await evaluator.evaluate(
            conditions, "room_forest_1", "area_forest", "npc_wolf", session
        )
        
        assert result.can_spawn is True

    @pytest.mark.asyncio
    async def test_evaluate_excludes_fauna_condition(self, mock_world):
        """Test excludes_fauna dependency condition."""
        # Add wolf to room
        wolf = MockNpc(id="wolf_1", template_id="npc_wolf", room_id="room_forest_1")
        mock_world.npcs = {"wolf_1": wolf}
        mock_world.rooms["room_forest_1"].npc_ids = ["wolf_1"]
        
        evaluator = SpawnConditionEvaluator(world=mock_world)
        
        # Rabbit should not spawn when wolf present
        conditions = SpawnConditions(excludes_fauna=["npc_wolf"])
        session = MagicMock()
        
        result = await evaluator.evaluate(
            conditions, "room_forest_1", "area_forest", "npc_rabbit", session
        )
        
        assert result.can_spawn is False
        assert any("excludes_fauna" in c for c in result.failed_conditions)

    @pytest.mark.asyncio
    async def test_evaluate_all_spawns_batch(self, spawn_evaluator):
        """Test batch evaluation of multiple spawn definitions."""
        spawn_defs = [
            {
                "template_id": "npc_deer",
                "room_id": "room_forest_1",
                "spawn_conditions": {"time_of_day": ["day"]},
            },
            {
                "template_id": "npc_wolf",
                "room_id": "room_forest_2",
                "spawn_conditions": {},
            },
        ]
        
        session = MagicMock()
        
        results = await spawn_evaluator.evaluate_all_spawns(
            spawn_defs, "area_forest", session
        )
        
        assert len(results) == 2
        assert "npc_deer@room_forest_1" in results
        assert "npc_wolf@room_forest_2" in results


# ============================================================================
# PopulationConfig Tests
# ============================================================================


@pytest.mark.systems
class TestPopulationConfig:
    """Test PopulationConfig dataclass."""

    def test_default_for_area(self):
        """Test creating default config."""
        config = PopulationConfig.default_for_area("area_forest")
        
        assert config.area_id == "area_forest"
        assert config.max_fauna_total == 100
        assert config.max_flora_total == 200
        assert config.base_recovery_rate == 0.1
        assert config.critical_recovery_rate == 0.5

    def test_template_caps(self):
        """Test setting template caps."""
        config = PopulationConfig(
            area_id="area_forest",
            template_caps={
                "npc_deer": 10,
                "npc_wolf": 3,
            }
        )
        
        assert config.template_caps["npc_deer"] == 10
        assert config.template_caps["npc_wolf"] == 3


# ============================================================================
# PopulationSnapshot Tests
# ============================================================================


@pytest.mark.systems
class TestPopulationSnapshot:
    """Test PopulationSnapshot dataclass."""

    def test_get_population_ratio(self):
        """Test population ratio calculation."""
        snapshot = PopulationSnapshot(
            area_id="area_forest",
            timestamp=time.time(),
            fauna_counts={"npc_deer": 5},
        )
        
        ratio = snapshot.get_population_ratio("npc_deer", 10)
        assert ratio == 0.5
        
        # Zero cap
        ratio_zero = snapshot.get_population_ratio("npc_deer", 0)
        assert ratio_zero == 1.0
        
        # Missing template
        ratio_missing = snapshot.get_population_ratio("npc_wolf", 10)
        assert ratio_missing == 0.0


# ============================================================================
# PopulationManager Tests
# ============================================================================


@pytest.mark.systems
class TestPopulationManager:
    """Test PopulationManager."""

    def test_initialization(self, population_manager, mock_world):
        """Test PopulationManager initialization."""
        assert population_manager.world is mock_world
        assert len(population_manager._configs) == 0

    def test_set_and_get_config(self, population_manager):
        """Test setting and getting config."""
        config = PopulationConfig(
            area_id="area_forest",
            template_caps={"npc_deer": 10},
        )
        
        population_manager.set_config(config)
        
        retrieved = population_manager.get_config("area_forest")
        assert retrieved is config
        assert retrieved.template_caps["npc_deer"] == 10

    def test_get_config_creates_default(self, population_manager):
        """Test that get_config creates default if not set."""
        config = population_manager.get_config("area_new")
        
        assert config is not None
        assert config.area_id == "area_new"

    def test_set_template_cap(self, population_manager):
        """Test setting individual template cap."""
        population_manager.set_template_cap("area_forest", "npc_deer", 15)
        
        config = population_manager.get_config("area_forest")
        assert config.template_caps["npc_deer"] == 15

    def test_get_population_snapshot(self, population_manager, mock_world):
        """Test getting population snapshot."""
        # Add NPCs
        deer1 = MockNpc(id="deer_1", template_id="npc_deer", room_id="room_forest_1")
        deer2 = MockNpc(id="deer_2", template_id="npc_deer", room_id="room_forest_2")
        mock_world.npcs = {"deer_1": deer1, "deer_2": deer2}
        
        snapshot = population_manager.get_population_snapshot("area_forest")
        
        assert snapshot.area_id == "area_forest"
        assert snapshot.total_fauna == 2
        assert snapshot.fauna_counts["npc_deer"] == 2

    def test_snapshot_caching(self, population_manager, mock_world):
        """Test that snapshots are cached."""
        snapshot1 = population_manager.get_population_snapshot("area_forest")
        snapshot2 = population_manager.get_population_snapshot("area_forest")
        
        # Should be same object (cached)
        assert snapshot1 is snapshot2
        
        # Force refresh should create new
        snapshot3 = population_manager.get_population_snapshot("area_forest", force_refresh=True)
        assert snapshot3 is not snapshot1

    def test_calculate_spawn_rate_at_cap(self, population_manager, mock_world):
        """Test spawn rate is 0 when at cap."""
        population_manager.set_template_cap("area_forest", "npc_deer", 2)
        
        # Add NPCs to meet cap
        deer1 = MockNpc(id="deer_1", template_id="npc_deer", room_id="room_forest_1")
        deer2 = MockNpc(id="deer_2", template_id="npc_deer", room_id="room_forest_2")
        mock_world.npcs = {"deer_1": deer1, "deer_2": deer2}
        
        rate = population_manager.calculate_spawn_rate("npc_deer", "area_forest")
        
        assert rate == 0.0

    def test_calculate_spawn_rate_below_cap(self, population_manager, mock_world):
        """Test spawn rate is positive when below cap."""
        population_manager.set_template_cap("area_forest", "npc_deer", 10)
        
        # Add one NPC (below cap)
        deer1 = MockNpc(id="deer_1", template_id="npc_deer", room_id="room_forest_1")
        mock_world.npcs = {"deer_1": deer1}
        
        rate = population_manager.calculate_spawn_rate("npc_deer", "area_forest")
        
        assert rate > 0.0

    def test_calculate_spawn_rate_critical(self, population_manager, mock_world):
        """Test spawn rate is high when critically low."""
        population_manager.set_template_cap("area_forest", "npc_deer", 20)
        
        # Add one NPC (5% of cap - critical)
        deer1 = MockNpc(id="deer_1", template_id="npc_deer", room_id="room_forest_1")
        mock_world.npcs = {"deer_1": deer1}
        
        config = population_manager.get_config("area_forest")
        rate = population_manager.calculate_spawn_rate("npc_deer", "area_forest")
        
        # Should use critical recovery rate
        assert rate >= config.base_recovery_rate

    @pytest.mark.asyncio
    async def test_record_death(self, population_manager, mock_world):
        """Test recording fauna death."""
        await population_manager.record_death("npc_deer", "room_forest_1")
        
        assert "npc_deer" in population_manager._recent_deaths
        assert len(population_manager._recent_deaths["npc_deer"]) == 1

    @pytest.mark.asyncio
    async def test_record_death_boosts_spawn_rate(self, population_manager, mock_world):
        """Test that recent deaths boost spawn rate."""
        population_manager.set_template_cap("area_forest", "npc_deer", 10)
        
        # Get initial rate
        initial_rate = population_manager.calculate_spawn_rate("npc_deer", "area_forest")
        
        # Record several deaths
        for _ in range(5):
            await population_manager.record_death("npc_deer", "room_forest_1")
        
        # Get boosted rate
        boosted_rate = population_manager.calculate_spawn_rate("npc_deer", "area_forest")
        
        # Should be higher due to death recovery boost
        assert boosted_rate >= initial_rate

    @pytest.mark.asyncio
    async def test_apply_predation_no_fauna_system(self, population_manager):
        """Test predation with no fauna system does nothing."""
        session = MagicMock()
        result = await population_manager.apply_predation("area_forest", session)
        
        assert len(result.prey_despawned) == 0
        assert len(result.predators_fed) == 0

    @pytest.mark.asyncio
    async def test_apply_population_control(self, population_manager, mock_world):
        """Test population control despawns excess."""
        population_manager.set_template_cap("area_forest", "npc_deer", 1)
        config = population_manager.get_config("area_forest")
        config.overpopulation_cull_rate = 1.0  # Cull all excess
        
        # Add excess NPCs
        deer1 = MockNpc(id="deer_1", template_id="npc_deer", room_id="room_forest_1")
        deer2 = MockNpc(id="deer_2", template_id="npc_deer", room_id="room_forest_2")
        deer3 = MockNpc(id="deer_3", template_id="npc_deer", room_id="room_forest_2")
        mock_world.npcs = {"deer_1": deer1, "deer_2": deer2, "deer_3": deer3}
        
        session = MagicMock()
        despawned = await population_manager.apply_population_control("area_forest", session)
        
        # Should have despawned some excess (at least 1)
        assert despawned > 0

    def test_get_area_health(self, population_manager, mock_world):
        """Test getting ecological health metrics."""
        # Setup mock fauna system
        mock_fauna_system = MagicMock()
        
        # Create mock fauna properties
        deer_fauna = MagicMock()
        from daemons.engine.systems.fauna import Diet
        deer_fauna.diet = Diet.HERBIVORE
        
        wolf_fauna = MagicMock()
        wolf_fauna.diet = Diet.CARNIVORE
        
        mock_fauna_system.get_fauna_properties.side_effect = lambda tid: {
            "npc_deer": deer_fauna,
            "npc_wolf": wolf_fauna,
        }.get(tid)
        
        population_manager.fauna_system = mock_fauna_system
        
        # Add NPCs
        deer1 = MockNpc(id="deer_1", template_id="npc_deer", room_id="room_forest_1")
        wolf1 = MockNpc(id="wolf_1", template_id="npc_wolf", room_id="room_forest_1")
        mock_world.npcs = {"deer_1": deer1, "wolf_1": wolf1}
        
        health = population_manager.get_area_health("area_forest")
        
        assert health["area_id"] == "area_forest"
        assert health["total_fauna"] == 2
        assert health["predator_count"] == 1
        assert health["herbivore_count"] == 1
        assert "ecosystem_health" in health

    def test_has_player_in_room(self, population_manager, mock_world):
        """Test checking for player in room."""
        from daemons.engine.world import WorldPlayer
        
        player = WorldPlayer(
            id="player_1",
            name="TestPlayer",
            room_id="room_forest_1",
            character_class="adventurer",
            level=1,
        )
        mock_world.players = {"player_1": player}
        
        assert population_manager._has_player_in_room("room_forest_1") is True
        assert population_manager._has_player_in_room("room_forest_2") is False


# ============================================================================
# EvaluationResult Tests
# ============================================================================


@pytest.mark.systems
class TestEvaluationResult:
    """Test EvaluationResult dataclass."""

    def test_is_allowed_alias(self):
        """Test is_allowed property aliases can_spawn."""
        result_allowed = EvaluationResult(can_spawn=True)
        assert result_allowed.is_allowed is True
        
        result_denied = EvaluationResult(can_spawn=False)
        assert result_denied.is_allowed is False

    def test_failed_conditions_list(self):
        """Test failed conditions list."""
        result = EvaluationResult(
            can_spawn=False,
            failed_conditions=["time_of_day: night", "temperature: too cold"],
        )
        
        assert len(result.failed_conditions) == 2
        assert "time_of_day: night" in result.failed_conditions


# ============================================================================
# Light Level Calculation Tests
# ============================================================================


@pytest.mark.systems
class TestLightLevelCalculation:
    """Test light level calculation in evaluator."""

    def test_light_level_daytime(self, mock_world):
        """Test light level calculation during day."""
        mock_time_manager = MagicMock()
        mock_time_manager.get_hour.return_value = 12  # Noon
        
        evaluator = SpawnConditionEvaluator(
            world=mock_world,
            time_manager=mock_time_manager,
        )
        
        level = evaluator._calculate_light_level("room_forest_1", "area_forest")
        
        # Should be high during day
        assert level >= 80

    def test_light_level_nighttime(self, mock_world):
        """Test light level calculation at night."""
        mock_time_manager = MagicMock()
        mock_time_manager.get_hour.return_value = 0  # Midnight
        
        evaluator = SpawnConditionEvaluator(
            world=mock_world,
            time_manager=mock_time_manager,
        )
        
        level = evaluator._calculate_light_level("room_forest_1", "area_forest")
        
        # Should be low at night
        assert level <= 20

    def test_light_level_weather_reduction(self, mock_world):
        """Test light level reduced by weather."""
        mock_time_manager = MagicMock()
        mock_time_manager.get_hour.return_value = 12  # Noon
        
        mock_weather_system = MagicMock()
        mock_weather = MagicMock()
        mock_weather_type = MagicMock()
        mock_weather_type.value = "storm"
        mock_weather.weather_type = mock_weather_type
        mock_weather_system.get_current_weather.return_value = mock_weather
        
        evaluator = SpawnConditionEvaluator(
            world=mock_world,
            time_manager=mock_time_manager,
            weather_system=mock_weather_system,
        )
        
        level = evaluator._calculate_light_level("room_forest_1", "area_forest")
        
        # Storm should reduce light
        assert level < 100

    def test_light_level_indoor_override(self, mock_world):
        """Test light level for indoor rooms."""
        mock_world.rooms["room_forest_1"].room_type = "indoor"
        
        evaluator = SpawnConditionEvaluator(world=mock_world)
        
        level = evaluator._calculate_light_level("room_forest_1", "area_forest")
        
        # Indoor should have low ambient light
        assert level <= 30
