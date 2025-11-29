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
    - Costs rage
    - Moderate damage per target
    - Scales with strength
    - Requires level 10
    """
    try:
        if not isinstance(targets, list):
            targets = [targets]
        
        total_damage = 0
        targets_hit = []
        
        # Base damage for whirlwind
        base_damage = context.get('base_damage', 60)
        strength = getattr(caster, 'strength', 10)
        
        # Warrior scaling: 1.5x strength
        damage_per_target = int(base_damage + (strength * 1.5))
        
        import random
        for target in targets:
            # Whirlwind has decent accuracy
            hit_roll = random.randint(1, 20) + (caster.armor_class // 2) + 3
            if hit_roll >= target.armor_class:
                old_hp = target.current_health
                target.current_health = max(0, target.current_health - damage_per_target)
                total_damage += damage_per_target
                targets_hit.append(target.id)
                
                logger.info(f"Whirlwind hit {target.name} for {damage_per_target} damage")
        
        return BehaviorResult(
            success=True,
            damage_dealt=total_damage,
            targets_hit=targets_hit,
            cooldown_applied=ability_template.cooldown or 0.0,
            message=f"Whirlwind! You spin and hit {len(targets_hit)} enemies for {total_damage} total damage!"
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
    
    Bash enemy with shield:
    - Moderate melee damage
    - Applies stun effect
    - Scales with strength
    - Short cooldown for frequent use
    """
    try:
        base_damage = context.get('base_damage', 40)
        strength = getattr(caster, 'strength', 10)
        damage = int(base_damage + (strength * 0.8))
        
        # Hit check
        import random
        hit_roll = random.randint(1, 20) + (caster.armor_class // 2)
        
        if hit_roll >= target.armor_class:
            old_hp = target.current_health
            target.current_health = max(0, target.current_health - damage)
            
            logger.info(f"{caster.name} shield bashed {target.name} for {damage} damage + stun")
            
            return BehaviorResult(
                success=True,
                damage_dealt=damage,
                targets_hit=[target.id],
                effects_applied=["stun"],
                cooldown_applied=ability_template.cooldown or 0.0,
                message=f"Shield Bash! You hit {target.name} for {damage} damage and stun them!"
            )
        else:
            return BehaviorResult(
                success=True,
                damage_dealt=0,
                targets_hit=[],
                message=f"Your shield bash missed {target.name}!"
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
    
    More powerful variant of fireball:
    - Affects larger area
    - Higher damage per target
    - Applies burning effect for damage over time
    - High mana cost and longer cooldown
    """
    try:
        if not isinstance(targets, list):
            targets = [targets]
        
        total_damage = 0
        targets_hit = []
        
        # Inferno is powerful - high base damage
        base_damage = context.get('base_damage', 120)
        intelligence = getattr(caster, 'intelligence', 10)
        
        # Mage scaling: 1.4x intelligence
        damage_per_target = int(base_damage + (intelligence * 1.4))
        
        import random
        for target in targets:
            # Spells are hard to dodge
            hit_roll = random.randint(1, 20) + (caster.armor_class // 2) + 10
            if hit_roll >= target.armor_class:
                old_hp = target.current_health
                target.current_health = max(0, target.current_health - damage_per_target)
                total_damage += damage_per_target
                targets_hit.append(target.id)
                
                logger.info(f"Inferno hit {target.name} for {damage_per_target} damage")
        
        return BehaviorResult(
            success=True,
            damage_dealt=total_damage,
            targets_hit=targets_hit,
            effects_applied=["burning"],  # DoT effect
            cooldown_applied=ability_template.cooldown or 0.0,
            message=f"Inferno! You scorch {len(targets_hit)} enemies for {total_damage} total damage!"
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
    
    Launches multiple magical projectiles:
    - Reliable damage per cast
    - Low cooldown for frequent use
    - Scales with intelligence
    - Can chain to multiple targets in implementation
    """
    try:
        missile_count = context.get('missile_count', 3)
        base_damage_per_missile = context.get('base_damage_per_missile', 25)
        intelligence = getattr(caster, 'intelligence', 10)
        
        # Each missile benefits from intelligence scaling
        damage_per_missile = int(base_damage_per_missile + (intelligence * 0.6))
        total_damage = damage_per_missile * missile_count
        
        # High accuracy for guaranteed hit
        import random
        hit_roll = random.randint(1, 20) + (caster.armor_class // 2) + 12
        
        if hit_roll >= target.armor_class:
            old_hp = target.current_health
            target.current_health = max(0, target.current_health - total_damage)
            
            logger.info(
                f"Arcane Missiles hit {target.name} "
                f"({missile_count} missiles x {damage_per_missile} = {total_damage} damage)"
            )
            
            return BehaviorResult(
                success=True,
                damage_dealt=total_damage,
                targets_hit=[target.id],
                cooldown_applied=ability_template.cooldown or 0.0,
                message=f"Arcane Missiles! {missile_count} projectiles strike {target.name} for {total_damage} total damage!"
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
        dexterity = getattr(caster, 'dexterity', 10)
        
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
