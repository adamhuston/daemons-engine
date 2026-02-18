# backend/app/engine/behaviors/social.py
"""Social behavior scripts - control NPC interactions with others."""
from .base import BehaviorContext, BehaviorResult, BehaviorScript, behavior


@behavior(
    name="social",
    description="NPC alerts nearby allies when attacked (alias for calls_for_help)",
    priority=55,  # Run early when damaged
    defaults={
        "calls_for_help": True,
        "help_radius": 1,  # How many rooms away to alert
    },
)
class Social(BehaviorScript):
    async def on_damaged(
        self, ctx: BehaviorContext, attacker_id: str, damage: int
    ) -> BehaviorResult:
        if not ctx.config.get("calls_for_help", True):
            return BehaviorResult.nothing()

        # Find allies in the same room (faction-aware, includes NPCs and players)
        npc_faction = ctx.template.faction_id
        allies = []
        
        # Check NPCs
        for npc_id in ctx.get_npcs_in_room():
            other_npc = ctx.world.npcs.get(npc_id)
            if not other_npc:
                continue
            
            other_template = ctx.world.npc_templates.get(other_npc.template_id)
            if not other_template:
                continue
            
            # Only call same-faction NPCs for help
            # If this NPC has no faction, call everyone (backward compatibility)
            if npc_faction is None or other_template.faction_id == npc_faction:
                allies.append(npc_id)
        
        # Check players
        for player_id in ctx.get_players_in_room():
            player = ctx.world.players.get(player_id)
            if not player:
                continue
            
            # Only call same-faction players for help
            # If this NPC has no faction, call everyone (backward compatibility)
            if npc_faction is None or player.faction_id == npc_faction:
                allies.append(player_id)
        
        if allies:
            return BehaviorResult(
                handled=False,  # Don't prevent other responses
                call_for_help=True,
                message=f"{ctx.npc.name} cries out for help!",
            )

        return BehaviorResult.nothing()


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

        # Find allies in the same room (faction-aware, includes NPCs and players)
        npc_faction = ctx.template.faction_id
        allies = []
        
        # Check NPCs
        for npc_id in ctx.get_npcs_in_room():
            other_npc = ctx.world.npcs.get(npc_id)
            if not other_npc:
                continue
            
            other_template = ctx.world.npc_templates.get(other_npc.template_id)
            if not other_template:
                continue
            
            # Only call same-faction NPCs for help
            # If this NPC has no faction, call everyone (backward compatibility)
            if npc_faction is None or other_template.faction_id == npc_faction:
                allies.append(npc_id)
        
        # Check players
        for player_id in ctx.get_players_in_room():
            player = ctx.world.players.get(player_id)
            if not player:
                continue
            
            # Only call same-faction players for help
            # If this NPC has no faction, call everyone (backward compatibility)
            if npc_faction is None or player.faction_id == npc_faction:
                allies.append(player_id)
        
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
