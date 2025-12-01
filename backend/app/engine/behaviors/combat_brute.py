# backend/app/engine/behaviors/combat_brute.py
"""
Phase 14.3: Brute/Melee AI behavior scripts for NPCs with physical abilities.

These behaviors make NPCs intelligently use their melee/physical abilities:
- Prioritize high-damage attacks
- Build and spend rage effectively
- Use defensive abilities when wounded
"""
import random

from .base import BehaviorContext, BehaviorResult, BehaviorScript, behavior


@behavior(
    name="brute_ai",
    description="Melee-focused AI - uses power attacks, rage abilities",
    priority=75,  # Run before generic combat behaviors
    defaults={
        "low_health_threshold": 25,  # Percent HP to trigger defensive mode
        "high_rage_threshold": 80,  # Percent rage to use expensive abilities
        "power_attack_abilities": [],  # High-damage abilities (rage spenders)
        "defensive_abilities": [],  # Self-heals, damage reduction
        "basic_abilities": [],  # Low-cost fillers
    },
)
class BruteAI(BehaviorScript):
    """
    Intelligent melee AI for NPC warriors, berserkers, brutes, etc.

    Behavior:
    1. When health drops below threshold, use defensive abilities
    2. When rage is high, use expensive power attacks
    3. Use basic abilities to fill gaps
    4. Falls back to auto-attacks if no abilities ready
    """

    async def on_combat_action(
        self, ctx: BehaviorContext, target_id: str
    ) -> BehaviorResult:
        """
        Choose and use a melee ability based on combat situation.

        Called during combat ticks for NPCs with character sheets.
        """
        # Check if NPC has abilities
        if not ctx.has_abilities():
            return BehaviorResult.nothing()

        # Get health and resource status
        health_pct = ctx.get_health_percent()
        rage_pct = ctx.get_resource_percent("rage")

        low_health_threshold = ctx.config.get("low_health_threshold", 25)
        high_rage_threshold = ctx.config.get("high_rage_threshold", 80)

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
                    target_id=ctx.npc.id,  # Self-target
                    message=f"{ctx.npc.name} roars and braces for impact!",
                )

        # Priority 2: Power attacks when rage is high
        if rage_pct is not None and rage_pct >= high_rage_threshold:
            power_attacks = ctx.config.get("power_attack_abilities", [])
            power_ready = [a for a in ready_abilities if a in power_attacks]
            if power_ready:
                ability_id = random.choice(power_ready)
                return BehaviorResult.use_ability(
                    ability_id=ability_id,
                    target_id=target_id,
                    message=f"{ctx.npc.name} unleashes a devastating strike!",
                )

        # Priority 3: Basic abilities for consistent damage
        basic = ctx.config.get("basic_abilities", [])
        basic_ready = [a for a in ready_abilities if a in basic]
        if basic_ready:
            ability_id = random.choice(basic_ready)
            return BehaviorResult.use_ability(
                ability_id=ability_id,
                target_id=target_id,
            )

        # Priority 4: Any ready ability
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

        Brutes might use last-stand abilities or go berserk.
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
                target_id=ctx.npc.id,
                message=f"{ctx.npc.name} lets out a defiant roar!",
            )

        return BehaviorResult.nothing()


@behavior(
    name="brute_simple",
    description="Simple melee AI - randomly uses available physical abilities",
    priority=85,
    defaults={
        "ability_chance": 0.5,  # Chance to use ability vs basic attack
    },
)
class SimpleBruteAI(BehaviorScript):
    """
    Simple melee AI that randomly selects from available abilities.

    Good for basic warrior-type enemies.
    """

    async def on_combat_action(
        self, ctx: BehaviorContext, target_id: str
    ) -> BehaviorResult:
        """Randomly use an available physical ability."""
        if not ctx.has_abilities():
            return BehaviorResult.nothing()

        # Random chance to use ability vs basic attack
        ability_chance = ctx.config.get("ability_chance", 0.5)
        if random.random() > ability_chance:
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
    name="berserker_ai",
    description="Berserker AI - more aggressive at low health, ignores defense",
    priority=70,
    defaults={
        "enrage_health_threshold": 40,  # Below this, goes berserk
        "enrage_damage_bonus": 1.5,  # Damage multiplier when enraged (for future use)
        "power_abilities": [],  # Big damage abilities
        "frenzy_abilities": [],  # Low-cooldown spam abilities
    },
)
class BerserkerAI(BehaviorScript):
    """
    Berserker AI that becomes more dangerous at low health.

    Instead of going defensive, berserkers go all-out offense.
    """

    async def on_combat_action(
        self, ctx: BehaviorContext, target_id: str
    ) -> BehaviorResult:
        """Berserker combat - more aggressive when hurt."""
        if not ctx.has_abilities():
            return BehaviorResult.nothing()

        ready_abilities = ctx.get_ready_abilities()
        if not ready_abilities:
            return BehaviorResult.nothing()

        health_pct = ctx.get_health_percent()
        enrage_threshold = ctx.config.get("enrage_health_threshold", 40)
        is_enraged = health_pct < enrage_threshold

        # When enraged: spam frenzy abilities
        if is_enraged:
            frenzy = ctx.config.get("frenzy_abilities", [])
            frenzy_ready = [a for a in ready_abilities if a in frenzy]
            if frenzy_ready:
                ability_id = random.choice(frenzy_ready)
                return BehaviorResult.use_ability(
                    ability_id=ability_id,
                    target_id=target_id,
                    message=f"{ctx.npc.name}'s eyes glow with rage as they attack wildly!",
                )

        # Not enraged: use power abilities
        power = ctx.config.get("power_abilities", [])
        power_ready = [a for a in ready_abilities if a in power]
        if power_ready:
            ability_id = random.choice(power_ready)
            return BehaviorResult.use_ability(
                ability_id=ability_id,
                target_id=target_id,
            )

        # Fallback: Any ready ability
        if ready_abilities:
            return BehaviorResult.use_ability(
                ability_id=random.choice(ready_abilities),
                target_id=target_id,
            )

        return BehaviorResult.nothing()

    async def on_low_health(
        self, ctx: BehaviorContext, health_percent: float
    ) -> BehaviorResult:
        """
        Berserkers don't use defensive abilities - they attack harder.

        This hook intentionally returns nothing to let combat_action handle it.
        """
        # Berserkers don't flee or defend - they keep fighting
        return BehaviorResult.nothing()
