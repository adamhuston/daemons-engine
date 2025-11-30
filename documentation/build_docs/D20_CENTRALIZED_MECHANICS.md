# D20 Mechanics - Centralized Source of Truth

## Overview

All D20 mechanics (attack rolls, ability modifiers, proficiency bonuses, etc.) are now centralized in a single module: `backend/app/engine/systems/d20.py`

This provides a **single source of truth** for game balance. Tweaking values in this module affects the entire game instantly.

## Benefits

1. **Consistency**: All systems use identical formulas
2. **Easy Balancing**: Change proficiency scaling in one place
3. **Maintainability**: No duplicate formula implementations
4. **Transparency**: Clear constants for all magic numbers
5. **Testing**: Test mechanics in isolation

## Architecture

```
d20.py (source of truth)
    ↓
WorldEntity methods (convenience wrappers)
    ↓
Combat, Abilities, Skills (game systems)
```

## Usage Examples

### Direct Use (for systems without entity context)

```python
from app.engine.systems import d20

# Calculate ability modifier
strength = 16
str_mod = d20.calculate_ability_modifier(strength)  # +3

# Calculate attack bonus
level = 5
attack_bonus = d20.calculate_melee_attack_bonus(strength, level)  # +6 (prof+3, str+3)

# Make an attack roll
is_hit, roll, total, is_crit = d20.make_attack_roll(attack_bonus, target_ac=15)
# Returns: (True, 12, 18, False) - hit with 12+6=18 vs AC 15

# Make a saving throw
dex_mod = d20.calculate_ability_modifier(14)  # +2
success, roll, total = d20.make_saving_throw(dex_mod, dc=15)
# Returns: (True, 15, 17) - saved with 15+2=17 vs DC 15
```

### Via WorldEntity Methods (for entity-based code)

```python
# Entities have convenience methods that delegate to d20 module
attack_bonus = attacker.get_melee_attack_bonus()
spell_bonus = caster.get_spell_attack_bonus()
spell_dc = caster.get_spell_save_dc()

# Make a saving throw
success, total = target.make_saving_throw("dexterity", dc=15)
```

### In Ability Behaviors

```python
from app.engine.systems import d20

async def my_spell_behavior(caster, target, ability_template, combat_system, **context):
    # Get attack bonus from caster
    spell_attack = caster.get_spell_attack_bonus()
    target_ac = target.get_effective_armor_class()

    # Make attack roll using centralized mechanics
    is_hit, roll, total, is_crit = d20.make_attack_roll(spell_attack, target_ac)

    if not is_hit:
        return BehaviorResult(
            success=True,
            message=f"Your spell misses! (rolled {roll}+{spell_attack}={total} vs AC {target_ac})"
        )

    # Calculate damage
    import random
    base_damage = random.randint(1, 8)
    int_mod = caster.get_ability_modifier(caster.get_effective_intelligence())
    damage = base_damage + int_mod

    # Apply critical hit damage
    if is_crit:
        damage = d20.calculate_critical_damage(damage, int_mod)

    # ...
```

## Tuning Game Balance

All D20 constants are at the top of `d20.py`:

```python
# Ability score that represents "average" (modifier = +0)
ABILITY_BASELINE = 10  # Change to 12 to make everyone weaker

# Base proficiency bonus at level 1
BASE_PROFICIENCY = 2  # Change to 3 for faster scaling

# How many levels between proficiency increases
PROFICIENCY_SCALE = 4  # Change to 3 for +1 every 3 levels

# Spell save DC base value
SPELL_DC_BASE = 8  # Change to 10 to make spells harder to resist

# Critical hit mechanics
CRIT_DOUBLES_DICE = True  # Set to False to use multiplier instead
CRIT_MULTIPLIER = 2.0  # Only used if CRIT_DOUBLES_DICE = False
```

### Example: Faster Proficiency Scaling

Want proficiency to scale faster? Just change one constant:

```python
# Before (standard D&D):
PROFICIENCY_SCALE = 4
# Level 1-4: +2, 5-8: +3, 9-12: +4...

# After (faster progression):
PROFICIENCY_SCALE = 3
# Level 1-3: +2, 4-6: +3, 7-9: +4...
```

This change affects:
- All melee attacks
- All spell attacks
- All spell save DCs
- All saving throws (if proficient)

### Example: Alternative Critical Hit System

Want 3x damage crits instead of doubling dice?

```python
CRIT_DOUBLES_DICE = False
CRIT_MULTIPLIER = 3.0
```

Now all critical hits (melee, spells, abilities) multiply total damage by 3x.

## Standard DCs

Pre-defined difficulty classes for skill checks:

```python
from app.engine.systems import d20

# Use standard DCs
if player_roll >= d20.DC_HARD:  # 20
    # Success on hard check

# Or calculate dynamic DCs
flee_dc = d20.calculate_dynamic_dc(base_dc=15, modifier=-5)  # DC 10 (easier)
```

## Future Features

The d20 module includes placeholder functions for future mechanics:

```python
# Advantage: roll 2d20, take higher
roll = d20.roll_with_advantage()

# Disadvantage: roll 2d20, take lower
roll = d20.roll_with_disadvantage()
```

## Migration

All existing code has been updated to use the centralized module:

- ✅ `WorldEntity` D20 helper methods → delegate to `d20.py`
- ✅ `combat.py` attack rolls → use `d20.make_attack_roll()`
- ✅ `combat.py` critical damage → use `d20.calculate_critical_damage()`
- ✅ Ability behaviors → use `d20` module for calculations

## Testing

The d20 module is pure functions with no dependencies, making it easy to test:

```python
import pytest
from app.engine.systems import d20

def test_ability_modifiers():
    assert d20.calculate_ability_modifier(10) == 0
    assert d20.calculate_ability_modifier(20) == 5
    assert d20.calculate_ability_modifier(8) == -1

def test_proficiency_scaling():
    assert d20.calculate_proficiency_bonus(1) == 2
    assert d20.calculate_proficiency_bonus(5) == 3
    assert d20.calculate_proficiency_bonus(20) == 6
```

## Summary

**Before**: D20 formulas scattered across multiple files
**After**: Single source of truth in `d20.py`

**Want to change how crits work?** Edit one constant.
**Want to adjust proficiency scaling?** Edit one constant.
**Want to add advantage/disadvantage?** Functions already exist.

All game systems automatically use the updated mechanics!
