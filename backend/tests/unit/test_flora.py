"""
Unit tests for Phase 17.4: Flora System

Tests cover:
- FloraTemplate loading from YAML
- FloraInstance management (spawn, despawn)
- Harvest mechanics (cooldowns, tools, dormancy)
- Respawn system (passive, weather-boosted, season refresh)
- Biome compatibility
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daemons.engine.systems.flora import (
    DENSITY_LIMITS,
    RARITY_WEIGHTS,
    FloraInstance,
    FloraRespawnConfig,
    FloraSystem,
    FloraTemplate,
    FloraType,
    HarvestItem,
    HarvestResult,
    LightRequirement,
    MoistureRequirement,
    Rarity,
    SustainabilityConfig,
)


# === Fixtures ===


@pytest.fixture
def mock_world():
    """Create a mock World object."""
    world = MagicMock()
    world.areas = {}
    world.rooms = {}
    return world


@pytest.fixture
def mock_biome_system():
    """Create a mock BiomeSystem."""
    biome_system = MagicMock()
    biome_system.get_biome_for_area.return_value = MagicMock(
        flora_tags=["temperate", "forest", "woodland"],
        base_temperature=70,
    )
    return biome_system


@pytest.fixture
def mock_temperature_system():
    """Create a mock TemperatureSystem."""
    temp_system = MagicMock()
    temp_system.calculate_room_temperature.return_value = MagicMock(
        effective_temperature=72
    )
    return temp_system


@pytest.fixture
def mock_weather_system():
    """Create a mock WeatherSystem."""
    weather_system = MagicMock()
    return weather_system


@pytest.fixture
def flora_system(mock_world, mock_biome_system, mock_temperature_system, mock_weather_system):
    """Create a FloraSystem with mocked dependencies."""
    with patch.object(FloraSystem, "_load_templates"):
        system = FloraSystem(
            world=mock_world,
            biome_system=mock_biome_system,
            temperature_system=mock_temperature_system,
            weather_system=mock_weather_system,
        )
    return system


@pytest.fixture
def sample_template():
    """Create a sample flora template."""
    return FloraTemplate(
        id="flora_test_berry",
        name="test berry bush",
        description="A test berry bush for unit testing.",
        flora_type=FloraType.SHRUB,
        biome_tags=["temperate", "forest"],
        temperature_range=(40, 90),
        harvestable=True,
        harvest_items=[
            HarvestItem(item_id="item_berries", quantity=3, chance=0.8),
            HarvestItem(item_id="item_seeds", quantity=1, chance=0.2),
        ],
        harvest_cooldown=3600,
        rarity=Rarity.COMMON,
        cluster_size=(2, 5),
    )


@pytest.fixture
def sample_instance():
    """Create a sample flora instance."""
    return FloraInstance(
        id=1,
        template_id="flora_test_berry",
        room_id="test_room_1",
        quantity=3,
        spawned_at=time.time(),
    )


# === FloraTemplate Tests ===


class TestFloraTemplate:
    """Tests for FloraTemplate dataclass."""

    def test_create_basic_template(self):
        """Test creating a basic flora template."""
        template = FloraTemplate(
            id="flora_oak",
            name="oak tree",
            description="A tall oak tree.",
            flora_type=FloraType.TREE,
        )
        assert template.id == "flora_oak"
        assert template.name == "oak tree"
        assert template.flora_type == FloraType.TREE
        assert template.harvestable is False
        assert template.rarity == Rarity.COMMON

    def test_template_with_harvest_items(self, sample_template):
        """Test template with harvest items."""
        assert sample_template.harvestable is True
        assert len(sample_template.harvest_items) == 2
        assert sample_template.harvest_items[0].item_id == "item_berries"
        assert sample_template.harvest_items[0].quantity == 3
        assert sample_template.harvest_items[0].chance == 0.8

    def test_template_defaults(self):
        """Test template default values."""
        template = FloraTemplate(
            id="flora_test",
            name="test",
            description="test",
            flora_type=FloraType.GRASS,
        )
        assert template.temperature_range == (32, 100)
        assert template.light_requirement == LightRequirement.ANY
        assert template.moisture_requirement == MoistureRequirement.MODERATE
        assert template.cluster_size == (1, 3)
        assert template.provides_cover is False


# === FloraInstance Tests ===


class TestFloraInstance:
    """Tests for FloraInstance dataclass."""

    def test_create_instance(self, sample_instance):
        """Test creating a flora instance."""
        assert sample_instance.id == 1
        assert sample_instance.template_id == "flora_test_berry"
        assert sample_instance.room_id == "test_room_1"
        assert sample_instance.quantity == 3
        assert sample_instance.is_depleted is False

    def test_to_dict(self, sample_instance):
        """Test serialization to dictionary."""
        data = sample_instance.to_dict()
        assert data["id"] == 1
        assert data["template_id"] == "flora_test_berry"
        assert data["room_id"] == "test_room_1"
        assert data["quantity"] == 3
        assert data["is_depleted"] is False


# === FloraSystem Template Management ===


class TestFloraSystemTemplates:
    """Tests for FloraSystem template management."""

    def test_get_template_not_found(self, flora_system):
        """Test getting a template that doesn't exist."""
        result = flora_system.get_template("nonexistent")
        assert result is None

    def test_get_template_found(self, flora_system, sample_template):
        """Test getting a template that exists."""
        flora_system._templates["flora_test_berry"] = sample_template
        result = flora_system.get_template("flora_test_berry")
        assert result == sample_template

    def test_get_all_templates(self, flora_system, sample_template):
        """Test getting all templates."""
        flora_system._templates["flora_test_berry"] = sample_template
        flora_system._templates["flora_oak"] = FloraTemplate(
            id="flora_oak",
            name="oak",
            description="oak tree",
            flora_type=FloraType.TREE,
        )
        templates = flora_system.get_all_templates()
        assert len(templates) == 2

    def test_get_templates_for_biome(self, flora_system, sample_template, mock_biome_system):
        """Test getting templates compatible with a biome."""
        flora_system._templates["flora_test_berry"] = sample_template
        
        # Add incompatible template
        desert_template = FloraTemplate(
            id="flora_cactus",
            name="cactus",
            description="desert cactus",
            flora_type=FloraType.SHRUB,
            biome_tags=["desert", "arid"],  # Not in mock biome's flora_tags
        )
        flora_system._templates["flora_cactus"] = desert_template
        
        biome = mock_biome_system.get_biome_for_area("test_area")
        compatible = flora_system.get_templates_for_biome(biome)
        
        # sample_template should match, desert_template should not
        assert sample_template in compatible
        assert desert_template not in compatible


# === Harvest System Tests ===


class TestHarvestSystem:
    """Tests for harvest mechanics."""

    def test_can_harvest_not_harvestable(self, flora_system, sample_instance):
        """Test cannot harvest non-harvestable flora."""
        template = FloraTemplate(
            id="flora_test_grass",
            name="grass",
            description="just grass",
            flora_type=FloraType.GRASS,
            harvestable=False,
        )
        flora_system._templates["flora_test_grass"] = template
        sample_instance.template_id = "flora_test_grass"
        
        can, reason = flora_system.can_harvest("player1", sample_instance)
        assert can is False
        assert "cannot harvest" in reason.lower()

    def test_can_harvest_depleted(self, flora_system, sample_template, sample_instance):
        """Test cannot harvest depleted flora."""
        flora_system._templates["flora_test_berry"] = sample_template
        sample_instance.is_depleted = True
        
        can, reason = flora_system.can_harvest("player1", sample_instance)
        assert can is False
        assert "depleted" in reason.lower()

    def test_can_harvest_on_cooldown(self, flora_system, sample_template, sample_instance):
        """Test cannot harvest flora on cooldown."""
        flora_system._templates["flora_test_berry"] = sample_template
        sample_instance.last_harvested_at = time.time()  # Just now
        
        can, reason = flora_system.can_harvest("player1", sample_instance)
        assert can is False
        assert "recently harvested" in reason.lower()

    def test_can_harvest_cooldown_expired(self, flora_system, sample_template, sample_instance):
        """Test can harvest after cooldown expires."""
        flora_system._templates["flora_test_berry"] = sample_template
        sample_instance.last_harvested_at = time.time() - 7200  # 2 hours ago
        
        can, reason = flora_system.can_harvest("player1", sample_instance)
        assert can is True
        assert reason == ""

    def test_can_harvest_wrong_tool(self, flora_system, sample_instance):
        """Test cannot harvest without required tool."""
        template = FloraTemplate(
            id="flora_test_tree",
            name="tree",
            description="a tree",
            flora_type=FloraType.TREE,
            harvestable=True,
            harvest_tool="axe",
        )
        flora_system._templates["flora_test_tree"] = template
        sample_instance.template_id = "flora_test_tree"
        
        can, reason = flora_system.can_harvest("player1", sample_instance, equipped_tool="sword")
        assert can is False
        assert "need a axe" in reason.lower()

    def test_can_harvest_with_correct_tool(self, flora_system, sample_instance):
        """Test can harvest with correct tool."""
        template = FloraTemplate(
            id="flora_test_tree",
            name="tree",
            description="a tree",
            flora_type=FloraType.TREE,
            harvestable=True,
            harvest_tool="axe",
        )
        flora_system._templates["flora_test_tree"] = template
        sample_instance.template_id = "flora_test_tree"
        
        can, reason = flora_system.can_harvest("player1", sample_instance, equipped_tool="axe")
        assert can is True

    def test_can_harvest_dormant_season(self, flora_system, sample_template, sample_instance):
        """Test cannot harvest during dormant season."""
        from daemons.engine.systems.biome import Season
        
        sample_template.dormant_seasons = ["winter"]
        flora_system._templates["flora_test_berry"] = sample_template
        
        can, reason = flora_system.can_harvest(
            "player1", sample_instance, current_season=Season.WINTER
        )
        assert can is False
        assert "dormant" in reason.lower()


# === Respawn System Tests ===


class TestRespawnSystem:
    """Tests for flora respawn mechanics."""

    def test_get_respawn_chance_base(self, flora_system, sample_template):
        """Test base respawn chance."""
        chance = flora_system.get_respawn_chance(sample_template)
        # Base 5% * shrub modifier (1.0) = 5%
        assert chance == pytest.approx(0.05, rel=0.01)

    def test_get_respawn_chance_rain_boost(self, flora_system, sample_template, mock_weather_system):
        """Test respawn chance boosted by rain."""
        from daemons.engine.systems.weather import WeatherType
        
        weather_state = MagicMock()
        weather_state.weather_type = WeatherType.RAIN
        
        chance = flora_system.get_respawn_chance(sample_template, weather_state)
        # Base 5% + 50% rain boost, capped at 1.0
        expected = min(1.0, (0.05 + 0.50) * 1.0)
        assert chance == pytest.approx(expected, rel=0.01)

    def test_get_respawn_chance_storm_boost(self, flora_system, sample_template, mock_weather_system):
        """Test respawn chance boosted by storm."""
        from daemons.engine.systems.weather import WeatherType
        
        weather_state = MagicMock()
        weather_state.weather_type = WeatherType.STORM
        
        chance = flora_system.get_respawn_chance(sample_template, weather_state)
        # Base 5% + 75% storm boost
        expected = min(1.0, (0.05 + 0.75) * 1.0)
        assert chance == pytest.approx(expected, rel=0.01)

    def test_get_respawn_chance_grass_modifier(self, flora_system):
        """Test grass has higher respawn rate."""
        grass_template = FloraTemplate(
            id="flora_grass",
            name="grass",
            description="grass",
            flora_type=FloraType.GRASS,
        )
        chance = flora_system.get_respawn_chance(grass_template)
        # Base 5% * grass modifier (2.0) = 10%
        assert chance == pytest.approx(0.10, rel=0.01)

    def test_get_respawn_chance_tree_modifier(self, flora_system):
        """Test trees have lower respawn rate."""
        tree_template = FloraTemplate(
            id="flora_tree",
            name="tree",
            description="tree",
            flora_type=FloraType.TREE,
        )
        chance = flora_system.get_respawn_chance(tree_template)
        # Base 5% * tree modifier (0.1) = 0.5%
        assert chance == pytest.approx(0.005, rel=0.01)


# === Condition Checking Tests ===


class TestConditionChecking:
    """Tests for flora condition checking."""

    def test_can_exist_in_room_compatible(
        self, flora_system, sample_template, mock_biome_system, mock_temperature_system
    ):
        """Test flora can exist in compatible room."""
        room = MagicMock()
        area = MagicMock()
        area.id = "test_area"
        
        can_exist, warnings = flora_system.can_exist_in_room(sample_template, room, area)
        assert can_exist is True
        assert len(warnings) == 0

    def test_can_exist_in_room_wrong_biome(
        self, flora_system, mock_biome_system, mock_temperature_system
    ):
        """Test flora cannot exist in incompatible biome."""
        # Set up biome that doesn't match
        mock_biome_system.get_biome_for_area.return_value = MagicMock(
            flora_tags=["arctic", "tundra"],
        )
        
        desert_template = FloraTemplate(
            id="flora_cactus",
            name="cactus",
            description="desert cactus",
            flora_type=FloraType.SHRUB,
            biome_tags=["desert", "arid"],
        )
        
        room = MagicMock()
        area = MagicMock()
        area.id = "test_area"
        
        can_exist, _ = flora_system.can_exist_in_room(desert_template, room, area)
        assert can_exist is False

    def test_is_dormant_winter(self, flora_system, sample_template):
        """Test flora dormancy check."""
        from daemons.engine.systems.biome import Season
        
        sample_template.dormant_seasons = ["winter"]
        
        assert flora_system.is_dormant(sample_template, Season.WINTER) is True
        assert flora_system.is_dormant(sample_template, Season.SUMMER) is False


# === Display Tests ===


class TestFloraDisplay:
    """Tests for flora display formatting."""

    def test_get_description_default(self, flora_system, sample_template):
        """Test getting default description."""
        desc = flora_system.get_description(sample_template)
        assert desc == sample_template.description

    def test_get_description_seasonal(self, flora_system, sample_template):
        """Test getting seasonal description."""
        from daemons.engine.systems.biome import Season
        
        sample_template.seasonal_variants = {
            "summer": "A berry bush heavy with ripe fruit.",
            "winter": "A bare berry bush.",
        }
        
        summer_desc = flora_system.get_description(sample_template, Season.SUMMER)
        assert summer_desc == "A berry bush heavy with ripe fruit."
        
        winter_desc = flora_system.get_description(sample_template, Season.WINTER)
        assert winter_desc == "A bare berry bush."
        
        # Fall not defined, should return default
        fall_desc = flora_system.get_description(sample_template, Season.FALL)
        assert fall_desc == sample_template.description

    def test_format_room_flora_empty(self, flora_system):
        """Test formatting empty flora list."""
        result = flora_system.format_room_flora([])
        assert result == ""

    def test_format_room_flora_single(self, flora_system, sample_template, sample_instance):
        """Test formatting single flora type."""
        flora_system._templates["flora_test_berry"] = sample_template
        result = flora_system.format_room_flora([sample_instance])
        assert "test berry bush" in result.lower()

    def test_format_room_flora_multiple(self, flora_system, sample_template, sample_instance):
        """Test formatting multiple flora types."""
        flora_system._templates["flora_test_berry"] = sample_template
        
        tree_template = FloraTemplate(
            id="flora_oak",
            name="oak tree",
            description="an oak",
            flora_type=FloraType.TREE,
        )
        flora_system._templates["flora_oak"] = tree_template
        
        tree_instance = FloraInstance(
            id=2,
            template_id="flora_oak",
            room_id="test_room_1",
            quantity=1,
            spawned_at=time.time(),
        )
        
        result = flora_system.format_room_flora([sample_instance, tree_instance])
        assert "berry" in result.lower()
        assert "oak" in result.lower()


# === Configuration Tests ===


class TestFloraConfiguration:
    """Tests for flora configuration dataclasses."""

    def test_respawn_config_defaults(self):
        """Test FloraRespawnConfig default values."""
        config = FloraRespawnConfig()
        assert config.passive_respawn_chance == 0.05
        assert config.rain_respawn_boost == 0.50
        assert config.storm_respawn_boost == 0.75
        assert config.season_change_refresh is True

    def test_respawn_config_type_modifiers(self):
        """Test FloraRespawnConfig type modifiers."""
        config = FloraRespawnConfig()
        assert config.type_modifiers[FloraType.GRASS] == 2.0
        assert config.type_modifiers[FloraType.TREE] == 0.1

    def test_sustainability_config_defaults(self):
        """Test SustainabilityConfig defaults (disabled)."""
        config = SustainabilityConfig()
        assert config.enabled is False
        assert config.overharvest_threshold == 10

    def test_rarity_weights(self):
        """Test RARITY_WEIGHTS constants."""
        assert RARITY_WEIGHTS[Rarity.COMMON] == 1.0
        assert RARITY_WEIGHTS[Rarity.UNCOMMON] == 0.5
        assert RARITY_WEIGHTS[Rarity.RARE] == 0.2
        assert RARITY_WEIGHTS[Rarity.VERY_RARE] == 0.05

    def test_density_limits(self):
        """Test DENSITY_LIMITS constants."""
        assert DENSITY_LIMITS["barren"] == 0
        assert DENSITY_LIMITS["sparse"] == 2
        assert DENSITY_LIMITS["moderate"] == 5
        assert DENSITY_LIMITS["dense"] == 8
        assert DENSITY_LIMITS["lush"] == 12


# === Integration Tests ===


class TestFloraIntegration:
    """Integration tests for flora system."""

    @pytest.mark.asyncio
    async def test_spawn_flora(self, flora_system, sample_template):
        """Test spawning flora in a room."""
        flora_system._templates["flora_test_berry"] = sample_template
        
        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()
        
        with patch("daemons.engine.systems.flora.FloraInstanceModel") as MockModel:
            mock_instance = MagicMock()
            mock_instance.id = 1
            mock_instance.template_id = "flora_test_berry"
            mock_instance.room_id = "test_room"
            mock_instance.quantity = 3
            mock_instance.last_harvested_at = None
            mock_instance.last_harvested_by = None
            mock_instance.harvest_count = 0
            mock_instance.is_depleted = False
            mock_instance.depleted_at = None
            mock_instance.spawned_at = time.time()
            mock_instance.is_permanent = False
            MockModel.return_value = mock_instance
            
            result = await flora_system.spawn_flora(
                room_id="test_room",
                template_id="flora_test_berry",
                session=mock_session,
                quantity=3,
            )
            
            assert result is not None
            assert result.template_id == "flora_test_berry"
            assert result.room_id == "test_room"
            mock_session.add.assert_called_once()
            mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_spawn_flora_unknown_template(self, flora_system):
        """Test spawning flora with unknown template."""
        mock_session = AsyncMock()
        
        result = await flora_system.spawn_flora(
            room_id="test_room",
            template_id="nonexistent",
            session=mock_session,
        )
        
        assert result is None
        mock_session.add.assert_not_called()
