# backend/app/engine/behaviors/base.py
"""
Base classes and decorators for the behavior script system.

Behavior scripts are modular, composable AI routines that can be dropped into
the behaviors/ directory and automatically loaded at runtime.

Each behavior script defines:
1. Metadata (name, description, config schema)
2. Hook functions that get called at specific points in the game loop
3. Default configuration values

Example behavior script:

    from .base import behavior, BehaviorContext

    @behavior(
        name="wanders_sometimes",
        description="NPC occasionally moves to adjacent rooms",
        defaults={"wander_chance": 0.1, "wander_interval": 60.0}
    )
    class WandersSometimes:
        async def on_wander_tick(self, ctx: BehaviorContext) -> bool:
            '''Called when NPC's wander timer fires. Return True if handled.'''
            if random.random() < ctx.config["wander_chance"]:
                await ctx.move_random()
                return True
            return False
"""
from __future__ import annotations

import random
from abc import ABC
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ..world import NpcTemplate, World, WorldNpc


# =============================================================================
# Behavior Context - passed to all behavior hooks
# =============================================================================


@dataclass
class BehaviorContext:
    """
    Context object passed to behavior hooks.

    Provides access to the NPC, world state, and helper methods for common actions.
    """

    npc: "WorldNpc"
    world: "World"
    template: "NpcTemplate"
    config: dict[str, Any]  # Resolved behavior config for this NPC

    # Callback to broadcast messages to room
    broadcast: Callable[[str, str], None] | None = None  # (room_id, message)

    def get_room(self):
        """Get the NPC's current room."""
        return self.world.rooms.get(self.npc.room_id)

    def get_exits(self) -> dict[str, str]:
        """Get available exits from current room."""
        room = self.get_room()
        return room.exits if room else {}

    def get_random_exit(self) -> tuple[str, str] | None:
        """Get a random exit direction and destination room ID."""
        exits = self.get_exits()
        if not exits:
            return None
        direction = random.choice(list(exits.keys()))
        return (direction, exits[direction])

    def get_entities_in_room(self) -> list[str]:
        """Get all entity IDs in the NPC's current room."""
        room = self.get_room()
        return list(room.entities) if room else []

    def get_players_in_room(self) -> list[str]:
        """Get all player IDs in the NPC's current room."""
        room = self.get_room()
        if not room:
            return []
        return [eid for eid in room.entities if eid in self.world.players]

    def get_npcs_in_room(self) -> list[str]:
        """Get all NPC IDs in the NPC's current room (excluding self)."""
        room = self.get_room()
        if not room:
            return []
        return [
            eid
            for eid in room.entities
            if eid in self.world.npcs and eid != self.npc.id
        ]


# =============================================================================
# Behavior Result - returned from behavior hooks
# =============================================================================


@dataclass
class BehaviorResult:
    """
    Result from a behavior hook execution.

    Behaviors return this to indicate what happened and what actions to take.
    """

    handled: bool = False  # True if this behavior handled the event
    message: str | None = None  # Message to broadcast to room
    move_to: str | None = None  # Room ID to move NPC to
    move_direction: str | None = None  # Direction moved (for messaging)
    attack_target: str | None = None  # Entity ID to attack
    flee: bool = False  # NPC should flee
    call_for_help: bool = False  # Alert nearby allies
    custom_data: dict[str, Any] = field(default_factory=dict)  # Extensible

    @classmethod
    def nothing(cls) -> "BehaviorResult":
        """Return a result indicating no action was taken."""
        return cls(handled=False)

    @classmethod
    def was_handled(cls, message: str | None = None) -> "BehaviorResult":
        """Return a result indicating the event was handled."""
        return cls(handled=True, message=message)

    @classmethod
    def move(
        cls, direction: str, room_id: str, message: str | None = None
    ) -> "BehaviorResult":
        """Return a result indicating the NPC should move."""
        return cls(
            handled=True, move_to=room_id, move_direction=direction, message=message
        )


# =============================================================================
# Behavior Script Base Class
# =============================================================================


class BehaviorScript(ABC):
    """
    Base class for all behavior scripts.

    Subclass this and implement the hooks you need. All hooks are optional
    except those marked as abstract (none currently).

    Hooks are called in priority order (lower = earlier). If a hook returns
    BehaviorResult with handled=True, subsequent behaviors may be skipped
    depending on the hook type.
    """

    # Metadata - override in subclass or use @behavior decorator
    name: str = "unnamed"
    description: str = ""
    priority: int = 100  # Lower = runs first
    defaults: dict[str, Any] = {}

    # --- Lifecycle Hooks ---

    async def on_spawn(self, ctx: BehaviorContext) -> BehaviorResult:
        """Called when NPC spawns into the world."""
        return BehaviorResult.nothing()

    async def on_death(self, ctx: BehaviorContext) -> BehaviorResult:
        """Called when NPC dies."""
        return BehaviorResult.nothing()

    # --- Tick Hooks (called on timer intervals) ---

    async def on_idle_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        """
        Called on idle timer tick. Use for ambient messages, emotes, etc.
        Return handled=True to suppress other idle behaviors.
        """
        return BehaviorResult.nothing()

    async def on_wander_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        """
        Called on wander timer tick. Use for movement decisions.
        Return handled=True with move_to to actually move.
        """
        return BehaviorResult.nothing()

    # --- Combat Hooks ---

    async def on_combat_start(
        self, ctx: BehaviorContext, attacker_id: str
    ) -> BehaviorResult:
        """Called when combat begins with this NPC."""
        return BehaviorResult.nothing()

    async def on_damaged(
        self, ctx: BehaviorContext, attacker_id: str, damage: int
    ) -> BehaviorResult:
        """
        Called when NPC takes damage. Use for flee checks, call for help, etc.
        """
        return BehaviorResult.nothing()

    async def on_combat_tick(
        self, ctx: BehaviorContext, target_id: str
    ) -> BehaviorResult:
        """Called during combat to decide attacks."""
        return BehaviorResult.nothing()

    # --- Awareness Hooks ---

    async def on_player_enter(
        self, ctx: BehaviorContext, player_id: str
    ) -> BehaviorResult:
        """Called when a player enters the NPC's room."""
        return BehaviorResult.nothing()

    async def on_player_leave(
        self, ctx: BehaviorContext, player_id: str
    ) -> BehaviorResult:
        """Called when a player leaves the NPC's room."""
        return BehaviorResult.nothing()

    async def on_npc_enter(self, ctx: BehaviorContext, npc_id: str) -> BehaviorResult:
        """Called when another NPC enters the room."""
        return BehaviorResult.nothing()

    # --- Interaction Hooks ---

    async def on_talked_to(
        self, ctx: BehaviorContext, player_id: str, message: str
    ) -> BehaviorResult:
        """Called when a player talks to or interacts with this NPC."""
        return BehaviorResult.nothing()

    async def on_given_item(
        self, ctx: BehaviorContext, player_id: str, item_id: str
    ) -> BehaviorResult:
        """Called when a player gives an item to this NPC."""
        return BehaviorResult.nothing()


# =============================================================================
# Behavior Decorator - for registering behavior scripts
# =============================================================================

# Global registry of all loaded behavior scripts
_BEHAVIOR_REGISTRY: dict[str, type[BehaviorScript]] = {}


def behavior(
    name: str,
    description: str = "",
    priority: int = 100,
    defaults: dict[str, Any] | None = None,
):
    """
    Decorator to register a behavior script class.

    Usage:
        @behavior(
            name="wanders_sometimes",
            description="NPC occasionally moves to adjacent rooms",
            defaults={"wander_chance": 0.1}
        )
        class WandersSometimes(BehaviorScript):
            async def on_wander_tick(self, ctx: BehaviorContext) -> BehaviorResult:
                ...
    """

    def decorator(cls: type[BehaviorScript]) -> type[BehaviorScript]:
        cls.name = name
        cls.description = description
        cls.priority = priority
        cls.defaults = defaults or {}

        # Register the behavior
        if name in _BEHAVIOR_REGISTRY:
            print(f"[Behavior] Warning: Overwriting behavior '{name}'")
        _BEHAVIOR_REGISTRY[name] = cls

        return cls

    return decorator


def get_behavior(name: str) -> type[BehaviorScript] | None:
    """Get a registered behavior class by name."""
    return _BEHAVIOR_REGISTRY.get(name)


def get_all_behaviors() -> dict[str, type[BehaviorScript]]:
    """Get all registered behavior classes."""
    return _BEHAVIOR_REGISTRY.copy()


def get_behavior_instance(name: str) -> BehaviorScript | None:
    """Get a new instance of a registered behavior."""
    cls = _BEHAVIOR_REGISTRY.get(name)
    return cls() if cls else None


def get_behavior_defaults(behavior_names: list[str]) -> dict[str, Any]:
    """
    Merge default configs from multiple behaviors.

    Later behaviors override earlier ones for conflicting keys.
    """
    result: dict[str, Any] = {}
    for name in behavior_names:
        cls = _BEHAVIOR_REGISTRY.get(name)
        if cls:
            result.update(cls.defaults)
    return result
