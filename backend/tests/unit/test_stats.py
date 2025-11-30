"""
Unit tests for stat calculations, damage formulas, and level up logic.

Tests combat math, stat scaling, and progression systems.
"""

import pytest
from app.engine.world import LEVEL_UP_STAT_GAINS, XP_THRESHOLDS

# ============================================================================
# Level Calculation Tests
# ============================================================================


@pytest.mark.unit
def test_level_from_xp():
    """Test determining level from XP amount."""

    def get_level_from_xp(xp: int) -> int:
        """Calculate level based on total XP."""
        for level in range(len(XP_THRESHOLDS) - 1, -1, -1):
            if xp >= XP_THRESHOLDS[level]:
                return level + 1
        return 1

    assert get_level_from_xp(0) == 1
    assert get_level_from_xp(50) == 1
    assert get_level_from_xp(100) == 2
    assert get_level_from_xp(249) == 2
    assert get_level_from_xp(250) == 3
    assert get_level_from_xp(500) == 4
    assert get_level_from_xp(10000) == 11


@pytest.mark.unit
def test_xp_for_next_level():
    """Test calculating XP needed for next level."""

    def xp_for_next_level(current_level: int) -> int:
        """Calculate XP needed to reach next level."""
        if current_level >= len(XP_THRESHOLDS):
            return float("inf")
        return XP_THRESHOLDS[current_level]

    assert xp_for_next_level(1) == 100  # Level 1 -> 2
    assert xp_for_next_level(2) == 250  # Level 2 -> 3
    assert xp_for_next_level(5) == 1750  # Level 5 -> 6


@pytest.mark.unit
def test_xp_progress_percentage():
    """Test calculating progress toward next level."""

    def xp_progress(current_xp: int, current_level: int) -> float:
        """Calculate percentage progress to next level."""
        if current_level >= len(XP_THRESHOLDS) - 1:
            return 100.0

        current_threshold = XP_THRESHOLDS[current_level - 1] if current_level > 1 else 0
        next_threshold = XP_THRESHOLDS[current_level]

        xp_into_level = current_xp - current_threshold
        xp_needed = next_threshold - current_threshold

        return (xp_into_level / xp_needed) * 100.0

    # At start of level 1 (0 XP)
    assert xp_progress(0, 1) == 0.0

    # Halfway to level 2 (50 XP out of 100)
    assert xp_progress(50, 1) == 50.0

    # Just reached level 2 (100 XP)
    assert xp_progress(100, 2) == 0.0

    # Halfway to level 3 (175 XP = 100 + 75, need 150 total)
    assert xp_progress(175, 2) == 50.0


# ============================================================================
# Stat Calculation Tests
# ============================================================================


@pytest.mark.unit
def test_base_stats_calculation():
    """Test calculating base stats for a character."""

    def calculate_base_stats(level: int, character_class: str) -> dict:
        """Calculate base stats for a character at given level."""
        # Base stats at level 1
        base_hp = 100
        base_mp = 50

        # Add level-up bonuses
        levels_gained = level - 1
        total_hp = base_hp + (levels_gained * LEVEL_UP_STAT_GAINS.get("max_health", 10))
        total_mp = base_mp + (levels_gained * LEVEL_UP_STAT_GAINS.get("max_energy", 5))

        return {"max_hp": total_hp, "max_mp": total_mp}

    # Level 1
    stats_l1 = calculate_base_stats(1, "warrior")
    assert stats_l1["max_hp"] == 100
    assert stats_l1["max_mp"] == 50

    # Level 5 (4 level-ups)
    stats_l5 = calculate_base_stats(5, "warrior")
    assert stats_l5["max_hp"] == 100 + (4 * 10)  # 140
    assert stats_l5["max_mp"] == 50 + (4 * 5)  # 70

    # Level 10 (9 level-ups)
    stats_l10 = calculate_base_stats(10, "warrior")
    assert stats_l10["max_hp"] == 100 + (9 * 10)  # 190
    assert stats_l10["max_mp"] == 50 + (9 * 5)  # 95


@pytest.mark.unit
def test_attribute_modifiers():
    """Test calculating stat modifiers from attributes."""

    def get_modifier(attribute_value: int) -> int:
        """Calculate modifier from attribute (D&D style)."""
        return (attribute_value - 10) // 2

    assert get_modifier(10) == 0  # Average attribute
    assert get_modifier(12) == 1  # +1 modifier
    assert get_modifier(14) == 2  # +2 modifier
    assert get_modifier(16) == 3  # +3 modifier
    assert get_modifier(8) == -1  # -1 modifier
    assert get_modifier(6) == -2  # -2 modifier


# ============================================================================
# Damage Calculation Tests
# ============================================================================


@pytest.mark.unit
def test_basic_damage_calculation():
    """Test basic damage calculation formula."""

    def calculate_damage(
        base_damage: int, attacker_strength: int, defender_armor: int
    ) -> int:
        """Calculate damage with strength and armor modifiers."""
        str_modifier = (attacker_strength - 10) // 2
        damage = base_damage + str_modifier - defender_armor
        return max(1, damage)  # Minimum 1 damage

    # No modifiers
    assert calculate_damage(10, 10, 0) == 10

    # +3 strength modifier (+3 damage)
    assert calculate_damage(10, 16, 0) == 13

    # 5 armor (-5 damage)
    assert calculate_damage(10, 10, 5) == 5

    # High armor, but minimum 1 damage
    assert calculate_damage(10, 10, 20) == 1

    # Combined: +3 str, 2 armor
    assert calculate_damage(10, 16, 2) == 11


@pytest.mark.unit
def test_critical_hit_multiplier():
    """Test critical hit damage calculation."""

    def calculate_critical_damage(
        base_damage: int, crit_multiplier: float = 2.0
    ) -> int:
        """Calculate critical hit damage."""
        return int(base_damage * crit_multiplier)

    assert calculate_critical_damage(10) == 20
    assert calculate_critical_damage(15) == 30
    assert calculate_critical_damage(10, crit_multiplier=1.5) == 15
    assert calculate_critical_damage(10, crit_multiplier=3.0) == 30


@pytest.mark.unit
def test_damage_variance():
    """Test damage variance calculation."""

    def calculate_damage_range(
        base_damage: int, variance: float = 0.2
    ) -> tuple[int, int]:
        """Calculate min and max damage with variance."""
        min_damage = int(base_damage * (1 - variance))
        max_damage = int(base_damage * (1 + variance))
        return (min_damage, max_damage)

    # 20% variance on 100 damage = 80-120
    min_dmg, max_dmg = calculate_damage_range(100, 0.2)
    assert min_dmg == 80
    assert max_dmg == 120

    # 10% variance on 50 damage = 45-55
    min_dmg, max_dmg = calculate_damage_range(50, 0.1)
    assert min_dmg == 45
    assert max_dmg == 55


# ============================================================================
# Resistance/Vulnerability Tests
# ============================================================================


@pytest.mark.unit
def test_damage_type_resistance():
    """Test damage reduction from resistance."""

    def apply_resistance(damage: int, resistance_percent: int) -> int:
        """Apply resistance to reduce damage."""
        reduction = (damage * resistance_percent) // 100
        return max(0, damage - reduction)

    # 50% fire resistance
    assert apply_resistance(100, 50) == 50

    # 25% resistance
    assert apply_resistance(100, 25) == 75

    # 100% resistance (immune)
    assert apply_resistance(100, 100) == 0


@pytest.mark.unit
def test_damage_type_vulnerability():
    """Test damage increase from vulnerability."""

    def apply_vulnerability(damage: int, vulnerability_percent: int) -> int:
        """Apply vulnerability to increase damage."""
        increase = (damage * vulnerability_percent) // 100
        return damage + increase

    # 50% vulnerability (take 50% more damage)
    assert apply_vulnerability(100, 50) == 150

    # 25% vulnerability
    assert apply_vulnerability(100, 25) == 125

    # 100% vulnerability (double damage)
    assert apply_vulnerability(100, 100) == 200


# ============================================================================
# Healing Calculation Tests
# ============================================================================


@pytest.mark.unit
def test_healing_calculation():
    """Test healing amount calculation."""

    def calculate_healing(
        base_healing: int, healer_wisdom: int, target_max_hp: int
    ) -> int:
        """Calculate healing with wisdom modifier."""
        wis_modifier = (healer_wisdom - 10) // 2
        total_healing = base_healing + wis_modifier
        return min(total_healing, target_max_hp)  # Can't overheal

    # No modifier
    assert calculate_healing(50, 10, 200) == 50

    # +3 wisdom modifier
    assert calculate_healing(50, 16, 200) == 53

    # Can't overheal
    assert calculate_healing(50, 10, 40) == 40


@pytest.mark.unit
def test_healing_over_time():
    """Test healing over time calculation."""

    def calculate_hot(
        healing_per_tick: int, num_ticks: int, tick_interval: float
    ) -> dict:
        """Calculate healing over time totals."""
        total_healing = healing_per_tick * num_ticks
        total_duration = num_ticks * tick_interval

        return {
            "total_healing": total_healing,
            "duration": total_duration,
            "ticks": num_ticks,
        }

    # 10 HP per tick, 5 ticks, 2 seconds between ticks
    hot = calculate_hot(10, 5, 2.0)
    assert hot["total_healing"] == 50
    assert hot["duration"] == 10.0
    assert hot["ticks"] == 5


# ============================================================================
# Resource Calculation Tests
# ============================================================================


@pytest.mark.unit
def test_mana_cost_calculation():
    """Test mana cost calculation with modifiers."""

    def calculate_mana_cost(
        base_cost: int, intelligence: int, cost_reduction_percent: int = 0
    ) -> int:
        """Calculate final mana cost with modifiers."""
        # Higher intelligence can reduce costs (optional)
        int_modifier = (intelligence - 10) // 2
        cost_reduction = max(0, int_modifier * 2)  # 2% per int modifier point

        # Add equipment/effect reductions
        total_reduction = min(
            cost_reduction + cost_reduction_percent, 80
        )  # Max 80% reduction

        final_cost = base_cost - (base_cost * total_reduction // 100)
        return max(1, final_cost)  # Minimum 1 mana

    # No modifiers
    assert calculate_mana_cost(50, 10, 0) == 50

    # +3 int modifier = 6% reduction
    assert calculate_mana_cost(50, 16, 0) == 47

    # 25% cost reduction from equipment
    assert calculate_mana_cost(100, 10, 25) == 75

    # Max reduction cap (80%)
    # int 30: int_modifier = (30-10)//2 = 10, cost_reduction = 10*2 = 20%
    # total_reduction = min(20 + 50, 80) = 70%
    # final_cost = 100 - (100 * 70 // 100) = 30
    assert calculate_mana_cost(100, 30, 50) == 30


@pytest.mark.unit
def test_rage_generation():
    """Test rage generation from damage."""

    def generate_rage(damage_dealt: int, rage_per_damage: float = 0.1) -> int:
        """Calculate rage generated from dealing damage."""
        return int(damage_dealt * rage_per_damage)

    # 10% rage per damage
    assert generate_rage(100, 0.1) == 10
    assert generate_rage(50, 0.1) == 5

    # 20% rage per damage
    assert generate_rage(100, 0.2) == 20


# ============================================================================
# Status Effect Duration Tests
# ============================================================================


@pytest.mark.unit
def test_effect_duration_calculation():
    """Test status effect duration with modifiers."""

    def calculate_effect_duration(
        base_duration: float, caster_level: int, target_resistance: int = 0
    ) -> float:
        """Calculate status effect duration."""
        # Duration scales slightly with caster level
        level_bonus = (caster_level - 1) * 0.1
        duration = base_duration + level_bonus

        # Resistance reduces duration
        reduction = (duration * target_resistance) // 100
        final_duration = max(1.0, duration - reduction)

        return final_duration

    # Base duration at level 1
    assert calculate_effect_duration(5.0, 1, 0) == 5.0

    # Duration increase at level 10 (+0.9 seconds)
    assert calculate_effect_duration(5.0, 10, 0) == 5.9

    # 50% resistance
    duration = calculate_effect_duration(10.0, 1, 50)
    assert 4.0 <= duration <= 6.0


# ============================================================================
# Attack Speed Tests
# ============================================================================


@pytest.mark.unit
def test_attack_speed_calculation():
    """Test attack speed and cooldown calculation."""

    def calculate_attack_cooldown(
        base_cooldown: float, dexterity: int, haste_percent: int = 0
    ) -> float:
        """Calculate attack cooldown with modifiers."""
        # Dexterity reduces cooldown
        dex_modifier = (dexterity - 10) // 2
        dex_reduction = max(0, dex_modifier * 2)  # 2% per dex modifier

        # Haste effects
        total_reduction = min(dex_reduction + haste_percent, 50)  # Max 50% reduction

        final_cooldown = base_cooldown * (100 - total_reduction) / 100
        return max(0.5, final_cooldown)  # Minimum 0.5s cooldown

    # No modifiers
    assert calculate_attack_cooldown(2.0, 10, 0) == 2.0

    # +3 dex modifier = 6% reduction
    assert calculate_attack_cooldown(2.0, 16, 0) == pytest.approx(1.88, 0.01)

    # 20% haste
    assert calculate_attack_cooldown(2.0, 10, 20) == 1.6

    # Max reduction cap (50%)
    assert calculate_attack_cooldown(2.0, 30, 50) == 1.0
