# backend/app/engine/behaviors/combat.py
"""Combat behavior scripts - control aggression and attack patterns."""
from .base import BehaviorContext, BehaviorResult, BehaviorScript, behavior


@behavior(
    name="aggressive",
    description="NPC attacks players on sight",
    priority=80,
    defaults={
        "aggro_on_sight": True,
        "attacks_first": True,
    },
)
class Aggressive(BehaviorScript):
    async def on_player_enter(
        self, ctx: BehaviorContext, player_id: str
    ) -> BehaviorResult:
        if not ctx.config.get("aggro_on_sight", True):
            return BehaviorResult.nothing()

        player = ctx.world.players.get(player_id)
        player_name = player.name if player else "someone"

        return BehaviorResult(
            handled=True,
            attack_target=player_id,
            message=f"{ctx.npc.name} snarls and attacks {player_name}!",
        )


@behavior(
    name="defensive",
    description="NPC only attacks if attacked first",
    priority=90,
    defaults={
        "aggro_on_sight": False,
        "attacks_if_attacked": True,
    },
)
class Defensive(BehaviorScript):
    async def on_damaged(
        self, ctx: BehaviorContext, attacker_id: str, damage: int
    ) -> BehaviorResult:
        if not ctx.config.get("attacks_if_attacked", True):
            return BehaviorResult.nothing()

        return BehaviorResult(
            handled=True,
            attack_target=attacker_id,
            message=f"{ctx.npc.name} retaliates!",
        )


@behavior(
    name="pacifist",
    description="NPC never attacks, even if attacked",
    priority=70,  # Higher priority to override other combat behaviors
    defaults={
        "aggro_on_sight": False,
        "attacks_if_attacked": False,
    },
)
class Pacifist(BehaviorScript):
    async def on_player_enter(
        self, ctx: BehaviorContext, player_id: str
    ) -> BehaviorResult:
        # Override aggressive behavior - do nothing
        return BehaviorResult.handled()

    async def on_damaged(
        self, ctx: BehaviorContext, attacker_id: str, damage: int
    ) -> BehaviorResult:
        # Don't retaliate
        return BehaviorResult.handled(
            message=f"{ctx.npc.name} cowers but does not fight back."
        )


@behavior(
    name="peaceful",
    description="NPC is peaceful and won't attack unless provoked (alias for non-aggressive)",
    priority=70,
    defaults={
        "aggro_on_sight": False,
        "attacks_if_attacked": False,
    },
)
class Peaceful(BehaviorScript):
    """Peaceful creatures don't initiate combat."""
    async def on_player_enter(
        self, ctx: BehaviorContext, player_id: str
    ) -> BehaviorResult:
        # Don't aggro on sight
        return BehaviorResult.was_handled()

    async def on_damaged(
        self, ctx: BehaviorContext, attacker_id: str, damage: int
    ) -> BehaviorResult:
        # Peaceful creatures don't fight back
        return BehaviorResult.was_handled()
