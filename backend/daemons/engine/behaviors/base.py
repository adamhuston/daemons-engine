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

Phase 14.3 additions:
- on_combat_action() hook for NPC ability decisions
- on_low_health() hook for defensive ability triggers
- BehaviorContext helpers for ability system integration
- BehaviorResult.cast_ability field for ability execution
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

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

    npc: WorldNpc
    world: World
    template: NpcTemplate
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

    # ========== Phase 14.3: Ability System Integration ==========

    def has_abilities(self) -> bool:
        """Check if the NPC has a character sheet with abilities."""
        return self.npc.has_character_sheet()

    def get_learned_abilities(self) -> set[str]:
        """Get the set of ability IDs this NPC has learned."""
        return self.npc.get_learned_abilities()

    def get_ability_loadout(self) -> list[str]:
        """Get the NPC's equipped ability loadout (ordered list of ability IDs)."""
        loadout = self.npc.get_ability_loadout()
        return [slot.ability_id for slot in loadout if slot.ability_id]

    def get_available_abilities(
        self, ability_executor: Any = None
    ) -> list[dict[str, Any]]:
        """
        Get abilities that are currently usable (not on cooldown, enough resources).

        Args:
            ability_executor: Optional AbilityExecutor instance for cooldown checking.
                            If not provided, returns all loadout abilities without
                            cooldown/resource validation.

        Returns:
            List of dicts with ability info: [{"ability_id": str, "ready": bool}, ...]
        """
        if not self.has_abilities():
            return []

        loadout = self.get_ability_loadout()
        if not loadout:
            return []

        available = []
        for ability_id in loadout:
            info = {"ability_id": ability_id, "ready": True}

            # Check cooldown if executor provided
            if ability_executor:
                cooldown_remaining = ability_executor.get_ability_cooldown(
                    self.npc.id, ability_id
                )
                if cooldown_remaining > 0:
                    info["ready"] = False
                    info["cooldown_remaining"] = cooldown_remaining

            # Check resource costs
            # Note: Full resource validation would require ClassSystem access
            # For now, we just mark as ready if no cooldown

            available.append(info)

        return available

    def get_ready_abilities(self, ability_executor: Any = None) -> list[str]:
        """
        Get list of ability IDs that are ready to use (not on cooldown).

        Convenience method that filters get_available_abilities() for ready abilities.
        """
        available = self.get_available_abilities(ability_executor)
        return [a["ability_id"] for a in available if a.get("ready", False)]

    def get_combat_target(self) -> str | None:
        """Get the NPC's current combat target ID, or None if not in combat."""
        if self.npc.combat.is_in_combat():
            return self.npc.combat.target_id
        return None

    def get_health_percent(self) -> float:
        """Get the NPC's current health as a percentage (0.0 to 100.0)."""
        if self.npc.max_health <= 0:
            return 0.0
        return (self.npc.current_health / self.npc.max_health) * 100.0

    def get_resource_percent(self, resource_id: str) -> float | None:
        """
        Get an NPC resource pool as a percentage (0.0 to 100.0).

        Args:
            resource_id: The resource ID (e.g., "mana", "rage", "energy")

        Returns:
            Percentage of resource remaining, or None if resource doesn't exist.
        """
        pool = self.npc.get_resource_pool(resource_id)
        if not pool or pool.max <= 0:
            return None
        return (pool.current / pool.max) * 100.0


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

    # Phase 14.3: Ability system integration
    cast_ability: str | None = None  # Ability ID to cast
    ability_target: str | None = (
        None  # Target entity ID for ability (defaults to combat target)
    )

    custom_data: dict[str, Any] = field(default_factory=dict)  # Extensible

    @classmethod
    def nothing(cls) -> BehaviorResult:
        """Return a result indicating no action was taken."""
        return cls(handled=False)

    @classmethod
    def was_handled(cls, message: str | None = None) -> BehaviorResult:
        """Return a result indicating the event was handled."""
        return cls(handled=True, message=message)

    @classmethod
    def move(
        cls, direction: str, room_id: str, message: str | None = None
    ) -> BehaviorResult:
        """Return a result indicating the NPC should move."""
        return cls(
            handled=True, move_to=room_id, move_direction=direction, message=message
        )

    @classmethod
    def use_ability(
        cls,
        ability_id: str,
        target_id: str | None = None,
        message: str | None = None,
    ) -> BehaviorResult:
        """
        Return a result indicating the NPC should cast an ability.

        Phase 14.3: New factory method for ability casting.

        Args:
            ability_id: The ability to cast
            target_id: Optional target entity ID (defaults to combat target)
            message: Optional message to broadcast
        """
        return cls(
            handled=True,
            cast_ability=ability_id,
            ability_target=target_id,
            message=message,
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

    @abstractmethod
    def get_behavior_id(self) -> str:
        """Return the unique identifier for this behavior."""
        ...

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

    # --- Phase 14.3: Ability Combat Hooks ---

    async def on_combat_action(
        self, ctx: BehaviorContext, target_id: str
    ) -> BehaviorResult:
        """
        Called during combat to decide ability usage.

        Phase 14.3: New hook for NPC ability AI. Called after on_combat_tick
        if NPC has a character_sheet with abilities.

        Implement this hook to make NPCs use abilities intelligently:
        - Check available abilities with ctx.get_ready_abilities()
        - Choose based on situation (health, mana, target type)
        - Return BehaviorResult.use_ability(ability_id, target_id)

        Args:
            ctx: BehaviorContext with ability helpers
            target_id: Current combat target entity ID

        Returns:
            BehaviorResult with cast_ability set to use an ability
        """
        return BehaviorResult.nothing()

    async def on_low_health(
        self, ctx: BehaviorContext, health_percent: float
    ) -> BehaviorResult:
        """
        Called when NPC health drops below a threshold (default 30%).

        Phase 14.3: New hook for defensive ability triggers.

        Use this for:
        - Casting healing abilities
        - Activating defensive buffs
        - Emergency escape abilities

        Args:
            ctx: BehaviorContext with ability helpers
            health_percent: Current health as percentage (0.0-100.0)

        Returns:
            BehaviorResult with cast_ability for defensive ability
        """
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

        # Add get_behavior_id implementation if not already defined
        if "get_behavior_id" not in cls.__dict__:
            cls.get_behavior_id = lambda self: name  # type: ignore[method-assign]

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
