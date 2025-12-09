"""
Phase 17.5: Fauna AI Behaviors

Behavior scripts for fauna NPCs that implement ecological behaviors:
- GrazingBehavior: Herbivores eating flora
- HuntingBehavior: Carnivores seeking prey
- FleeingBehavior: Prey fleeing from predators
- TerritorialBehavior: Defending territory

These behaviors integrate with the NPC AI system and FaunaSystem.
"""

import logging
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from daemons.engine.systems.fauna import FaunaProperties, FaunaSystem
    from daemons.engine.systems.flora import FloraSystem, FloraType
    from daemons.engine.world import WorldNpc, WorldPlayer, WorldRoom

logger = logging.getLogger(__name__)


@dataclass
class BehaviorResult:
    """Result of a behavior tick."""

    message: Optional[str] = None  # Message to broadcast to room
    move_direction: Optional[str] = None  # Direction to move
    attack_target: Optional[Any] = None  # Target to attack (NPC or Player)
    state_changes: dict[str, Any] = None  # State changes to apply to NPC

    def __post_init__(self):
        if self.state_changes is None:
            self.state_changes = {}


@dataclass
class BehaviorContext:
    """Context provided to behavior scripts."""

    room: "WorldRoom"
    available_exits: list[str]
    engine: Any = None  # WorldEngine reference
    area_id: Optional[str] = None  # Area ID for the current room
    nearby_players: Optional[list["WorldPlayer"]] = None
    nearby_npcs: Optional[list["WorldNpc"]] = None
    fauna_system: Optional["FaunaSystem"] = None
    flora_system: Optional["FloraSystem"] = None

    def __post_init__(self):
        if self.nearby_players is None:
            self.nearby_players = []
        if self.nearby_npcs is None:
            self.nearby_npcs = []


class BaseBehavior:
    """Base class for fauna behaviors."""

    id: str = "base"
    priority: int = 50  # Higher = more important

    def on_tick(
        self, npc: "WorldNpc", ctx: BehaviorContext
    ) -> Optional[BehaviorResult]:
        """Called each AI tick. Override in subclasses."""
        return None

    def on_player_enter(
        self, npc: "WorldNpc", player: "WorldPlayer", ctx: BehaviorContext
    ) -> Optional[BehaviorResult]:
        """Called when a player enters the room."""
        return None

    def on_player_exit(
        self, npc: "WorldNpc", player: "WorldPlayer", ctx: BehaviorContext
    ) -> Optional[BehaviorResult]:
        """Called when a player exits the room."""
        return None

    def on_damage_taken(
        self, npc: "WorldNpc", damage: int, source: Any, ctx: BehaviorContext
    ) -> Optional[BehaviorResult]:
        """Called when NPC takes damage."""
        return None


class GrazingBehavior(BaseBehavior):
    """
    Herbivore behavior: wander and 'eat' flora.

    Herbivores will:
    - Seek out edible flora when hungry
    - Wander randomly when not hungry
    - Flee if predators are nearby
    """

    id = "grazing"
    priority = 30

    # Flora types that herbivores can eat
    EDIBLE_FLORA_TYPES = {"grass", "flower", "shrub"}

    def on_tick(
        self, npc: "WorldNpc", ctx: BehaviorContext
    ) -> Optional[BehaviorResult]:
        """Process grazing behavior."""
        # Check for predators first
        if ctx.fauna_system:
            predators = ctx.fauna_system.find_predators_in_room(
                npc.template_id, npc.room_id
            )
            if predators:
                # Flee! Let FleeingBehavior handle it
                return None

        # Check hunger state
        hunger = self._get_npc_state(npc, "hunger", 0)

        if hunger > 50:
            # Hungry - look for food
            return self._try_to_graze(npc, ctx)

        # Not hungry - random wandering
        if random.random() < 0.2 and ctx.available_exits:
            direction = random.choice(ctx.available_exits)
            return BehaviorResult(move_direction=direction)

        return None

    def _try_to_graze(
        self, npc: "WorldNpc", ctx: BehaviorContext
    ) -> Optional[BehaviorResult]:
        """Try to find and eat flora."""
        if not ctx.flora_system:
            return None

        # This would need async, so just return a grazing message
        # Real implementation would check for edible flora
        hunger = self._get_npc_state(npc, "hunger", 0)

        # Simulate finding food
        if random.random() < 0.6:
            new_hunger = max(0, hunger - 30)
            return BehaviorResult(
                message=f"The {npc.name} grazes contentedly.",
                state_changes={"hunger": new_hunger},
            )

        # No food found, wander to find some
        if ctx.available_exits:
            direction = random.choice(ctx.available_exits)
            return BehaviorResult(move_direction=direction)

        return None

    def _get_npc_state(self, npc: "WorldNpc", key: str, default: Any) -> Any:
        """Get NPC state value - checks direct attributes first, then state dict."""
        # Check direct attribute first (e.g., npc.hunger)
        if hasattr(npc, key):
            value = getattr(npc, key, None)
            if value is not None:
                return value
        # Fall back to state dict
        if hasattr(npc, "state") and npc.state:
            return npc.state.get(key, default)
        return default


class HuntingBehavior(BaseBehavior):
    """
    Carnivore behavior: seek and attack prey.

    Carnivores will:
    - Hunt prey when hungry
    - Attack weakest prey in room
    - Track prey scent (future enhancement)
    """

    id = "hunting"
    priority = 40

    def on_tick(
        self, npc: "WorldNpc", ctx: BehaviorContext
    ) -> Optional[BehaviorResult]:
        """Process hunting behavior."""
        if not ctx.fauna_system:
            return None

        # Check hunger
        hunger = self._get_npc_state(npc, "hunger", 0)

        if hunger < 50:
            # Not very hungry, just patrol occasionally
            if random.random() < 0.15 and ctx.available_exits:
                direction = random.choice(ctx.available_exits)
                return BehaviorResult(move_direction=direction)
            return None

        # Hungry - look for prey
        prey_list = ctx.fauna_system.find_prey_in_room(npc.template_id, npc.room_id)

        if prey_list:
            # Attack weakest prey
            target = min(
                prey_list,
                key=lambda p: getattr(p, "current_health", 100),
            )
            return BehaviorResult(
                message=f"The {npc.name} lunges at the {target.name}!",
                attack_target=target,
            )

        # No prey here - hunt/wander
        if random.random() < 0.3 and ctx.available_exits:
            direction = random.choice(ctx.available_exits)
            return BehaviorResult(
                message=f"The {npc.name} prowls {direction}ward.",
                move_direction=direction,
            )

        return None

    def _get_npc_state(self, npc: "WorldNpc", key: str, default: Any) -> Any:
        """Get NPC state value."""
        if hasattr(npc, "state") and npc.state:
            return npc.state.get(key, default)
        return default


class FleeingBehavior(BaseBehavior):
    """
    Prey behavior: flee from predators.

    Prey will:
    - Detect predators in room
    - Flee to safety
    - Run faster when injured
    """

    id = "fleeing"
    priority = 100  # Highest priority - survival!

    def on_tick(
        self, npc: "WorldNpc", ctx: BehaviorContext
    ) -> Optional[BehaviorResult]:
        """Check for predators and flee."""
        if not ctx.fauna_system:
            return None

        predators = ctx.fauna_system.find_predators_in_room(
            npc.template_id, npc.room_id
        )

        if not predators:
            return None

        # Predator detected! Flee!
        safe_exits = self._find_safe_exits(npc, predators, ctx)

        if safe_exits:
            direction = random.choice(safe_exits)
            return BehaviorResult(
                message=f"The {npc.name} bolts away in fear!",
                move_direction=direction,
            )

        # No safe exits - cower
        return BehaviorResult(
            message=f"The {npc.name} trembles in fear!",
        )

    def on_damage_taken(
        self, npc: "WorldNpc", damage: int, source: Any, ctx: BehaviorContext
    ) -> Optional[BehaviorResult]:
        """Flee when taking damage."""
        if not ctx.available_exits:
            return None

        # Always try to flee when hit
        direction = random.choice(ctx.available_exits)
        return BehaviorResult(
            message=f"The {npc.name} flees in terror!",
            move_direction=direction,
        )

    def _find_safe_exits(
        self,
        npc: "WorldNpc",
        predators: list["WorldNpc"],
        ctx: BehaviorContext,
    ) -> list[str]:
        """Find exits that don't lead toward predators."""
        # Simplified: return all available exits
        # Future: track predator positions and avoid
        return ctx.available_exits


class TerritorialBehavior(BaseBehavior):
    """
    Territorial fauna: defend territory from intruders.

    Territorial fauna will:
    - Attack players/NPCs that enter their territory
    - Stay within territory_radius of spawn point
    - Display warning before attacking
    """

    id = "territorial"
    priority = 60

    def on_player_enter(
        self, npc: "WorldNpc", player: "WorldPlayer", ctx: BehaviorContext
    ) -> Optional[BehaviorResult]:
        """React to player entering territory."""
        if not ctx.fauna_system:
            return None

        fauna = ctx.fauna_system.get_fauna_properties(npc.template_id)
        if not fauna or not fauna.territorial:
            return None

        # Check if player is in territory
        spawn_room = self._get_npc_state(npc, "spawn_room", npc.room_id)
        in_territory = self._is_in_territory(
            spawn_room, npc.room_id, fauna.territory_radius, ctx
        )

        if not in_territory:
            return None

        # Player entered territory - warning first
        warning_given = self._get_npc_state(npc, "warning_given", False)

        if not warning_given:
            return BehaviorResult(
                message=f"The {npc.name} growls menacingly at you!",
                state_changes={"warning_given": True},
            )

        # Already warned - attack!
        return BehaviorResult(
            message=f"The {npc.name} attacks to defend its territory!",
            attack_target=player,
        )

    def on_tick(
        self, npc: "WorldNpc", ctx: BehaviorContext
    ) -> Optional[BehaviorResult]:
        """Patrol territory and return if strayed too far."""
        if not ctx.fauna_system:
            return None

        fauna = ctx.fauna_system.get_fauna_properties(npc.template_id)
        if not fauna or not fauna.territorial:
            return None

        spawn_room = self._get_npc_state(npc, "spawn_room", npc.room_id)
        in_territory = self._is_in_territory(
            spawn_room, npc.room_id, fauna.territory_radius, ctx
        )

        if not in_territory:
            # Strayed too far - return home
            # Would need pathfinding; for now, just wander back
            if ctx.available_exits:
                direction = random.choice(ctx.available_exits)
                return BehaviorResult(move_direction=direction)

        # Reset warning if no players present
        if not ctx.nearby_players:
            return BehaviorResult(state_changes={"warning_given": False})

        return None

    def _is_in_territory(
        self,
        spawn_room: str,
        current_room: str,
        radius: int,
        ctx: BehaviorContext,
    ) -> bool:
        """Check if current room is within territory radius."""
        if spawn_room == current_room:
            return True

        # Simplified: always return True
        # Real implementation would calculate room distance
        return True

    def _get_npc_state(self, npc: "WorldNpc", key: str, default: Any) -> Any:
        """Get NPC state value."""
        if hasattr(npc, "state") and npc.state:
            return npc.state.get(key, default)
        return default


class PackBehavior(BaseBehavior):
    """
    Pack behavior: coordinate with pack members.

    Pack fauna will:
    - Stay near pack leader
    - Assist pack members in combat
    - Follow leader's movement
    """

    id = "pack"
    priority = 45

    def on_tick(
        self, npc: "WorldNpc", ctx: BehaviorContext
    ) -> Optional[BehaviorResult]:
        """Coordinate with pack."""
        # Find pack leader
        leader_id = self._get_npc_state(npc, "pack_leader_id", None)
        if not leader_id:
            return None

        # Check if leader is in same room
        leader = next(
            (n for n in ctx.nearby_npcs if n.id == leader_id),
            None,
        )

        if not leader:
            # Leader not here - try to find them
            # Would need pathfinding
            if ctx.available_exits:
                direction = random.choice(ctx.available_exits)
                return BehaviorResult(move_direction=direction)

        return None

    def _get_npc_state(self, npc: "WorldNpc", key: str, default: Any) -> Any:
        """Get NPC state value."""
        if hasattr(npc, "state") and npc.state:
            return npc.state.get(key, default)
        return default


# === Behavior Registry ===

FAUNA_BEHAVIORS: dict[str, type[BaseBehavior]] = {
    "grazing": GrazingBehavior,
    "hunting": HuntingBehavior,
    "fleeing": FleeingBehavior,
    "territorial": TerritorialBehavior,
    "pack": PackBehavior,
}


def get_behavior(behavior_id: str) -> Optional[BaseBehavior]:
    """Get a behavior instance by ID."""
    behavior_class = FAUNA_BEHAVIORS.get(behavior_id)
    if behavior_class:
        return behavior_class()
    return None


def get_behaviors_for_fauna(fauna_properties: "FaunaProperties") -> list[BaseBehavior]:
    """Get all applicable behaviors for a fauna type."""
    behaviors = []

    # Add diet-based behaviors
    from daemons.engine.systems.fauna import Diet

    if fauna_properties.diet == Diet.HERBIVORE:
        behaviors.append(GrazingBehavior())
    elif fauna_properties.diet in [Diet.CARNIVORE, Diet.OMNIVORE]:
        behaviors.append(HuntingBehavior())

    # All prey can flee
    if fauna_properties.predator_tags:
        behaviors.append(FleeingBehavior())

    # Territorial behavior
    if fauna_properties.territorial:
        behaviors.append(TerritorialBehavior())

    # Pack behavior
    if fauna_properties.pack_size[1] > 1:
        behaviors.append(PackBehavior())

    # Sort by priority (highest first)
    behaviors.sort(key=lambda b: b.priority, reverse=True)

    return behaviors
