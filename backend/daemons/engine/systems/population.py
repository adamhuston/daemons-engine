"""
Phase 17.6: Population Manager

Manages ecological population dynamics for fauna and flora.

Responsibilities:
- Track population counts per area
- Calculate spawn rates based on population levels
- Apply ecological dynamics (predator-prey, herbivore-flora)
- Manage population recovery rates
- Record births/deaths for population tracking

Design Decisions (see Phase17_implementation.md):
- Abstract death model: no loot/corpses, just despawn
- Predator-prey dynamics affect spawn rates
- Single tick interval for performance tuning
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from daemons.engine.systems.fauna import Diet, FaunaProperties, FaunaSystem
    from daemons.engine.systems.flora import FloraSystem
    from daemons.engine.systems.spawn_conditions import SpawnConditionEvaluator
    from daemons.engine.world import World, WorldNpc

logger = logging.getLogger(__name__)


# === Dataclasses ===


@dataclass
class PopulationConfig:
    """
    Population management settings for an area.

    Configure per-template caps and ecological dynamics.
    """

    area_id: str

    # Per-template population caps
    template_caps: dict[str, int] = field(default_factory=dict)  # template_id -> max

    # Global caps
    max_fauna_total: int = 100
    max_flora_total: int = 200

    # Ecological dynamics multipliers
    predator_pressure: float = 1.0  # Multiplier on prey mortality rate
    prey_abundance: float = 1.0  # Multiplier on predator spawn rate
    flora_dependency: float = 1.0  # Herbivore spawn rate from flora

    # Recovery rates (per-tick spawn chance when below cap)
    base_recovery_rate: float = 0.1  # Normal recovery
    critical_recovery_rate: float = 0.5  # When population < 25% of cap
    overpopulation_cull_rate: float = 0.1  # Despawn rate when over cap

    @classmethod
    def default_for_area(cls, area_id: str) -> "PopulationConfig":
        """Create default population config for an area."""
        return cls(area_id=area_id)


@dataclass
class PopulationSnapshot:
    """
    Current population state for an area at a point in time.

    Used for spawn rate calculations and ecological dynamics.
    """

    area_id: str
    timestamp: float

    # Fauna counts by template
    fauna_counts: dict[str, int] = field(default_factory=dict)
    total_fauna: int = 0

    # Flora counts by template
    flora_counts: dict[str, int] = field(default_factory=dict)
    total_flora: int = 0

    # Ecological metrics
    predator_count: int = 0
    prey_count: int = 0
    herbivore_count: int = 0

    def get_population_ratio(self, template_id: str, cap: int) -> float:
        """Get population as ratio of cap (0.0-1.0+)."""
        if cap <= 0:
            return 1.0
        count = self.fauna_counts.get(template_id, 0)
        return count / cap


@dataclass
class PredationResult:
    """Result of predation processing."""

    prey_despawned: list[str] = field(default_factory=list)  # NPC IDs
    predators_fed: list[str] = field(default_factory=list)  # NPC IDs
    messages: list[str] = field(default_factory=list)  # Flavor messages


@dataclass
class SpawnResult:
    """Result of population spawn processing."""

    spawned_count: int = 0
    spawned_templates: list[str] = field(default_factory=list)
    skipped_conditions: list[str] = field(default_factory=list)
    skipped_population: list[str] = field(default_factory=list)


# === Population Manager ===


class PopulationManager:
    """
    Manages ecological population dynamics for an area.

    Integrates with FaunaSystem and FloraSystem to:
    - Track current populations
    - Calculate spawn rates based on ecological balance
    - Apply predator-prey dynamics
    - Manage population recovery
    """

    def __init__(
        self,
        world: "World",
        fauna_system: Optional["FaunaSystem"] = None,
        flora_system: Optional["FloraSystem"] = None,
        spawn_evaluator: Optional["SpawnConditionEvaluator"] = None,
    ):
        self.world = world
        self.fauna_system = fauna_system
        self.flora_system = flora_system
        self.spawn_evaluator = spawn_evaluator

        # Area configs
        self._configs: dict[str, PopulationConfig] = {}

        # Cache snapshots for performance
        self._snapshot_cache: dict[str, PopulationSnapshot] = {}
        self._snapshot_ttl: float = 5.0  # Seconds

        # Track recent deaths for recovery rate adjustments
        self._recent_deaths: dict[str, list[float]] = {}  # template_id -> timestamps
        self._death_window: float = 60.0  # Seconds to track

        logger.info("PopulationManager initialized")

    # === Configuration ===

    def set_config(self, config: PopulationConfig) -> None:
        """Set population config for an area."""
        self._configs[config.area_id] = config
        logger.debug(f"Set population config for area {config.area_id}")

    def get_config(self, area_id: str) -> PopulationConfig:
        """Get population config for area, creating default if needed."""
        if area_id not in self._configs:
            self._configs[area_id] = PopulationConfig.default_for_area(area_id)
        return self._configs[area_id]

    def set_template_cap(
        self, area_id: str, template_id: str, cap: int
    ) -> None:
        """Set population cap for a specific template in an area."""
        config = self.get_config(area_id)
        config.template_caps[template_id] = cap

    # === Population Snapshots ===

    def get_population_snapshot(
        self, area_id: str, force_refresh: bool = False
    ) -> PopulationSnapshot:
        """
        Get current population counts for an area.

        Uses caching for performance.
        """
        # Check cache
        if not force_refresh and area_id in self._snapshot_cache:
            cached = self._snapshot_cache[area_id]
            if time.time() - cached.timestamp < self._snapshot_ttl:
                return cached

        # Build fresh snapshot
        snapshot = PopulationSnapshot(
            area_id=area_id,
            timestamp=time.time(),
        )

        # Count fauna
        for npc in self.world.npcs.values():
            room = self.world.rooms.get(npc.room_id)
            if not room or getattr(room, "area_id", None) != area_id:
                continue

            template_id = npc.template_id
            snapshot.fauna_counts[template_id] = (
                snapshot.fauna_counts.get(template_id, 0) + 1
            )
            snapshot.total_fauna += 1

            # Track by diet
            if self.fauna_system:
                fauna = self.fauna_system.get_fauna_properties(template_id)
                if fauna:
                    from daemons.engine.systems.fauna import Diet

                    if fauna.diet == Diet.CARNIVORE:
                        snapshot.predator_count += 1
                    elif fauna.diet == Diet.HERBIVORE:
                        snapshot.herbivore_count += 1
                        snapshot.prey_count += 1
                    elif fauna.diet == Diet.OMNIVORE:
                        # Omnivores count as both
                        snapshot.prey_count += 1

        # Count flora (if flora system available)
        # Note: Flora counts would come from flora_instances table
        # For now, we estimate based on room flora

        self._snapshot_cache[area_id] = snapshot
        return snapshot

    def invalidate_cache(self, area_id: Optional[str] = None) -> None:
        """Invalidate population cache for area(s)."""
        if area_id:
            self._snapshot_cache.pop(area_id, None)
        else:
            self._snapshot_cache.clear()

    # === Spawn Rate Calculation ===

    def calculate_spawn_rate(
        self,
        template_id: str,
        area_id: str,
        snapshot: Optional[PopulationSnapshot] = None,
    ) -> float:
        """
        Calculate effective spawn rate based on population dynamics.

        Returns a rate multiplier (0.0 = don't spawn, 1.0+ = spawn)
        """
        config = self.get_config(area_id)

        if snapshot is None:
            snapshot = self.get_population_snapshot(area_id)

        current = snapshot.fauna_counts.get(template_id, 0)
        cap = config.template_caps.get(template_id, 10)

        # At or over cap - don't spawn
        if current >= cap:
            return 0.0

        # Calculate base rate based on population level
        ratio = current / cap

        if ratio < 0.25:
            # Critical - high recovery rate
            rate = config.critical_recovery_rate
        else:
            # Normal - rate decreases as we approach cap
            rate = config.base_recovery_rate * (1 - ratio)

        # Apply ecological modifiers
        if self.fauna_system:
            fauna = self.fauna_system.get_fauna_properties(template_id)
            if fauna:
                rate = self._apply_ecological_modifiers(
                    rate, fauna, config, snapshot
                )

        # Apply recent death boost
        rate = self._apply_death_recovery_boost(rate, template_id)

        return max(0.0, rate)

    def _apply_ecological_modifiers(
        self,
        base_rate: float,
        fauna: "FaunaProperties",
        config: PopulationConfig,
        snapshot: PopulationSnapshot,
    ) -> float:
        """Apply ecological dynamics to spawn rate."""
        from daemons.engine.systems.fauna import Diet

        rate = base_rate

        match fauna.diet:
            case Diet.HERBIVORE:
                # Herbivore spawn rate depends on flora abundance
                flora_ratio = min(2.0, snapshot.total_flora / 100)
                rate *= flora_ratio * config.flora_dependency

                # Also affected by predator pressure (fewer spawn if many predators)
                if snapshot.predator_count > 0:
                    predator_factor = 1.0 / (1.0 + snapshot.predator_count * 0.1)
                    rate *= predator_factor

            case Diet.CARNIVORE:
                # Carnivore spawn rate depends on prey abundance
                prey_ratio = min(2.0, snapshot.prey_count / 50)
                rate *= prey_ratio * config.prey_abundance

            case Diet.OMNIVORE:
                # Omnivores benefit from both
                food_available = (snapshot.prey_count + snapshot.total_flora) / 100
                rate *= min(1.5, food_available)

            case Diet.SCAVENGER:
                # Scavengers spawn based on total fauna (more deaths = more food)
                fauna_ratio = min(1.5, snapshot.total_fauna / 50)
                rate *= fauna_ratio

        return rate

    def _apply_death_recovery_boost(
        self, rate: float, template_id: str
    ) -> float:
        """Boost spawn rate if many recent deaths of this template."""
        now = time.time()
        deaths = self._recent_deaths.get(template_id, [])

        # Clean old deaths
        deaths = [t for t in deaths if now - t < self._death_window]
        self._recent_deaths[template_id] = deaths

        # Boost rate based on recent deaths
        if deaths:
            death_count = len(deaths)
            boost = 1.0 + (death_count * 0.1)  # 10% boost per recent death
            rate *= min(2.0, boost)

        return rate

    # === Death Tracking ===

    async def record_death(
        self, template_id: str, room_id: str
    ) -> None:
        """Record a fauna death for population tracking."""
        now = time.time()

        if template_id not in self._recent_deaths:
            self._recent_deaths[template_id] = []
        self._recent_deaths[template_id].append(now)

        # Invalidate cache
        room = self.world.rooms.get(room_id)
        if room:
            area_id = getattr(room, "area_id", None)
            if area_id:
                self.invalidate_cache(area_id)

        logger.debug(f"Recorded death of {template_id} in room {room_id}")

    async def record_birth(
        self, template_id: str, room_id: str
    ) -> None:
        """Record a fauna spawn for population tracking."""
        room = self.world.rooms.get(room_id)
        if room:
            area_id = getattr(room, "area_id", None)
            if area_id:
                self.invalidate_cache(area_id)

        logger.debug(f"Recorded birth of {template_id} in room {room_id}")

    # === Hunger/Need Processing ===

    def update_fauna_hunger(self, area_id: str, hunger_increment: int = 10) -> None:
        """
        Update hunger for all fauna in an area.

        Called each ecosystem tick to gradually increase hunger.
        When hunger > 50, herbivores will graze.
        When hunger > 70, predators will attempt to hunt.
        """
        import random
        import time as time_module

        from daemons.engine.systems.fauna import Diet

        if not self.fauna_system:
            return

        for npc in self.world.npcs.values():
            if not npc.is_alive():
                continue

            room = self.world.rooms.get(npc.room_id)
            if not room or getattr(room, "area_id", None) != area_id:
                continue

            # Only fauna with diet tracking
            fauna = self.fauna_system.get_fauna_properties(npc.template_id)
            if not fauna:
                continue

            # Initialize hunger if not set (newly spawned fauna)
            if npc.hunger is None:
                npc.hunger = random.randint(20, 50)
                npc.last_hunger_update = time_module.time()

            # All fauna get hungry over time
            current = npc.hunger
            new_hunger = min(100, current + hunger_increment)
            npc.hunger = new_hunger
            npc.last_hunger_update = time_module.time()

    # === Predation Dynamics ===

    async def apply_predation(
        self,
        area_id: str,
        session: "AsyncSession",
    ) -> PredationResult:
        """
        Apply predator-prey dynamics abstractly.

        Predators "feed" by causing prey despawn with no drops.
        This is the abstract fauna death model.
        """
        result = PredationResult()

        if not self.fauna_system:
            return result

        config = self.get_config(area_id)

        # Find hungry predators
        predators = self._get_hungry_predators(area_id)

        for predator in predators:
            # Find available prey
            prey = self._find_available_prey(predator, area_id)

            if prey:
                # Abstract kill - just despawn, no loot/corpse
                await self._despawn_prey(prey, session)

                result.prey_despawned.append(prey.id)
                result.predators_fed.append(predator.id)

                # Mark predator as fed
                self._mark_predator_fed(predator)

                # Record death for population tracking
                await self.record_death(prey.template_id, prey.room_id)

                # Add flavor message
                result.messages.append(
                    f"A {predator.name} catches its prey."
                )

        return result

    def _get_hungry_predators(self, area_id: str) -> list["WorldNpc"]:
        """Get predators in area that need to feed."""
        hungry = []

        if not self.fauna_system:
            return hungry

        for npc in self.world.npcs.values():
            room = self.world.rooms.get(npc.room_id)
            if not room or getattr(room, "area_id", None) != area_id:
                continue

            fauna = self.fauna_system.get_fauna_properties(npc.template_id)
            if not fauna:
                continue

            from daemons.engine.systems.fauna import Diet

            if fauna.diet not in [Diet.CARNIVORE, Diet.OMNIVORE]:
                continue

            # Check hunger state (if tracked)
            hunger = getattr(npc, "hunger", 50)
            if hunger > 70:  # Hungry
                hungry.append(npc)

        return hungry

    def _find_available_prey(
        self, predator: "WorldNpc", area_id: str
    ) -> Optional["WorldNpc"]:
        """Find available prey for a predator."""
        if not self.fauna_system:
            return None

        pred_fauna = self.fauna_system.get_fauna_properties(predator.template_id)
        if not pred_fauna or not pred_fauna.prey_tags:
            return None

        # Look in same room first
        prey_in_room = self.fauna_system.find_prey_in_room(
            predator.template_id, predator.room_id
        )

        if prey_in_room:
            import random

            return random.choice(prey_in_room)

        return None

    async def _despawn_prey(
        self, prey: "WorldNpc", session: "AsyncSession"
    ) -> None:
        """Despawn prey silently - no drops, no corpse."""
        # Remove from world
        self.world.npcs.pop(prey.id, None)

        # Remove from room
        room = self.world.rooms.get(prey.room_id)
        if room:
            npc_ids = getattr(room, "npc_ids", [])
            if prey.id in npc_ids:
                npc_ids.remove(prey.id)

        logger.debug(f"Despawned prey {prey.template_id} ({prey.id})")

    def _mark_predator_fed(self, predator: "WorldNpc") -> None:
        """Mark predator as having fed recently."""
        # Reset hunger state
        if hasattr(predator, "hunger"):
            predator.hunger = 0
        # Or set state via state dict if available
        if hasattr(predator, "state"):
            predator.state["hunger"] = 0
            predator.state["last_fed"] = time.time()

    # === Population Control ===

    async def apply_population_control(
        self,
        area_id: str,
        session: "AsyncSession",
    ) -> int:
        """
        Apply population control if over caps.

        Returns number of NPCs despawned.
        """
        config = self.get_config(area_id)
        snapshot = self.get_population_snapshot(area_id, force_refresh=True)
        despawned = 0

        # Check per-template caps
        for template_id, count in snapshot.fauna_counts.items():
            cap = config.template_caps.get(template_id, 10)
            excess = count - cap

            if excess > 0:
                # Despawn some excess
                to_despawn = min(
                    excess,
                    int(excess * config.overpopulation_cull_rate) + 1,
                )

                despawned += await self._despawn_excess(
                    template_id, area_id, to_despawn, session
                )

        # Check total cap
        if snapshot.total_fauna > config.max_fauna_total:
            excess = snapshot.total_fauna - config.max_fauna_total
            to_despawn = min(
                excess,
                int(excess * config.overpopulation_cull_rate) + 1,
            )

            # Despawn from most populous template
            if snapshot.fauna_counts:
                most_populous = max(
                    snapshot.fauna_counts.keys(),
                    key=lambda k: snapshot.fauna_counts[k],
                )
                despawned += await self._despawn_excess(
                    most_populous, area_id, to_despawn, session
                )

        if despawned > 0:
            logger.debug(f"Population control despawned {despawned} NPCs in {area_id}")
            self.invalidate_cache(area_id)

        return despawned

    async def _despawn_excess(
        self,
        template_id: str,
        area_id: str,
        count: int,
        session: "AsyncSession",
    ) -> int:
        """Despawn excess NPCs of a template."""
        despawned = 0

        # Find NPCs to despawn
        candidates = []
        for npc in list(self.world.npcs.values()):
            if npc.template_id != template_id:
                continue

            room = self.world.rooms.get(npc.room_id)
            if not room or getattr(room, "area_id", None) != area_id:
                continue

            # Don't despawn if player in room
            if self._has_player_in_room(npc.room_id):
                continue

            candidates.append(npc)

        # Despawn up to count
        import random

        random.shuffle(candidates)

        for npc in candidates[:count]:
            await self._despawn_prey(npc, session)
            despawned += 1

        return despawned

    def _has_player_in_room(self, room_id: str) -> bool:
        """Check if any players are in a room."""
        for player in self.world.players.values():
            if player.room_id == room_id:
                return True
        return False

    # === Utility Methods ===

    def get_area_health(self, area_id: str) -> dict[str, Any]:
        """
        Get ecological health metrics for an area.

        Useful for debugging and admin tools.
        """
        snapshot = self.get_population_snapshot(area_id)
        config = self.get_config(area_id)

        # Calculate health metrics
        predator_prey_ratio = (
            snapshot.predator_count / max(1, snapshot.prey_count)
        )
        herbivore_flora_ratio = (
            snapshot.herbivore_count / max(1, snapshot.total_flora / 10)
        )

        # Healthy ecosystem: ~1:5 predator:prey ratio
        predator_health = 1.0 - abs(predator_prey_ratio - 0.2) / 0.2
        predator_health = max(0.0, min(1.0, predator_health))

        # Healthy ecosystem: ~1:10 herbivore:flora ratio
        herbivore_health = 1.0 - abs(herbivore_flora_ratio - 0.1) / 0.1
        herbivore_health = max(0.0, min(1.0, herbivore_health))

        return {
            "area_id": area_id,
            "total_fauna": snapshot.total_fauna,
            "total_flora": snapshot.total_flora,
            "predator_count": snapshot.predator_count,
            "prey_count": snapshot.prey_count,
            "herbivore_count": snapshot.herbivore_count,
            "predator_prey_ratio": predator_prey_ratio,
            "herbivore_flora_ratio": herbivore_flora_ratio,
            "ecosystem_health": (predator_health + herbivore_health) / 2,
            "fauna_counts": snapshot.fauna_counts,
            "template_caps": config.template_caps,
        }
