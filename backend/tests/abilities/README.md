# Ability Testing Guide

This directory contains comprehensive tests for the Phase 9 ability system.

## Test Organization

- **conftest.py** - Pytest fixtures for ability testing
- **builders.py** - Builder pattern utilities for creating test data
- **../fixtures/ability_samples.py** - Sample ability templates for testing

## Available Fixtures

### Character Sheets

Pre-configured character sheets for different classes:

```python
def test_warrior_abilities(warrior_sheet):
    # warrior_sheet has rage pool and warrior abilities
    assert warrior_sheet.class_id == "warrior"
    assert "power_attack" in warrior_sheet.learned_abilities

def test_mage_abilities(mage_sheet):
    # mage_sheet has mana pool and mage abilities
    assert mage_sheet.class_id == "mage"
    assert "fireball" in mage_sheet.learned_abilities

def test_rogue_abilities(rogue_sheet):
    # rogue_sheet has energy pool and rogue abilities
    assert rogue_sheet.class_id == "rogue"
    assert "backstab" in rogue_sheet.learned_abilities
```

Special-purpose sheets:
- `low_level_sheet` - Level 1 character for testing level requirements
- `empty_resources_sheet` - Empty mana pool for testing resource validation

### World Entities

Pre-configured players and NPCs:

```python
def test_targeting(mock_warrior, mock_enemy_npc):
    # mock_warrior is a WorldPlayer with warrior character sheet
    # mock_enemy_npc is a WorldNpc for targeting
    pass

def test_aoe_abilities(mock_room_with_entities):
    # Room with warrior, enemy, and ally for AOE testing
    assert len(mock_room_with_entities.entity_ids) == 3
```

### System Mocks

Mock game systems for isolated testing:

```python
def test_damage_calculation(mock_combat_system):
    # CombatSystem instance for damage calculations
    pass

def test_buffs(mock_effect_system):
    # EffectSystem instance for buff/debuff testing
    pass

def test_events(mock_event_dispatcher):
    # EventDispatcher instance for event testing
    pass

def test_cooldowns(mock_time_manager):
    # TimeEventManager instance for cooldown testing
    pass
```

### Ability Executor

Fully configured AbilityExecutor:

```python
def test_ability_execution(ability_executor, mock_warrior):
    # AbilityExecutor with all dependencies wired up
    result = await ability_executor.execute_ability(
        player=mock_warrior,
        ability_id="melee_attack",
        target_name="TestGoblin"
    )
    assert result.success
```

### Behavior Context Factory

Create contexts for testing behavior functions directly:

```python
def test_fireball_behavior(behavior_context_factory, mock_mage, mock_enemy_npc):
    from tests.fixtures.ability_samples import SAMPLE_FIREBALL

    context = behavior_context_factory(
        caster=mock_mage,
        target=mock_enemy_npc,
        ability_template=SAMPLE_FIREBALL
    )

    # Call behavior function with context
    result = await fireball_behavior(**context.to_dict())
    assert result.success
```

### Cooldown Helper

Utilities for testing cooldown mechanics:

```python
def test_cooldown_validation(cooldown_helper, mock_warrior):
    # Set a cooldown that expires in 5 seconds
    cooldown_helper.set_cooldown(mock_warrior, "power_attack", 5.0)

    # Set a GCD that expires in 1 second
    cooldown_helper.set_gcd(mock_warrior, "combat", 1.0)

    # Clear all cooldowns for clean state
    cooldown_helper.clear_all_cooldowns(mock_warrior)
```

## Using Builders

For custom test scenarios, use builder utilities:

### AbilityTemplateBuilder

```python
from tests.abilities.builders import AbilityTemplateBuilder

def test_custom_ability():
    ability = (AbilityTemplateBuilder()
               .with_id("test_fireball")
               .with_behavior("fireball")
               .with_damage(20, 30)
               .with_mana_cost(50)
               .with_cooldown(5.0)
               .with_scaling("intelligence", 0.6)
               .build())

    assert ability["damage_min"] == 20
    assert ability["resource_cost"]["amount"] == 50
```

### CharacterSheetBuilder

```python
from tests.abilities.builders import CharacterSheetBuilder

def test_custom_character():
    sheet = (CharacterSheetBuilder()
             .with_class("warrior")
             .with_level(10)
             .with_rage_pool(current=75, maximum=100)
             .with_learned_abilities(["melee_attack", "whirlwind"])
             .build())

    assert sheet.level == 10
    assert sheet.resources["rage"].current == 75
```

### WorldPlayerBuilder

```python
from tests.abilities.builders import WorldPlayerBuilder

def test_custom_player():
    player = (WorldPlayerBuilder()
              .with_name("TestHero")
              .with_stats(strength=20, intelligence=8)
              .with_health(150, 150)
              .with_character_sheet(custom_sheet)
              .build())

    assert player.strength == 20
    assert player.max_health == 150
```

### WorldNpcBuilder

```python
from tests.abilities.builders import WorldNpcBuilder

def test_custom_npc():
    boss = (WorldNpcBuilder()
            .with_name("DragonBoss")
            .with_template("ancient_dragon")
            .with_health(1000, 1000)
            .with_stats(strength=25, intelligence=20)
            .build())

    assert boss.max_health == 1000
```

## Sample Ability Templates

Pre-defined ability templates for common test scenarios:

```python
from tests.fixtures.ability_samples import (
    SAMPLE_MELEE_ATTACK,
    SAMPLE_FIREBALL,
    SAMPLE_WHIRLWIND,
    ALL_COMBAT_ABILITIES,
    ALL_MAGE_ABILITIES,
)

def test_melee_damage():
    ability = SAMPLE_MELEE_ATTACK
    assert ability["damage_min"] == 5
    assert ability["damage_max"] == 10

def test_all_mage_abilities():
    for ability in ALL_MAGE_ABILITIES:
        assert ability["resource_cost"]["type"] == "mana"
```

Available collections:
- `ALL_COMBAT_ABILITIES` - Combat damage abilities
- `ALL_PASSIVE_ABILITIES` - Buffs and passives
- `ALL_CROWD_CONTROL_ABILITIES` - Stuns, polymorphs
- `ALL_UTILITY_ABILITIES` - Non-combat abilities
- `ALL_MAGE_ABILITIES` - Mage-specific abilities
- `ALL_WARRIOR_ABILITIES` - Warrior-specific abilities
- `ALL_ROGUE_ABILITIES` - Rogue-specific abilities

## Test Patterns

### Testing Damage Calculation

```python
@pytest.mark.asyncio
async def test_fireball_damage(behavior_context_factory, mock_mage, mock_enemy_npc):
    from tests.fixtures.ability_samples import SAMPLE_FIREBALL
    from app.engine.systems.ability_behaviors import fireball_behavior

    context = behavior_context_factory(mock_mage, mock_enemy_npc, SAMPLE_FIREBALL)
    result = await fireball_behavior(**context.to_dict())

    assert result.success
    assert result.damage_dealt > 0
    assert mock_enemy_npc.entity_id in result.targets_hit
```

### Testing Resource Consumption

```python
def test_ability_consumes_mana(mage_sheet):
    initial_mana = mage_sheet.resources["mana"].current

    # Simulate mana consumption
    cost = 50
    mage_sheet.resources["mana"].current -= cost

    assert mage_sheet.resources["mana"].current == initial_mana - cost
```

### Testing Validation

```python
@pytest.mark.asyncio
async def test_insufficient_resources(ability_executor, empty_resources_sheet):
    from tests.abilities.builders import WorldPlayerBuilder

    player = (WorldPlayerBuilder()
              .with_character_sheet(empty_resources_sheet)
              .build())

    result = await ability_executor.execute_ability(
        player=player,
        ability_id="fireball",
        target_name="TestEnemy"
    )

    assert not result.success
    assert "insufficient mana" in result.error.lower()
```

### Testing Cooldowns

```python
@pytest.mark.asyncio
async def test_cooldown_prevents_cast(ability_executor, cooldown_helper, mock_warrior):
    cooldown_helper.set_cooldown(mock_warrior, "power_attack", 5.0)

    result = await ability_executor.execute_ability(
        player=mock_warrior,
        ability_id="power_attack",
        target_name="TestEnemy"
    )

    assert not result.success
    assert "cooldown" in result.error.lower()
```

## Running Tests

Run all ability tests:
```bash
pytest backend/tests/abilities/ -v
```

Run specific test file:
```bash
pytest backend/tests/abilities/test_ability_executor.py -v
```

Run tests with specific marker:
```bash
pytest -m abilities -v
```

Run with coverage:
```bash
pytest backend/tests/abilities/ --cov=app.engine.systems.abilities --cov-report=html
```
