## Executive Summary

This document provides a comprehensive architecture and implementation plan for Phases 17.4 (Flora System), 17.5 (Fauna System), and 17.6 (Condition-Dependent Spawn Cycles). These three phases are tightly coupled and should be designed holistically to ensure seamless integration.

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Environment Systems                                 │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│ TemperatureSystem│  WeatherSystem  │   BiomeSystem   │    SeasonSystem       │
│   (Phase 17.1)   │  (Phase 17.2)   │  (Phase 17.3)   │    (Phase 17.3)       │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬────────────┘
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SpawnConditionEvaluator (Phase 17.6)                   │
│  Unified condition checking: temperature, weather, time, season, biome     │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│   FloraSystem (17.4)    │     │   FaunaSystem (17.5)    │
│  - Template loading     │     │  - NPC extension        │
│  - Instance management  │     │  - Pack spawning        │
│  - Harvest mechanics    │     │  - Activity periods     │
│  - Seasonal variants    │     │  - Predator-prey        │
└───────────┬─────────────┘     └───────────┬─────────────┘
            │                               │
            ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PopulationManager (Phase 17.6)                      │
│    Area-wide caps, competition dynamics, recovery rates, ecosystem balance  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 17.4: Flora System

### Data Model Architecture

#### Flora Template (YAML Definition)

```yaml
# world_data/flora/_schema.yaml
type: object
required: [id, name, description, flora_type]
properties:
  id:
    type: string
    pattern: "^flora_[a-z_]+$"
  name:
    type: string
  description:
    type: string
  flora_type:
    type: string
    enum: [tree, shrub, grass, flower, fungus, vine, aquatic]

  # Environmental Requirements
  biome_tags:
    type: array
    items:
      type: string
    description: "Compatible biome tags from biome definitions"
  temperature_range:
    type: array
    items:
      type: integer
    minItems: 2
    maxItems: 2
    description: "[min_temp, max_temp] in Fahrenheit"
  light_requirement:
    type: string
    enum: [full_sun, partial_shade, shade, any]
    default: any
  moisture_requirement:
    type: string
    enum: [arid, dry, moderate, wet, aquatic]
    default: moderate

  # Interaction Properties
  harvestable:
    type: boolean
    default: false
  harvest_items:
    type: array
    items:
      type: object
      properties:
        item_id:
          type: string
        quantity:
          type: integer
          default: 1
        chance:
          type: number
          minimum: 0
          maximum: 1
          default: 1.0
        skill_bonus:
          type: string
          description: "Skill that improves harvest chance"
  harvest_cooldown:
    type: integer
    default: 3600
    description: "Seconds until re-harvestable"
  harvest_tool:
    type: string
    description: "Required tool item_type (axe, sickle, etc.)"

  # Visual/Seasonal
  seasonal_variants:
    type: object
    properties:
      spring:
        type: string
      summer:
        type: string
      fall:
        type: string
      winter:
        type: string

  # Gameplay Effects
  provides_cover:
    type: boolean
    default: false
    description: "Provides stealth bonus"
  cover_bonus:
    type: integer
    default: 2
  blocks_movement:
    type: boolean
    default: false
  blocks_directions:
    type: array
    items:
      type: string
      enum: [north, south, east, west, up, down]

  # Spawning
  rarity:
    type: string
    enum: [common, uncommon, rare, very_rare]
    default: common
  cluster_size:
    type: array
    items:
      type: integer
    minItems: 2
    maxItems: 2
    default: [1, 3]
    description: "[min, max] plants per cluster"
```

#### Database Schema

```python
# Alembic migration: phase17_4_flora.py

# Flora template cache (loaded from YAML)
# No database table needed - templates are static

# Flora instances (runtime state)
class FloraInstance(Base):
    __tablename__ = "flora_instances"

    id = Column(Integer, primary_key=True)
    template_id = Column(String(64), nullable=False, index=True)
    room_id = Column(String(64), ForeignKey("rooms.id"), nullable=False, index=True)

    # State
    quantity = Column(Integer, default=1)  # How many plants in this cluster
    last_harvested_at = Column(DateTime, nullable=True)
    last_harvested_by = Column(Integer, ForeignKey("players.id"), nullable=True)
    harvest_count = Column(Integer, default=0)  # Total times harvested

    # Spawn tracking
    spawned_at = Column(DateTime, default=func.now())
    is_permanent = Column(Boolean, default=False)  # Designer-placed vs spawned

    # Indexes
    __table_args__ = (
        Index("ix_flora_room_template", "room_id", "template_id"),
    )

# Room flora configuration (YAML-defined, cached)
# Stored in room.flora_config JSON field
```

#### Room Schema Extension

```yaml
# Add to rooms/_schema.yaml
flora_config:
  type: object
  properties:
    density:
      type: string
      enum: [barren, sparse, moderate, dense, lush]
      default: moderate
    permanent_flora:
      type: array
      description: "Designer-placed flora that never despawns"
      items:
        type: object
        properties:
          template_id:
            type: string
          quantity:
            type: integer
            default: 1
    spawn_pools:
      type: array
      description: "Flora that can spawn/despawn based on conditions"
      items:
        type: object
        properties:
          template_id:
            type: string
          weight:
            type: integer
            default: 1
          max_quantity:
            type: integer
            default: 5
```

### FloraSystem Class Design

```python
# backend/daemons/engine/systems/flora.py

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class FloraType(str, Enum):
    TREE = "tree"
    SHRUB = "shrub"
    GRASS = "grass"
    FLOWER = "flower"
    FUNGUS = "fungus"
    VINE = "vine"
    AQUATIC = "aquatic"

class LightRequirement(str, Enum):
    FULL_SUN = "full_sun"
    PARTIAL_SHADE = "partial_shade"
    SHADE = "shade"
    ANY = "any"

class Rarity(str, Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"

@dataclass
class HarvestItem:
    item_id: str
    quantity: int = 1
    chance: float = 1.0
    skill_bonus: Optional[str] = None

@dataclass
class FloraTemplate:
    id: str
    name: str
    description: str
    flora_type: FloraType

    # Environmental
    biome_tags: list[str] = field(default_factory=list)
    temperature_range: tuple[int, int] = (32, 100)
    light_requirement: LightRequirement = LightRequirement.ANY
    moisture_requirement: str = "moderate"

    # Interaction
    harvestable: bool = False
    harvest_items: list[HarvestItem] = field(default_factory=list)
    harvest_cooldown: int = 3600
    harvest_tool: Optional[str] = None

    # Visual
    seasonal_variants: dict[str, str] = field(default_factory=dict)

    # Gameplay
    provides_cover: bool = False
    cover_bonus: int = 2
    blocks_movement: bool = False
    blocks_directions: list[str] = field(default_factory=list)

    # Spawning
    rarity: Rarity = Rarity.COMMON
    cluster_size: tuple[int, int] = (1, 3)

@dataclass
class FloraInstance:
    id: int
    template_id: str
    room_id: str
    quantity: int
    last_harvested_at: Optional[datetime] = None
    last_harvested_by: Optional[int] = None
    is_permanent: bool = False

class FloraSystem:
    """Manages flora templates and instances."""

    def __init__(
        self,
        biome_system: BiomeSystem,
        temperature_system: TemperatureSystem,
        season_system: SeasonSystem
    ):
        self.biome_system = biome_system
        self.temperature_system = temperature_system
        self.season_system = season_system
        self._templates: dict[str, FloraTemplate] = {}
        self._room_flora_cache: dict[str, list[FloraInstance]] = {}

    # Template Management
    def load_templates(self, yaml_path: Path) -> int:
        """Load flora templates from YAML files."""
        pass

    def get_template(self, template_id: str) -> Optional[FloraTemplate]:
        """Get a flora template by ID."""
        pass

    def get_templates_for_biome(self, biome_id: str) -> list[FloraTemplate]:
        """Get all flora compatible with a biome."""
        pass

    # Instance Management
    async def get_room_flora(
        self,
        room: WorldRoom,
        session: AsyncSession
    ) -> list[FloraInstance]:
        """Get all flora instances in a room."""
        pass

    async def spawn_flora(
        self,
        room: WorldRoom,
        template_id: str,
        quantity: int,
        permanent: bool,
        session: AsyncSession
    ) -> FloraInstance:
        """Spawn flora in a room."""
        pass

    async def despawn_flora(
        self,
        instance_id: int,
        session: AsyncSession
    ) -> bool:
        """Remove a flora instance (marks as depleted, not deleted)."""
        pass

    # Respawn System (see Design Decisions section for full details)
    async def process_respawns(
        self,
        area: WorldArea,
        weather_system: WeatherSystem,
        session: AsyncSession
    ) -> int:
        """Process flora respawns using hybrid system.

        Uses passive chance + event-triggered respawns:
        - Base passive_respawn_chance per tick
        - Boosted during rain/storms
        - Full refresh on season changes

        Returns count of respawned flora.
        """
        pass

    def get_respawn_chance(
        self,
        instance: FloraInstance,
        template: FloraTemplate,
        weather_state: WeatherState
    ) -> float:
        """Calculate respawn chance based on weather and flora type."""
        config = self.respawn_config
        base_chance = config.passive_respawn_chance

        # Weather boost
        if weather_state.weather_type == WeatherType.RAIN:
            base_chance += config.rain_respawn_boost
        elif weather_state.weather_type == WeatherType.STORM:
            base_chance += config.storm_respawn_boost

        # Flora type modifier
        type_mod = config.type_modifiers.get(template.flora_type, 1.0)

        return min(1.0, base_chance * type_mod)

    # Condition Checking
    def can_exist_in_room(
        self,
        template: FloraTemplate,
        room: WorldRoom,
        area: WorldArea
    ) -> tuple[bool, list[str]]:
        """Check if flora can exist in room conditions.

        Returns (can_exist, list of warning messages).
        """
        warnings = []

        # Check biome compatibility
        biome = self.biome_system.get_biome_for_area(area)
        if biome and template.biome_tags:
            if not any(tag in biome.flora_tags for tag in template.biome_tags):
                return False, ["Incompatible biome"]

        # Check temperature
        temp = self.temperature_system.calculate_room_temperature(room, area)
        min_t, max_t = template.temperature_range
        if temp.effective_temperature < min_t or temp.effective_temperature > max_t:
            warnings.append(f"Temperature {temp.effective_temperature}°F outside range")

        # Check light (would need LightingSystem integration)
        # Check moisture (would need weather integration)

        return len(warnings) == 0, warnings

    # Harvest System
    async def can_harvest(
        self,
        player: WorldPlayer,
        instance: FloraInstance,
        session: AsyncSession
    ) -> tuple[bool, str]:
        """Check if player can harvest this flora."""
        template = self.get_template(instance.template_id)
        if not template:
            return False, "Unknown flora type"

        if not template.harvestable:
            return False, f"You cannot harvest {template.name}"

        # Check cooldown
        if instance.last_harvested_at:
            elapsed = (datetime.utcnow() - instance.last_harvested_at).total_seconds()
            if elapsed < template.harvest_cooldown:
                remaining = int(template.harvest_cooldown - elapsed)
                return False, f"{template.name} was recently harvested. Try again in {remaining}s"

        # Check tool requirement
        if template.harvest_tool:
            if not player.has_equipped_item_type(template.harvest_tool):
                return False, f"You need a {template.harvest_tool} to harvest {template.name}"

        return True, ""

    async def harvest(
        self,
        player: WorldPlayer,
        instance: FloraInstance,
        session: AsyncSession
    ) -> HarvestResult:
        """Harvest flora and grant items.

        By default, harvesting has no lasting ecosystem impact.
        The sustainability hook (on_harvest) is a no-op unless
        SustainabilityConfig is explicitly enabled.
        See Design Decisions section for extensibility details.
        """
        template = self.get_template(instance.template_id)

        # Calculate harvest results
        result = self._calculate_harvest(player, instance, template)

        # Mark instance as depleted
        instance.last_harvested_at = datetime.utcnow()
        instance.last_harvested_by = player.id
        instance.harvest_count += 1

        # Grant items to player
        for item_id, quantity in result.items_gained:
            await self.item_system.give_item(player, item_id, quantity, session)

        # Sustainability hook - no-op by default (see Design Decisions)
        await self.on_harvest(instance, player)

        await session.commit()
        return result

    async def on_harvest(
        self,
        flora: FloraInstance,
        harvester: WorldPlayer
    ) -> None:
        """Hook for sustainability tracking - no-op by default.

        Override or enable SustainabilityConfig to track player impact.
        See Design Decisions section for sustainability system design.
        """
        if not self.sustainability_config or not self.sustainability_config.enabled:
            return

        # Track harvesting for sustainability impact
        area_id = self._get_area_for_room(flora.room_id)
        self.sustainability_config.area_harvest_counts[area_id] = \
            self.sustainability_config.area_harvest_counts.get(area_id, 0) + 1

    # Display
    def get_description(
        self,
        template: FloraTemplate,
        season: Season
    ) -> str:
        """Get flora description for current season."""
        if season.value in template.seasonal_variants:
            return template.seasonal_variants[season.value]
        return template.description

    def format_room_flora(
        self,
        flora_list: list[FloraInstance],
        season: Season
    ) -> str:
        """Format flora list for room description."""
        pass
```

### Harvest Command Implementation

```python
# backend/daemons/engine/commands/harvest.py

class HarvestCommand(BaseCommand):
    """Gather resources from harvestable flora."""

    name = "harvest"
    aliases = ["gather", "pick"]
    usage = "harvest <plant>"

    async def execute(
        self,
        player: WorldPlayer,
        args: list[str],
        engine: WorldEngine
    ) -> CommandResult:
        if not args:
            return CommandResult.error("Harvest what? Usage: harvest <plant>")

        target_name = " ".join(args).lower()

        # Find flora in room
        flora_list = await engine.flora_system.get_room_flora(
            player.room,
            engine.session
        )

        # Match by name
        matched = None
        for instance in flora_list:
            template = engine.flora_system.get_template(instance.template_id)
            if template and target_name in template.name.lower():
                matched = (instance, template)
                break

        if not matched:
            return CommandResult.error(f"You don't see any {target_name} here.")

        instance, template = matched

        # Check harvestability
        can_harvest, reason = await engine.flora_system.can_harvest(
            player, instance, engine.session
        )
        if not can_harvest:
            return CommandResult.error(reason)

        # Perform harvest
        result = await engine.flora_system.harvest(
            player, instance, engine.session
        )

        # Format output
        output = [f"You harvest from the {template.name}."]
        for item, qty in result.items_gained:
            output.append(f"  + {qty}x {item.name}")

        if result.flora_depleted:
            output.append(f"The {template.name} has been exhausted.")

        return CommandResult.success("\n".join(output))
```

---

## Phase 17.5: Fauna System

### Design Philosophy

The Fauna System extends the existing NPC system rather than creating a parallel system. Fauna are NPCs with additional ecological properties that inform their spawning, behavior, and interactions.

### NPC Schema Extensions

```yaml
# Add to npcs/_schema.yaml

# Fauna-specific fields (optional, presence indicates fauna)
is_fauna:
  type: boolean
  default: false
  description: "Distinguishes wildlife from humanoids"

fauna_type:
  type: string
  enum: [mammal, bird, reptile, amphibian, fish, insect, arachnid]
  description: "Biological classification"

# Environmental Requirements
biome_tags:
  type: array
  items:
    type: string
  description: "Where this creature naturally spawns"

temperature_tolerance:
  type: array
  items:
    type: integer
  minItems: 2
  maxItems: 2
  description: "[min, max] survival temperature"

activity_period:
  type: string
  enum: [diurnal, nocturnal, crepuscular, always]
  default: always
  description: "When the creature is active"

# Ecological Role
diet:
  type: string
  enum: [herbivore, carnivore, omnivore, scavenger]

prey_tags:
  type: array
  items:
    type: string
  description: "fauna_tags of creatures this hunts"

predator_tags:
  type: array
  items:
    type: string
  description: "fauna_tags of creatures that hunt this"

fauna_tags:
  type: array
  items:
    type: string
  description: "Tags for prey/predator matching (e.g., 'small_mammal', 'ungulate')"

# Group Behavior
pack_size:
  type: array
  items:
    type: integer
  minItems: 2
  maxItems: 2
  default: [1, 1]
  description: "[min, max] group size"

pack_leader_template:
  type: string
  description: "NPC template for pack leader (optional)"

# Territory
territorial:
  type: boolean
  default: false

territory_radius:
  type: integer
  default: 3
  description: "Rooms from spawn point"

# Migration
migratory:
  type: boolean
  default: false

migration_seasons:
  type: array
  items:
    type: string
    enum: [spring, summer, fall, winter]
  description: "Seasons when creature migrates away"

# Drops/Resources
skinnable:
  type: boolean
  default: false

skin_items:
  type: array
  items:
    type: object
    properties:
      item_id:
        type: string
      chance:
        type: number
```

### FaunaSystem Class Design

```python
# backend/daemons/engine/systems/fauna.py

from dataclasses import dataclass
from enum import Enum
from typing import Optional

class ActivityPeriod(str, Enum):
    DIURNAL = "diurnal"      # Day active
    NOCTURNAL = "nocturnal"  # Night active
    CREPUSCULAR = "crepuscular"  # Dawn/dusk active
    ALWAYS = "always"        # Always active

class Diet(str, Enum):
    HERBIVORE = "herbivore"
    CARNIVORE = "carnivore"
    OMNIVORE = "omnivore"
    SCAVENGER = "scavenger"

@dataclass
class FaunaProperties:
    """Fauna-specific properties extracted from NPC template."""
    fauna_type: str
    biome_tags: list[str]
    temperature_tolerance: tuple[int, int]
    activity_period: ActivityPeriod
    diet: Diet
    prey_tags: list[str]
    predator_tags: list[str]
    fauna_tags: list[str]
    pack_size: tuple[int, int]
    territorial: bool
    territory_radius: int
    migratory: bool
    migration_seasons: list[str]

class FaunaSystem:
    """Extends NPC system with fauna-specific behaviors."""

    def __init__(
        self,
        npc_system: NpcSystem,
        biome_system: BiomeSystem,
        temperature_system: TemperatureSystem,
        season_system: SeasonSystem,
        time_system: TimeSystem
    ):
        self.npc_system = npc_system
        self.biome_system = biome_system
        self.temperature_system = temperature_system
        self.season_system = season_system
        self.time_system = time_system

    def get_fauna_properties(self, npc_template: NpcTemplate) -> Optional[FaunaProperties]:
        """Extract fauna properties from NPC template."""
        if not getattr(npc_template, 'is_fauna', False):
            return None
        # Build FaunaProperties from template fields
        pass

    def is_active_now(
        self,
        fauna: FaunaProperties,
        area: WorldArea
    ) -> bool:
        """Check if fauna is active at current time."""
        time_of_day = self.time_system.get_time_of_day(area)

        match fauna.activity_period:
            case ActivityPeriod.DIURNAL:
                return time_of_day in [TimeOfDay.DAWN, TimeOfDay.DAY]
            case ActivityPeriod.NOCTURNAL:
                return time_of_day in [TimeOfDay.DUSK, TimeOfDay.NIGHT]
            case ActivityPeriod.CREPUSCULAR:
                return time_of_day in [TimeOfDay.DAWN, TimeOfDay.DUSK]
            case ActivityPeriod.ALWAYS:
                return True
        return True

    def is_migrated(
        self,
        fauna: FaunaProperties,
        area: WorldArea
    ) -> bool:
        """Check if fauna has migrated away for the season."""
        if not fauna.migratory:
            return False
        current_season = self.season_system.get_season(area)
        return current_season.value in fauna.migration_seasons

    def can_survive_temperature(
        self,
        fauna: FaunaProperties,
        room: WorldRoom,
        area: WorldArea
    ) -> bool:
        """Check if temperature is survivable."""
        temp = self.temperature_system.calculate_room_temperature(room, area)
        min_t, max_t = fauna.temperature_tolerance
        return min_t <= temp.effective_temperature <= max_t

    def calculate_pack_size(
        self,
        fauna: FaunaProperties
    ) -> int:
        """Calculate actual pack size for spawning."""
        min_size, max_size = fauna.pack_size
        return random.randint(min_size, max_size)

    async def spawn_pack(
        self,
        template_id: str,
        room: WorldRoom,
        session: AsyncSession
    ) -> list[WorldNpc]:
        """Spawn a pack of fauna."""
        template = self.npc_system.get_template(template_id)
        fauna = self.get_fauna_properties(template)

        if not fauna:
            # Not fauna, spawn single NPC
            return [await self.npc_system.spawn_npc(template_id, room, session)]

        pack_size = self.calculate_pack_size(fauna)
        pack = []

        # Spawn pack leader if defined
        if fauna.pack_size[0] > 1 and template.pack_leader_template:
            leader = await self.npc_system.spawn_npc(
                template.pack_leader_template, room, session
            )
            pack.append(leader)
            pack_size -= 1

        # Spawn rest of pack
        for _ in range(pack_size):
            npc = await self.npc_system.spawn_npc(template_id, room, session)
            pack.append(npc)

        return pack

    def find_prey_in_room(
        self,
        predator: WorldNpc,
        room: WorldRoom
    ) -> list[WorldNpc]:
        """Find potential prey NPCs in the room."""
        fauna = self.get_fauna_properties(predator.template)
        if not fauna or not fauna.prey_tags:
            return []

        prey = []
        for npc in room.npcs:
            npc_fauna = self.get_fauna_properties(npc.template)
            if npc_fauna and any(tag in npc_fauna.fauna_tags for tag in fauna.prey_tags):
                prey.append(npc)

        return prey

    def find_predators_in_room(
        self,
        prey: WorldNpc,
        room: WorldRoom
    ) -> list[WorldNpc]:
        """Find predator NPCs in the room."""
        fauna = self.get_fauna_properties(prey.template)
        if not fauna or not fauna.predator_tags:
            return []

        predators = []
        for npc in room.npcs:
            npc_fauna = self.get_fauna_properties(npc.template)
            if npc_fauna and any(tag in npc_fauna.fauna_tags for tag in fauna.predator_tags):
                predators.append(npc)

        return predators

    # Death Handling (see Design Decisions section)
    async def handle_fauna_death(
        self,
        npc: WorldNpc,
        cause: str,
        session: AsyncSession
    ) -> None:
        """Handle fauna death - abstract model, no loot/corpse.

        Fauna death is abstract: the creature simply disappears.
        No drops, no corpse entity, no player loot.
        This keeps fauna as world ambiance rather than loot sources.
        """
        logger.debug(f"Fauna {npc.template_id} died in room {npc.room_id}: {cause}")

        # Update population tracking
        await self.population_manager.record_death(npc.template_id, npc.room_id)

        # Simply remove from world
        await self.npc_system.remove_npc(npc.id, session)

        # Optional flavor message for nearby players
        if cause == "combat":
            await self._broadcast_to_room(
                npc.room_id,
                f"The {npc.name} flees into the underbrush!"
            )

    # Cross-Area Migration (see Design Decisions section)
    async def consider_migration(
        self,
        npc: WorldNpc,
        current_room: WorldRoom,
        session: AsyncSession
    ) -> Optional[WorldRoom]:
        """Determine if fauna should migrate to adjacent area.

        Fauna can move between areas with biome awareness:
        - Won't migrate to unsuitable biomes
        - Will attempt to return if in unsuitable climate
        """
        fauna = self.get_fauna_properties(npc.template)
        if not fauna:
            return None

        current_biome = self.biome_system.get_room_biome(current_room.id)

        # Check if current location is suitable
        if not self._is_biome_suitable(fauna, current_biome):
            # Fauna is in unsuitable climate - try to return home
            return await self._find_suitable_adjacent_room(npc, fauna, session)

        # Random chance to explore (based on fauna properties)
        migration_chance = getattr(fauna, 'migration_tendency', 0.05)
        if random.random() > migration_chance:
            return None

        # Find adjacent rooms including cross-area exits
        adjacent = await self._get_adjacent_rooms(current_room, include_area_exits=True)

        # Filter to suitable biomes only
        suitable = [
            room for room in adjacent
            if self._is_biome_suitable(fauna, self.biome_system.get_room_biome(room.id))
        ]

        return random.choice(suitable) if suitable else None

    def _is_biome_suitable(
        self,
        fauna: FaunaProperties,
        biome: Optional[BiomeDefinition]
    ) -> bool:
        """Check if fauna can survive in this biome."""
        if not biome:
            return True  # Unknown biome, allow

        # Check preferred biomes
        if fauna.biome_tags and biome.name not in fauna.biome_tags:
            # Allow if biome has compatible fauna_tags
            if not any(tag in biome.fauna_tags for tag in fauna.biome_tags):
                return False

        # Check temperature tolerance
        if hasattr(fauna, 'temperature_tolerance'):
            min_t, max_t = fauna.temperature_tolerance
            if not (min_t <= biome.base_temperature <= max_t):
                return False

        return True
```

### Fauna AI Behaviors

```python
# backend/daemons/engine/npc_ai/fauna_behaviors.py

class GrazingBehavior(BehaviorScript):
    """Herbivore behavior: wander and 'eat' flora."""

    id = "grazing"

    def on_tick(self, npc: WorldNpc, ctx: BehaviorContext) -> BehaviorResult:
        # Check if hungry (custom state)
        hunger = npc.get_state("hunger", 0)

        if hunger > 50:
            # Look for edible flora
            flora = ctx.engine.flora_system.get_room_flora(npc.room)
            edible = [f for f in flora if self._is_edible(f)]

            if edible:
                target = random.choice(edible)
                npc.set_state("hunger", hunger - 30)
                return BehaviorResult(
                    message=f"{npc.name} grazes on some {target.template.name}."
                )

        # Otherwise, wander
        if random.random() < 0.2:
            direction = random.choice(ctx.available_exits)
            return BehaviorResult(move_direction=direction)

        return BehaviorResult()

    def _is_edible(self, flora: FloraInstance) -> bool:
        # Grass, flowers, shrubs are edible
        return flora.template.flora_type in [
            FloraType.GRASS, FloraType.FLOWER, FloraType.SHRUB
        ]


class HuntingBehavior(BehaviorScript):
    """Carnivore behavior: seek and attack prey."""

    id = "hunting"

    def on_tick(self, npc: WorldNpc, ctx: BehaviorContext) -> BehaviorResult:
        fauna_system = ctx.engine.fauna_system

        # Look for prey in current room
        prey_list = fauna_system.find_prey_in_room(npc, npc.room)

        if prey_list:
            # Attack weakest prey
            target = min(prey_list, key=lambda p: p.current_hp)
            return BehaviorResult(attack_target=target)

        # No prey here, track or wander
        # Could implement scent tracking in future
        if random.random() < 0.3:
            direction = random.choice(ctx.available_exits)
            return BehaviorResult(move_direction=direction)

        return BehaviorResult()


class FleeingBehavior(BehaviorScript):
    """Prey behavior: flee from predators."""

    id = "fleeing_predator"

    def on_tick(self, npc: WorldNpc, ctx: BehaviorContext) -> BehaviorResult:
        fauna_system = ctx.engine.fauna_system

        # Check for predators
        predators = fauna_system.find_predators_in_room(npc, npc.room)

        if predators:
            # Flee! Pick exit away from predator
            safe_exits = self._find_safe_exits(npc, predators, ctx)
            if safe_exits:
                return BehaviorResult(
                    move_direction=random.choice(safe_exits),
                    message=f"{npc.name} bolts away in fear!"
                )

        return BehaviorResult()

    def _find_safe_exits(self, npc, predators, ctx) -> list[str]:
        # Return exits that don't lead toward predators
        # Simplified: just return all exits for now
        return ctx.available_exits


class TerritorialBehavior(BehaviorScript):
    """Territorial fauna: attacks intruders."""

    id = "territorial"

    def on_player_enter(self, npc: WorldNpc, player: WorldPlayer, ctx: BehaviorContext) -> BehaviorResult:
        fauna = ctx.engine.fauna_system.get_fauna_properties(npc.template)

        if fauna and fauna.territorial:
            # Check if player is in territory
            spawn_room = npc.get_state("spawn_room")
            distance = ctx.engine.calculate_room_distance(spawn_room, npc.room.id)

            if distance <= fauna.territory_radius:
                # Player entered territory - become aggressive
                return BehaviorResult(
                    message=f"{npc.name} growls menacingly at you!",
                    attack_target=player
                )

        return BehaviorResult()
```

---

## Phase 17.6: Condition-Dependent Spawn Cycles

### Spawn Condition Schema

```yaml
# Extend npc_spawns/_schema.yaml

spawns:
  type: array
  items:
    type: object
    required: [template_id, room_id]
    properties:
      template_id:
        type: string
      room_id:
        type: string
      quantity:
        type: integer
        default: 1

      # NEW: Spawn conditions
      spawn_conditions:
        type: object
        properties:
          # Time conditions
          time_of_day:
            type: array
            items:
              type: string
              enum: [dawn, day, dusk, night]

          # Temperature conditions
          temperature_min:
            type: integer
          temperature_max:
            type: integer
          temperature_range:
            type: array
            items:
              type: integer
            minItems: 2
            maxItems: 2

          # Weather conditions
          weather_is:
            type: array
            items:
              type: string
              enum: [clear, cloudy, overcast, rain, storm, snow, fog, wind]
          weather_not:
            type: array
            items:
              type: string
          weather_intensity_min:
            type: number
          weather_intensity_max:
            type: number

          # Season conditions
          season_is:
            type: array
            items:
              type: string
              enum: [spring, summer, fall, winter]
          season_not:
            type: array
            items:
              type: string

          # Biome conditions
          biome_is:
            type: array
            items:
              type: string
          biome_match:
            type: boolean
            description: "Only spawn if NPC's biome_tags match room's biome"

          # Light conditions
          light_level_min:
            type: integer
            minimum: 0
            maximum: 100
          light_level_max:
            type: integer
            minimum: 0
            maximum: 100

          # Population conditions
          max_in_area:
            type: integer
            description: "Maximum of this template in area"
          max_in_room:
            type: integer
            description: "Maximum of this template in room"

          # Dependency conditions
          requires_flora:
            type: array
            items:
              type: string
            description: "Flora template_ids that must be present"
          requires_fauna:
            type: array
            items:
              type: string
            description: "Fauna template_ids that must be present (prey)"
          excludes_fauna:
            type: array
            items:
              type: string
            description: "Fauna that prevents spawn (predators)"
```

### SpawnConditionEvaluator

```python
# backend/daemons/engine/systems/spawn_conditions.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class SpawnConditions:
    """Parsed spawn conditions from YAML."""
    time_of_day: Optional[list[str]] = None
    temperature_range: Optional[tuple[int, int]] = None
    weather_is: Optional[list[str]] = None
    weather_not: Optional[list[str]] = None
    weather_intensity_range: Optional[tuple[float, float]] = None
    season_is: Optional[list[str]] = None
    season_not: Optional[list[str]] = None
    biome_is: Optional[list[str]] = None
    biome_match: bool = False
    light_level_range: Optional[tuple[int, int]] = None
    max_in_area: Optional[int] = None
    max_in_room: Optional[int] = None
    requires_flora: Optional[list[str]] = None
    requires_fauna: Optional[list[str]] = None
    excludes_fauna: Optional[list[str]] = None

@dataclass
class EvaluationResult:
    """Result of condition evaluation."""
    can_spawn: bool
    failed_conditions: list[str]
    warnings: list[str]

class SpawnConditionEvaluator:
    """Evaluates spawn conditions against current environment."""

    def __init__(
        self,
        time_system: TimeSystem,
        temperature_system: TemperatureSystem,
        weather_system: WeatherSystem,
        season_system: SeasonSystem,
        biome_system: BiomeSystem,
        lighting_system: LightingSystem,
        flora_system: FloraSystem,
        fauna_system: FaunaSystem
    ):
        self.time_system = time_system
        self.temperature_system = temperature_system
        self.weather_system = weather_system
        self.season_system = season_system
        self.biome_system = biome_system
        self.lighting_system = lighting_system
        self.flora_system = flora_system
        self.fauna_system = fauna_system

    async def evaluate(
        self,
        conditions: SpawnConditions,
        room: WorldRoom,
        area: WorldArea,
        template: NpcTemplate,
        session: AsyncSession
    ) -> EvaluationResult:
        """Evaluate all spawn conditions."""
        failed = []
        warnings = []

        # Time of day
        if conditions.time_of_day:
            current_time = self.time_system.get_time_of_day(area)
            if current_time.value not in conditions.time_of_day:
                failed.append(f"time_of_day: {current_time.value} not in {conditions.time_of_day}")

        # Temperature
        if conditions.temperature_range:
            temp = self.temperature_system.calculate_room_temperature(room, area)
            min_t, max_t = conditions.temperature_range
            if not (min_t <= temp.effective_temperature <= max_t):
                failed.append(f"temperature: {temp.effective_temperature}°F not in [{min_t}, {max_t}]")

        # Weather
        if conditions.weather_is or conditions.weather_not:
            weather = self.weather_system.get_current_weather(area.id)
            if conditions.weather_is and weather.weather_type.value not in conditions.weather_is:
                failed.append(f"weather_is: {weather.weather_type.value} not in {conditions.weather_is}")
            if conditions.weather_not and weather.weather_type.value in conditions.weather_not:
                failed.append(f"weather_not: {weather.weather_type.value} in {conditions.weather_not}")

        # Season
        if conditions.season_is or conditions.season_not:
            season = self.season_system.get_season(area)
            if conditions.season_is and season.value not in conditions.season_is:
                failed.append(f"season_is: {season.value} not in {conditions.season_is}")
            if conditions.season_not and season.value in conditions.season_not:
                failed.append(f"season_not: {season.value} in {conditions.season_not}")

        # Biome match
        if conditions.biome_match:
            fauna = self.fauna_system.get_fauna_properties(template)
            if fauna:
                biome = self.biome_system.get_biome_for_area(area)
                if biome and fauna.biome_tags:
                    if not any(tag in biome.fauna_tags for tag in fauna.biome_tags):
                        failed.append(f"biome_match: fauna tags {fauna.biome_tags} not in biome {biome.fauna_tags}")

        # Population limits
        if conditions.max_in_room:
            count = await self._count_in_room(template.id, room, session)
            if count >= conditions.max_in_room:
                failed.append(f"max_in_room: {count} >= {conditions.max_in_room}")

        if conditions.max_in_area:
            count = await self._count_in_area(template.id, area, session)
            if count >= conditions.max_in_area:
                failed.append(f"max_in_area: {count} >= {conditions.max_in_area}")

        # Flora requirements
        if conditions.requires_flora:
            room_flora = await self.flora_system.get_room_flora(room, session)
            flora_ids = {f.template_id for f in room_flora}
            missing = set(conditions.requires_flora) - flora_ids
            if missing:
                failed.append(f"requires_flora: missing {missing}")

        # Fauna requirements (prey must be present)
        if conditions.requires_fauna:
            room_npcs = room.npcs
            npc_templates = {n.template_id for n in room_npcs}
            missing = set(conditions.requires_fauna) - npc_templates
            if missing:
                failed.append(f"requires_fauna: missing {missing}")

        # Fauna exclusions (predators prevent spawn)
        if conditions.excludes_fauna:
            room_npcs = room.npcs
            npc_templates = {n.template_id for n in room_npcs}
            present = set(conditions.excludes_fauna) & npc_templates
            if present:
                failed.append(f"excludes_fauna: {present} present")

        return EvaluationResult(
            can_spawn=len(failed) == 0,
            failed_conditions=failed,
            warnings=warnings
        )

    async def _count_in_room(self, template_id: str, room: WorldRoom, session: AsyncSession) -> int:
        return sum(1 for npc in room.npcs if npc.template_id == template_id)

    async def _count_in_area(self, template_id: str, area: WorldArea, session: AsyncSession) -> int:
        # Query database for count
        pass
```

### PopulationManager

```python
# backend/daemons/engine/systems/population.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class PopulationConfig:
    """Population management settings for an area."""
    area_id: str

    # Per-template caps
    template_caps: dict[str, int]  # template_id -> max count

    # Ecological dynamics
    predator_pressure: float = 1.0  # Multiplier on prey mortality
    prey_abundance: float = 1.0     # Multiplier on predator spawning
    flora_dependency: float = 1.0   # Herbivore spawn rate from flora

    # Recovery rates
    base_recovery_rate: float = 0.1  # Per-tick spawn chance when below cap
    critical_recovery_rate: float = 0.5  # When population < 25% of cap

@dataclass
class PopulationSnapshot:
    """Current population state for an area."""
    area_id: str
    timestamp: datetime
    counts: dict[str, int]  # template_id -> count
    flora_counts: dict[str, int]  # template_id -> count
    total_fauna: int
    total_flora: int

class PopulationManager:
    """Manages ecological population dynamics."""

    def __init__(
        self,
        fauna_system: FaunaSystem,
        flora_system: FloraSystem,
        spawn_evaluator: SpawnConditionEvaluator
    ):
        self.fauna_system = fauna_system
        self.flora_system = flora_system
        self.spawn_evaluator = spawn_evaluator
        self._configs: dict[str, PopulationConfig] = {}

    def get_population_snapshot(
        self,
        area: WorldArea,
        session: AsyncSession
    ) -> PopulationSnapshot:
        """Get current population counts for area."""
        pass

    def calculate_spawn_rate(
        self,
        template_id: str,
        area: WorldArea,
        snapshot: PopulationSnapshot
    ) -> float:
        """Calculate effective spawn rate based on population dynamics."""
        config = self._configs.get(area.id)
        if not config:
            return 1.0

        current = snapshot.counts.get(template_id, 0)
        cap = config.template_caps.get(template_id, 10)

        if current >= cap:
            return 0.0

        # Base rate
        ratio = current / cap
        if ratio < 0.25:
            rate = config.critical_recovery_rate
        else:
            rate = config.base_recovery_rate * (1 - ratio)

        # Ecological modifiers
        template = self.fauna_system.npc_system.get_template(template_id)
        fauna = self.fauna_system.get_fauna_properties(template)

        if fauna:
            match fauna.diet:
                case Diet.HERBIVORE:
                    # Spawn rate depends on flora
                    flora_ratio = snapshot.total_flora / 100  # Normalize
                    rate *= min(2.0, flora_ratio * config.flora_dependency)

                case Diet.CARNIVORE:
                    # Spawn rate depends on prey
                    prey_count = sum(
                        snapshot.counts.get(t, 0)
                        for t in self._get_prey_templates(fauna)
                    )
                    prey_ratio = prey_count / 50  # Normalize
                    rate *= min(2.0, prey_ratio * config.prey_abundance)

        return rate

    async def apply_predation(self, area: WorldArea, session: AsyncSession) -> PredationResult:
        """Apply predator-prey dynamics abstractly."""
        result = PredationResult([], [])

        for predator in self._get_hungry_predators(area):
            prey = self._find_available_prey(predator, area)
            if prey:
                # Simply despawn - no death event, no loot
                await self._despawn_npc_silent(prey, session)
                result.prey_despawned.append(prey.id)
                result.predators_fed.append(predator.id)
                predator.set_state("hunger", 0)

        return result

    def _get_prey_templates(self, fauna: FaunaProperties) -> list[str]:
        """Get template IDs that match prey_tags."""
        pass
```

### Integration with Spawn System

```python
# Extend backend/daemons/engine/engine.py

class WorldEngine:
    def __init__(self, ...):
        # ... existing init ...

        # Performance configuration (see Design Decisions section)
        # Adjust ecosystem_tick_interval to tune performance vs responsiveness
        self.perf_config = PerformanceConfig(ecosystem_tick_interval=5.0)

        # Track tick counters for multiplier-based scheduling
        self._ecosystem_tick_count = 0

    async def housekeeping_tick(self):
        """Extended with ecological processing.

        Uses PerformanceConfig to control tick frequency.
        Adjust perf_config.ecosystem_tick_interval to tune performance.
        """
        self._ecosystem_tick_count += 1

        # Existing housekeeping...

        # Flora respawn (every flora_update_multiplier ticks)
        if self._ecosystem_tick_count % self.perf_config.flora_update_multiplier == 0:
            await self._process_flora_respawns()

        # Fauna AI and movement (every fauna_ai_multiplier ticks)
        if self._ecosystem_tick_count % self.perf_config.fauna_ai_multiplier == 0:
            await self._process_fauna_ai()

        # Spawn checks (every spawn_check_multiplier ticks)
        if self._ecosystem_tick_count % self.perf_config.spawn_check_multiplier == 0:
            await self._process_fauna_spawns()

        # Migration (every migration_multiplier ticks)
        if self._ecosystem_tick_count % self.perf_config.migration_multiplier == 0:
            await self._process_fauna_migration()

        # Population dynamics (same as spawn check)
        if self._ecosystem_tick_count % self.perf_config.spawn_check_multiplier == 0:
            await self._process_population_dynamics()

    async def _process_fauna_spawns(self):
        """Process fauna spawning with conditions."""
        for area in self.loaded_areas.values():
            for spawn_def in area.npc_spawns:
                # Check if already spawned
                if self._is_spawn_active(spawn_def):
                    continue

                # Parse conditions
                conditions = SpawnConditions.from_dict(
                    spawn_def.get("spawn_conditions", {})
                )

                # Get template
                template = self.npc_system.get_template(spawn_def["template_id"])
                room = self.get_room(spawn_def["room_id"])

                # Evaluate conditions
                result = await self.spawn_evaluator.evaluate(
                    conditions, room, area, template, self.session
                )

                if not result.can_spawn:
                    continue

                # Check population rate
                snapshot = self.population_manager.get_population_snapshot(area)
                rate = self.population_manager.calculate_spawn_rate(
                    template.id, area, snapshot
                )

                if random.random() > rate:
                    continue

                # Spawn!
                fauna = self.fauna_system.get_fauna_properties(template)
                if fauna:
                    npcs = await self.fauna_system.spawn_pack(
                        template.id, room, self.session
                    )
                else:
                    npc = await self.npc_system.spawn_npc(
                        template.id, room, self.session
                    )
                    npcs = [npc]

                # Announce spawn (if visible to players)
                for npc in npcs:
                    await self._announce_spawn(npc, room)
```

---

## Design Decisions

This section documents key design decisions based on architectural discussions.

### 1. Flora Respawn Mechanics

Flora uses a **hybrid respawn system**:

- **Passive Respawn**: Small chance (configurable, default 5%) per housekeeping tick for depleted flora to respawn
- **Event-Triggered Respawn**: Guaranteed respawn during specific world events:
  - Rain/Storm weather → immediate respawn chance boost (50%)
  - Season change → full flora refresh for seasonal plants
  - Special world events (e.g., "spring bloom") → area-wide flora regeneration

```python
@dataclass
class FloraRespawnConfig:
    """Configuration for flora respawn mechanics."""
    passive_respawn_chance: float = 0.05  # 5% per tick
    rain_respawn_boost: float = 0.50      # 50% during rain
    storm_respawn_boost: float = 0.75     # 75% during storms
    season_change_refresh: bool = True     # Full refresh on season change

    # Per-flora-type modifiers
    type_modifiers: dict[FloraType, float] = field(default_factory=lambda: {
        FloraType.GRASS: 2.0,      # Grass regrows fast
        FloraType.FLOWER: 1.5,     # Flowers moderate
        FloraType.SHRUB: 1.0,      # Shrubs normal
        FloraType.TREE: 0.1,       # Trees very slow
        FloraType.FUNGUS: 1.5,     # Fungi moderate (moisture-dependent)
    })
```

### 2. Fauna Death Handling

Fauna uses an **abstract death model** - no loot, no corpses:

- When fauna dies (from combat or despawn), it simply disappears
- No item drops, no corpse entities to manage
- Keeps the system lightweight and avoids inventory bloat
- Fauna exists purely for world ambiance and ecological simulation

```python
async def handle_fauna_death(self, npc: NPC, cause: str) -> None:
    """Handle fauna death - simple cleanup, no loot/corpse."""
    # Log for debugging/metrics
    logger.debug(f"Fauna {npc.template_id} died in room {npc.room_id}: {cause}")

    # Update population tracking
    await self.population_manager.record_death(npc.template_id, npc.room_id)

    # Simply remove from world - no corpse, no loot
    await self.remove_npc(npc.id)

    # Optionally notify nearby players
    if cause == "combat":
        await self._broadcast_fauna_flees(npc)  # "The rabbit bolts into the underbrush!"
```

**Rationale**: This keeps fauna as environmental decoration rather than a loot piñata. Players interact with fauna for immersion, not grinding.

### 3. Player Impact on Ecosystem

**Default behavior**: No lasting player impact on flora/fauna populations.

- Harvesting flora depletes that instance temporarily (respawns via hybrid system above)
- Killing fauna removes that instance temporarily (respawns via population manager)
- No persistent "player harvested too much" tracking by default

**Extensibility for sustainability systems**: The architecture supports future sustainability mechanics:

```python
@dataclass
class SustainabilityConfig:
    """Optional sustainability tracking - disabled by default."""
    enabled: bool = False

    # If enabled, track harvesting impact
    overharvest_threshold: int = 10       # Harvests before impact triggers
    recovery_penalty_duration: int = 100   # Ticks before normal respawn resumes

    # Per-area tracking (only populated if enabled)
    area_harvest_counts: dict[str, int] = field(default_factory=dict)

class FloraSystem:
    def __init__(self, sustainability_config: Optional[SustainabilityConfig] = None):
        self.sustainability = sustainability_config or SustainabilityConfig()

    async def on_harvest(self, flora: FloraInstance, harvester: Character) -> None:
        """Hook for sustainability tracking - no-op by default."""
        if not self.sustainability.enabled:
            return

        # Track harvesting for sustainability impact
        area_id = self.get_area_for_room(flora.room_id)
        self.sustainability.area_harvest_counts[area_id] = \
            self.sustainability.area_harvest_counts.get(area_id, 0) + 1
```

**Rationale**: Sustainability systems add complexity that not all game implementations need. The hooks exist for future expansion without burdening the core system.

### 4. Cross-Area Fauna Migration

Fauna can **migrate between areas** with **biome-aware behavior**:

- Fauna may wander across area boundaries as part of natural movement
- Migration respects biome compatibility (fauna won't migrate to unsuitable biomes)
- If fauna finds itself in an unsuitable climate, it will attempt to return to a suitable area

```python
class FaunaMigrationBehavior:
    """Handles fauna movement between areas with biome awareness."""

    async def consider_migration(self, npc: NPC, current_room: Room) -> Optional[Room]:
        """Determine if fauna should migrate to adjacent area."""
        fauna = self.fauna_system.get_fauna_properties(npc.template_id)
        if not fauna:
            return None

        current_biome = self.biome_system.get_room_biome(current_room.id)

        # Check if current location is suitable
        if not self._is_biome_suitable(fauna, current_biome):
            # Fauna is in unsuitable climate - try to return home
            return await self._find_suitable_adjacent_room(npc, fauna)

        # Random chance to explore adjacent areas
        if random.random() > fauna.migration_tendency:
            return None

        # Find adjacent rooms (including cross-area)
        adjacent = await self.get_adjacent_rooms(current_room, include_area_exits=True)

        # Filter to suitable biomes only
        suitable = [
            room for room in adjacent
            if self._is_biome_suitable(fauna, self.biome_system.get_room_biome(room.id))
        ]

        if suitable:
            return random.choice(suitable)
        return None

    def _is_biome_suitable(self, fauna: FaunaProperties, biome: BiomeDefinition) -> bool:
        """Check if fauna can survive in this biome."""
        # Check biome tags against fauna preferences
        if fauna.preferred_biomes and biome.name not in fauna.preferred_biomes:
            return False

        # Check temperature tolerance
        if not (fauna.temp_min <= biome.base_temperature <= fauna.temp_max):
            return False

        return True
```

**Rationale**: Migration adds ecological realism - deer don't teleport, they wander. Biome awareness prevents desert scorpions from ending up in the arctic.

### 5. Performance Budget

Performance uses a **balanced approach** with an **easily adjustable variable**:

```python
@dataclass
class PerformanceConfig:
    """Ecosystem performance configuration - easily adjustable."""

    # Master tick interval (seconds) - adjust this one variable to tune performance
    ecosystem_tick_interval: float = 5.0  # Default: 5 seconds

    # Derived intervals (multiples of master tick)
    flora_update_multiplier: int = 2      # Every 2 ecosystem ticks (10s)
    fauna_ai_multiplier: int = 1          # Every ecosystem tick (5s)
    spawn_check_multiplier: int = 4       # Every 4 ecosystem ticks (20s)
    migration_multiplier: int = 6         # Every 6 ecosystem ticks (30s)

    # Batch processing limits
    max_fauna_per_tick: int = 50          # Process at most 50 fauna per tick
    max_flora_per_tick: int = 100         # Process at most 100 flora per tick

    # Population caps (hard limits)
    max_fauna_per_area: int = 20
    max_flora_per_room: int = 10

    @property
    def flora_tick_interval(self) -> float:
        return self.ecosystem_tick_interval * self.flora_update_multiplier

    @property
    def spawn_tick_interval(self) -> float:
        return self.ecosystem_tick_interval * self.spawn_check_multiplier

# Usage: Adjust one variable to scale performance
config = PerformanceConfig(ecosystem_tick_interval=10.0)  # Slower, less CPU
config = PerformanceConfig(ecosystem_tick_interval=2.0)   # Faster, more responsive
```

**Rationale**: A single "master knob" (`ecosystem_tick_interval`) lets server operators easily tune performance vs. responsiveness based on their hardware and player count. The multiplier system keeps relative timing consistent.

---

## Summary of Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Flora Respawn | Hybrid: passive chance + event-triggered | Natural feel without guaranteed timers |
| Fauna Death | Abstract (no loot/corpse) | Keeps fauna as ambiance, not loot source |
| Player Impact | No default impact, extensible hooks | Simple by default, complex when needed |
| Cross-Area Migration | Allowed, biome-aware | Ecological realism with safety checks |
| Performance | Single adjustable master tick | Easy tuning for different server loads |

---

## Next Steps

With design decisions documented, implementation can proceed:

1. **Phase 17.4**: Implement FloraSystem with hybrid respawn
2. **Phase 17.5**: Implement FaunaSystem with abstract death and migration
3. **Phase 17.6**: Implement SpawnConditionEvaluator and PopulationManager
4. **Testing**: Comprehensive unit tests for each phase
5. **Integration**: Connect all systems through EcosystemManager
```
