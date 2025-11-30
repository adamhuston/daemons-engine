# backend/app/engine/behaviors/social.py
"""Social behavior scripts - control NPC interactions with others."""
from .base import BehaviorContext, BehaviorResult, BehaviorScript, behavior


@behavior(
    name="calls_for_help",
    description="NPC alerts nearby allies when attacked",
    priority=55,  # Run early when damaged
    defaults={
        "calls_for_help": True,
        "help_radius": 1,  # How many rooms away to alert
    },
)
class CallsForHelp(BehaviorScript):
    async def on_damaged(
        self, ctx: BehaviorContext, attacker_id: str, damage: int
    ) -> BehaviorResult:
        if not ctx.config.get("calls_for_help", True):
            return BehaviorResult.nothing()

        # Find allies in the same room
        allies = ctx.get_npcs_in_room()
        if allies:
            return BehaviorResult(
                handled=False,  # Don't prevent other responses
                call_for_help=True,
                message=f"{ctx.npc.name} cries out for help!",
            )

        return BehaviorResult.nothing()


@behavior(
    name="loner",
    description="NPC does not call for help when attacked",
    priority=50,  # Override calls_for_help
    defaults={
        "calls_for_help": False,
    },
)
class Loner(BehaviorScript):
    # Simply provides the config default - no special behavior needed
    pass
