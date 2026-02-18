# backend/app/engine/behaviors/support.py
"""
Phase 3: Support behavior scripts for NPCs with healing/buff abilities.

These behaviors make NPCs intelligently support their faction allies:
- Prioritize healing same-faction NPCs
- Target faction members with buffs
- Coordinate with faction in combat
"""
import random

from .base import BehaviorContext, BehaviorResult, BehaviorScript, behavior


@behavior(
    name="healer",
    description="NPC heals faction allies when they're injured",
    priority=80,  # Run before generic combat behaviors
    defaults={
        "heal_threshold": 70,  # Heal allies below this HP percent
        "self_heal_threshold": 50,  # Heal self below this HP percent
        "healing_abilities": [],  # Ability IDs for healing
        "prefer_lowest_hp": True,  # Target lowest HP ally
    },
)
class Healer(BehaviorScript):
    """
    Intelligent healer AI for NPC clerics, shamans, priests, etc.

    Behavior:
    1. Heals self if critically low
    2. Heals same-faction allies below threshold
    3. Prioritizes lowest HP allies
    """

    def _find_faction_allies(self, ctx: BehaviorContext) -> list[tuple[str, float]]:
        """
        Find same-faction entities (NPCs and players) in room and their HP percentages.
        
        Returns:
            List of (entity_id, hp_percent) tuples for faction allies
        """
        npc_faction = ctx.template.faction_id
        if not npc_faction:
            return []
        
        allies = []
        
        # Check NPCs in room
        for npc_id in ctx.get_npcs_in_room():
            other_npc = ctx.world.npcs.get(npc_id)
            if not other_npc:
                continue
            
            other_template = ctx.world.npc_templates.get(other_npc.template_id)
            if not other_template:
                continue
            
            # Only consider same-faction NPCs
            if other_template.faction_id == npc_faction:
                hp_percent = (other_npc.current_health / other_npc.max_health) * 100
                allies.append((npc_id, hp_percent))
        
        # Check players in room
        for player_id in ctx.get_players_in_room():
            player = ctx.world.players.get(player_id)
            if not player:
                continue
            
            # Only consider same-faction players
            if player.faction_id == npc_faction:
                hp_percent = (player.current_health / player.max_health) * 100
                allies.append((player_id, hp_percent))
        
        return allies

    async def on_combat_action(
        self, ctx: BehaviorContext, target_id: str
    ) -> BehaviorResult:
        """
        Choose heal target based on faction allies' health status.
        """
        # Check if NPC has abilities
        if not ctx.has_abilities():
            return BehaviorResult.nothing()

        # Get healing abilities
        healing_abilities = ctx.config.get("healing_abilities", [])
        if not healing_abilities:
            return BehaviorResult.nothing()

        ready_abilities = ctx.get_ready_abilities()
        healing_ready = [a for a in ready_abilities if a in healing_abilities]
        if not healing_ready:
            return BehaviorResult.nothing()

        # Check self health first
        self_health_pct = ctx.get_health_percent()
        self_heal_threshold = ctx.config.get("self_heal_threshold", 50)
        
        if self_health_pct < self_heal_threshold:
            ability_id = random.choice(healing_ready)
            return BehaviorResult.use_ability(
                ability_id=ability_id,
                target_id=ctx.npc.id,  # Self-heal
                message=f"{ctx.npc.name} channels healing energy!",
            )

        # Find faction allies who need healing
        heal_threshold = ctx.config.get("heal_threshold", 70)
        allies = self._find_faction_allies(ctx)
        
        # Filter to only allies below threshold
        injured_allies = [(npc_id, hp) for npc_id, hp in allies if hp < heal_threshold]
        
        if not injured_allies:
            return BehaviorResult.nothing()

        # Choose target (lowest HP if configured)
        if ctx.config.get("prefer_lowest_hp", True):
            target_id = min(injured_allies, key=lambda x: x[1])[0]
        else:
            target_id = random.choice(injured_allies)[0]

        # Get target name for message
        target = ctx.world.npcs.get(target_id) or ctx.world.players.get(target_id)
        target_name = target.name if target else "ally"

        ability_id = random.choice(healing_ready)
        return BehaviorResult.use_ability(
            ability_id=ability_id,
            target_id=target_id,
            message=f"{ctx.npc.name} channels healing energy to {target_name}!",
        )


@behavior(
    name="buffer",
    description="NPC buffs faction allies in combat",
    priority=75,
    defaults={
        "buff_abilities": [],  # Ability IDs for buffs
        "buff_cooldown": 30.0,  # Don't spam buffs
        "prefer_damaged_allies": True,  # Buff allies in combat
    },
)
class Buffer(BehaviorScript):
    """
    Intelligent buffer AI for NPCs with buff abilities.

    Behavior:
    1. Buffs faction allies who are in combat
    2. Prioritizes injured allies
    3. Avoids wasting buffs on full-health/inactive allies
    """

    def _find_faction_allies(self, ctx: BehaviorContext) -> list[tuple[str, float, bool]]:
        """
        Find same-faction entities (NPCs and players) in room with health and combat status.
        
        Returns:
            List of (entity_id, hp_percent, in_combat) tuples
        """
        npc_faction = ctx.template.faction_id
        if not npc_faction:
            return []
        
        allies = []
        
        # Check NPCs in room
        for npc_id in ctx.get_npcs_in_room():
            other_npc = ctx.world.npcs.get(npc_id)
            if not other_npc:
                continue
            
            other_template = ctx.world.npc_templates.get(other_npc.template_id)
            if not other_template:
                continue
            
            # Only consider same-faction NPCs
            if other_template.faction_id == npc_faction:
                hp_percent = (other_npc.current_health / other_npc.max_health) * 100
                in_combat = bool(other_npc.target_id)
                allies.append((npc_id, hp_percent, in_combat))
        
        # Check players in room
        for player_id in ctx.get_players_in_room():
            player = ctx.world.players.get(player_id)
            if not player:
                continue
            
            # Only consider same-faction players
            if player.faction_id == npc_faction:
                hp_percent = (player.current_health / player.max_health) * 100
                in_combat = bool(player.combat.is_in_combat())
                allies.append((player_id, hp_percent, in_combat))
        
        return allies

    async def on_combat_action(
        self, ctx: BehaviorContext, target_id: str
    ) -> BehaviorResult:
        """
        Choose buff target based on faction allies' combat status.
        """
        # Check if NPC has abilities
        if not ctx.has_abilities():
            return BehaviorResult.nothing()

        # Get buff abilities
        buff_abilities = ctx.config.get("buff_abilities", [])
        if not buff_abilities:
            return BehaviorResult.nothing()

        ready_abilities = ctx.get_ready_abilities()
        buff_ready = [a for a in ready_abilities if a in buff_abilities]
        if not buff_ready:
            return BehaviorResult.nothing()

        # Find faction allies
        allies = self._find_faction_allies(ctx)
        if not allies:
            return BehaviorResult.nothing()

        # Prefer allies in combat
        if ctx.config.get("prefer_damaged_allies", True):
            combat_allies = [(npc_id, hp, combat) for npc_id, hp, combat in allies if combat]
            if combat_allies:
                # Buff lowest HP ally in combat
                target_id = min(combat_allies, key=lambda x: x[1])[0]
            else:
                return BehaviorResult.nothing()
        else:
            # Random ally
            target_id = random.choice([npc_id for npc_id, _, _ in allies])

        # Get target name for message
        target = ctx.world.npcs.get(target_id) or ctx.world.players.get(target_id)
        target_name = target.name if target else "ally"

        ability_id = random.choice(buff_ready)
        return BehaviorResult.use_ability(
            ability_id=ability_id,
            target_id=target_id,
            message=f"{ctx.npc.name} empowers {target_name} with magical energy!",
        )
