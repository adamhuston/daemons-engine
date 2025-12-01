# backend/app/engine/behaviors/combat_caster.py
"""
Phase 14.3: Caster AI behavior scripts for NPCs with spellcasting abilities.

These behaviors make NPCs intelligently use their magical abilities:
- Prioritize ranged spells over melee
- Use defensive abilities when low on health
- Manage mana/resource pools efficiently
"""
import random

from .base import BehaviorContext, BehaviorResult, BehaviorScript, behavior


@behavior(
    name="caster_ai",
    description="Intelligent spellcasting AI - uses ranged abilities, defensive when hurt",
    priority=75,  # Run before generic combat behaviors
    defaults={
        "prefer_ranged": True,
        "low_health_threshold": 30,  # Percent HP to trigger defensive mode
        "low_mana_threshold": 20,  # Percent mana to conserve resources
        "offensive_abilities": [],  # Ability IDs to prioritize for damage
        "defensive_abilities": [],  # Ability IDs for healing/shields
        "utility_abilities": [],  # Buffs, debuffs, crowd control
    },
)
class CasterAI(BehaviorScript):
    """
    Intelligent caster AI for NPC mages, shamans, priests, etc.

    Behavior:
    1. When health drops below threshold, prioritize defensive abilities
    2. Otherwise, use offensive abilities on combat target
    3. Falls back to basic attacks if no abilities available
    """

    async def on_combat_action(
        self, ctx: BehaviorContext, target_id: str
    ) -> BehaviorResult:
        """
        Choose and cast an ability based on combat situation.

        Called during combat ticks for NPCs with character sheets.
        """
        # Check if NPC has abilities
        if not ctx.has_abilities():
            return BehaviorResult.nothing()

        # Get health status
        health_pct = ctx.get_health_percent()
        low_health_threshold = ctx.config.get("low_health_threshold", 30)

        # Check resource status (mana for casters)
        mana_pct = ctx.get_resource_percent("mana")
        low_mana_threshold = ctx.config.get("low_mana_threshold", 20)

        # Get available abilities
        ready_abilities = ctx.get_ready_abilities()
        if not ready_abilities:
            return BehaviorResult.nothing()

        # Priority 1: Defensive abilities when low health
        if health_pct < low_health_threshold:
            defensive = ctx.config.get("defensive_abilities", [])
            defensive_ready = [a for a in ready_abilities if a in defensive]
            if defensive_ready:
                ability_id = random.choice(defensive_ready)
                return BehaviorResult.use_ability(
                    ability_id=ability_id,
                    target_id=ctx.npc.id,  # Self-target for defensive
                    message=f"{ctx.npc.name} casts a protective spell!",
                )

        # Priority 2: Conserve mana if low
        if mana_pct is not None and mana_pct < low_mana_threshold:
            # Only use cheap/free abilities or skip casting
            # For now, just skip - could be enhanced to check ability costs
            return BehaviorResult.nothing()

        # Priority 3: Offensive abilities against target
        offensive = ctx.config.get("offensive_abilities", [])
        offensive_ready = [a for a in ready_abilities if a in offensive]
        if offensive_ready:
            ability_id = random.choice(offensive_ready)
            return BehaviorResult.use_ability(
                ability_id=ability_id,
                target_id=target_id,
                message=f"{ctx.npc.name} unleashes arcane power!",
            )

        # Priority 4: Any ready ability from loadout
        if ready_abilities:
            ability_id = random.choice(ready_abilities)
            return BehaviorResult.use_ability(
                ability_id=ability_id,
                target_id=target_id,
            )

        return BehaviorResult.nothing()

    async def on_low_health(
        self, ctx: BehaviorContext, health_percent: float
    ) -> BehaviorResult:
        """
        Emergency defensive response when health is critical.

        Triggered when health drops below threshold.
        """
        if not ctx.has_abilities():
            return BehaviorResult.nothing()

        ready_abilities = ctx.get_ready_abilities()
        defensive = ctx.config.get("defensive_abilities", [])
        defensive_ready = [a for a in ready_abilities if a in defensive]

        if defensive_ready:
            ability_id = random.choice(defensive_ready)
            return BehaviorResult.use_ability(
                ability_id=ability_id,
                target_id=ctx.npc.id,  # Self-target
                message=f"{ctx.npc.name} desperately invokes a protective ward!",
            )

        return BehaviorResult.nothing()


@behavior(
    name="caster_simple",
    description="Simple spellcasting AI - randomly uses available abilities",
    priority=85,
    defaults={
        "cast_chance": 0.7,  # Chance to cast when available (vs basic attack)
    },
)
class SimpleCasterAI(BehaviorScript):
    """
    Simple caster AI that randomly selects from available abilities.

    Good for basic enemies or when you don't need sophisticated AI.
    """

    async def on_combat_action(
        self, ctx: BehaviorContext, target_id: str
    ) -> BehaviorResult:
        """Randomly cast an available ability."""
        if not ctx.has_abilities():
            return BehaviorResult.nothing()

        # Random chance to use ability vs basic attack
        cast_chance = ctx.config.get("cast_chance", 0.7)
        if random.random() > cast_chance:
            return BehaviorResult.nothing()

        ready_abilities = ctx.get_ready_abilities()
        if not ready_abilities:
            return BehaviorResult.nothing()

        # Pick a random ready ability
        ability_id = random.choice(ready_abilities)
        return BehaviorResult.use_ability(
            ability_id=ability_id,
            target_id=target_id,
        )


@behavior(
    name="caster_tactical",
    description="Tactical spellcasting AI - adapts to target and situation",
    priority=70,  # Higher priority for smarter behavior
    defaults={
        "low_health_threshold": 40,
        "aoe_threshold": 2,  # Min enemies for AoE abilities
        "single_target_abilities": [],
        "aoe_abilities": [],
        "defensive_abilities": [],
        "buff_abilities": [],
    },
)
class TacticalCasterAI(BehaviorScript):
    """
    Tactical caster AI with situational awareness.

    Features:
    - Uses AoE abilities when multiple enemies present
    - Buffs self before engaging
    - Adapts spell selection to target resistances (future)
    """

    async def on_combat_action(
        self, ctx: BehaviorContext, target_id: str
    ) -> BehaviorResult:
        """Choose ability based on tactical situation."""
        if not ctx.has_abilities():
            return BehaviorResult.nothing()

        ready_abilities = ctx.get_ready_abilities()
        if not ready_abilities:
            return BehaviorResult.nothing()

        health_pct = ctx.get_health_percent()
        low_health_threshold = ctx.config.get("low_health_threshold", 40)

        # Count enemies in room
        players_in_room = ctx.get_players_in_room()
        enemy_count = len(players_in_room)

        # Priority 1: Defensive when hurt
        if health_pct < low_health_threshold:
            defensive = ctx.config.get("defensive_abilities", [])
            defensive_ready = [a for a in ready_abilities if a in defensive]
            if defensive_ready:
                return BehaviorResult.use_ability(
                    ability_id=random.choice(defensive_ready),
                    target_id=ctx.npc.id,
                )

        # Priority 2: AoE when multiple enemies
        aoe_threshold = ctx.config.get("aoe_threshold", 2)
        if enemy_count >= aoe_threshold:
            aoe = ctx.config.get("aoe_abilities", [])
            aoe_ready = [a for a in ready_abilities if a in aoe]
            if aoe_ready:
                return BehaviorResult.use_ability(
                    ability_id=random.choice(aoe_ready),
                    target_id=target_id,
                    message=f"{ctx.npc.name} begins casting a devastating area spell!",
                )

        # Priority 3: Single target offensive
        single = ctx.config.get("single_target_abilities", [])
        single_ready = [a for a in ready_abilities if a in single]
        if single_ready:
            return BehaviorResult.use_ability(
                ability_id=random.choice(single_ready),
                target_id=target_id,
            )

        # Fallback: Any ready ability
        if ready_abilities:
            return BehaviorResult.use_ability(
                ability_id=random.choice(ready_abilities),
                target_id=target_id,
            )

        return BehaviorResult.nothing()
