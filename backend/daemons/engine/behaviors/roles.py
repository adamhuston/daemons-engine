# backend/app/engine/behaviors/roles.py
"""Role behavior scripts - composite behaviors for specific NPC archetypes."""
import random

from .base import BehaviorContext, BehaviorResult, BehaviorScript, behavior


@behavior(
    name="merchant",
    description="NPC acts as a merchant - flees quickly, calls guards",
    priority=90,
    defaults={
        "is_merchant": True,
        "flees_at_health_percent": 75,
        "calls_for_help": True,
        "wander_enabled": True,
        "wander_chance": 0.05,
        "wander_interval_min": 60.0,
        "wander_interval_max": 180.0,
    },
)
class Merchant(BehaviorScript):
    async def on_talked_to(
        self, ctx: BehaviorContext, player_id: str, message: str
    ) -> BehaviorResult:
        if not ctx.config.get("is_merchant", True):
            return BehaviorResult.nothing()

        player = ctx.world.players.get(player_id)
        player_name = player.name if player else "traveler"

        return BehaviorResult.handled(
            message=f'{ctx.npc.name} says, "Welcome, {player_name}! Care to see my wares?"'
        )

    async def on_damaged(
        self, ctx: BehaviorContext, attacker_id: str, damage: int
    ) -> BehaviorResult:
        # Merchants panic easily
        threshold = ctx.config.get("flees_at_health_percent", 75)
        health_percent = (ctx.npc.current_health / ctx.npc.max_health) * 100

        if health_percent <= threshold:
            exit_info = ctx.get_random_exit()
            if exit_info:
                direction, dest_room = exit_info
                return BehaviorResult(
                    handled=True,
                    flee=True,
                    call_for_help=True,
                    move_to=dest_room,
                    move_direction=direction,
                    message=f'{ctx.npc.name} shrieks, "Guards! GUARDS!" and flees {direction}!',
                )

        return BehaviorResult(
            handled=False,
            call_for_help=True,
            message=f'{ctx.npc.name} cries out, "Help! I\'m being robbed!"',
        )


@behavior(
    name="guard",
    description="NPC guards an area - attacks hostiles, doesn't wander",
    priority=85,
    defaults={
        "wander_enabled": False,
        "calls_for_help": True,
        "aggro_on_sight": False,
        "attacks_hostiles_on_sight": True,
    },
)
class Guard(BehaviorScript):
    async def on_npc_enter(self, ctx: BehaviorContext, npc_id: str) -> BehaviorResult:
        if not ctx.config.get("attacks_hostiles_on_sight", True):
            return BehaviorResult.nothing()

        # Check if the entering NPC is hostile
        other_npc = ctx.world.npcs.get(npc_id)
        if not other_npc:
            return BehaviorResult.nothing()

        other_template = ctx.world.npc_templates.get(other_npc.template_id)
        if not other_template or other_template.npc_type != "hostile":
            return BehaviorResult.nothing()

        return BehaviorResult(
            handled=True,
            attack_target=npc_id,
            message=f'{ctx.npc.name} shouts, "Halt, creature!" and moves to intercept {other_npc.name}!',
        )

    async def on_wander_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        # Guards don't wander
        return BehaviorResult.handled()


@behavior(
    name="patrol",
    description="NPC patrols an area, wandering frequently and returning to spawn",
    priority=95,
    defaults={
        "wander_enabled": True,
        "wander_chance": 0.3,
        "wander_interval_min": 20.0,
        "wander_interval_max": 40.0,
        "returns_to_spawn": True,
    },
)
class Patrol(BehaviorScript):
    async def on_wander_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        if not ctx.config.get("wander_enabled", True):
            return BehaviorResult.nothing()

        chance = ctx.config.get("wander_chance", 0.3)
        if ctx.config.get("returns_to_spawn", True):
            # Bias toward spawn room if far away
            if ctx.npc.room_id != ctx.npc.spawn_room_id:
                chance *= 1.5  # More likely to move when away from spawn

        if random.random() > chance:
            return BehaviorResult.nothing()

        exit_info = ctx.get_random_exit()
        if not exit_info:
            return BehaviorResult.nothing()

        direction, dest_room = exit_info
        return BehaviorResult.move(
            direction=direction,
            room_id=dest_room,
            message=f"{ctx.npc.name} continues their patrol {direction}.",
        )
