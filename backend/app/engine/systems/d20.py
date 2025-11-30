"""
D20 Mechanics - Centralized source of truth for tabletop RPG mechanics.

This module provides standalone functions and constants for D20 system mechanics.
Tweak values here to adjust game balance globally.

All combat, ability, and skill check calculations should reference these functions
to ensure consistency across the codebase.
"""

import random
from typing import Literal

# =============================================================================
# Core D20 Constants
# =============================================================================

# Ability score that represents "average" (modifier = +0)
ABILITY_BASELINE = 10

# Base proficiency bonus at level 1
BASE_PROFICIENCY = 2

# How many levels between proficiency increases
PROFICIENCY_SCALE = 4

# Spell save DC base value
SPELL_DC_BASE = 8

# Critical hit ranges (inclusive)
CRITICAL_HIT_ROLL = 20  # Natural 20
CRITICAL_MISS_ROLL = 1  # Natural 1

# Critical hit mechanics
CRIT_DOUBLES_DICE = True  # If False, could use multiplier instead
CRIT_MULTIPLIER = 2.0  # Only used if CRIT_DOUBLES_DICE = False


# =============================================================================
# Regeneration Rates
# =============================================================================

# Health regeneration (HP per second)
HEALTH_REGEN_AWAKE = 0.5  # HP/sec while awake
HEALTH_REGEN_SLEEPING = 2.0  # HP/sec while sleeping (4x faster)

# Resource regeneration (% of max per second)
RESOURCE_REGEN_AWAKE = 0.01  # 1% of max resource per second (100 sec to full)
RESOURCE_REGEN_SLEEPING = 0.04  # 4% of max resource per second (25 sec to full)

# Regeneration tick interval
REGEN_TICK_INTERVAL = 3.0  # Apply regen every 3 seconds

# Combat penalties
SLEEPING_AC_PENALTY = -5  # AC penalty while sleeping (you're defenseless)


# =============================================================================
# Ability Modifiers
# =============================================================================

def calculate_ability_modifier(stat_value: int) -> int:
    """
    Calculate D20 ability modifier from a stat value.
    
    Formula: (stat - ABILITY_BASELINE) // 2
    
    Examples:
        10 -> +0
        12 -> +1
        14 -> +2
        16 -> +3
        18 -> +4
        20 -> +5
        8 -> -1
        6 -> -2
    
    Args:
        stat_value: The ability score (strength, dex, int, etc.)
        
    Returns:
        The modifier to add to d20 rolls
    """
    return (stat_value - ABILITY_BASELINE) // 2


# =============================================================================
# Proficiency Bonus
# =============================================================================

def calculate_proficiency_bonus(level: int) -> int:
    """
    Calculate proficiency bonus based on character level.
    
    Formula: BASE_PROFICIENCY + (level - 1) // PROFICIENCY_SCALE
    
    Default progression (BASE=2, SCALE=4):
        Levels 1-4:  +2
        Levels 5-8:  +3
        Levels 9-12: +4
        Levels 13-16: +5
        Levels 17-20: +6
    
    Args:
        level: Character level (1-20)
        
    Returns:
        Proficiency bonus for the level
    """
    return BASE_PROFICIENCY + (level - 1) // PROFICIENCY_SCALE


# =============================================================================
# Attack Bonuses
# =============================================================================

def calculate_melee_attack_bonus(strength: int, level: int, finesse: bool = False, dexterity: int = 10) -> int:
    """
    Calculate melee attack bonus.
    
    Formula: proficiency_bonus + ability_modifier
    Uses strength by default, or dexterity for finesse weapons.
    
    Args:
        strength: Strength stat value
        level: Character level
        finesse: If True, use dexterity instead of strength
        dexterity: Dexterity stat value (only used if finesse=True)
        
    Returns:
        Total melee attack bonus
    """
    ability_stat = dexterity if finesse else strength
    ability_mod = calculate_ability_modifier(ability_stat)
    prof_bonus = calculate_proficiency_bonus(level)
    return prof_bonus + ability_mod


def calculate_spell_attack_bonus(intelligence: int, level: int) -> int:
    """
    Calculate spell attack bonus.
    
    Formula: proficiency_bonus + intelligence_modifier
    
    Args:
        intelligence: Intelligence stat value
        level: Character level
        
    Returns:
        Total spell attack bonus
    """
    int_mod = calculate_ability_modifier(intelligence)
    prof_bonus = calculate_proficiency_bonus(level)
    return prof_bonus + int_mod


def calculate_spell_save_dc(intelligence: int, level: int) -> int:
    """
    Calculate spell save difficulty class.
    
    Formula: SPELL_DC_BASE + proficiency_bonus + intelligence_modifier
    
    Targets must roll d20 + their save modifier >= this DC to resist.
    
    Args:
        intelligence: Intelligence stat value
        level: Character level
        
    Returns:
        Spell save DC
    """
    int_mod = calculate_ability_modifier(intelligence)
    prof_bonus = calculate_proficiency_bonus(level)
    return SPELL_DC_BASE + prof_bonus + int_mod


# =============================================================================
# D20 Rolls
# =============================================================================

SaveType = Literal["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]


def roll_d20() -> int:
    """
    Roll a d20.
    
    Returns:
        Random integer from 1 to 20
    """
    return random.randint(1, 20)


def is_critical_hit(roll: int) -> bool:
    """
    Check if a d20 roll is a critical hit.
    
    Args:
        roll: The d20 roll result (1-20)
        
    Returns:
        True if the roll is a critical hit
    """
    return roll >= CRITICAL_HIT_ROLL


def is_critical_miss(roll: int) -> bool:
    """
    Check if a d20 roll is a critical miss.
    
    Args:
        roll: The d20 roll result (1-20)
        
    Returns:
        True if the roll is a critical miss (auto-fail)
    """
    return roll <= CRITICAL_MISS_ROLL


def make_attack_roll(bonus: int, target_ac: int) -> tuple[bool, int, int, bool]:
    """
    Make a complete attack roll against a target AC.
    
    Args:
        bonus: Total attack bonus (proficiency + ability modifier)
        target_ac: Target's armor class
        
    Returns:
        Tuple of (hit, roll, total, is_crit)
        - hit: True if attack hits
        - roll: The d20 roll (1-20)
        - total: Roll + bonus
        - is_crit: True if critical hit
    """
    roll = roll_d20()
    total = roll + bonus
    
    # Critical miss always fails
    if is_critical_miss(roll):
        return (False, roll, total, False)
    
    # Critical hit always hits
    if is_critical_hit(roll):
        return (True, roll, total, True)
    
    # Normal hit/miss
    hit = (total >= target_ac)
    return (hit, roll, total, False)


def make_saving_throw(
    save_modifier: int,
    dc: int
) -> tuple[bool, int, int]:
    """
    Make a saving throw against a DC.
    
    Args:
        save_modifier: Total save modifier (ability mod + proficiency if proficient)
        dc: Difficulty class to beat
        
    Returns:
        Tuple of (success, roll, total)
        - success: True if save succeeded
        - roll: The d20 roll (1-20)
        - total: Roll + modifier
    """
    roll = roll_d20()
    total = roll + save_modifier
    
    # Natural 1 always fails
    if is_critical_miss(roll):
        return (False, roll, total)
    
    # Natural 20 always succeeds
    if is_critical_hit(roll):
        return (True, roll, total)
    
    # Normal success/fail
    success = (total >= dc)
    return (success, roll, total)


# =============================================================================
# Damage Calculations
# =============================================================================

def calculate_critical_damage(base_damage: int, modifier: int) -> int:
    """
    Calculate critical hit damage.
    
    If CRIT_DOUBLES_DICE is True:
        Doubles the dice damage (base_damage - modifier), then adds modifier back.
    Otherwise:
        Multiplies total damage by CRIT_MULTIPLIER.
    
    Args:
        base_damage: Total damage including modifier
        modifier: The ability modifier that was added to base damage
        
    Returns:
        Critical hit damage
    """
    if CRIT_DOUBLES_DICE:
        # Standard D20: double the dice, add modifier once
        dice_damage = base_damage - modifier
        return (dice_damage * 2) + modifier
    else:
        # Alternative: multiply everything
        return int(base_damage * CRIT_MULTIPLIER)


# =============================================================================
# Difficulty Classes
# =============================================================================

# Standard DCs for skill checks (can be used as guidelines)
DC_VERY_EASY = 5
DC_EASY = 10
DC_MEDIUM = 15
DC_HARD = 20
DC_VERY_HARD = 25
DC_NEARLY_IMPOSSIBLE = 30


def calculate_dynamic_dc(base_dc: int, modifier: float = 0.0) -> int:
    """
    Calculate a dynamic DC with adjustments.
    
    Useful for flee mechanics, contested checks, etc.
    
    Args:
        base_dc: Starting difficulty class
        modifier: Adjustment to DC (negative = easier, positive = harder)
        
    Returns:
        Adjusted DC (minimum 5)
    """
    return max(5, int(base_dc + modifier))


# =============================================================================
# Advantage/Disadvantage (Future feature)
# =============================================================================

def roll_with_advantage() -> int:
    """
    Roll 2d20, take the higher result.
    
    Returns:
        The higher of two d20 rolls
    """
    return max(roll_d20(), roll_d20())


def roll_with_disadvantage() -> int:
    """
    Roll 2d20, take the lower result.
    
    Returns:
        The lower of two d20 rolls
    """
    return min(roll_d20(), roll_d20())
