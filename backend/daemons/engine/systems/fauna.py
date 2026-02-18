"""
Phase 17.5: Fauna System

Extends the NPC system with fauna-specific behaviors for wildlife simulation.

Fauna provides:
- Ecological wildlife that responds to environment
- Predator-prey dynamics
- Activity periods (diurnal, nocturnal, crepuscular)
- Pack spawning with leaders
- Migration based on seasons
- Cross-area movement with biome awareness

Design Decisions (see Phase17_implementation.md):
- Abstract death model: no loot, no corpses
- Cross-area migration with biome awareness
- Fauna as world ambiance, not loot sources
"""

import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from daemons.engine.systems.biome import BiomeDefinition, BiomeSystem, Season
    from daemons.engine.systems.temperature import TemperatureSystem
    from daemons.engine.systems.time_manager import TimeManager
    from daemons.engine.world import World, WorldArea, WorldNpc, WorldRoom

logger = logging.getLogger(__name__)


# === Enums ===


class ActivityPeriod(str, Enum):
    """When fauna is active."""

    DIURNAL = "diurnal"  # Day active
    NOCTURNAL = "nocturnal"  # Night active
    CREPUSCULAR = "crepuscular"  # Dawn/dusk active
    ALWAYS = "always"  # Always active


class Diet(str, Enum):
    """Fauna diet type for predator-prey dynamics."""

    HERBIVORE = "herbivore"
    CARNIVORE = "carnivore"
    OMNIVORE = "omnivore"
    SCAVENGER = "scavenger"


class FaunaType(str, Enum):
    """Biological classification of fauna."""

    MAMMAL = "mammal"
    BIRD = "bird"
    REPTILE = "reptile"
    AMPHIBIAN = "amphibian"
    FISH = "fish"
    INSECT = "insect"
    ARACHNID = "arachnid"
    CRUSTACEAN = "crustacean"


class TimeOfDay(str, Enum):
    """Time of day periods for activity checks."""

    DAWN = "dawn"
    DAY = "day"
    DUSK = "dusk"
    NIGHT = "night"


# === Dataclasses ===


@dataclass
class FaunaProperties:
    """
    Fauna-specific properties extracted from NPC template.

    These properties extend the base NPC with ecological behaviors.
    """

    template_id: str
    fauna_type: FaunaType
    biome_tags: list[str] = field(default_factory=list)
    temperature_tolerance: tuple[int, int] = (32, 100)  # Fahrenheit
    activity_period: ActivityPeriod = ActivityPeriod.ALWAYS
    diet: Diet = Diet.HERBIVORE

    # Predator-prey relationships
    prey_tags: list[str] = field(default_factory=list)  # What this hunts
    predator_tags: list[str] = field(default_factory=list)  # What hunts this
    fauna_tags: list[str] = field(default_factory=list)  # Tags for matching

    # Pack behavior
    pack_size: tuple[int, int] = (1, 1)  # (min, max) group size
    pack_leader_template: Optional[str] = None

    # Territory
    territorial: bool = False
    territory_radius: int = 3  # Rooms from spawn point

    # Migration
    migratory: bool = False
    migration_seasons: list[str] = field(default_factory=list)
    migration_tendency: float = 0.05  # Chance to explore per tick

    # Behavior
    aggression: float = 0.0  # 0.0 = passive, 1.0 = attacks on sight
    flee_threshold: float = 0.25  # Health % to flee

    @classmethod
    def from_npc_template(cls, template: Any) -> Optional["FaunaProperties"]:
        """Extract FaunaProperties from an NPC template."""
        # Check if this is fauna
        if not getattr(template, "is_fauna", False):
            return None

        # Get fauna-specific data
        fauna_data = getattr(template, "fauna_data", {}) or {}

        temp_tolerance = fauna_data.get("temperature_tolerance", [32, 100])
        pack_size = fauna_data.get("pack_size", [1, 1])

        return cls(
            template_id=template.id,
            fauna_type=FaunaType(fauna_data.get("fauna_type", "mammal")),
            biome_tags=fauna_data.get("biome_tags", []),
            temperature_tolerance=(temp_tolerance[0], temp_tolerance[1]),
            activity_period=ActivityPeriod(
                fauna_data.get("activity_period", "always")
            ),
            diet=Diet(fauna_data.get("diet", "herbivore")),
            prey_tags=fauna_data.get("prey_tags", []),
            predator_tags=fauna_data.get("predator_tags", []),
            fauna_tags=fauna_data.get("fauna_tags", []),
            pack_size=(pack_size[0], pack_size[1]),
            pack_leader_template=fauna_data.get("pack_leader_template"),
            territorial=fauna_data.get("territorial", False),
            territory_radius=fauna_data.get("territory_radius", 3),
            migratory=fauna_data.get("migratory", False),
            migration_seasons=fauna_data.get("migration_seasons", []),
            migration_tendency=fauna_data.get("migration_tendency", 0.05),
            aggression=fauna_data.get("aggression", 0.0),
            flee_threshold=fauna_data.get("flee_threshold", 0.25),
        )


@dataclass
class PopulationSnapshot:
    """Current population state for an area."""

    area_id: str
    timestamp: float
    fauna_counts: dict[str, int] = field(default_factory=dict)  # template_id -> count
    flora_counts: dict[str, int] = field(default_factory=dict)  # template_id -> count
    total_fauna: int = 0
    total_flora: int = 0


# === Fauna System ===


class FaunaSystem:
    """
    Extends NPC system with fauna-specific behaviors.

    Responsibilities:
    - Extract and cache fauna properties from NPC templates
    - Handle fauna activity periods
    - Manage pack spawning
    - Process predator-prey interactions
    - Handle fauna death (abstract model - no loot/corpse)
    - Manage cross-area migration with biome awareness
    """

    def __init__(
        self,
        world: "World",
        biome_system: Optional["BiomeSystem"] = None,
        temperature_system: Optional["TemperatureSystem"] = None,
        time_manager: Optional["TimeManager"] = None,
    ):
        self.world = world
        self.biome_system = biome_system
        self.temperature_system = temperature_system
        self.time_manager = time_manager

        # Cache fauna properties by template_id
        self._fauna_cache: dict[str, FaunaProperties] = {}

        # Population manager will be set externally
        self.population_manager: Optional[Any] = None

        logger.info("FaunaSystem initialized")

    # === Fauna Properties ===

    def get_fauna_properties(self, template_id: str) -> Optional[FaunaProperties]:
        """Get fauna properties for an NPC template."""
        # Check cache first
        if template_id in self._fauna_cache:
            return self._fauna_cache[template_id]

        # Get NPC template from world
        template = self.world.npc_templates.get(template_id)
        if not template:
            return None

        # Extract properties
        props = FaunaProperties.from_npc_template(template)
        if props:
            self._fauna_cache[template_id] = props

        return props

    def is_fauna(self, npc: "WorldNpc") -> bool:
        """Check if an NPC is fauna."""
        return self.get_fauna_properties(npc.template_id) is not None

    def get_all_fauna_templates(self) -> list[FaunaProperties]:
        """Get all fauna templates from the world's NPC templates."""
        fauna_templates = []
        for template_id, template in self.world.npc_templates.items():
            props = self.get_fauna_properties(template_id)
            if props:
                fauna_templates.append(props)
        return fauna_templates

    def get_fauna_templates_for_biome(
        self, biome: "BiomeDefinition"
    ) -> list[FaunaProperties]:
        """Get all fauna templates compatible with a biome."""
        compatible = []
        for fauna in self.get_all_fauna_templates():
            if not fauna.biome_tags:
                # No biome requirements, compatible with all
                compatible.append(fauna)
            elif any(tag in biome.fauna_tags for tag in fauna.biome_tags):
                compatible.append(fauna)
        return compatible

    # === Activity Periods ===

    def get_time_of_day(self, area_id: str) -> TimeOfDay:
        """Get current time of day for an area."""
        if not self.time_manager:
            return TimeOfDay.DAY

        # Get hour from time manager
        hour = self.time_manager.get_hour()

        if 5 <= hour < 7:
            return TimeOfDay.DAWN
        elif 7 <= hour < 17:
            return TimeOfDay.DAY
        elif 17 <= hour < 20:
            return TimeOfDay.DUSK
        else:
            return TimeOfDay.NIGHT

    def is_active_now(self, fauna: FaunaProperties, area_id: str) -> bool:
        """Check if fauna is active at current time."""
        time_of_day = self.get_time_of_day(area_id)

        if fauna.activity_period == ActivityPeriod.DIURNAL:
            return time_of_day in [TimeOfDay.DAWN, TimeOfDay.DAY]
        elif fauna.activity_period == ActivityPeriod.NOCTURNAL:
            return time_of_day in [TimeOfDay.DUSK, TimeOfDay.NIGHT]
        elif fauna.activity_period == ActivityPeriod.CREPUSCULAR:
            return time_of_day in [TimeOfDay.DAWN, TimeOfDay.DUSK]
        else:  # ALWAYS
            return True

    # === Migration and Seasons ===

    def is_migrated(self, fauna: FaunaProperties, area_id: str) -> bool:
        """Check if fauna has migrated away for the season."""
        if not fauna.migratory or not self.biome_system:
            return False

        # Get current season from biome system
        season = self.biome_system.get_season(area_id)
        if not season:
            return False

        return season.value in fauna.migration_seasons

    def can_survive_temperature(
        self, fauna: FaunaProperties, room_id: str, area_id: str
    ) -> bool:
        """Check if temperature is survivable for fauna."""
        if not self.temperature_system:
            return True

        room = self.world.rooms.get(room_id)
        if not room:
            return True

        temp = self.temperature_system.calculate_room_temperature(room, area_id)
        min_t, max_t = fauna.temperature_tolerance
        return min_t <= temp.effective_temperature <= max_t

    # === Pack Spawning ===

    def calculate_pack_size(self, fauna: FaunaProperties) -> int:
        """Calculate actual pack size for spawning."""
        min_size, max_size = fauna.pack_size
        return random.randint(min_size, max_size)

    def _create_npc_from_template(
        self, template_id: str, room_id: str
    ) -> Optional["WorldNpc"]:
        """Create a WorldNpc instance from a template."""
        from daemons.engine.world import WorldNpc

        template = self.world.npc_templates.get(template_id)
        if not template:
            logger.warning(f"Cannot spawn unknown fauna template: {template_id}")
            return None

        npc_id = str(uuid.uuid4())
        # Start with random hunger (20-50) so fauna exhibit behaviors sooner
        initial_hunger = random.randint(20, 50)
        npc = WorldNpc(
            id=npc_id,
            template_id=template.id,
            name=template.name,
            room_id=room_id,
            spawn_room_id=room_id,
            max_health=template.max_health,
            current_health=template.max_health,
            level=template.level,
            keywords=template.keywords.copy() if template.keywords else [],
            behaviors=template.behaviors.copy() if template.behaviors else [],
            # Initialize fauna state with random hunger
            hunger=initial_hunger,
            last_hunger_update=time.time(),
        )

        # Add to world
        self.world.npcs[npc_id] = npc

        # Add to room's entity tracking
        room = self.world.rooms.get(room_id)
        if room:
            room.entities.add(npc_id)

        logger.debug(f"Spawned fauna {template.name} ({npc_id[:8]}) in {room_id}")
        return npc

    async def spawn_pack(
        self,
        template_id: str,
        room_id: str,
        session: "AsyncSession",
    ) -> list["WorldNpc"]:
        """
        Spawn a pack of fauna in a room.

        Uses pack_size and pack_leader_template from fauna properties.
        """
        fauna = self.get_fauna_properties(template_id)
        if not fauna:
            logger.warning(f"Cannot spawn pack for non-fauna: {template_id}")
            return []

        pack_size = self.calculate_pack_size(fauna)
        pack: list["WorldNpc"] = []

        # Spawn leader if defined
        if fauna.pack_leader_template and pack_size > 1:
            leader = self._create_npc_from_template(fauna.pack_leader_template, room_id)
            if leader:
                pack.append(leader)
                pack_size -= 1

        # Spawn pack members
        for _ in range(pack_size):
            npc = self._create_npc_from_template(template_id, room_id)
            if npc:
                pack.append(npc)

        logger.debug(
            f"Spawned pack of {len(pack)} {template_id} in room {room_id}"
        )

        return pack

    async def spawn_fauna_for_room(
        self,
        room: "WorldRoom",
        area: "WorldArea",
        session: "AsyncSession",
        max_fauna: Optional[int] = None,
    ) -> list["WorldNpc"]:
        """
        Spawn appropriate fauna for a room based on biome.

        Uses biome fauna_tags for compatibility, respects area fauna density.
        Modeled after FloraSystem.spawn_flora_for_room().
        """
        spawned: list["WorldNpc"] = []

        # Determine max fauna from area's fauna_density
        if max_fauna is None:
            density = getattr(area, "fauna_density", "moderate")
            density_limits = {
                "sparse": 2,
                "moderate": 4,
                "dense": 8,
                "lush": 12,
            }
            max_fauna = density_limits.get(density, 4)

        if max_fauna <= 0:
            return spawned

        # Count existing fauna in room
        current_count = 0
        for npc in self.world.npcs.values():
            if npc.room_id == room.id and self.is_fauna(npc):
                current_count += 1

        if current_count >= max_fauna:
            return spawned

        # Get compatible fauna templates for biome
        if self.biome_system:
            biome = self.biome_system.get_biome_for_area(area)
            if biome:
                compatible = self.get_fauna_templates_for_biome(biome)
            else:
                compatible = self.get_all_fauna_templates()
        else:
            compatible = self.get_all_fauna_templates()

        if not compatible:
            return spawned

        # Filter by activity period (don't spawn nocturnal animals during day, etc.)
        active_compatible = [
            f for f in compatible
            if self.is_active_now(f, area.id)
        ]
        if not active_compatible:
            # Fall back to all compatible if none are active
            active_compatible = compatible

        # Filter out migrated fauna
        non_migrated = [
            f for f in active_compatible
            if not self.is_migrated(f, area.id)
        ]
        if not non_migrated:
            non_migrated = active_compatible

        # Check temperature survival
        if self.temperature_system:
            surviving = [
                f for f in non_migrated
                if self.can_survive_temperature(f, room.id, area.id)
            ]
            if not surviving:
                surviving = non_migrated
        else:
            surviving = non_migrated

        if not surviving:
            return spawned

        # Weighted selection - rarer fauna spawn less frequently
        # Use a simple weight system based on pack size (smaller = rarer)
        weights = []
        for fauna in surviving:
            # Smaller pack sizes = rarer creatures = lower weight
            avg_pack = (fauna.pack_size[0] + fauna.pack_size[1]) / 2
            weight = max(1.0, avg_pack)
            weights.append(weight)

        # Spawn fauna (as pack)
        remaining = max_fauna - current_count
        if remaining > 0 and surviving:
            fauna = random.choices(surviving, weights=weights, k=1)[0]

            # Spawn pack (pack_size handles quantity)
            pack = await self.spawn_pack(fauna.template_id, room.id, session)

            # Only add up to remaining capacity
            for npc in pack[:remaining]:
                spawned.append(npc)

        return spawned

    # === Predator-Prey Dynamics ===

    def find_prey_in_room(
        self, predator_id: str, room_id: str
    ) -> list["WorldNpc"]:
        """Find potential prey NPCs in a room."""
        predator_fauna = self.get_fauna_properties(predator_id)
        if not predator_fauna or not predator_fauna.prey_tags:
            return []

        room = self.world.rooms.get(room_id)
        if not room:
            return []

        prey = []
        for npc_id in getattr(room, "npc_ids", []):
            npc = self.world.npcs.get(npc_id)
            if not npc:
                continue

            npc_fauna = self.get_fauna_properties(npc.template_id)
            if npc_fauna and any(
                tag in npc_fauna.fauna_tags for tag in predator_fauna.prey_tags
            ):
                prey.append(npc)

        return prey

    def find_predators_in_room(
        self, prey_id: str, room_id: str
    ) -> list["WorldNpc"]:
        """Find predator NPCs in a room."""
        prey_fauna = self.get_fauna_properties(prey_id)
        if not prey_fauna or not prey_fauna.predator_tags:
            return []

        room = self.world.rooms.get(room_id)
        if not room:
            return []

        predators = []
        for npc_id in getattr(room, "npc_ids", []):
            npc = self.world.npcs.get(npc_id)
            if not npc:
                continue

            npc_fauna = self.get_fauna_properties(npc.template_id)
            if npc_fauna and any(
                tag in npc_fauna.fauna_tags for tag in prey_fauna.predator_tags
            ):
                predators.append(npc)

        return predators

    # === Death Handling ===

    async def handle_fauna_death(
        self,
        npc: "WorldNpc",
        cause: str,
        session: "AsyncSession",
    ) -> None:
        """
        Handle fauna death - abstract model, no loot/corpse.

        Fauna death is abstract: the creature simply disappears.
        No drops, no corpse entity, no player loot.
        This keeps fauna as world ambiance rather than loot sources.
        """
        logger.debug(f"Fauna {npc.template_id} died in room {npc.room_id}: {cause}")

        # Update population tracking
        if self.population_manager:
            await self.population_manager.record_death(npc.template_id, npc.room_id)

        # Remove from world (would need NPC system integration)
        # For now, just log
        logger.debug(f"Would remove fauna {npc.id} from world")

        # Optional: broadcast flavor message
        if cause == "combat":
            # Would broadcast: "The rabbit flees into the underbrush!"
            pass

    # === Cross-Area Migration ===

    async def consider_migration(
        self,
        npc: "WorldNpc",
        current_room_id: str,
        session: "AsyncSession",
    ) -> Optional[str]:
        """
        Determine if fauna should migrate to adjacent area.

        Fauna can move between areas with biome awareness:
        - Won't migrate to unsuitable biomes
        - Will attempt to return if in unsuitable climate

        Returns: new room_id if migration should occur, None otherwise
        """
        fauna = self.get_fauna_properties(npc.template_id)
        if not fauna:
            return None

        room = self.world.rooms.get(current_room_id)
        if not room:
            return None

        # Get current area
        area_id = getattr(room, "area_id", None)
        if not area_id:
            return None

        area = self.world.areas.get(area_id)

        # Check if current location is suitable
        if self.biome_system and area:
            current_biome = self.biome_system.get_biome_for_area(area)
            if current_biome and not self._is_biome_suitable(fauna, current_biome):
                # Fauna is in unsuitable climate - try to return home
                return await self._find_suitable_adjacent_room(
                    npc, fauna, current_room_id
                )

        # Random chance to explore
        if random.random() > fauna.migration_tendency:
            return None

        # Find adjacent rooms including cross-area exits
        adjacent = self._get_adjacent_rooms(current_room_id, include_area_exits=True)

        # Filter to suitable biomes only
        suitable = []
        for adj_room_id in adjacent:
            adj_room = self.world.rooms.get(adj_room_id)
            if not adj_room:
                continue

            adj_area_id = getattr(adj_room, "area_id", None)
            adj_area = self.world.areas.get(adj_area_id) if adj_area_id else None
            if adj_area and self.biome_system:
                adj_biome = self.biome_system.get_biome_for_area(adj_area)
                if adj_biome and self._is_biome_suitable(fauna, adj_biome):
                    suitable.append(adj_room_id)
            else:
                suitable.append(adj_room_id)

        if suitable:
            return random.choice(suitable)
        return None

    def _is_biome_suitable(
        self, fauna: FaunaProperties, biome: "BiomeDefinition"
    ) -> bool:
        """Check if fauna can survive in this biome."""
        if not biome:
            return True  # Unknown biome, allow

        # Check preferred biomes via fauna_tags
        if fauna.biome_tags:
            if not any(tag in biome.fauna_tags for tag in fauna.biome_tags):
                return False

        # Check temperature tolerance
        min_t, max_t = fauna.temperature_tolerance
        base_temp = getattr(biome, "base_temperature", 70)
        if not (min_t <= base_temp <= max_t):
            return False

        return True

    def _get_adjacent_rooms(
        self, room_id: str, include_area_exits: bool = False
    ) -> list[str]:
        """Get adjacent room IDs."""
        room = self.world.rooms.get(room_id)
        if not room:
            return []

        adjacent = []
        for direction in ["north", "south", "east", "west", "up", "down"]:
            exit_id = getattr(room, f"{direction}_id", None)
            if exit_id:
                adjacent.append(exit_id)

        return adjacent

    async def _find_suitable_adjacent_room(
        self,
        npc: "WorldNpc",
        fauna: FaunaProperties,
        current_room_id: str,
    ) -> Optional[str]:
        """Find an adjacent room with suitable biome."""
        adjacent = self._get_adjacent_rooms(current_room_id, include_area_exits=True)

        for adj_room_id in adjacent:
            adj_room = self.world.rooms.get(adj_room_id)
            if not adj_room:
                continue

            adj_area_id = getattr(adj_room, "area_id", None)
            adj_area = self.world.areas.get(adj_area_id) if adj_area_id else None
            if adj_area and self.biome_system:
                adj_biome = self.biome_system.get_biome_for_area(adj_area)
                if adj_biome and self._is_biome_suitable(fauna, adj_biome):
                    return adj_room_id

        return None

    # === Utility Methods ===

    def get_fauna_in_area(self, area_id: str) -> list["WorldNpc"]:
        """Get all fauna NPCs in an area."""
        fauna_list = []

        for npc in self.world.npcs.values():
            if not self.is_fauna(npc):
                continue

            room = self.world.rooms.get(npc.room_id)
            if room and getattr(room, "area_id", None) == area_id:
                fauna_list.append(npc)

        return fauna_list

    def get_population_snapshot(self, area_id: str) -> PopulationSnapshot:
        """Get current population counts for an area."""
        import time

        snapshot = PopulationSnapshot(
            area_id=area_id,
            timestamp=time.time(),
        )

        # Count fauna
        for npc in self.world.npcs.values():
            room = self.world.rooms.get(npc.room_id)
            if room and getattr(room, "area_id", None) == area_id:
                if self.is_fauna(npc):
                    template_id = npc.template_id
                    snapshot.fauna_counts[template_id] = (
                        snapshot.fauna_counts.get(template_id, 0) + 1
                    )
                    snapshot.total_fauna += 1

        # Flora counts would come from FloraSystem
        # (left empty here, filled in by ecosystem manager)

        return snapshot
