"""
Unit tests for Phase 17.5: FaunaSystem

Tests fauna behaviors, activity periods, pack spawning, predator-prey dynamics,
migration, and death handling.
"""

import pytest
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch, AsyncMock

from daemons.engine.systems.fauna import (
    ActivityPeriod,
    Diet,
    FaunaProperties,
    FaunaSystem,
    FaunaType,
    PopulationSnapshot,
    TimeOfDay,
)
from daemons.engine.world import World, WorldRoom


# ============================================================================
# Test Fixtures
# ============================================================================


@dataclass
class MockNpcTemplate:
    """Mock NPC template for testing."""
    id: str
    name: str
    is_fauna: bool = False
    fauna_data: Optional[dict] = None


@dataclass
class MockNpc:
    """Mock NPC for testing."""
    id: str
    template_id: str
    room_id: str
    name: str = "Test NPC"


@pytest.fixture
def mock_world():
    """Create a mock World with rooms."""
    world = World(rooms={}, players={})
    world.npcs = {}
    world.npc_templates = {}
    
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
def fauna_system(mock_world):
    """Create FaunaSystem with mock world."""
    return FaunaSystem(world=mock_world)


@pytest.fixture
def deer_template():
    """Create a deer NPC template with fauna data."""
    return MockNpcTemplate(
        id="npc_deer",
        name="Deer",
        is_fauna=True,
        fauna_data={
            "fauna_type": "mammal",
            "biome_tags": ["forest", "grassland"],
            "temperature_tolerance": [20, 90],
            "activity_period": "crepuscular",
            "diet": "herbivore",
            "prey_tags": [],
            "predator_tags": ["carnivore", "wolf"],
            "fauna_tags": ["herbivore", "deer", "prey"],
            "pack_size": [1, 4],
            "pack_leader_template": None,
            "territorial": False,
            "territory_radius": 3,
            "migratory": True,
            "migration_seasons": ["winter"],
            "migration_tendency": 0.1,
            "aggression": 0.0,
            "flee_threshold": 0.5,
        }
    )


@pytest.fixture
def wolf_template():
    """Create a wolf NPC template with fauna data."""
    return MockNpcTemplate(
        id="npc_wolf",
        name="Wolf",
        is_fauna=True,
        fauna_data={
            "fauna_type": "mammal",
            "biome_tags": ["forest", "tundra"],
            "temperature_tolerance": [0, 80],
            "activity_period": "nocturnal",
            "diet": "carnivore",
            "prey_tags": ["herbivore", "prey"],
            "predator_tags": [],
            "fauna_tags": ["carnivore", "wolf", "predator"],
            "pack_size": [3, 7],
            "pack_leader_template": "npc_alpha_wolf",
            "territorial": True,
            "territory_radius": 5,
            "migratory": False,
            "migration_seasons": [],
            "migration_tendency": 0.05,
            "aggression": 0.7,
            "flee_threshold": 0.2,
        }
    )


# ============================================================================
# Enum Tests
# ============================================================================


@pytest.mark.systems
class TestFaunaEnums:
    """Test fauna enumeration types."""

    def test_activity_period_values(self):
        """Test ActivityPeriod enum values."""
        assert ActivityPeriod.DIURNAL.value == "diurnal"
        assert ActivityPeriod.NOCTURNAL.value == "nocturnal"
        assert ActivityPeriod.CREPUSCULAR.value == "crepuscular"
        assert ActivityPeriod.ALWAYS.value == "always"

    def test_diet_values(self):
        """Test Diet enum values."""
        assert Diet.HERBIVORE.value == "herbivore"
        assert Diet.CARNIVORE.value == "carnivore"
        assert Diet.OMNIVORE.value == "omnivore"
        assert Diet.SCAVENGER.value == "scavenger"

    def test_fauna_type_values(self):
        """Test FaunaType enum values."""
        assert FaunaType.MAMMAL.value == "mammal"
        assert FaunaType.BIRD.value == "bird"
        assert FaunaType.REPTILE.value == "reptile"
        assert FaunaType.AMPHIBIAN.value == "amphibian"
        assert FaunaType.FISH.value == "fish"
        assert FaunaType.INSECT.value == "insect"
        assert FaunaType.ARACHNID.value == "arachnid"
        assert FaunaType.CRUSTACEAN.value == "crustacean"

    def test_time_of_day_values(self):
        """Test TimeOfDay enum values."""
        assert TimeOfDay.DAWN.value == "dawn"
        assert TimeOfDay.DAY.value == "day"
        assert TimeOfDay.DUSK.value == "dusk"
        assert TimeOfDay.NIGHT.value == "night"


# ============================================================================
# FaunaProperties Tests
# ============================================================================


@pytest.mark.systems
class TestFaunaProperties:
    """Test FaunaProperties dataclass."""

    def test_from_npc_template_fauna(self, deer_template):
        """Test extracting fauna properties from NPC template."""
        props = FaunaProperties.from_npc_template(deer_template)
        
        assert props is not None
        assert props.template_id == "npc_deer"
        assert props.fauna_type == FaunaType.MAMMAL
        assert props.activity_period == ActivityPeriod.CREPUSCULAR
        assert props.diet == Diet.HERBIVORE
        assert "forest" in props.biome_tags
        assert props.temperature_tolerance == (20, 90)
        assert props.migratory is True
        assert "winter" in props.migration_seasons

    def test_from_npc_template_non_fauna(self):
        """Test that non-fauna returns None."""
        non_fauna = MockNpcTemplate(
            id="npc_villager",
            name="Villager",
            is_fauna=False,
        )
        props = FaunaProperties.from_npc_template(non_fauna)
        assert props is None

    def test_predator_prey_tags(self, wolf_template):
        """Test predator/prey tag extraction."""
        props = FaunaProperties.from_npc_template(wolf_template)
        
        assert props is not None
        assert "herbivore" in props.prey_tags
        assert "prey" in props.prey_tags
        assert "carnivore" in props.fauna_tags
        assert "predator" in props.fauna_tags

    def test_pack_configuration(self, wolf_template):
        """Test pack size configuration."""
        props = FaunaProperties.from_npc_template(wolf_template)
        
        assert props is not None
        assert props.pack_size == (3, 7)
        assert props.pack_leader_template == "npc_alpha_wolf"

    def test_territorial_configuration(self, wolf_template):
        """Test territorial configuration."""
        props = FaunaProperties.from_npc_template(wolf_template)
        
        assert props is not None
        assert props.territorial is True
        assert props.territory_radius == 5

    def test_default_values(self):
        """Test default values when fauna_data is minimal."""
        minimal_fauna = MockNpcTemplate(
            id="npc_creature",
            name="Generic Creature",
            is_fauna=True,
            fauna_data={},
        )
        props = FaunaProperties.from_npc_template(minimal_fauna)
        
        assert props is not None
        assert props.fauna_type == FaunaType.MAMMAL
        assert props.activity_period == ActivityPeriod.ALWAYS
        assert props.diet == Diet.HERBIVORE
        assert props.pack_size == (1, 1)
        assert props.territorial is False
        assert props.migratory is False


# ============================================================================
# FaunaSystem Basic Tests
# ============================================================================


@pytest.mark.systems
class TestFaunaSystemBasics:
    """Test basic FaunaSystem functionality."""

    def test_initialization(self, fauna_system, mock_world):
        """Test FaunaSystem initialization."""
        assert fauna_system.world is mock_world
        assert fauna_system.biome_system is None
        assert fauna_system.temperature_system is None
        assert fauna_system.time_manager is None

    def test_get_fauna_properties_caching(self, fauna_system, mock_world, deer_template):
        """Test that fauna properties are cached."""
        mock_world.npc_templates["npc_deer"] = deer_template
        
        # First call - should extract and cache
        props1 = fauna_system.get_fauna_properties("npc_deer")
        assert props1 is not None
        
        # Second call - should return cached
        props2 = fauna_system.get_fauna_properties("npc_deer")
        assert props1 is props2  # Same object

    def test_get_fauna_properties_missing(self, fauna_system):
        """Test getting properties for non-existent template."""
        props = fauna_system.get_fauna_properties("npc_nonexistent")
        assert props is None

    def test_is_fauna(self, fauna_system, mock_world, deer_template):
        """Test is_fauna check."""
        mock_world.npc_templates["npc_deer"] = deer_template
        
        deer_npc = MockNpc(
            id="deer_1",
            template_id="npc_deer",
            room_id="room_forest_1",
        )
        mock_world.npcs["deer_1"] = deer_npc
        
        assert fauna_system.is_fauna(deer_npc) is True


# ============================================================================
# Activity Period Tests
# ============================================================================


@pytest.mark.systems
class TestActivityPeriods:
    """Test activity period logic."""

    def test_get_time_of_day_no_manager(self, fauna_system):
        """Test default time of day without time manager."""
        assert fauna_system.get_time_of_day("area_forest") == TimeOfDay.DAY

    def test_get_time_of_day_dawn(self, mock_world):
        """Test dawn detection."""
        mock_time_manager = MagicMock()
        mock_time_manager.get_hour.return_value = 6
        
        fauna_system = FaunaSystem(world=mock_world, time_manager=mock_time_manager)
        assert fauna_system.get_time_of_day("area_forest") == TimeOfDay.DAWN

    def test_get_time_of_day_day(self, mock_world):
        """Test day detection."""
        mock_time_manager = MagicMock()
        mock_time_manager.get_hour.return_value = 12
        
        fauna_system = FaunaSystem(world=mock_world, time_manager=mock_time_manager)
        assert fauna_system.get_time_of_day("area_forest") == TimeOfDay.DAY

    def test_get_time_of_day_dusk(self, mock_world):
        """Test dusk detection."""
        mock_time_manager = MagicMock()
        mock_time_manager.get_hour.return_value = 18
        
        fauna_system = FaunaSystem(world=mock_world, time_manager=mock_time_manager)
        assert fauna_system.get_time_of_day("area_forest") == TimeOfDay.DUSK

    def test_get_time_of_day_night(self, mock_world):
        """Test night detection."""
        mock_time_manager = MagicMock()
        mock_time_manager.get_hour.return_value = 23
        
        fauna_system = FaunaSystem(world=mock_world, time_manager=mock_time_manager)
        assert fauna_system.get_time_of_day("area_forest") == TimeOfDay.NIGHT

    def test_is_active_diurnal_during_day(self, mock_world, deer_template):
        """Test diurnal fauna active during day."""
        mock_time_manager = MagicMock()
        mock_time_manager.get_hour.return_value = 12
        mock_world.npc_templates["npc_deer"] = deer_template
        
        fauna_system = FaunaSystem(world=mock_world, time_manager=mock_time_manager)
        
        # Create diurnal fauna
        diurnal = FaunaProperties(
            template_id="diurnal_test",
            fauna_type=FaunaType.BIRD,
            activity_period=ActivityPeriod.DIURNAL,
        )
        
        assert fauna_system.is_active_now(diurnal, "area_forest") is True

    def test_is_active_diurnal_during_night(self, mock_world):
        """Test diurnal fauna inactive at night."""
        mock_time_manager = MagicMock()
        mock_time_manager.get_hour.return_value = 23
        
        fauna_system = FaunaSystem(world=mock_world, time_manager=mock_time_manager)
        
        diurnal = FaunaProperties(
            template_id="diurnal_test",
            fauna_type=FaunaType.BIRD,
            activity_period=ActivityPeriod.DIURNAL,
        )
        
        assert fauna_system.is_active_now(diurnal, "area_forest") is False

    def test_is_active_nocturnal(self, mock_world):
        """Test nocturnal fauna active at night."""
        mock_time_manager = MagicMock()
        mock_time_manager.get_hour.return_value = 23
        
        fauna_system = FaunaSystem(world=mock_world, time_manager=mock_time_manager)
        
        nocturnal = FaunaProperties(
            template_id="nocturnal_test",
            fauna_type=FaunaType.MAMMAL,
            activity_period=ActivityPeriod.NOCTURNAL,
        )
        
        assert fauna_system.is_active_now(nocturnal, "area_forest") is True

    def test_is_active_crepuscular(self, mock_world):
        """Test crepuscular fauna active at dawn/dusk."""
        mock_time_manager = MagicMock()
        
        fauna_system = FaunaSystem(world=mock_world, time_manager=mock_time_manager)
        
        crepuscular = FaunaProperties(
            template_id="crepuscular_test",
            fauna_type=FaunaType.MAMMAL,
            activity_period=ActivityPeriod.CREPUSCULAR,
        )
        
        # Active at dawn
        mock_time_manager.get_hour.return_value = 6
        assert fauna_system.is_active_now(crepuscular, "area_forest") is True
        
        # Active at dusk
        mock_time_manager.get_hour.return_value = 18
        assert fauna_system.is_active_now(crepuscular, "area_forest") is True
        
        # Inactive at midday
        mock_time_manager.get_hour.return_value = 12
        assert fauna_system.is_active_now(crepuscular, "area_forest") is False

    def test_is_active_always(self, fauna_system):
        """Test always-active fauna."""
        always_active = FaunaProperties(
            template_id="always_test",
            fauna_type=FaunaType.INSECT,
            activity_period=ActivityPeriod.ALWAYS,
        )
        
        # Should always be active
        assert fauna_system.is_active_now(always_active, "area_forest") is True


# ============================================================================
# Migration Tests
# ============================================================================


@pytest.mark.systems
class TestMigration:
    """Test migration logic."""

    def test_is_migrated_non_migratory(self, fauna_system):
        """Test non-migratory fauna never migrates."""
        non_migratory = FaunaProperties(
            template_id="resident_test",
            fauna_type=FaunaType.MAMMAL,
            migratory=False,
        )
        
        assert fauna_system.is_migrated(non_migratory, "area_forest") is False

    def test_is_migrated_no_biome_system(self, fauna_system):
        """Test migration without biome system returns False."""
        migratory = FaunaProperties(
            template_id="migratory_test",
            fauna_type=FaunaType.BIRD,
            migratory=True,
            migration_seasons=["winter"],
        )
        
        assert fauna_system.is_migrated(migratory, "area_forest") is False

    def test_is_migrated_during_migration_season(self, mock_world):
        """Test fauna migrates during migration season."""
        mock_biome_system = MagicMock()
        mock_season = MagicMock()
        mock_season.value = "winter"
        mock_biome_system.get_season.return_value = mock_season
        
        fauna_system = FaunaSystem(world=mock_world, biome_system=mock_biome_system)
        
        migratory = FaunaProperties(
            template_id="migratory_bird",
            fauna_type=FaunaType.BIRD,
            migratory=True,
            migration_seasons=["winter"],
        )
        
        assert fauna_system.is_migrated(migratory, "area_forest") is True

    def test_is_migrated_outside_migration_season(self, mock_world):
        """Test fauna doesn't migrate outside migration season."""
        mock_biome_system = MagicMock()
        mock_season = MagicMock()
        mock_season.value = "summer"
        mock_biome_system.get_season.return_value = mock_season
        
        fauna_system = FaunaSystem(world=mock_world, biome_system=mock_biome_system)
        
        migratory = FaunaProperties(
            template_id="migratory_bird",
            fauna_type=FaunaType.BIRD,
            migratory=True,
            migration_seasons=["winter"],
        )
        
        assert fauna_system.is_migrated(migratory, "area_forest") is False


# ============================================================================
# Temperature Tolerance Tests
# ============================================================================


@pytest.mark.systems
class TestTemperatureTolerance:
    """Test temperature tolerance checks."""

    def test_no_temperature_system(self, fauna_system):
        """Test tolerance without temperature system returns True."""
        fauna = FaunaProperties(
            template_id="test",
            fauna_type=FaunaType.MAMMAL,
            temperature_tolerance=(32, 100),
        )
        
        assert fauna_system.can_survive_temperature(fauna, "room_1", "area_1") is True

    def test_within_tolerance(self, mock_world):
        """Test fauna survives within temperature tolerance."""
        mock_temp_system = MagicMock()
        mock_temp = MagicMock()
        mock_temp.effective_temperature = 70
        mock_temp_system.calculate_room_temperature.return_value = mock_temp
        
        fauna_system = FaunaSystem(world=mock_world, temperature_system=mock_temp_system)
        
        fauna = FaunaProperties(
            template_id="test",
            fauna_type=FaunaType.MAMMAL,
            temperature_tolerance=(32, 100),
        )
        
        assert fauna_system.can_survive_temperature(fauna, "room_forest_1", "area_forest") is True

    def test_below_tolerance(self, mock_world):
        """Test fauna cannot survive below minimum temperature."""
        mock_temp_system = MagicMock()
        mock_temp = MagicMock()
        mock_temp.effective_temperature = 10  # Below 32
        mock_temp_system.calculate_room_temperature.return_value = mock_temp
        
        fauna_system = FaunaSystem(world=mock_world, temperature_system=mock_temp_system)
        
        fauna = FaunaProperties(
            template_id="test",
            fauna_type=FaunaType.MAMMAL,
            temperature_tolerance=(32, 100),
        )
        
        assert fauna_system.can_survive_temperature(fauna, "room_forest_1", "area_forest") is False

    def test_above_tolerance(self, mock_world):
        """Test fauna cannot survive above maximum temperature."""
        mock_temp_system = MagicMock()
        mock_temp = MagicMock()
        mock_temp.effective_temperature = 120  # Above 100
        mock_temp_system.calculate_room_temperature.return_value = mock_temp
        
        fauna_system = FaunaSystem(world=mock_world, temperature_system=mock_temp_system)
        
        fauna = FaunaProperties(
            template_id="test",
            fauna_type=FaunaType.MAMMAL,
            temperature_tolerance=(32, 100),
        )
        
        assert fauna_system.can_survive_temperature(fauna, "room_forest_1", "area_forest") is False


# ============================================================================
# Pack Spawning Tests
# ============================================================================


@pytest.mark.systems
class TestPackSpawning:
    """Test pack spawning logic."""

    def test_calculate_pack_size(self, fauna_system):
        """Test pack size calculation within range."""
        fauna = FaunaProperties(
            template_id="test",
            fauna_type=FaunaType.MAMMAL,
            pack_size=(3, 7),
        )
        
        for _ in range(20):
            size = fauna_system.calculate_pack_size(fauna)
            assert 3 <= size <= 7

    def test_calculate_pack_size_single(self, fauna_system):
        """Test pack size for solitary fauna."""
        fauna = FaunaProperties(
            template_id="test",
            fauna_type=FaunaType.MAMMAL,
            pack_size=(1, 1),
        )
        
        size = fauna_system.calculate_pack_size(fauna)
        assert size == 1

    @pytest.mark.asyncio
    async def test_spawn_pack_non_fauna(self, fauna_system):
        """Test spawn_pack returns empty for non-fauna."""
        from unittest.mock import MagicMock
        session = MagicMock()
        
        pack = await fauna_system.spawn_pack("npc_nonexistent", "room_1", session)
        assert pack == []


# ============================================================================
# Predator-Prey Dynamics Tests
# ============================================================================


@pytest.mark.systems
class TestPredatorPreyDynamics:
    """Test predator-prey relationship detection."""

    def test_find_prey_in_room(self, fauna_system, mock_world, deer_template, wolf_template):
        """Test finding prey in a room."""
        mock_world.npc_templates["npc_deer"] = deer_template
        mock_world.npc_templates["npc_wolf"] = wolf_template
        
        # Add deer to room
        deer_npc = MockNpc(
            id="deer_1",
            template_id="npc_deer",
            room_id="room_forest_1",
        )
        mock_world.npcs["deer_1"] = deer_npc
        mock_world.rooms["room_forest_1"].npc_ids = ["deer_1"]
        
        # Wolf looking for prey
        prey = fauna_system.find_prey_in_room("npc_wolf", "room_forest_1")
        
        assert len(prey) == 1
        assert prey[0].template_id == "npc_deer"

    def test_find_prey_empty_room(self, fauna_system, mock_world, wolf_template):
        """Test finding prey in empty room."""
        mock_world.npc_templates["npc_wolf"] = wolf_template
        
        prey = fauna_system.find_prey_in_room("npc_wolf", "room_forest_1")
        assert len(prey) == 0

    def test_find_predators_in_room(self, fauna_system, mock_world, deer_template, wolf_template):
        """Test finding predators in a room."""
        mock_world.npc_templates["npc_deer"] = deer_template
        mock_world.npc_templates["npc_wolf"] = wolf_template
        
        # Add wolf to room
        wolf_npc = MockNpc(
            id="wolf_1",
            template_id="npc_wolf",
            room_id="room_forest_1",
        )
        mock_world.npcs["wolf_1"] = wolf_npc
        mock_world.rooms["room_forest_1"].npc_ids = ["wolf_1"]
        
        # Deer looking for predators
        predators = fauna_system.find_predators_in_room("npc_deer", "room_forest_1")
        
        assert len(predators) == 1
        assert predators[0].template_id == "npc_wolf"

    def test_find_predators_no_predators(self, fauna_system, mock_world, deer_template):
        """Test finding predators when none exist."""
        mock_world.npc_templates["npc_deer"] = deer_template
        
        predators = fauna_system.find_predators_in_room("npc_deer", "room_forest_1")
        assert len(predators) == 0


# ============================================================================
# Death Handling Tests
# ============================================================================


@pytest.mark.systems
class TestDeathHandling:
    """Test abstract fauna death handling."""

    @pytest.mark.asyncio
    async def test_handle_fauna_death_logs(self, fauna_system, mock_world, deer_template):
        """Test that fauna death is logged."""
        from unittest.mock import MagicMock, AsyncMock
        
        mock_world.npc_templates["npc_deer"] = deer_template
        
        deer_npc = MockNpc(
            id="deer_1",
            template_id="npc_deer",
            room_id="room_forest_1",
        )
        
        session = MagicMock()
        
        with patch('daemons.engine.systems.fauna.logger') as mock_logger:
            await fauna_system.handle_fauna_death(deer_npc, "combat", session)
            
            # Should log the death
            assert mock_logger.debug.called

    @pytest.mark.asyncio
    async def test_handle_fauna_death_updates_population(self, fauna_system, mock_world, deer_template):
        """Test that death updates population manager."""
        mock_world.npc_templates["npc_deer"] = deer_template
        
        # Add population manager
        mock_pop_manager = MagicMock()
        mock_pop_manager.record_death = AsyncMock()
        fauna_system.population_manager = mock_pop_manager
        
        deer_npc = MockNpc(
            id="deer_1",
            template_id="npc_deer",
            room_id="room_forest_1",
        )
        
        session = MagicMock()
        await fauna_system.handle_fauna_death(deer_npc, "combat", session)
        
        mock_pop_manager.record_death.assert_called_once_with("npc_deer", "room_forest_1")


# ============================================================================
# Population Snapshot Tests
# ============================================================================


@pytest.mark.systems
class TestPopulationSnapshot:
    """Test population snapshot functionality."""

    def test_get_population_snapshot_empty(self, fauna_system):
        """Test snapshot of empty area."""
        snapshot = fauna_system.get_population_snapshot("area_forest")
        
        assert snapshot.area_id == "area_forest"
        assert snapshot.total_fauna == 0
        assert len(snapshot.fauna_counts) == 0

    def test_get_population_snapshot_with_fauna(self, fauna_system, mock_world, deer_template, wolf_template):
        """Test snapshot with fauna in area."""
        mock_world.npc_templates["npc_deer"] = deer_template
        mock_world.npc_templates["npc_wolf"] = wolf_template
        
        # Add NPCs
        deer1 = MockNpc(id="deer_1", template_id="npc_deer", room_id="room_forest_1")
        deer2 = MockNpc(id="deer_2", template_id="npc_deer", room_id="room_forest_1")
        wolf1 = MockNpc(id="wolf_1", template_id="npc_wolf", room_id="room_forest_2")
        
        mock_world.npcs = {
            "deer_1": deer1,
            "deer_2": deer2,
            "wolf_1": wolf1,
        }
        
        snapshot = fauna_system.get_population_snapshot("area_forest")
        
        assert snapshot.total_fauna == 3
        assert snapshot.fauna_counts["npc_deer"] == 2
        assert snapshot.fauna_counts["npc_wolf"] == 1


# ============================================================================
# Utility Method Tests
# ============================================================================


@pytest.mark.systems
class TestUtilityMethods:
    """Test utility methods."""

    def test_get_adjacent_rooms(self, fauna_system):
        """Test getting adjacent room IDs."""
        adjacent = fauna_system._get_adjacent_rooms("room_forest_1")
        
        assert "room_forest_2" in adjacent

    def test_get_adjacent_rooms_invalid(self, fauna_system):
        """Test getting adjacent rooms for invalid room."""
        adjacent = fauna_system._get_adjacent_rooms("room_nonexistent")
        assert adjacent == []

    def test_get_fauna_in_area(self, fauna_system, mock_world, deer_template):
        """Test getting all fauna in an area."""
        mock_world.npc_templates["npc_deer"] = deer_template
        
        deer1 = MockNpc(id="deer_1", template_id="npc_deer", room_id="room_forest_1")
        deer2 = MockNpc(id="deer_2", template_id="npc_deer", room_id="room_forest_2")
        
        mock_world.npcs = {
            "deer_1": deer1,
            "deer_2": deer2,
        }
        
        fauna_list = fauna_system.get_fauna_in_area("area_forest")
        
        assert len(fauna_list) == 2

    def test_is_biome_suitable_no_biome(self, fauna_system):
        """Test biome suitability with no biome returns True."""
        fauna = FaunaProperties(
            template_id="test",
            fauna_type=FaunaType.MAMMAL,
        )
        
        assert fauna_system._is_biome_suitable(fauna, None) is True

    def test_is_biome_suitable_matching_tags(self, fauna_system):
        """Test biome suitability with matching tags."""
        mock_biome = MagicMock()
        mock_biome.fauna_tags = ["forest", "temperate"]
        mock_biome.base_temperature = 70
        
        fauna = FaunaProperties(
            template_id="test",
            fauna_type=FaunaType.MAMMAL,
            biome_tags=["forest"],
            temperature_tolerance=(32, 100),
        )
        
        assert fauna_system._is_biome_suitable(fauna, mock_biome) is True

    def test_is_biome_suitable_no_matching_tags(self, fauna_system):
        """Test biome suitability with no matching tags."""
        mock_biome = MagicMock()
        mock_biome.fauna_tags = ["desert", "arid"]
        mock_biome.base_temperature = 70
        
        fauna = FaunaProperties(
            template_id="test",
            fauna_type=FaunaType.MAMMAL,
            biome_tags=["forest", "tundra"],
            temperature_tolerance=(32, 100),
        )
        
        assert fauna_system._is_biome_suitable(fauna, mock_biome) is False

    def test_is_biome_suitable_temperature_out_of_range(self, fauna_system):
        """Test biome suitability with temperature out of range."""
        mock_biome = MagicMock()
        mock_biome.fauna_tags = ["forest"]
        mock_biome.base_temperature = 110  # Too hot
        
        fauna = FaunaProperties(
            template_id="test",
            fauna_type=FaunaType.MAMMAL,
            biome_tags=["forest"],
            temperature_tolerance=(32, 100),
        )
        
        assert fauna_system._is_biome_suitable(fauna, mock_biome) is False
