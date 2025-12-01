# backend/app/engine/behaviors/flee.py
"""Flee behavior scripts - control when NPCs retreat from combat."""
from .base import BehaviorContext, BehaviorResult, BehaviorScript, behavior


@behavior(
    name="cowardly",
    description="NPC flees when below 50% health",
    priority=60,  # Check flee before other combat responses
    defaults={
        "flees_at_health_percent": 50,
    },
)
class Cowardly(BehaviorScript):
    async def on_damaged(
        self, ctx: BehaviorContext, attacker_id: str, damage: int
    ) -> BehaviorResult:
        threshold = ctx.config.get("flees_at_health_percent", 50)
        if threshold <= 0:
            return BehaviorResult.nothing()

        health_percent = (ctx.npc.current_health / ctx.npc.max_health) * 100
        if health_percent > threshold:
            return BehaviorResult.nothing()

        # Try to flee
        exit_info = ctx.get_random_exit()
        if exit_info:
            direction, dest_room = exit_info
            return BehaviorResult(
                handled=True,
                flee=True,
                move_to=dest_room,
                move_direction=direction,
                message=f"{ctx.npc.name} panics and flees {direction}!",
            )

        return BehaviorResult.handled(
            message=f"{ctx.npc.name} looks around desperately for an escape!"
        )


@behavior(
    name="cautious",
    description="NPC flees when below 30% health",
    priority=60,
    defaults={
        "flees_at_health_percent": 30,
    },
)
class Cautious(BehaviorScript):
    async def on_damaged(
        self, ctx: BehaviorContext, attacker_id: str, damage: int
    ) -> BehaviorResult:
        threshold = ctx.config.get("flees_at_health_percent", 30)
        if threshold <= 0:
            return BehaviorResult.nothing()

        health_percent = (ctx.npc.current_health / ctx.npc.max_health) * 100
        if health_percent > threshold:
            return BehaviorResult.nothing()

        exit_info = ctx.get_random_exit()
        if exit_info:
            direction, dest_room = exit_info
            return BehaviorResult(
                handled=True,
                flee=True,
                move_to=dest_room,
                move_direction=direction,
                message=f"{ctx.npc.name} decides discretion is the better part of valor and retreats {direction}!",
            )

        return BehaviorResult.nothing()


@behavior(
    name="brave",
    description="NPC only flees when critically wounded (10% health)",
    priority=60,
    defaults={
        "flees_at_health_percent": 10,
    },
)
class Brave(BehaviorScript):
    async def on_damaged(
        self, ctx: BehaviorContext, attacker_id: str, damage: int
    ) -> BehaviorResult:
        threshold = ctx.config.get("flees_at_health_percent", 10)
        if threshold <= 0:
            return BehaviorResult.nothing()

        health_percent = (ctx.npc.current_health / ctx.npc.max_health) * 100
        if health_percent > threshold:
            return BehaviorResult.nothing()

        exit_info = ctx.get_random_exit()
        if exit_info:
            direction, dest_room = exit_info
            return BehaviorResult(
                handled=True,
                flee=True,
                move_to=dest_room,
                move_direction=direction,
                message=f"{ctx.npc.name} finally breaks and stumbles {direction}!",
            )

        return BehaviorResult.nothing()


@behavior(
    name="fearless",
    description="NPC never flees, fights to the death",
    priority=50,  # High priority to override other flee behaviors
    defaults={
        "flees_at_health_percent": 0,
    },
)
class Fearless(BehaviorScript):
    async def on_damaged(
        self, ctx: BehaviorContext, attacker_id: str, damage: int
    ) -> BehaviorResult:
        # Never flee - let other behaviors handle the damage response
        return BehaviorResult.nothing()
