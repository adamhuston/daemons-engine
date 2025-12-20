"""
Phase 17.4: Flora System

Manages flora templates and instances for harvestable plants and vegetation.

Flora provides:
- Environmental decoration and ambiance
- Harvestable resources (herbs, berries, wood, etc.)
- Cover and movement modifiers
- Biome-appropriate vegetation

The system is designed for extensibility:
- Templates loaded from YAML for easy content creation
- Instances track runtime state (harvest cooldowns, depletion)
- Hybrid respawn: passive chance + event-triggered (rain, seasons)
- Sustainability hooks for optional player impact tracking
"""

import logging
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from daemons.models import FloraInstance as FloraInstanceModel

if TYPE_CHECKING:
    from daemons.engine.systems.biome import BiomeDefinition, BiomeSystem, Season
    from daemons.engine.systems.temperature import TemperatureSystem
    from daemons.engine.systems.weather import WeatherState, WeatherSystem, WeatherType
    from daemons.engine.world import World, WorldArea, WorldRoom

logger = logging.getLogger(__name__)


# === Enums ===


class FloraType(str, Enum):
    """Types of flora for categorization and behavior."""

    TREE = "tree"
    SHRUB = "shrub"
    GRASS = "grass"
    FLOWER = "flower"
    FUNGUS = "fungus"
    VINE = "vine"
    AQUATIC = "aquatic"


class LightRequirement(str, Enum):
    """Light requirements for flora growth."""

    FULL_SUN = "full_sun"
    PARTIAL_SHADE = "partial_shade"
    SHADE = "shade"
    ANY = "any"


class MoistureRequirement(str, Enum):
    """Moisture requirements for flora growth."""

    ARID = "arid"
    DRY = "dry"
    MODERATE = "moderate"
    WET = "wet"
    AQUATIC = "aquatic"


class Rarity(str, Enum):
    """Flora rarity levels affecting spawn rates."""

    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"


# Rarity to spawn weight multiplier
RARITY_WEIGHTS = {
    Rarity.COMMON: 1.0,
    Rarity.UNCOMMON: 0.5,
    Rarity.RARE: 0.2,
    Rarity.VERY_RARE: 0.05,
}

# Flora density to max flora per room
DENSITY_LIMITS = {
    "barren": 0,
    "sparse": 2,
    "moderate": 5,
    "dense": 8,
    "lush": 12,
}


# === Dataclasses ===


@dataclass
class HarvestItem:
    """An item that can be obtained from harvesting flora."""

    item_id: str
    quantity: int = 1
    chance: float = 1.0
    skill_bonus: Optional[str] = None  # Skill that improves chance


@dataclass
class FloraTemplate:
    """
    Complete definition of a flora type loaded from YAML.

    This is the static template - instances use FloraInstance.
    """

    id: str
    name: str
    description: str
    flora_type: FloraType

    # Environmental requirements
    biome_tags: list[str] = field(default_factory=list)
    temperature_range: tuple[int, int] = (32, 100)  # Fahrenheit
    light_requirement: LightRequirement = LightRequirement.ANY
    moisture_requirement: MoistureRequirement = MoistureRequirement.MODERATE

    # Interaction properties
    harvestable: bool = False
    harvest_items: list[HarvestItem] = field(default_factory=list)
    harvest_cooldown: int = 3600  # Seconds until re-harvestable
    harvest_tool: Optional[str] = None  # Required tool item_type
    harvest_skill: Optional[str] = None  # Skill check for harvesting
    harvest_dc: int = 10  # Difficulty class if skill check required

    # Visual/seasonal
    seasonal_variants: dict[str, str] = field(default_factory=dict)
    dormant_seasons: list[str] = field(default_factory=list)  # Seasons when not harvestable

    # Gameplay effects
    provides_cover: bool = False
    cover_bonus: int = 2
    blocks_movement: bool = False
    blocks_directions: list[str] = field(default_factory=list)

    # Light emission (for bioluminescent flora like glowing mushrooms)
    provides_light: bool = False  # Whether flora emits light
    light_intensity: int = 0  # Light contribution (0-50)

    # Spawning
    rarity: Rarity = Rarity.COMMON
    cluster_size: tuple[int, int] = (1, 3)  # (min, max) plants per cluster


@dataclass
class FloraInstance:
    """
    Runtime state of a flora instance in the world.

    Corresponds to a database row in flora_instances.
    """

    id: int
    template_id: str
    room_id: str
    quantity: int
    last_harvested_at: Optional[float] = None  # Unix timestamp
    last_harvested_by: Optional[str] = None
    harvest_count: int = 0
    is_depleted: bool = False
    depleted_at: Optional[float] = None
    spawned_at: float = field(default_factory=time.time)
    is_permanent: bool = False

    @classmethod
    def from_model(cls, model: FloraInstanceModel) -> "FloraInstance":
        """Create from SQLAlchemy model."""
        return cls(
            id=model.id,
            template_id=model.template_id,
            room_id=model.room_id,
            quantity=model.quantity,
            last_harvested_at=model.last_harvested_at,
            last_harvested_by=model.last_harvested_by,
            harvest_count=model.harvest_count,
            is_depleted=model.is_depleted,
            depleted_at=model.depleted_at,
            spawned_at=model.spawned_at,
            is_permanent=model.is_permanent,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "template_id": self.template_id,
            "room_id": self.room_id,
            "quantity": self.quantity,
            "last_harvested_at": self.last_harvested_at,
            "harvest_count": self.harvest_count,
            "is_depleted": self.is_depleted,
            "is_permanent": self.is_permanent,
        }


@dataclass
class HarvestResult:
    """Result of a harvest action."""

    success: bool
    message: str
    items_gained: list[tuple[str, int]] = field(default_factory=list)  # (item_id, quantity)
    flora_depleted: bool = False
    skill_check_result: Optional[int] = None  # Roll result if skill check was made


@dataclass
class FloraRespawnConfig:
    """Configuration for flora respawn mechanics (see Design Decisions)."""

    passive_respawn_chance: float = 0.05  # 5% per tick
    rain_respawn_boost: float = 0.50  # 50% during rain
    storm_respawn_boost: float = 0.75  # 75% during storms
    season_change_refresh: bool = True  # Full refresh on season change

    # Spreading mechanics - flora can spread to connected rooms
    spread_chance: float = 0.10  # 10% chance to spread when regenerating
    spread_rain_boost: float = 0.15  # +15% during rain
    spread_storm_boost: float = 0.20  # +20% during storms

    # Per-flora-type modifiers
    type_modifiers: dict[FloraType, float] = field(
        default_factory=lambda: {
            FloraType.GRASS: 2.0,  # Grass regrows fast
            FloraType.FLOWER: 1.5,  # Flowers moderate
            FloraType.SHRUB: 1.0,  # Shrubs normal
            FloraType.TREE: 0.1,  # Trees very slow
            FloraType.FUNGUS: 1.5,  # Fungi moderate (moisture-dependent)
            FloraType.VINE: 1.2,  # Vines moderate
            FloraType.AQUATIC: 1.3,  # Aquatic moderate
        }
    )

    # Spread modifiers by flora type (some spread more easily)
    spread_type_modifiers: dict[FloraType, float] = field(
        default_factory=lambda: {
            FloraType.GRASS: 2.5,  # Grass spreads very easily
            FloraType.FLOWER: 1.5,  # Flowers spread via seeds
            FloraType.SHRUB: 0.8,  # Shrubs spread slowly
            FloraType.TREE: 0.2,  # Trees spread very slowly
            FloraType.FUNGUS: 2.0,  # Fungi spread via spores
            FloraType.VINE: 1.8,  # Vines spread quickly
            FloraType.AQUATIC: 1.0,  # Aquatic normal
        }
    )


@dataclass
class SustainabilityConfig:
    """Optional sustainability tracking - disabled by default (see Design Decisions)."""

    enabled: bool = False

    # If enabled, track harvesting impact
    overharvest_threshold: int = 10  # Harvests before impact triggers
    recovery_penalty_duration: int = 100  # Ticks before normal respawn resumes

    # Per-area tracking (only populated if enabled)
    area_harvest_counts: dict[str, int] = field(default_factory=dict)


# === Flora System ===


class FloraSystem:
    """
    Manages flora templates and instances.

    Responsibilities:
    - Load flora templates from YAML files
    - Spawn/despawn flora instances in rooms
    - Handle harvest interactions
    - Process respawns using hybrid system
    - Provide biome compatibility queries
    """

    def __init__(
        self,
        world: "World",
        biome_system: Optional["BiomeSystem"] = None,
        temperature_system: Optional["TemperatureSystem"] = None,
        weather_system: Optional["WeatherSystem"] = None,
        world_data_path: Optional[str] = None,
        respawn_config: Optional[FloraRespawnConfig] = None,
        sustainability_config: Optional[SustainabilityConfig] = None,
    ):
        self.world = world
        self.biome_system = biome_system
        self.temperature_system = temperature_system
        self.weather_system = weather_system

        # Configuration
        self.respawn_config = respawn_config or FloraRespawnConfig()
        self.sustainability_config = sustainability_config or SustainabilityConfig()

        # Template storage
        self._templates: dict[str, FloraTemplate] = {}

        # Determine world_data path
        if world_data_path is None:
            # Go up from systems/ to engine/ to daemons/, then into world_data/
            world_data_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "world_data"
            )
        self._flora_path = os.path.join(world_data_path, "flora")

        # Load flora templates
        self._load_templates()
        logger.info(f"FloraSystem initialized with {len(self._templates)} templates")

    # === Template Management ===

    def _load_templates(self) -> None:
        """Load all flora templates from YAML files."""
        if not os.path.isdir(self._flora_path):
            logger.warning(f"Flora directory not found: {self._flora_path}")
            return

        for filename in os.listdir(self._flora_path):
            if filename.endswith(".yaml") and not filename.startswith("_"):
                filepath = os.path.join(self._flora_path, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    if data and "id" in data:
                        template = self._parse_template(data)
                        self._templates[template.id] = template
                        logger.debug(f"Loaded flora template: {template.id}")
                except Exception as e:
                    logger.error(f"Failed to load flora from {filename}: {e}")

    def _parse_template(self, data: dict) -> FloraTemplate:
        """Parse a flora template from YAML data."""
        temp_range = data.get("temperature_range", [32, 100])

        # Parse harvest items
        harvest_items = []
        for item_data in data.get("harvest_items", []):
            harvest_items.append(
                HarvestItem(
                    item_id=item_data["item_id"],
                    quantity=item_data.get("quantity", 1),
                    chance=item_data.get("chance", 1.0),
                    skill_bonus=item_data.get("skill_bonus"),
                )
            )

        cluster_size = data.get("cluster_size", [1, 3])

        return FloraTemplate(
            id=data["id"],
            name=data.get("name", data["id"]),
            description=data.get("description", ""),
            flora_type=FloraType(data.get("flora_type", "shrub")),
            biome_tags=data.get("biome_tags", []),
            temperature_range=(temp_range[0], temp_range[1]),
            light_requirement=LightRequirement(data.get("light_requirement", "any")),
            moisture_requirement=MoistureRequirement(
                data.get("moisture_requirement", "moderate")
            ),
            harvestable=data.get("harvestable", False),
            harvest_items=harvest_items,
            harvest_cooldown=data.get("harvest_cooldown", 3600),
            harvest_tool=data.get("harvest_tool"),
            harvest_skill=data.get("harvest_skill"),
            harvest_dc=data.get("harvest_dc", 10),
            seasonal_variants=data.get("seasonal_variants", {}),
            dormant_seasons=data.get("dormant_seasons", []),
            provides_cover=data.get("provides_cover", False),
            cover_bonus=data.get("cover_bonus", 2),
            blocks_movement=data.get("blocks_movement", False),
            blocks_directions=data.get("blocks_directions", []),
            provides_light=data.get("provides_light", False),
            light_intensity=data.get("light_intensity", 0),
            rarity=Rarity(data.get("rarity", "common")),
            cluster_size=(cluster_size[0], cluster_size[1]),
        )

    def get_template(self, template_id: str) -> Optional[FloraTemplate]:
        """Get a flora template by ID."""
        return self._templates.get(template_id)

    def get_all_templates(self) -> list[FloraTemplate]:
        """Get all loaded flora templates."""
        return list(self._templates.values())

    def get_templates_for_biome(
        self, biome: "BiomeDefinition"
    ) -> list[FloraTemplate]:
        """Get all flora templates compatible with a biome."""
        compatible = []
        for template in self._templates.values():
            if not template.biome_tags:
                # No biome requirements, compatible with all
                compatible.append(template)
            elif any(tag in biome.flora_tags for tag in template.biome_tags):
                compatible.append(template)
        return compatible

    # === Instance Management ===

    async def get_room_flora(
        self, room_id: str, session: AsyncSession, include_depleted: bool = False
    ) -> list[FloraInstance]:
        """Get all flora instances in a room."""
        stmt = select(FloraInstanceModel).where(FloraInstanceModel.room_id == room_id)
        if not include_depleted:
            stmt = stmt.where(FloraInstanceModel.is_depleted == False)  # noqa: E712

        result = await session.execute(stmt)
        models = result.scalars().all()
        return [FloraInstance.from_model(m) for m in models]

    async def spawn_flora(
        self,
        room_id: str,
        template_id: str,
        session: AsyncSession,
        quantity: int = 1,
        permanent: bool = False,
    ) -> Optional[FloraInstance]:
        """Spawn flora in a room."""
        template = self.get_template(template_id)
        if not template:
            logger.warning(f"Cannot spawn unknown flora template: {template_id}")
            return None

        # Create database record
        model = FloraInstanceModel(
            template_id=template_id,
            room_id=room_id,
            quantity=quantity,
            is_permanent=permanent,
            spawned_at=time.time(),
        )
        session.add(model)
        await session.flush()  # Get the ID

        instance = FloraInstance.from_model(model)
        logger.debug(f"Spawned flora {template_id} in room {room_id}")
        return instance

    async def despawn_flora(
        self, instance_id: int, session: AsyncSession, permanent_delete: bool = False
    ) -> bool:
        """Remove or deplete a flora instance."""
        stmt = select(FloraInstanceModel).where(FloraInstanceModel.id == instance_id)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return False

        if permanent_delete:
            await session.delete(model)
        else:
            # Mark as depleted for respawn
            model.is_depleted = True
            model.depleted_at = time.time()

        return True

    # === Condition Checking ===

    def can_exist_in_room(
        self,
        template: FloraTemplate,
        room: "WorldRoom",
        area: "WorldArea",
    ) -> tuple[bool, list[str]]:
        """
        Check if flora can exist in room conditions.

        Returns (can_exist, list of warning messages).
        """
        warnings = []

        # Check biome compatibility
        if self.biome_system and template.biome_tags:
            biome = self.biome_system.get_biome_for_area(area.id)
            if biome and not any(tag in biome.flora_tags for tag in template.biome_tags):
                return False, ["Incompatible biome"]

        # Check temperature
        if self.temperature_system:
            temp = self.temperature_system.calculate_room_temperature(room, area)
            min_t, max_t = template.temperature_range
            if temp.effective_temperature < min_t or temp.effective_temperature > max_t:
                warnings.append(
                    f"Temperature {temp.effective_temperature}°F outside range [{min_t}, {max_t}]"
                )

        return len(warnings) == 0, warnings

    def is_dormant(self, template: FloraTemplate, season: "Season") -> bool:
        """Check if flora is dormant in the current season."""
        return season.value in template.dormant_seasons

    # === Harvest System ===

    def can_harvest(
        self,
        player_id: str,
        instance: FloraInstance,
        equipped_tool: Optional[str] = None,
        current_season: Optional["Season"] = None,
    ) -> tuple[bool, str]:
        """Check if player can harvest this flora."""
        template = self.get_template(instance.template_id)
        if not template:
            return False, "Unknown flora type"

        if not template.harvestable:
            return False, f"You cannot harvest {template.name}."

        if instance.is_depleted:
            return False, f"The {template.name} has been depleted."

        # Check dormancy
        if current_season and self.is_dormant(template, current_season):
            return False, f"The {template.name} is dormant in {current_season.value}."

        # Check cooldown
        if instance.last_harvested_at:
            elapsed = time.time() - instance.last_harvested_at
            if elapsed < template.harvest_cooldown:
                remaining = int(template.harvest_cooldown - elapsed)
                return False, f"{template.name} was recently harvested. Try again in {remaining}s."

        # Check tool requirement
        if template.harvest_tool and equipped_tool != template.harvest_tool:
            return False, f"You need a {template.harvest_tool} to harvest {template.name}."

        return True, ""

    async def harvest(
        self,
        player_id: str,
        instance: FloraInstance,
        session: AsyncSession,
        skill_roll: Optional[int] = None,
    ) -> HarvestResult:
        """
        Harvest flora and grant items.

        By default, harvesting has no lasting ecosystem impact.
        The sustainability hook (on_harvest) is a no-op unless
        SustainabilityConfig is explicitly enabled.
        """
        template = self.get_template(instance.template_id)
        if not template:
            return HarvestResult(success=False, message="Unknown flora type")

        # Calculate harvest results
        items_gained: list[tuple[str, int]] = []

        for harvest_item in template.harvest_items:
            # Check chance
            roll = random.random()
            effective_chance = harvest_item.chance

            # Apply skill bonus if provided
            if skill_roll is not None and harvest_item.skill_bonus:
                # Higher skill roll = better chance
                effective_chance = min(1.0, effective_chance + (skill_roll - 10) * 0.02)

            if roll <= effective_chance:
                items_gained.append((harvest_item.item_id, harvest_item.quantity))

        # Update instance state
        stmt = select(FloraInstanceModel).where(FloraInstanceModel.id == instance.id)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            model.last_harvested_at = time.time()
            model.last_harvested_by = player_id
            model.harvest_count += 1

            # Deplete if quantity exhausted (for now, always deplete after harvest)
            model.quantity -= 1
            flora_depleted = model.quantity <= 0
            if flora_depleted:
                model.is_depleted = True
                model.depleted_at = time.time()

        # Sustainability hook - no-op by default
        await self.on_harvest(instance, player_id)

        message = f"You harvest from the {template.name}."
        if items_gained:
            item_strs = [f"{qty}x {item_id}" for item_id, qty in items_gained]
            message += f" You obtain: {', '.join(item_strs)}."
        else:
            message += " You find nothing useful."

        if flora_depleted:
            message += f" The {template.name} has been exhausted."

        return HarvestResult(
            success=True,
            message=message,
            items_gained=items_gained,
            flora_depleted=flora_depleted,
            skill_check_result=skill_roll,
        )

    async def on_harvest(self, flora: FloraInstance, harvester_id: str) -> None:
        """
        Hook for sustainability tracking - no-op by default.

        Override or enable SustainabilityConfig to track player impact.
        """
        if not self.sustainability_config.enabled:
            return

        # Track harvesting for sustainability impact
        # (Would need to look up area from room)
        logger.debug(f"Sustainability tracking: {harvester_id} harvested {flora.template_id}")

    # === Respawn System ===

    def _get_adjacent_room_ids(self, room_id: str) -> list[str]:
        """Get IDs of rooms connected to this room."""
        room = self.world.rooms.get(room_id)
        if not room:
            return []

        adjacent = []
        for direction in ["north", "south", "east", "west", "up", "down"]:
            exit_id = getattr(room, f"{direction}_id", None)
            if exit_id:
                adjacent.append(exit_id)
        return adjacent

    def get_spread_chance(
        self,
        template: FloraTemplate,
        weather_state: Optional["WeatherState"] = None,
    ) -> float:
        """Calculate spread chance based on weather and flora type."""
        config = self.respawn_config
        base_chance = config.spread_chance

        # Weather boost
        if weather_state and self.weather_system:
            from daemons.engine.systems.weather import WeatherType

            if weather_state.weather_type == WeatherType.RAIN:
                base_chance += config.spread_rain_boost
            elif weather_state.weather_type == WeatherType.STORM:
                base_chance += config.spread_storm_boost

        # Flora type modifier
        type_mod = config.spread_type_modifiers.get(template.flora_type, 1.0)

        return min(1.0, base_chance * type_mod)

    async def _try_spread_flora(
        self,
        source_room_id: str,
        template: FloraTemplate,
        session: AsyncSession,
        weather_state: Optional["WeatherState"] = None,
    ) -> Optional[FloraInstance]:
        """
        Attempt to spread flora to an adjacent room.

        Returns the new FloraInstance if spread succeeded, None otherwise.
        """
        # Get adjacent rooms
        adjacent = self._get_adjacent_room_ids(source_room_id)
        if not adjacent:
            return None

        # Pick a random adjacent room
        target_room_id = random.choice(adjacent)
        target_room = self.world.rooms.get(target_room_id)
        if not target_room:
            return None

        # Get the area for biome/compatibility checks
        area_id = getattr(target_room, "area_id", None)
        area = self.world.areas.get(area_id) if area_id else None

        # Check if flora can exist in target room
        if area:
            can_exist, _ = self.can_exist_in_room(template, target_room, area)
            if not can_exist:
                return None

            # Check biome compatibility
            if self.biome_system:
                biome = self.biome_system.get_biome_for_area(area_id)
                if biome and template.biome_tags:
                    if not any(tag in biome.flora_tags for tag in template.biome_tags):
                        return None

        # Check if target room already has this flora type
        existing = await self.get_room_flora(target_room_id, session)
        for flora in existing:
            if flora.template_id == template.id:
                # Already has this flora, don't duplicate
                return None

        # Check density limit
        if area:
            density = getattr(area, "flora_density", "moderate")
            max_flora = DENSITY_LIMITS.get(density, 5)
            current_count = sum(f.quantity for f in existing)
            if current_count >= max_flora:
                return None

        # Spread! Create new flora instance
        quantity = random.randint(*template.cluster_size)
        # Start with smaller quantity for spread (seeds/spores)
        quantity = max(1, quantity // 2)

        instance = await self.spawn_flora(
            target_room_id, template.id, session, quantity=quantity
        )

        if instance:
            logger.debug(
                f"Flora {template.id} spread from {source_room_id} to {target_room_id}"
            )

        return instance

    async def process_respawns(
        self,
        area_id: str,
        session: AsyncSession,
        weather_state: Optional["WeatherState"] = None,
    ) -> int:
        """
        Process flora respawns using hybrid system.

        Uses passive chance + event-triggered respawns:
        - Base passive_respawn_chance per tick
        - Boosted during rain/storms
        - Full refresh on season changes
        - Chance to spread to connected rooms when regenerating

        Returns count of respawned flora.
        """
        # Get all depleted flora in the area
        # (This is simplified - would need room-to-area mapping)
        stmt = select(FloraInstanceModel).where(
            FloraInstanceModel.is_depleted == True  # noqa: E712
        )
        result = await session.execute(stmt)
        depleted = result.scalars().all()

        respawned = 0
        spread_count = 0

        for model in depleted:
            template = self.get_template(model.template_id)
            if not template:
                continue

            # Calculate respawn chance
            chance = self.get_respawn_chance(template, weather_state)

            if random.random() <= chance:
                # Respawn!
                model.is_depleted = False
                model.depleted_at = None
                model.quantity = random.randint(*template.cluster_size)
                respawned += 1

                # Chance to spread to adjacent room
                spread_chance = self.get_spread_chance(template, weather_state)
                if random.random() <= spread_chance:
                    spread_result = await self._try_spread_flora(
                        model.room_id, template, session, weather_state
                    )
                    if spread_result:
                        spread_count += 1

        if respawned > 0:
            logger.debug(f"Respawned {respawned} flora instances")
        if spread_count > 0:
            logger.debug(f"Flora spread to {spread_count} new locations")

        return respawned

    def get_respawn_chance(
        self,
        template: FloraTemplate,
        weather_state: Optional["WeatherState"] = None,
    ) -> float:
        """Calculate respawn chance based on weather and flora type."""
        config = self.respawn_config
        base_chance = config.passive_respawn_chance

        # Weather boost
        if weather_state and self.weather_system:
            from daemons.engine.systems.weather import WeatherType

            if weather_state.weather_type == WeatherType.RAIN:
                base_chance += config.rain_respawn_boost
            elif weather_state.weather_type == WeatherType.STORM:
                base_chance += config.storm_respawn_boost

        # Flora type modifier
        type_mod = config.type_modifiers.get(template.flora_type, 1.0)

        return min(1.0, base_chance * type_mod)

    async def process_season_change(
        self, area_id: str, new_season: "Season", session: AsyncSession
    ) -> int:
        """
        Handle season change - refresh seasonal flora.

        Called when a season changes in an area.
        """
        if not self.respawn_config.season_change_refresh:
            return 0

        # Refresh all depleted flora (simplified)
        stmt = select(FloraInstanceModel).where(
            FloraInstanceModel.is_depleted == True  # noqa: E712
        )
        result = await session.execute(stmt)
        depleted = result.scalars().all()

        refreshed = 0
        for model in depleted:
            template = self.get_template(model.template_id)
            if not template:
                continue

            # Don't refresh if dormant in new season
            if new_season.value in template.dormant_seasons:
                continue

            model.is_depleted = False
            model.depleted_at = None
            model.quantity = random.randint(*template.cluster_size)
            refreshed += 1

        if refreshed > 0:
            logger.info(f"Season change: refreshed {refreshed} flora instances")

        return refreshed

    # === Display ===

    def get_description(
        self, template: FloraTemplate, season: Optional["Season"] = None
    ) -> str:
        """Get flora description for current season."""
        if season and season.value in template.seasonal_variants:
            return template.seasonal_variants[season.value]
        return template.description

    def format_room_flora(
        self,
        flora_list: list[FloraInstance],
        season: Optional["Season"] = None,
    ) -> str:
        """Format flora list for room description."""
        if not flora_list:
            return ""

        # Group by template
        grouped: dict[str, int] = {}
        for instance in flora_list:
            template = self.get_template(instance.template_id)
            if template:
                name = template.name
                grouped[name] = grouped.get(name, 0) + instance.quantity

        if not grouped:
            return ""

        # Format as natural language
        parts = []
        for name, count in grouped.items():
            if count > 1:
                parts.append(f"{count} {name}")
            else:
                parts.append(f"a {name}")

        if len(parts) == 1:
            return f"You see {parts[0]} here."
        elif len(parts) == 2:
            return f"You see {parts[0]} and {parts[1]} here."
        else:
            return f"You see {', '.join(parts[:-1])}, and {parts[-1]} here."

    # === Spawning Helpers ===

    async def spawn_flora_for_room(
        self,
        room: "WorldRoom",
        area: "WorldArea",
        session: AsyncSession,
        max_flora: Optional[int] = None,
    ) -> list[FloraInstance]:
        """
        Spawn appropriate flora for a room based on biome.

        Uses area flora density and biome compatibility.
        Skips rooms with no_flora=True.
        """
        spawned = []

        # Check if room disallows flora
        if getattr(room, "no_flora", False):
            logger.debug(f"Room {room.id} has no_flora=True, skipping flora spawn")
            return spawned

        # Determine max flora
        if max_flora is None:
            density = getattr(area, "flora_density", "moderate")
            max_flora = DENSITY_LIMITS.get(density, 5)

        if max_flora <= 0:
            return spawned

        # Get existing flora count
        existing = await self.get_room_flora(room.id, session)
        current_count = sum(f.quantity for f in existing)

        if current_count >= max_flora:
            return spawned

        # Get compatible templates
        if self.biome_system:
            biome = self.biome_system.get_biome_for_area(area)
            if biome:
                compatible = self.get_templates_for_biome(biome)
            else:
                compatible = self.get_all_templates()
        else:
            compatible = self.get_all_templates()

        if not compatible:
            return spawned

        # Weighted random selection
        weights = [RARITY_WEIGHTS[t.rarity] for t in compatible]
        remaining = max_flora - current_count

        while remaining > 0 and compatible:
            template = random.choices(compatible, weights=weights, k=1)[0]

            # Check room compatibility
            can_exist, _ = self.can_exist_in_room(template, room, area)
            if not can_exist:
                continue

            # Spawn a cluster
            quantity = min(remaining, random.randint(*template.cluster_size))
            instance = await self.spawn_flora(
                room.id, template.id, session, quantity=quantity
            )
            if instance:
                spawned.append(instance)
                remaining -= quantity

            # Don't spawn too many of one type
            if len(spawned) >= 3:
                break

        return spawned
