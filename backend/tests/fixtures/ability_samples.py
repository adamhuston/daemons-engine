"""Sample ability templates for testing."""

from tests.abilities.builders import AbilityTemplateBuilder

# Basic melee attack - most common case
SAMPLE_MELEE_ATTACK = (
    AbilityTemplateBuilder()
    .with_id("melee_attack")
    .with_name("Melee Attack")
    .with_field("description", "A basic melee attack for testing")
    .with_cooldown(0.0)
    .with_gcd_category("combat")
    .with_no_cost()
    .with_behavior("melee_attack")
    .with_target_type("enemy")
    .with_level_requirement(1)
    .build()
)

# High mana cost spell (FIREBALL)
SAMPLE_FIREBALL = (
    AbilityTemplateBuilder()
    .with_id("fireball")
    .with_name("Fireball")
    .with_field("description", "A powerful fire spell")
    .with_cooldown(2.0)
    .with_gcd_category("combat")
    .with_mana_cost(80)
    .with_behavior("magic_attack")
    .with_target_type("enemy")
    .with_level_requirement(1)  # Level 1 so it doesn't block mana validation tests
    .build()
)

# Cooldown ability (POWER_ATTACK)
SAMPLE_POWER_ATTACK = (
    AbilityTemplateBuilder()
    .with_id("power_attack")
    .with_name("Power Attack")
    .with_field("description", "A powerful attack with cooldown")
    .with_cooldown(10.0)
    .with_gcd_category("combat")
    .with_rage_cost(30)
    .with_behavior("melee_attack")
    .with_target_type("enemy")
    .with_level_requirement(1)  # Level 1 for basic tests
    .build()
)

# Self-target buff (RALLY)
SAMPLE_RALLY = (
    AbilityTemplateBuilder()
    .with_id("rally")
    .with_name("Rally")
    .with_field("description", "A buff that targets the caster")
    .with_cooldown(30.0)
    .with_gcd_category("utility")
    .with_mana_cost(20)
    .with_behavior("apply_buff")
    .with_target_type("self")
    .with_level_requirement(1)  # Level 1 for basic tests
    .build()
)

# Ally-target heal
SAMPLE_ALLY_HEAL = (
    AbilityTemplateBuilder()
    .with_id("heal")
    .with_name("Heal")
    .with_field("description", "Heals an ally")
    .with_cooldown(1.5)
    .with_gcd_category("utility")
    .with_mana_cost(30)
    .with_behavior("heal")
    .with_target_type("ally")
    .with_level_requirement(1)
    .build()
)

# Room-target AoE
SAMPLE_AOE_ABILITY = (
    AbilityTemplateBuilder()
    .with_id("earthquake")
    .with_name("Earthquake")
    .with_field("description", "Damages all enemies in the room")
    .with_cooldown(45.0)
    .with_gcd_category("combat")
    .with_mana_cost(100)
    .with_behavior("aoe_damage")
    .with_target_type("room")
    .with_level_requirement(10)
    .build()
)

# High level requirement
SAMPLE_HIGH_LEVEL_ABILITY = (
    AbilityTemplateBuilder()
    .with_id("ultimate")
    .with_name("Ultimate Ability")
    .with_field("description", "A powerful ultimate ability")
    .with_cooldown(120.0)
    .with_gcd_category("combat")
    .with_mana_cost(150)
    .with_behavior("ultimate_damage")
    .with_target_type("enemy")
    .with_level_requirement(20)
    .build()
)

# Rage cost ability
SAMPLE_RAGE_ABILITY = (
    AbilityTemplateBuilder()
    .with_id("execute")
    .with_name("Execute")
    .with_field("description", "A finishing move using rage")
    .with_cooldown(6.0)
    .with_gcd_category("combat")
    .with_rage_cost(40)
    .with_behavior("execute")
    .with_target_type("enemy")
    .with_level_requirement(8)
    .build()
)

# Energy cost ability
SAMPLE_ENERGY_ABILITY = (
    AbilityTemplateBuilder()
    .with_id("backstab")
    .with_name("Backstab")
    .with_field("description", "A stealthy strike using energy")
    .with_cooldown(0.0)
    .with_gcd_category("combat")
    .with_energy_cost(35)
    .with_behavior("stealth_attack")
    .with_target_type("enemy")
    .with_level_requirement(4)
    .build()
)

# No GCD ability
SAMPLE_NO_GCD_ABILITY = (
    AbilityTemplateBuilder()
    .with_id("defensive_stance")
    .with_name("Defensive Stance")
    .with_field("description", "Enter defensive stance (no GCD)")
    .with_cooldown(0.0)
    .with_gcd_category("none")
    .with_no_cost()
    .with_behavior("stance_change")
    .with_target_type("self")
    .with_level_requirement(5)
    .build()
)

# Multiple target types for testing
SAMPLE_ENEMY_TARGET = (
    AbilityTemplateBuilder()
    .with_id("enemy_ability")
    .with_name("Enemy Ability")
    .with_field("description", "Ability that targets enemies")
    .with_cooldown(0.0)
    .with_gcd_category("combat")
    .with_no_cost()
    .with_behavior("attack")
    .with_target_type("enemy")
    .with_level_requirement(1)
    .build()
)

SAMPLE_ALLY_TARGET = (
    AbilityTemplateBuilder()
    .with_id("ally_ability")
    .with_name("Ally Ability")
    .with_field("description", "Ability that targets allies")
    .with_cooldown(0.0)
    .with_gcd_category("utility")
    .with_no_cost()
    .with_behavior("buff")
    .with_target_type("ally")
    .with_level_requirement(1)
    .build()
)

# Damage scaling ability
SAMPLE_SCALED_ATTACK = (
    AbilityTemplateBuilder()
    .with_id("scaled_attack")
    .with_name("Scaled Attack")
    .with_field("description", "Attack with stat scaling")
    .with_cooldown(3.0)
    .with_gcd_category("combat")
    .with_mana_cost(25)
    .with_behavior("melee_attack")
    .with_target_type("enemy")
    .with_damage(10, 20)
    .with_scaling("strength", 1.5)
    .with_level_requirement(6)
    .build()
)

# Instant cast ability
SAMPLE_INSTANT_ABILITY = (
    AbilityTemplateBuilder()
    .with_id("instant_cast")
    .with_name("Instant Cast")
    .with_field("description", "Instant cast ability")
    .with_cooldown(0.0)
    .with_gcd_category("combat")
    .with_mana_cost(15)
    .with_behavior("instant_damage")
    .with_target_type("enemy")
    .with_level_requirement(1)
    .build()
)

# Long cooldown ability
SAMPLE_LONG_COOLDOWN = (
    AbilityTemplateBuilder()
    .with_id("long_cooldown")
    .with_name("Long Cooldown")
    .with_field("description", "Ability with long cooldown")
    .with_cooldown(300.0)
    .with_gcd_category("combat")
    .with_no_cost()
    .with_behavior("ultimate")
    .with_target_type("enemy")
    .with_level_requirement(15)
    .build()
)

# Utility ability
SAMPLE_UTILITY = (
    AbilityTemplateBuilder()
    .with_id("utility_ability")
    .with_name("Utility Ability")
    .with_field("description", "General utility ability")
    .with_cooldown(10.0)
    .with_gcd_category("utility")
    .with_mana_cost(10)
    .with_behavior("utility")
    .with_target_type("self")
    .with_level_requirement(1)
    .build()
)

# Complex multi-cost ability
SAMPLE_COMPLEX_COST = (
    AbilityTemplateBuilder()
    .with_id("complex_cost")
    .with_name("Complex Cost")
    .with_field("description", "Ability with mana cost")
    .with_cooldown(15.0)
    .with_gcd_category("combat")
    .with_mana_cost(50)
    .with_behavior("complex_attack")
    .with_target_type("enemy")
    .with_level_requirement(12)
    .build()
)

# Low level starter ability
SAMPLE_STARTER_ABILITY = (
    AbilityTemplateBuilder()
    .with_id("starter_ability")
    .with_name("Starter Ability")
    .with_field("description", "Basic starter ability")
    .with_cooldown(0.0)
    .with_gcd_category("combat")
    .with_no_cost()
    .with_behavior("basic_attack")
    .with_target_type("enemy")
    .with_level_requirement(1)
    .build()
)

# Mid-level ability
SAMPLE_MID_LEVEL = (
    AbilityTemplateBuilder()
    .with_id("mid_level")
    .with_name("Mid Level Ability")
    .with_field("description", "Mid-level ability")
    .with_cooldown(8.0)
    .with_gcd_category("combat")
    .with_mana_cost(40)
    .with_behavior("mid_attack")
    .with_target_type("enemy")
    .with_level_requirement(10)
    .build()
)
