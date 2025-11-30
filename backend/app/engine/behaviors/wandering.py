# backend/app/engine/behaviors/wandering.py
"""Wandering behavior scripts - control how NPCs move around."""
import random

from .base import BehaviorContext, BehaviorResult, BehaviorScript, behavior


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
        return BehaviorResult.move(
            direction=direction,
            room_id=dest_room,
            message=f"{ctx.npc.name} wanders {direction}.",
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
        return BehaviorResult.move(
            direction=direction,
            room_id=dest_room,
            message=f"{ctx.npc.name} wanders {direction}.",
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
        return BehaviorResult.move(
            direction=direction,
            room_id=dest_room,
            message=f"{ctx.npc.name} wanders {direction}.",
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
