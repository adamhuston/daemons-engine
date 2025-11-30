# backend/app/engine/behaviors/example_mod.py
"""
Example mod behavior - demonstrates how to create new behaviors.

To create your own behavior mod:
1. Create a new .py file in the behaviors/ directory
2. Import the required base classes
3. Use the @behavior decorator to register your behavior
4. Implement any hooks you need

This file can be deleted - it's just an example!
"""
import random

from .base import BehaviorContext, BehaviorResult, BehaviorScript, behavior


@behavior(
    name="grumpy",
    description="NPC occasionally grumbles and complains",
    priority=110,  # Lower priority (runs after other idle behaviors)
    defaults={
        "grumble_chance": 0.2,
    },
)
class Grumpy(BehaviorScript):
    """A grumpy NPC that complains a lot."""

    GRUMBLES = [
        "*grumbles under breath*",
        "*mutters about the weather*",
        "*sighs heavily*",
        '"Everything was better in the old days..."',
        "*kicks at a pebble irritably*",
    ]

    async def on_idle_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        chance = ctx.config.get("grumble_chance", 0.2)
        if random.random() > chance:
            return BehaviorResult.nothing()

        grumble = random.choice(self.GRUMBLES)
        return BehaviorResult.handled(message=f"{ctx.npc.name} {grumble}")

    async def on_player_enter(
        self, ctx: BehaviorContext, player_id: str
    ) -> BehaviorResult:
        # 50% chance to grumble when someone enters
        if random.random() > 0.5:
            return BehaviorResult.nothing()

        player = ctx.world.players.get(player_id)
        player_name = player.name if player else "someone"

        return BehaviorResult.handled(
            message=f"{ctx.npc.name} glares at {player_name} suspiciously."
        )


@behavior(
    name="curious",
    description="NPC is curious about players and follows them",
    priority=95,
    defaults={
        "follow_chance": 0.3,
    },
)
class Curious(BehaviorScript):
    """A curious NPC that might follow players around."""

    async def on_player_leave(
        self, ctx: BehaviorContext, player_id: str
    ) -> BehaviorResult:
        chance = ctx.config.get("follow_chance", 0.3)
        if random.random() > chance:
            return BehaviorResult.nothing()

        player = ctx.world.players.get(player_id)
        if not player:
            return BehaviorResult.nothing()

        # Find which direction the player went
        player_room = ctx.world.rooms.get(player.room_id)
        current_room = ctx.get_room()

        if not current_room or not player_room:
            return BehaviorResult.nothing()

        # Check if player's new room is adjacent
        for direction, dest_id in current_room.exits.items():
            if dest_id == player.room_id:
                return BehaviorResult.move(
                    direction=direction,
                    room_id=dest_id,
                    message=f"{ctx.npc.name} curiously follows {player.name} {direction}.",
                )

        return BehaviorResult.nothing()
