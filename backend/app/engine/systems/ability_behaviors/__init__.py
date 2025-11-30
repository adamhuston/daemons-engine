"""
Phase 9d+: Ability Behaviors (Core, Custom, and Utility)

This package provides behavior implementations for abilities:
- core.py: Core combat behaviors shared across multiple abilities
- custom.py: Class-specific and custom combat ability behaviors
- utility.py: Non-combat utility abilities for exploration and interaction

Behaviors are registered with ClassSystem and executed by AbilityExecutor.
Each behavior is an async callable that resolves outcomes and effects.
"""

from .core import (aoe_attack_behavior, arcane_bolt_behavior,
                   backstab_behavior, damage_boost_behavior,
                   evasion_passive_behavior, fireball_behavior,
                   frostbolt_behavior, mana_regen_behavior,
                   mana_shield_behavior, melee_attack_behavior,
                   poison_strike_behavior, polymorph_behavior,
                   power_attack_behavior, quick_strike_behavior,
                   rally_passive_behavior, stun_effect_behavior)
from .custom import (arcane_missiles_behavior, inferno_behavior,
                     shadow_clone_behavior, shield_bash_behavior,
                     whirlwind_attack_behavior)
from .utility import (create_light_behavior, create_passage_behavior,
                      darkness_behavior, detect_magic_behavior,
                      teleport_behavior, true_sight_behavior,
                      unlock_container_behavior, unlock_door_behavior)

__all__ = [
    # Core behaviors
    "melee_attack_behavior",
    "arcane_bolt_behavior",
    "power_attack_behavior",
    "rally_passive_behavior",
    "aoe_attack_behavior",
    "stun_effect_behavior",
    "mana_regen_behavior",
    "fireball_behavior",
    "frostbolt_behavior",
    "mana_shield_behavior",
    "polymorph_behavior",
    "backstab_behavior",
    "quick_strike_behavior",
    "poison_strike_behavior",
    "evasion_passive_behavior",
    "damage_boost_behavior",
    # Custom behaviors
    "whirlwind_attack_behavior",
    "shield_bash_behavior",
    "inferno_behavior",
    "arcane_missiles_behavior",
    "shadow_clone_behavior",
    # Utility behaviors
    "create_light_behavior",
    "darkness_behavior",
    "unlock_door_behavior",
    "unlock_container_behavior",
    "detect_magic_behavior",
    "true_sight_behavior",
    "teleport_behavior",
    "create_passage_behavior",
]
