"""
Core ability behaviors - reusable across multiple abilities and classes.

These behaviors implement common ability patterns:
- Melee attacks with weapon scaling
- Power attacks (high damage, high cost)
- Passive buffs and auras
- Resource generation
- Crowd control effects
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BehaviorResult:
    """
    Result of executing an ability behavior.

    Used by AbilityExecutor to determine what happened when an ability was cast.
    """

    success: bool  # Whether the ability executed successfully
    damage_dealt: int = 0  # Total damage dealt (sum across all targets)
    targets_hit: list[str] = None  # List of entity IDs that were hit
    effects_applied: list[str] = None  # List of effect IDs that were applied
    resources_consumed: dict[str, int] = None  # Resource costs consumed
    cooldown_applied: float = 0.0  # Cooldown duration in seconds
    message: str = ""  # Human-readable result message
    error: str | None = None  # Error message if unsuccessful

    def __post_init__(self):
        if self.targets_hit is None:
            self.targets_hit = []
        if self.effects_applied is None:
            self.effects_applied = []
        if self.resources_consumed is None:
            self.resources_consumed = {}


async def melee_attack_behavior(
    caster,  # WorldPlayer or WorldEntity
    target,  # WorldEntity
    ability_template,
    combat_system,
    **context,
) -> BehaviorResult:
    """
    Basic melee attack behavior.

    Handles:
    - Weapon damage calculation with stat scaling
    - Attack roll vs target armor class
    - On-hit effects application

    Args:
        caster: The entity casting the ability
        target: The primary target
        ability_template: AbilityTemplate from ClassSystem
        combat_system: CombatSystem instance from WorldEngine
        **context: Additional context (scaling factors, modifiers, etc.)

    Returns:
        BehaviorResult with damage_dealt, effects_applied, success status
    """
    try:
        # Calculate base damage from caster's weapon
        base_damage = caster.base_attack_damage_min
        if hasattr(caster, "base_attack_damage_max"):
            import random

            base_damage = random.randint(
                caster.base_attack_damage_min, caster.base_attack_damage_max
            )

        # Apply stat scaling (e.g., strength modifier)
        scaling = ability_template.scaling or {}
        damage = base_damage

        for stat_name, multiplier in scaling.items():
            stat_value = getattr(caster, stat_name, 0)
            damage += int(stat_value * multiplier)

        # Simple hit/miss check (AC-based)
        import random

        hit_roll = random.randint(1, 20) + caster.armor_class // 2
        if hit_roll >= target.armor_class:
            # Hit - apply damage
            old_hp = target.current_health
            target.current_health = max(0, target.current_health - damage)

            logger.info(
                f"{caster.name} hit {target.name} for {damage} damage "
                f"({old_hp} -> {target.current_health} HP)"
            )

            return BehaviorResult(
                success=True,
                damage_dealt=damage,
                targets_hit=[target.id],
                cooldown_applied=ability_template.cooldown or 0.0,
                message=f"You hit {target.name} for {damage} damage!",
            )
        else:
            # Miss
            logger.info(f"{caster.name} missed {target.name}")
            return BehaviorResult(
                success=True,
                damage_dealt=0,
                targets_hit=[],
                cooldown_applied=ability_template.cooldown or 0.0,
                message=f"You missed {target.name}!",
            )

    except Exception as e:
        logger.error(f"Error in melee_attack_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Melee attack failed: {str(e)}")


async def arcane_bolt_behavior(
    caster, target, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    Basic arcane spell attack behavior.

    Uses D20 spell attack mechanics:
    - Spell attack roll: d20 + spell attack bonus vs target AC
    - Damage: 1d10 + intelligence modifier
    - Intelligence scaling from ability template

    Args:
        caster: The entity casting the ability
        target: The primary target
        ability_template: AbilityTemplate from ClassSystem
        combat_system: CombatSystem instance from WorldEngine
        **context: Additional context

    Returns:
        BehaviorResult with damage_dealt, success status
    """
    try:
        import random

        from .. import d20

        # ========== D20 SPELL ATTACK ROLL ==========
        spell_attack_bonus = caster.get_spell_attack_bonus()
        target_ac = target.get_effective_armor_class()

        # Use centralized d20 attack roll mechanics
        is_hit, attack_roll, attack_total, is_crit = d20.make_attack_roll(
            spell_attack_bonus, target_ac
        )

        # Miss
        if not is_hit:
            logger.info(
                f"{caster.name}'s Arcane Bolt missed {target.name} "
                f"(rolled {attack_roll}+{spell_attack_bonus}={attack_total} vs AC {target_ac})"
            )
            miss_message = f"Your Arcane Bolt misses {target.name}! (rolled {attack_roll}+{spell_attack_bonus}={attack_total} vs AC {target_ac})"
            return BehaviorResult(
                success=True,
                damage_dealt=0,
                targets_hit=[],
                cooldown_applied=ability_template.cooldown or 0.0,
                message=miss_message,
            )

        # ========== CALCULATE SPELL DAMAGE ==========
        # Base damage: 1d10
        base_damage = random.randint(1, 10)

        # Add intelligence modifier
        int_mod = caster.get_ability_modifier(caster.get_effective_intelligence())
        damage = base_damage + int_mod

        # Apply intelligence scaling from ability template
        scaling = ability_template.scaling or {}
        for stat_name, multiplier in scaling.items():
            if stat_name == "intelligence":
                stat_value = caster.get_effective_intelligence()
                # Add scaled damage (beyond the base modifier)
                extra_damage = (
                    int(stat_value * multiplier) - int_mod
                )  # Subtract already-added mod
                damage += max(0, extra_damage)

        # Critical hits use centralized d20 mechanics
        if is_crit:
            damage = d20.calculate_critical_damage(damage, int_mod)

        # Ensure minimum 1 damage
        damage = max(1, damage)

        # Apply damage to target
        old_hp = target.current_health
        target.current_health = max(0, target.current_health - damage)

        crit_text = " **CRITICAL HIT!**" if is_crit else ""
        roll_info = (
            " (natural 20!)"
            if is_crit
            else f" (rolled {attack_roll}+{spell_attack_bonus}={attack_total} vs AC {target_ac})"
        )

        logger.info(
            f"{caster.name} hit {target.name} with Arcane Bolt for {damage} damage{crit_text} "
            f"({old_hp} -> {target.current_health} HP)"
        )

        return BehaviorResult(
            success=True,
            damage_dealt=damage,
            targets_hit=[target.id],
            cooldown_applied=ability_template.cooldown or 0.0,
            message=f"Your Arcane Bolt hits {target.name} for {damage} damage!{crit_text}{roll_info}",
        )

    except Exception as e:
        logger.error(f"Error in arcane_bolt_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Arcane Bolt failed: {str(e)}")


async def power_attack_behavior(
    caster, target, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    High-damage attack that costs more resources but deals extra damage.

    Warrior variant of power attack:
    - Uses strength for scaling
    - 1.5x damage multiplier vs melee_attack
    - Costs rage
    """
    try:
        # Similar to melee attack but with damage boost
        base_damage = caster.base_attack_damage_min
        if hasattr(caster, "base_attack_damage_max"):
            import random

            base_damage = random.randint(
                caster.base_attack_damage_min, caster.base_attack_damage_max
            )

        # Apply stat scaling with boost
        scaling = ability_template.scaling or {}
        damage = int(base_damage * 1.5)  # 1.5x damage multiplier for power attack

        for stat_name, multiplier in scaling.items():
            stat_value = getattr(caster, stat_name, 0)
            damage += int(stat_value * multiplier * 1.3)  # Also scale stat bonuses

        # Hit check
        import random

        hit_roll = random.randint(1, 20) + (caster.armor_class // 2)
        if hit_roll >= target.armor_class:
            target.current_health = max(0, target.current_health - damage)

            logger.info(
                f"{caster.name} power attacked {target.name} for {damage} damage"
            )

            return BehaviorResult(
                success=True,
                damage_dealt=damage,
                targets_hit=[target.id],
                cooldown_applied=ability_template.cooldown or 0.0,
                message=f"Powerful strike! You hit {target.name} for {damage} damage!",
            )
        else:
            return BehaviorResult(
                success=True,
                damage_dealt=0,
                targets_hit=[],
                cooldown_applied=ability_template.cooldown or 0.0,
                message=f"Your powerful attack missed {target.name}!",
            )

    except Exception as e:
        logger.error(f"Error in power_attack_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Power attack failed: {str(e)}")


async def rally_passive_behavior(
    caster, target, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    Passive buff that increases party damage and defense.

    Warrior ability (passive):
    - Boosts nearby allies' damage by 10%
    - Boosts nearby allies' armor class by 2
    - Affects caster and nearby room
    """
    try:
        # Get all entities in the room (from context or caster's room)
        if "room" in context:
            (context["room"].entities if hasattr(context["room"], "entities") else [])
        else:
            pass

        # Apply buff to caster at minimum
        affected = [caster]

        # In a full implementation, would apply buffs via EffectSystem
        # For now, just track it in behavior result

        logger.info(f"{caster.name} activated Rally - buffing nearby allies")

        return BehaviorResult(
            success=True,
            damage_dealt=0,
            targets_hit=[e.id for e in affected],
            effects_applied=["rally_buff"],
            message="Your rally inspires nearby allies! Damage and defense increased.",
        )

    except Exception as e:
        logger.error(f"Error in rally_passive_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Rally activation failed: {str(e)}")


async def aoe_attack_behavior(
    caster,
    targets,  # List of targets for AoE
    ability_template,
    combat_system,
    **context,
) -> BehaviorResult:
    """
    Area-of-effect attack hitting all targets in a room.

    Used by abilities like Whirlwind, Fireball, etc.
    - Calculates damage for each target separately
    - Applies scaling based on ability
    - Returns aggregate damage and all targets hit
    """
    try:
        if not isinstance(targets, list):
            targets = [targets]

        total_damage = 0
        targets_hit = []

        scaling = ability_template.scaling or {}

        for target in targets:
            # Base damage calculation
            base_damage = caster.base_attack_damage_min
            if hasattr(caster, "base_attack_damage_max"):
                import random

                base_damage = random.randint(
                    caster.base_attack_damage_min, caster.base_attack_damage_max
                )

            # Apply stat scaling
            damage = base_damage
            for stat_name, multiplier in scaling.items():
                stat_value = getattr(caster, stat_name, 0)
                damage += int(stat_value * multiplier)

            # AoE attacks typically have higher hit rate
            import random

            hit_roll = random.randint(1, 20) + (caster.armor_class // 2) + 5
            if hit_roll >= target.armor_class:
                target.current_health = max(0, target.current_health - damage)
                total_damage += damage
                targets_hit.append(target.id)

                logger.info(f"AoE hit {target.name} for {damage} damage")

        message = f"Your AoE attack hit {len(targets_hit)} targets for {total_damage} total damage!"

        return BehaviorResult(
            success=True,
            damage_dealt=total_damage,
            targets_hit=targets_hit,
            cooldown_applied=ability_template.cooldown or 0.0,
            message=message,
        )

    except Exception as e:
        logger.error(f"Error in aoe_attack_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"AoE attack failed: {str(e)}")


async def stun_effect_behavior(
    caster, target, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    Apply a stun effect to target.

    Stun prevents the target from taking actions for a duration.
    Usually combined with another attack (e.g., Shield Bash).
    """
    try:
        # Create stun effect
        stun_duration = context.get("stun_duration", 2.0)  # Default 2 seconds

        # In full implementation, would use EffectSystem
        # Effect would prevent targets from executing abilities

        logger.info(f"{caster.name} stunned {target.name} for {stun_duration}s")

        return BehaviorResult(
            success=True,
            targets_hit=[target.id],
            effects_applied=["stun"],
            message=f"You stun {target.name} for {stun_duration} seconds!",
        )

    except Exception as e:
        logger.error(f"Error in stun_effect_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Stun effect failed: {str(e)}")


async def mana_regen_behavior(
    caster, target, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    Restore mana to caster or target.

    Mage support ability - restores mana pool.
    Amount based on ability level and intelligence scaling.
    """
    try:
        base_regen = context.get("regen_amount", 50)
        scaling = ability_template.scaling or {}

        # Apply scaling
        regen_amount = base_regen
        for stat_name, multiplier in scaling.items():
            stat_value = getattr(caster, stat_name, 0)
            regen_amount += int(stat_value * multiplier)

        # Apply to target mana pool
        # Would use character_sheet.resource_pools['mana']
        # For now, just log it

        logger.info(f"{caster.name} restored {regen_amount} mana")

        return BehaviorResult(
            success=True,
            targets_hit=[target.id],
            message=f"You restore {regen_amount} mana!",
        )

    except Exception as e:
        logger.error(f"Error in mana_regen_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Mana regen failed: {str(e)}")


async def fireball_behavior(
    caster, targets, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    Fireball AoE attack - mage signature spell.

    Hits all enemies in target area with fire damage.
    Scales with intelligence, higher damage than melee.
    """
    try:
        if not isinstance(targets, list):
            targets = [targets]

        total_damage = 0
        targets_hit = []

        # Mage spells scale with intelligence at 1.2x
        base_damage = context.get("base_damage", 80)
        intelligence = getattr(caster, "intelligence", 10)
        damage_per_target = int(base_damage + (intelligence * 1.2))

        import random

        for target in targets:
            # Spell attacks are harder to dodge (higher hit rate)
            hit_roll = random.randint(1, 20) + (caster.armor_class // 2) + 8
            if hit_roll >= target.armor_class:
                target.current_health = max(
                    0, target.current_health - damage_per_target
                )
                total_damage += damage_per_target
                targets_hit.append(target.id)

                logger.info(
                    f"Fireball hit {target.name} for {damage_per_target} damage"
                )

        return BehaviorResult(
            success=True,
            damage_dealt=total_damage,
            targets_hit=targets_hit,
            effects_applied=["burning"],
            cooldown_applied=ability_template.cooldown or 0.0,
            message=f"Fireball! You burn {len(targets_hit)} enemies for {total_damage} total damage!",
        )

    except Exception as e:
        logger.error(f"Error in fireball_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Fireball failed: {str(e)}")


async def polymorph_behavior(
    caster, target, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    Transform target into another form temporarily.

    Mage crowd control ability - transforms enemy into harmless animal.
    Prevents target from taking actions; low damage but high utility.
    """
    try:
        duration = context.get("duration", 3.0)
        target_form = context.get("target_form", "sheep")

        logger.info(
            f"{caster.name} polymorphed {target.name} into a {target_form} for {duration}s"
        )

        return BehaviorResult(
            success=True,
            targets_hit=[target.id],
            effects_applied=["polymorphed"],
            message=f"You transform {target.name} into a {target_form}!",
        )

    except Exception as e:
        logger.error(f"Error in polymorph_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Polymorph failed: {str(e)}")


async def backstab_behavior(
    caster, target, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    Rogue single-target high-damage attack.

    Requires positioning (backstab bonus if attacking from behind).
    Scales with dexterity.
    Low resource cost but longer cooldown.
    """
    try:
        base_damage = caster.base_attack_damage_min
        if hasattr(caster, "base_attack_damage_max"):
            import random

            base_damage = random.randint(
                caster.base_attack_damage_min, caster.base_attack_damage_max
            )

        # Rogue scaling - dexterity at 1.3x
        dexterity = getattr(caster, "dexterity", 10)
        damage = int(base_damage + (dexterity * 1.3))

        # Backstab from behind bonus
        from_behind = context.get("from_behind", False)
        if from_behind:
            damage = int(damage * 1.5)

        # High accuracy for rogue
        import random

        hit_roll = random.randint(1, 20) + (caster.armor_class // 2) + 10
        if hit_roll >= target.armor_class:
            target.current_health = max(0, target.current_health - damage)

            msg = f"Backstab! You hit {target.name} for {damage} damage!"
            if from_behind:
                msg = f"Clean backstab! You hit {target.name} for {damage} damage!"

            logger.info(msg)

            return BehaviorResult(
                success=True,
                damage_dealt=damage,
                targets_hit=[target.id],
                cooldown_applied=ability_template.cooldown or 0.0,
                message=msg,
            )
        else:
            return BehaviorResult(
                success=True,
                damage_dealt=0,
                targets_hit=[],
                message=f"Your backstab missed {target.name}!",
            )

    except Exception as e:
        logger.error(f"Error in backstab_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Backstab failed: {str(e)}")


async def evasion_passive_behavior(
    caster, target, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    Rogue passive that increases dodge chance.

    Permanently increases AC (lower is better in some systems).
    Can stack with other defensive abilities.
    """
    try:
        ac_bonus = context.get("ac_bonus", -2)  # Lower AC = harder to hit

        logger.info(
            f"{caster.name} activated Evasion - AC increased by {abs(ac_bonus)}"
        )

        return BehaviorResult(
            success=True,
            targets_hit=[caster.id],
            effects_applied=["evasion_buff"],
            message="You move with greater evasion! Defense increased.",
        )

    except Exception as e:
        logger.error(f"Error in evasion_passive_behavior: {e}", exc_info=True)
        return BehaviorResult(
            success=False, error=f"Evasion activation failed: {str(e)}"
        )


async def damage_boost_behavior(
    caster, target, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    Temporary buff that increases damage output.

    Support ability used by multiple classes.
    Increases all ability damage by percentage for duration.
    """
    try:
        duration = context.get("duration", 5.0)
        damage_increase = context.get("damage_increase", 0.2)  # 20% boost

        logger.info(
            f"{caster.name} activated damage boost - +{int(damage_increase*100)}% "
            f"for {duration}s"
        )

        return BehaviorResult(
            success=True,
            targets_hit=[target.id],
            effects_applied=["damage_boost"],
            message=f"You surge with power! Damage increased by {int(damage_increase*100)}%!",
        )

    except Exception as e:
        logger.error(f"Error in damage_boost_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Damage boost failed: {str(e)}")


async def frostbolt_behavior(
    caster, target, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    Ice spell that damages and slows the target.

    Uses D20 spell attack mechanics.
    Damage: 1d8 + intelligence modifier + slow effect
    """
    try:
        import random

        from .. import d20

        # ========== D20 SPELL ATTACK ROLL ==========
        spell_attack_bonus = caster.get_spell_attack_bonus()
        target_ac = target.get_effective_armor_class()

        is_hit, attack_roll, attack_total, is_crit = d20.make_attack_roll(
            spell_attack_bonus, target_ac
        )

        if not is_hit:
            logger.info(f"{caster.name}'s Frostbolt missed {target.name}")
            return BehaviorResult(
                success=True,
                targets_hit=[],
                message=f"Your Frostbolt fizzles and misses {target.name}! (rolled {attack_roll}+{spell_attack_bonus}={attack_total} vs AC {target_ac})",
            )

        # ========== CALCULATE DAMAGE ==========
        base_damage = random.randint(1, 8)  # 1d8
        int_mod = caster.get_ability_modifier(caster.get_effective_intelligence())
        damage = base_damage + int_mod

        # Apply scaling
        scaling = ability_template.scaling or {}
        for stat_name, multiplier in scaling.items():
            if stat_name == "intelligence":
                stat_value = caster.get_effective_intelligence()
                extra_damage = int(stat_value * multiplier) - int_mod
                damage += max(0, extra_damage)

        if is_crit:
            damage = d20.calculate_critical_damage(damage, int_mod)

        damage = max(1, damage)

        # Apply damage
        target.current_health = max(0, target.current_health - damage)

        crit_text = " **CRITICAL!**" if is_crit else ""

        logger.info(
            f"{caster.name} hit {target.name} with Frostbolt for {damage} frost damage{crit_text}"
        )

        return BehaviorResult(
            success=True,
            targets_hit=[target.id],
            damage_dealt=damage,
            effects_applied=["slow_effect"],
            message=f"Your Frostbolt hits {target.name} for {damage} frost damage and slows them!{crit_text}",
        )

    except Exception as e:
        logger.error(f"Error in frostbolt_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Frostbolt failed: {str(e)}")


async def mana_shield_behavior(
    caster, target, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    Mana-based damage absorption shield.

    Creates a protective barrier that absorbs damage.
    Shield strength scales with intelligence: 5 HP per point of INT.
    """
    try:
        int_stat = caster.get_effective_intelligence()
        caster.get_ability_modifier(int_stat)

        # Shield strength: 5 HP per intelligence point
        shield_amount = int_stat * 5

        logger.info(
            f"{caster.name} activated Mana Shield - absorbs {shield_amount} damage"
        )

        return BehaviorResult(
            success=True,
            targets_hit=[caster.id],
            effects_applied=["shield_effect"],
            message=f"A shimmering barrier of mana surrounds you! (Shield: {shield_amount} HP)",
        )

    except Exception as e:
        logger.error(f"Error in mana_shield_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Mana Shield failed: {str(e)}")


async def quick_strike_behavior(
    caster, target, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    Fast melee attack for rogues.

    Uses D20 melee attack mechanics with dexterity (finesse weapon).
    Low-damage, low-cooldown strike that can be chained.
    """
    try:
        import random

        from .. import d20

        # ========== D20 MELEE ATTACK ROLL (Finesse) ==========
        # Use melee attack bonus with finesse (dexterity instead of strength)
        attack_bonus = caster.get_melee_attack_bonus(finesse=True)
        target_ac = target.get_effective_armor_class()

        is_hit, attack_roll, attack_total, is_crit = d20.make_attack_roll(
            attack_bonus, target_ac
        )

        # Get dex modifier for damage
        dex_mod = caster.get_ability_modifier(caster.get_effective_dexterity())

        if not is_hit:
            logger.info(f"{caster.name}'s Quick Strike missed {target.name}")
            return BehaviorResult(
                success=True,
                targets_hit=[],
                message=f"Your Quick Strike misses {target.name}! (rolled {attack_roll}+{attack_bonus}={attack_total} vs AC {target_ac})",
            )

        # ========== CALCULATE DAMAGE ==========
        # Base damage: 1d4 (light weapon)
        base_damage = random.randint(1, 4)
        damage = base_damage + dex_mod

        # Apply scaling
        scaling = ability_template.scaling or {}
        for stat_name, multiplier in scaling.items():
            if stat_name == "dexterity":
                stat_value = caster.get_effective_dexterity()
                extra_damage = int(stat_value * multiplier) - dex_mod
                damage += max(0, extra_damage)

        if is_crit:
            damage = d20.calculate_critical_damage(damage, dex_mod)

        damage = max(1, damage)

        # Apply damage
        target.current_health = max(0, target.current_health - damage)

        crit_text = " **CRITICAL!**" if is_crit else ""

        logger.info(
            f"{caster.name} hit {target.name} with Quick Strike for {damage} damage{crit_text}"
        )

        return BehaviorResult(
            success=True,
            targets_hit=[target.id],
            damage_dealt=damage,
            message=f"You quickly strike {target.name} for {damage} damage!{crit_text}",
        )

    except Exception as e:
        logger.error(f"Error in quick_strike_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Quick Strike failed: {str(e)}")


async def poison_strike_behavior(
    caster, target, ability_template, combat_system, **context
) -> BehaviorResult:
    """
    Melee attack that applies poison damage over time.

    Uses D20 melee attack with dexterity (finesse).
    Applies poison effect on hit.
    """
    try:
        import random

        from .. import d20

        # ========== D20 MELEE ATTACK ROLL (Finesse) ==========
        attack_bonus = caster.get_melee_attack_bonus(finesse=True)
        target_ac = target.get_effective_armor_class()

        is_hit, attack_roll, attack_total, is_crit = d20.make_attack_roll(
            attack_bonus, target_ac
        )

        # Get dex modifier for damage
        dex_mod = caster.get_ability_modifier(caster.get_effective_dexterity())

        if not is_hit:
            logger.info(f"{caster.name}'s Poison Strike missed {target.name}")
            return BehaviorResult(
                success=True,
                targets_hit=[],
                message=f"Your Poison Strike misses {target.name}!",
            )

        # ========== CALCULATE DAMAGE ==========
        # Base damage: 1d6 (poisoned blade)
        base_damage = random.randint(1, 6)
        damage = base_damage + dex_mod

        # Apply scaling
        scaling = ability_template.scaling or {}
        for stat_name, multiplier in scaling.items():
            if stat_name == "dexterity":
                stat_value = caster.get_effective_dexterity()
                extra_damage = int(stat_value * multiplier) - dex_mod
                damage += max(0, extra_damage)

        # Reduce initial damage (DoT will do more over time)
        damage = int(damage * 0.8)

        if is_crit:
            damage = d20.calculate_critical_damage(damage, dex_mod)

        damage = max(1, damage)

        # Apply damage
        target.current_health = max(0, target.current_health - damage)

        crit_text = " **CRITICAL!**" if is_crit else ""

        logger.info(
            f"{caster.name} hit {target.name} with Poison Strike for {damage} damage + poison{crit_text}"
        )

        return BehaviorResult(
            success=True,
            targets_hit=[target.id],
            damage_dealt=damage,
            effects_applied=["poison_effect"],
            message=f"You strike {target.name} with poisoned blades for {damage} damage!{crit_text} Poison spreads...",
        )

    except Exception as e:
        logger.error(f"Error in poison_strike_behavior: {e}", exc_info=True)
        return BehaviorResult(success=False, error=f"Poison Strike failed: {str(e)}")
