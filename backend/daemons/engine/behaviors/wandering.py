# backend/app/engine/behaviors/wandering.py
"""Wandering behavior scripts - control how NPCs move around."""
import random

from .base import BehaviorContext, BehaviorResult, BehaviorScript, behavior
from ..world import with_article


def _format_npc_name(name: str) -> str:
    """Format NPC name with article if it's a common noun (lowercase)."""
    if name and name[0].islower():
        return with_article(name)
    return name


@behavior(
    name="wanders_rarely",
    description="NPC occasionally wanders to adjacent rooms (low frequency)",
    priority=100,
    defaults={
        "wander_enabled": True,
        "wander_chance": 0.05,
        "wander_interval_min": 60.0,
        "wander_interval_max": 180.0,
    },
)
class WandersRarely(BehaviorScript):
    async def on_wander_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        if not ctx.config.get("wander_enabled", True):
            return BehaviorResult.nothing()

        chance = ctx.config.get("wander_chance", 0.05)
        if random.random() > chance:
            return BehaviorResult.nothing()

        exit_info = ctx.get_random_exit()
        if not exit_info:
            return BehaviorResult.nothing()

        direction, dest_room = exit_info
        npc_name = _format_npc_name(ctx.npc.name)
        return BehaviorResult.move(
            direction=direction,
            room_id=dest_room,
            message=f"{npc_name} wanders {direction}.",
        )


@behavior(
    name="wanders_sometimes",
    description="NPC wanders to adjacent rooms at moderate frequency",
    priority=100,
    defaults={
        "wander_enabled": True,
        "wander_chance": 0.1,
        "wander_interval_min": 30.0,
        "wander_interval_max": 90.0,
    },
)
class WandersSometimes(BehaviorScript):
    async def on_wander_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        if not ctx.config.get("wander_enabled", True):
            return BehaviorResult.nothing()

        chance = ctx.config.get("wander_chance", 0.1)
        if random.random() > chance:
            return BehaviorResult.nothing()

        exit_info = ctx.get_random_exit()
        if not exit_info:
            return BehaviorResult.nothing()

        direction, dest_room = exit_info
        npc_name = _format_npc_name(ctx.npc.name)
        return BehaviorResult.move(
            direction=direction,
            room_id=dest_room,
            message=f"{npc_name} wanders {direction}.",
        )


@behavior(
    name="wanders_frequently",
    description="NPC wanders often, moving around a lot",
    priority=100,
    defaults={
        "wander_enabled": True,
        "wander_chance": 0.2,
        "wander_interval_min": 15.0,
        "wander_interval_max": 45.0,
    },
)
class WandersFrequently(BehaviorScript):
    async def on_wander_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        if not ctx.config.get("wander_enabled", True):
            return BehaviorResult.nothing()

        chance = ctx.config.get("wander_chance", 0.2)
        if random.random() > chance:
            return BehaviorResult.nothing()

        exit_info = ctx.get_random_exit()
        if not exit_info:
            return BehaviorResult.nothing()

        direction, dest_room = exit_info
        npc_name = _format_npc_name(ctx.npc.name)
        return BehaviorResult.move(
            direction=direction,
            room_id=dest_room,
            message=f"{npc_name} wanders {direction}.",
        )


@behavior(
    name="stationary",
    description="NPC never wanders, stays in place",
    priority=50,  # Higher priority to override other wander behaviors
    defaults={
        "wander_enabled": False,
    },
)
class Stationary(BehaviorScript):
    async def on_wander_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        # Explicitly handled - we stay put
        return BehaviorResult.handled()


@behavior(
    name="wanders_nowhere",
    description="Alias for stationary - NPC stays in place",
    priority=50,
    defaults={
        "wander_enabled": False,
    },
)
class WandersNowhere(BehaviorScript):
    async def on_wander_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        return BehaviorResult.handled()


@behavior(
    name="patrols",
    description="NPC follows a defined patrol route (from spawn configuration)",
    priority=150,  # Higher priority than random wandering
    defaults={
        "wander_enabled": True,
        "wander_interval_min": 30.0,
        "wander_interval_max": 60.0,
    },
)
class Patrols(BehaviorScript):
    async def on_wander_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        """Move to next waypoint in patrol route."""
        npc = ctx.npc
        
        # Check if NPC has a patrol route configured
        if not npc.patrol_route or len(npc.patrol_route) < 2:
            # No patrol route, let other behaviors handle it
            return BehaviorResult.nothing()
        
        # Get next waypoint using engine's patrol logic
        next_waypoint = ctx.engine._get_next_patrol_waypoint(npc)
        
        if not next_waypoint:
            # Patrol complete (for "once" mode)
            return BehaviorResult.handled()
        
        # Check if next waypoint is accessible from current room
        current_room = ctx.world.rooms.get(npc.room_id)
        if not current_room:
            return BehaviorResult.nothing()
        
        # Find which direction leads to the next waypoint
        for direction, dest_room_id in current_room.exits.items():
            if dest_room_id == next_waypoint:
                npc_name = _format_npc_name(npc.name)
                return BehaviorResult.move(
                    direction=direction,
                    room_id=next_waypoint,
                    message=f"{npc_name} patrols {direction}.",
                )
        
        # Next waypoint not directly accessible - need pathfinding
        # For now, stay put and let return-to-patrol handle it
        print(f"[PATROL] {npc.name}: Next waypoint {next_waypoint} not directly accessible from {npc.room_id}")
        return BehaviorResult.handled()


@behavior(
    name="patrols",
    description="NPC follows a defined patrol route through waypoints",
    priority=150,  # Higher priority than standard wander behaviors
    defaults={
        "wander_enabled": True,
        "wander_interval_min": 45.0,
        "wander_interval_max": 75.0,
        "patrol_interval": 60.0,
    },
)
class Patrols(BehaviorScript):
    """
    NPC patrol behavior - moves through defined waypoints.
    
    Requires patrol_route to be set on NpcInstance:
    - patrol_route: list of room IDs
    - patrol_index: current waypoint (auto-managed)
    - patrol_mode: "loop", "bounce", or "once"
    - home_room_id: spawn point for return after combat
    """
    
    async def on_wander_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        """Move to next waypoint in patrol route."""
        if not ctx.config.get("wander_enabled", True):
            return BehaviorResult.nothing()
        
        # Get patrol route from NPC instance
        patrol_route = getattr(ctx.npc, "patrol_route", None) or []
        
        if not patrol_route or len(patrol_route) < 2:
            # No valid patrol route, fall back to nothing
            return BehaviorResult.nothing()
        
        # Get next waypoint
        next_room_id = self._get_next_patrol_waypoint(ctx)
        
        if not next_room_id:
            return BehaviorResult.nothing()
        
        # If already at target waypoint, just advance index
        if ctx.npc.room_id == next_room_id:
            return BehaviorResult.handled()
        
        # Find direction to next waypoint
        direction = self._find_direction_to_room(ctx, next_room_id)
        
        if not direction:
            # Can't find path, skip this waypoint
            return BehaviorResult.nothing()
        
        # Move to next room
        npc_name = _format_npc_name(ctx.npc.name)
        return BehaviorResult.move(
            direction=direction,
            room_id=next_room_id,
            message=f"{npc_name} continues patrol {direction}.",
        )
    
    def _get_next_patrol_waypoint(self, ctx: BehaviorContext) -> str | None:
        """
        Calculate next room in patrol route based on mode.
        
        Returns:
            Next room ID, or None if patrol complete
        """
        patrol_route = ctx.npc.patrol_route
        current_index = getattr(ctx.npc, "patrol_index", 0)
        patrol_mode = getattr(ctx.npc, "patrol_mode", "loop")
        
        if not patrol_route:
            return None
        
        route_length = len(patrol_route)
        
        if patrol_mode == "loop":
            # Circular: 0 → 1 → 2 → ... → n → 0
            next_index = (current_index + 1) % route_length
            
        elif patrol_mode == "bounce":
            # Back and forth: 0 → 1 → 2 → 1 → 0 → 1 → ...
            direction = getattr(ctx.npc, "_patrol_direction", 1)
            
            next_index = current_index + direction
            
            # Check boundaries
            if next_index >= route_length:
                next_index = route_length - 2
                direction = -1
            elif next_index < 0:
                next_index = 1
                direction = 1
            
            # Store direction for next tick
            ctx.npc._patrol_direction = direction
            
        elif patrol_mode == "once":
            # One-time: 0 → 1 → 2 → ... → n, then stop
            next_index = current_index + 1
            if next_index >= route_length:
                # Patrol complete, stay at last waypoint
                return None
        else:
            # Unknown mode, default to loop
            next_index = (current_index + 1) % route_length
        
        # Update patrol index
        ctx.npc.patrol_index = next_index
        
        return patrol_route[next_index]
    
    def _find_direction_to_room(self, ctx: BehaviorContext, target_room_id: str) -> str | None:
        """
        Find the exit direction to reach target room.
        
        Args:
            ctx: Behavior context
            target_room_id: Target room ID
            
        Returns:
            Direction name, or None if not adjacent
        """
        # Check if target is directly adjacent
        for direction, exit_room_id in ctx.current_room_exits.items():
            if exit_room_id == target_room_id:
                return direction
        
        # Target not adjacent - this shouldn't happen with proper patrol routes
        # Log warning and return None
        return None
