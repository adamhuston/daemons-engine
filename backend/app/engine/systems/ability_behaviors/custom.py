"""
Custom ability behaviors - class-specific and unique ability implementations.

These behaviors are specialized variants combining core mechanics:
- Warrior: Whirlwind, Shield Bash
- Mage: Inferno, Arcane Missiles
- Rogue: Shadow Clone
"""

import logging
from typing import List, Optional

from .core import BehaviorResult

logger = logging.getLogger(__name__)


async def whirlwind_attack_behavior(
    caster,
    targets,  # All enemies in room
    ability_template,
    combat_system,
    **context
) -> BehaviorResult:
    """
    Warrior signature AoE attack.
    
    Spin in place hitting all enemies in the room.
    Uses D20 melee attack rolls for each target.
    Damage: 1d12 + strength modifier per target
    """
    try:
        import random
        from .. import d20
        
        if not isinstance(targets, list):
            targets = [targets]
        
        total_damage = 0
        targets_hit = []
        messages = []
        
        # Get attack bonus once
        attack_bonus = caster.get_melee_attack_bonus()
        str_mod = caster.get_ability_modifier(caster.get_effective_strength())
        
        for target in targets:
            # D20 attack roll for each target using centralized mechanics
            target_ac = target.get_effective_armor_class()
            is_hit, attack_roll, attack_total, is_crit = d20.make_attack_roll(attack_bonus, target_ac)
            
            if is_hit:
                # Base damage: 1d12 (great weapon)
                base_damage = random.randint(1, 12)
                damage = base_damage + str_mod
                
                # Apply scaling from template
                scaling = ability_template.scaling or {}
                for stat_name, multiplier in scaling.items():
                    if stat_name == "strength":
                        stat_value = caster.get_effective_strength()
                        extra_damage = int(stat_value * multiplier) - str_mod
                        damage += max(0, extra_damage)
                
                # Critical hits use centralized d20 mechanics
                if is_crit:
                    damage = d20.calculate_critical_damage(damage, str_mod)
                
                damage = max(1, damage)
                
                # Apply damage
                old_hp = target.current_health
                target.current_health = max(0, target.current_health - damage)
                total_damage += damage
                targets_hit.append(target.id)
                
                crit_text = " **CRIT!**" if is_crit else ""
                logger.info(f"Whirlwind hit {target.name} for {damage} damage{crit_text}")
        
        hit_count = len(targets_hit)
        miss_count = len(targets) - hit_count
        
        message = f"Whirlwind! You spin and hit {hit_count} enemies for {total_damage} total damage!"
        if miss_count > 0:
            message += f" ({miss_count} missed)"
        
        return BehaviorResult(
            success=True,
            damage_dealt=total_damage,
            targets_hit=targets_hit,
            cooldown_applied=ability_template.cooldown or 0.0,
            message=message
        )
    
    except Exception as e:
        logger.error(f"Error in whirlwind_attack_behavior: {e}", exc_info=True)
        return BehaviorResult(
            success=False,
            error=f"Whirlwind attack failed: {str(e)}"
        )


async def shield_bash_behavior(
    caster,
    target,
    ability_template,
    combat_system,
    **context
) -> BehaviorResult:
    """
    Warrior defensive ability with crowd control.
    
    Bash enemy with shield using D20 mechanics:
    - D20 melee attack roll
    - Damage: 1d8 + strength modifier
    - Applies stun effect on hit
    - Scales with strength
    - Short cooldown for frequent use
    """
    try:
        import random
        from .. import d20
        
        # D20 attack roll using centralized mechanics
        attack_bonus = caster.get_melee_attack_bonus()
        target_ac = target.get_effective_armor_class()
        
        is_hit, attack_roll, attack_total, is_crit = d20.make_attack_roll(attack_bonus, target_ac)
        
        if not is_hit:
            return BehaviorResult(
                success=True,
                damage_dealt=0,
                targets_hit=[],
                message=f"Your shield bash missed {target.name}! (Rolled {attack_roll}, needed {target_ac - attack_bonus})"
            )
        
        # Base damage: 1d8 (shield)
        base_damage = random.randint(1, 8)
        str_mod = caster.get_ability_modifier(caster.get_effective_strength())
        damage = base_damage + str_mod
        
        # Apply scaling
        scaling = ability_template.scaling or {}
        for stat_name, multiplier in scaling.items():
            if stat_name == "strength":
                stat_value = caster.get_effective_strength()
                extra_damage = int(stat_value * multiplier) - str_mod
                damage += max(0, extra_damage)
        
        # Critical hit using centralized d20 mechanics
        if is_crit:
            damage = d20.calculate_critical_damage(damage, str_mod)
        
        damage = max(1, damage)
        
        # Apply damage
        target.current_health = max(0, target.current_health - damage)
        
        # Apply stun effect
        if not hasattr(target, 'status_effects'):
            target.status_effects = {}
        target.status_effects['stunned'] = 2  # 2 turns
        
        crit_text = " **CRIT!**" if is_crit else ""
        logger.info(f"{caster.name} shield bashed {target.name} for {damage} damage{crit_text} + stun")
        
        return BehaviorResult(
            success=True,
            damage_dealt=damage,
            targets_hit=[target.id],
            effects_applied=["stun"],
            cooldown_applied=ability_template.cooldown or 0.0,
            message=f"Shield Bash! You hit {target.name} for {damage} damage{crit_text} and stun them!"
        )
    
    except Exception as e:
        logger.error(f"Error in shield_bash_behavior: {e}", exc_info=True)
        return BehaviorResult(
            success=False,
            error=f"Shield bash failed: {str(e)}"
        )


async def inferno_behavior(
    caster,
    targets,
    ability_template,
    combat_system,
    **context
) -> BehaviorResult:
    """
    Mage ultimate AoE fire spell.
    
    More powerful variant of fireball using D20 mechanics:
    - D20 spell attack roll per target
    - Damage: 3d6 + intelligence modifier per hit
    - Applies burning effect for damage over time
    - High mana cost and longer cooldown
    """
    try:
        import random
        from .. import d20
        
        if not isinstance(targets, list):
            targets = [targets]
        
        total_damage = 0
        targets_hit = []
        
        # Get attack bonus once
        attack_bonus = caster.get_spell_attack_bonus()
        int_mod = caster.get_ability_modifier(caster.get_effective_intelligence())
        
        for target in targets:
            # D20 spell attack roll using centralized mechanics
            target_ac = target.get_effective_armor_class()
            is_hit, attack_roll, attack_total, is_crit = d20.make_attack_roll(attack_bonus, target_ac)
            
            if is_hit:
                # Base damage: 3d6 (powerful fire spell)
                base_damage = sum(random.randint(1, 6) for _ in range(3))
                damage = base_damage + int_mod
                
                # Apply scaling
                scaling = ability_template.scaling or {}
                for stat_name, multiplier in scaling.items():
                    if stat_name == "intelligence":
                        stat_value = caster.get_effective_intelligence()
                        extra_damage = int(stat_value * multiplier) - int_mod
                        damage += max(0, extra_damage)
                
                # Critical hit using centralized d20 mechanics
                if is_crit:
                    damage = d20.calculate_critical_damage(damage, int_mod)
                
                damage = max(1, damage)
                
                # Apply damage
                target.current_health = max(0, target.current_health - damage)
                total_damage += damage
                targets_hit.append(target.id)
                
                # Apply burning effect
                if not hasattr(target, 'status_effects'):
                    target.status_effects = {}
                target.status_effects['burning'] = 3  # 3 turns of DoT
                
                crit_text = " **CRIT!**" if is_crit else ""
                logger.info(f"Inferno hit {target.name} for {damage} fire damage{crit_text}")
        
        hit_count = len(targets_hit)
        miss_count = len(targets) - hit_count
        
        message = f"Inferno! You scorch {hit_count} enemies for {total_damage} total damage!"
        if miss_count > 0:
            message += f" ({miss_count} dodged the flames)"
        
        return BehaviorResult(
            success=True,
            damage_dealt=total_damage,
            targets_hit=targets_hit,
            effects_applied=["burning"],  # DoT effect
            cooldown_applied=ability_template.cooldown or 0.0,
            message=message
        )
    
    except Exception as e:
        logger.error(f"Error in inferno_behavior: {e}", exc_info=True)
        return BehaviorResult(
            success=False,
            error=f"Inferno failed: {str(e)}"
        )


async def arcane_missiles_behavior(
    caster,
    target,
    ability_template,
    combat_system,
    **context
) -> BehaviorResult:
    """
    Mage rapid-fire single-target spell.
    
    Launches multiple magical projectiles using D20 mechanics:
    - Each missile makes a D20 spell attack roll
    - Damage: 1d4+1 + intelligence modifier per missile
    - 3 missiles per cast
    - Low cooldown for frequent use
    - Scales with intelligence
    """
    try:
        import random
        from .. import d20
        
        missile_count = context.get('missile_count', 3)
        total_damage = 0
        hits = 0
        crits = 0
        
        attack_bonus = caster.get_spell_attack_bonus()
        int_mod = caster.get_ability_modifier(caster.get_effective_intelligence())
        target_ac = target.get_effective_armor_class()
        
        for i in range(missile_count):
            # Each missile rolls independently using centralized d20 mechanics
            is_hit, attack_roll, attack_total, is_crit = d20.make_attack_roll(attack_bonus, target_ac)
            
            if is_hit:
                # Missile damage: 1d4+1 (magic missile style)
                base_damage = random.randint(1, 4) + 1
                damage = base_damage + int_mod
                
                # Apply scaling
                scaling = ability_template.scaling or {}
                for stat_name, multiplier in scaling.items():
                    if stat_name == "intelligence":
                        stat_value = caster.get_effective_intelligence()
                        extra_damage = int(stat_value * multiplier) - int_mod
                        damage += max(0, extra_damage)
                
                # Critical hit using centralized d20 mechanics
                if is_crit:
                    damage = d20.calculate_critical_damage(damage, int_mod)
                    crits += 1
                
                damage = max(1, damage)
                target.current_health = max(0, target.current_health - damage)
                total_damage += damage
                hits += 1
                
                crit_text = " CRIT!" if is_crit else ""
                logger.info(
                    f"Arcane Missile {i+1} hit {target.name} for {damage} damage{crit_text}"
                )
        
        if hits > 0:
            crit_info = f" ({crits} crits!)" if crits > 0 else ""
            return BehaviorResult(
                success=True,
                damage_dealt=total_damage,
                targets_hit=[target.id],
                cooldown_applied=ability_template.cooldown or 0.0,
                message=f"Arcane Missiles! {hits}/{missile_count} projectiles strike {target.name} for {total_damage} total damage{crit_info}!"
            )
        else:
            return BehaviorResult(
                success=True,
                damage_dealt=0,
                targets_hit=[],
                message=f"Your arcane missiles missed {target.name}!"
            )
    
    except Exception as e:
        logger.error(f"Error in arcane_missiles_behavior: {e}", exc_info=True)
        return BehaviorResult(
            success=False,
            error=f"Arcane missiles failed: {str(e)}"
        )


async def shadow_clone_behavior(
    caster,
    target,
    ability_template,
    combat_system,
    **context
) -> BehaviorResult:
    """
    Rogue utility ability creating temporary decoys.
    
    Create shadow clones:
    - Splits caster position into multiple decoys
    - Enemies have reduced accuracy against clones
    - Clones deal reduced damage
    - High utility for escaping or confusing enemies
    - Energy cost, moderate cooldown
    """
    try:
        clone_count = context.get('clone_count', 2)
        duration = context.get('duration', 8.0)
        dexterity = caster.get_effective_dexterity()
        
        # More dexterity = more/better clones
        actual_clones = clone_count + (dexterity // 10)
        
        logger.info(
            f"{caster.name} created {actual_clones} shadow clones for {duration}s"
        )
        
        return BehaviorResult(
            success=True,
            targets_hit=[caster.id],  # Affects caster
            effects_applied=["shadow_clone"],
            cooldown_applied=ability_template.cooldown or 0.0,
            message=f"You shimmer and create {actual_clones} shadow clones for {duration} seconds!"
        )
    
    except Exception as e:
        logger.error(f"Error in shadow_clone_behavior: {e}", exc_info=True)
        return BehaviorResult(
            success=False,
            error=f"Shadow clone creation failed: {str(e)}"
        )
