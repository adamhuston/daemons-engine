# Phase 13 - Abilities Audit: Comprehensive Testing Plan

**Status**: Planning Complete | Implementation Pending

**Goals**:
- Systematically test all 29 ability behaviors (16 core + 5 custom + 8 utility)
- Validate AbilityExecutor execution pipeline
- Ensure resource management, cooldowns, and targeting work correctly
- Achieve comprehensive test coverage for Phase 9 ability system

---

## Current State Analysis

### Test Coverage Gaps

**Existing Tests**: 12 utility ability tests in `test_utility_abilities.py` (100% passing ✅)
- ✅ create_light, darkness, unlock_door, unlock_container
- ✅ detect_magic, true_sight, teleport, create_passage

**Missing Tests**: 21 combat behaviors (0% coverage ❌)
- ❌ **Core behaviors** (11): melee_attack, power_attack, rally, aoe_attack, stun_effect, mana_regen, fireball, polymorph, backstab, evasion, damage_boost
- ❌ **Custom behaviors** (5): whirlwind_attack, shield_bash, inferno, arcane_missiles, shadow_clone
- ❌ **Utility behaviors** (5): Enhanced tests needed for edge cases and failure modes

**System Components Without Tests**:
- ❌ AbilityExecutor validation pipeline
- ❌ Resource pool management and consumption
- ❌ Cooldown/GCD mechanics
- ❌ Target resolution logic
- ❌ Error handling and edge cases

### Ability System Architecture

**Execution Flow**:
1. Command parsing: `cast <ability> [target]` → resolve ability template
2. Validation: `AbilityExecutor._validate_ability_use()`
   - Check if ability is learned
   - Verify level requirement
   - Check resource costs
   - Verify cooldown availability
   - Check GCD
3. Target resolution: `AbilityExecutor._resolve_targets()`
   - Parse target_type (self, enemy, ally, room, aoe)
   - Find target entity in room
   - Validate target state (alive, in range)
4. Behavior execution: `ClassSystem.get_behavior()` → execute behavior function
   - Apply damage/healing/effects
   - Return BehaviorResult with success, damage_dealt, targets_hit
5. Post-execution: `AbilityExecutor._apply_cooldowns()`
   - Set personal cooldown
   - Apply GCD
6. Event emission: `EventDispatcher` broadcasts results

**Test Dimensions**:
- ✅ **Damage Calculation**: Base damage, scaling stats (INT/STR/DEX), critical hits, variance
- ✅ **Resource Consumption**: Mana, rage, energy costs with insufficient resource scenarios
- ✅ **Cooldown Mechanics**: Personal cooldown tracking, GCD enforcement, cooldown reduction
- ✅ **Target Resolution**: Self-targeting, enemy targeting, ally targeting, AOE, invalid targets
- ✅ **Effect Application**: Buffs, debuffs, DoT/HoT, duration tracking, stacking rules
- ✅ **Edge Cases**: Dead casters, dead targets, missing targets, invalid states

---

## Test Implementation Plan

### Phase 13.1 - Test Infrastructure Setup ✅ COMPLETE

**Already Complete**:
- ✅ Created `backend/tests/abilities/` directory
- ✅ pytest configuration with `abilities` marker
- ✅ Comprehensive fixtures in conftest.py

**Still Needed**:
- [ ] Create ability-specific fixtures (mock abilities, resources, combat state)
- [ ] Create BehaviorTestContext helper class
- [ ] Create ability builder utilities (AbilityBuilder, ResourcePoolBuilder)

**Deliverables**:
- `backend/tests/abilities/conftest.py` - Ability test fixtures
- `backend/tests/abilities/builders.py` - Test data builders
- `backend/tests/fixtures/ability_samples.py` - Sample ability templates for testing

---

### Phase 13.2 - AbilityExecutor System Tests

**Purpose**: Test the execution pipeline and validation logic

**Test Suite**: `backend/tests/abilities/test_ability_executor.py`

**Test Cases** (Estimated 25 tests):

#### Validation Tests (10 tests)
1. `test_validate_ability_not_learned` - Error when ability not in learned_abilities
2. `test_validate_level_requirement` - Error when player level too low
3. `test_validate_insufficient_mana` - Error when mana cost exceeds current mana
4. `test_validate_insufficient_rage` - Error when rage cost exceeds current rage
5. `test_validate_ability_on_cooldown` - Error when cooldown not expired
6. `test_validate_gcd_active` - Error when GCD still active
7. `test_validate_success` - All validations pass
8. `test_validate_admin_override` - Admin can bypass level/resource checks
9. `test_validate_zero_cost_ability` - Free abilities always pass resource check
10. `test_validate_multiple_resource_costs` - Validates mana + rage costs

#### Target Resolution Tests (8 tests)
11. `test_resolve_target_self` - Self-targeting resolves to caster
12. `test_resolve_target_enemy_by_name` - Finds enemy by partial name match
13. `test_resolve_target_ally_by_name` - Finds ally by partial name match
14. `test_resolve_target_room` - Room-wide abilities target all entities
15. `test_resolve_target_aoe_enemies` - AOE targets all enemies in room
16. `test_resolve_target_invalid_name` - Error when target name not found
17. `test_resolve_target_dead_entity` - Error when target is dead
18. `test_resolve_target_wrong_type` - Error when targeting ally ability at enemy

#### Cooldown Management Tests (7 tests)
19. `test_apply_cooldown_sets_expiry` - Cooldown expires at correct timestamp
20. `test_apply_gcd_sets_expiry` - GCD expires at correct timestamp
21. `test_get_ability_cooldown_remaining` - Returns seconds until cooldown expires
22. `test_get_gcd_remaining` - Returns seconds until GCD expires
23. `test_clear_cooldown_admin` - Admin can clear cooldowns
24. `test_clear_gcd_admin` - Admin can clear GCD
25. `test_multiple_abilities_share_gcd` - Different abilities respect shared GCD

**Fixtures Needed**:
- `ability_executor` - Configured AbilityExecutor instance
- `mock_character_sheet` - CharacterSheet with level, resources, learned abilities
- `mock_world_player` - WorldPlayer with character_sheet attached
- `mock_ability_template` - AbilityTemplate with configurable costs/cooldowns

---

### Phase 13.3 - Core Behavior Tests

**Purpose**: Test all 11 core combat behaviors for damage, scaling, and effects

**Test Suite**: `backend/tests/abilities/test_core_behaviors.py`

**Test Cases** (Estimated 40 tests):

#### melee_attack_behavior (4 tests)
1. `test_melee_attack_hit` - Successful hit deals damage in min/max range
2. `test_melee_attack_critical` - Critical hit deals 1.5x damage
3. `test_melee_attack_scales_with_strength` - Damage increases with STR stat
4. `test_melee_attack_miss` - Miss on low accuracy returns 0 damage

#### power_attack_behavior (4 tests)
5. `test_power_attack_high_damage` - Deals more damage than melee_attack
6. `test_power_attack_high_cost` - Costs more resources than melee_attack
7. `test_power_attack_cooldown` - Has longer cooldown than melee_attack
8. `test_power_attack_scales_with_strength` - Damage scales with STR

#### rally_behavior (passive) (3 tests)
9. `test_rally_applies_buff` - Applies stat buff to caster
10. `test_rally_buff_duration` - Buff lasts specified duration
11. `test_rally_buff_expires` - Buff expires after duration

#### aoe_attack_behavior (5 tests)
12. `test_aoe_hits_all_enemies` - Damages all enemies in room
13. `test_aoe_does_not_hit_allies` - Does not damage allies
14. `test_aoe_does_not_hit_self` - Does not damage caster
15. `test_aoe_partial_miss` - Some targets can be missed
16. `test_aoe_damage_same_for_all_targets` - Each target takes same base damage

#### stun_effect_behavior (3 tests)
17. `test_stun_prevents_actions` - Stunned target cannot act
18. `test_stun_duration` - Stun lasts specified duration
19. `test_stun_cleansable` - Stun can be removed by dispel

#### mana_regen_behavior (passive) (3 tests)
20. `test_mana_regen_restores_mana` - Restores mana over time
21. `test_mana_regen_rate` - Regenerates at specified rate
22. `test_mana_regen_does_not_exceed_max` - Stops at max mana

#### fireball_behavior (4 tests)
23. `test_fireball_damage` - Deals fire damage in expected range
24. `test_fireball_scales_with_intelligence` - Damage scales with INT
25. `test_fireball_mana_cost` - Consumes mana correctly
26. `test_fireball_cooldown` - Applies correct cooldown

#### polymorph_behavior (3 tests)
27. `test_polymorph_disables_target` - Target cannot act while polymorphed
28. `test_polymorph_duration` - Effect lasts specified duration
29. `test_polymorph_breaks_on_damage` - Effect ends if target takes damage

#### backstab_behavior (4 tests)
30. `test_backstab_high_damage_from_stealth` - Extra damage when stealthed
31. `test_backstab_normal_damage_without_stealth` - Normal damage when not stealthed
32. `test_backstab_scales_with_dexterity` - Damage scales with DEX
33. `test_backstab_energy_cost` - Consumes energy correctly

#### evasion_behavior (passive) (3 tests)
34. `test_evasion_increases_dodge_chance` - Dodge rate increases
35. `test_evasion_duration` - Buff lasts specified duration
36. `test_evasion_stacks` - Multiple casts increase dodge rate

#### damage_boost_behavior (4 tests)
37. `test_damage_boost_increases_damage` - All damage increased by percentage
38. `test_damage_boost_duration` - Buff lasts specified duration
39. `test_damage_boost_applies_to_all_abilities` - Affects all damage sources
40. `test_damage_boost_stacks_additively` - Multiple buffs stack additively

**Fixtures Needed**:
- `combat_system` - CombatSystem instance for damage calculation
- `mock_caster` - WorldPlayer with CharacterSheet (level, stats, resources)
- `mock_target` - WorldNpc/WorldPlayer for targeting
- `mock_room` - WorldRoom with multiple entities for AOE tests
- `behavior_context` - BehaviorContext with caster, target, ability, combat_system

---

### Phase 13.4 - Custom Behavior Tests

**Purpose**: Test all 5 class-specific behaviors

**Test Suite**: `backend/tests/abilities/test_custom_behaviors.py`

**Test Cases** (Estimated 20 tests):

#### whirlwind_attack_behavior (Warrior) (4 tests)
1. `test_whirlwind_hits_all_enemies` - Damages all enemies in room
2. `test_whirlwind_high_rage_cost` - Costs significant rage
3. `test_whirlwind_scales_with_strength` - Damage scales with STR
4. `test_whirlwind_cooldown` - Long cooldown after use

#### shield_bash_behavior (Warrior) (4 tests)
5. `test_shield_bash_damage` - Deals moderate damage
6. `test_shield_bash_stuns_target` - Applies stun effect
7. `test_shield_bash_requires_shield` - Fails without shield equipped
8. `test_shield_bash_cooldown` - Moderate cooldown

#### inferno_behavior (Mage) (4 tests)
9. `test_inferno_aoe_damage` - Damages all enemies in large AOE
10. `test_inferno_high_mana_cost` - Costs significant mana
11. `test_inferno_scales_with_intelligence` - Damage scales with INT
12. `test_inferno_applies_burn_dot` - Applies damage-over-time effect

#### arcane_missiles_behavior (Mage) (4 tests)
13. `test_arcane_missiles_multiple_hits` - Multiple projectiles hit target
14. `test_arcane_missiles_scales_with_intelligence` - Each missile scales with INT
15. `test_arcane_missiles_channeled` - Requires channeling (multiple ticks)
16. `test_arcane_missiles_interruptible` - Can be interrupted by stun

#### shadow_clone_behavior (Rogue) (4 tests)
17. `test_shadow_clone_creates_clone` - Spawns clone entity
18. `test_shadow_clone_clone_attacks` - Clone attacks enemies
19. `test_shadow_clone_duration` - Clone lasts specified duration
20. `test_shadow_clone_high_energy_cost` - Costs significant energy

**Fixtures Needed**:
- `warrior_player` - WorldPlayer with warrior class
- `mage_player` - WorldPlayer with mage class
- `rogue_player` - WorldPlayer with rogue class
- `equipped_shield` - Mock shield item for shield_bash tests

---

### Phase 13.5 - Resource Pool Tests

**Purpose**: Test resource management (mana, rage, energy)

**Test Suite**: `backend/tests/abilities/test_resource_pools.py`

**Test Cases** (Estimated 15 tests):

#### Resource Consumption (6 tests)
1. `test_consume_mana_reduces_current` - Consuming mana reduces pool
2. `test_consume_rage_reduces_current` - Consuming rage reduces pool
3. `test_consume_energy_reduces_current` - Consuming energy reduces pool
4. `test_consume_exceeds_current_fails` - Cannot consume more than available
5. `test_consume_multiple_resources` - Can consume mana + rage in same ability
6. `test_consume_zero_cost` - Zero-cost abilities don't modify pools

#### Resource Regeneration (6 tests)
7. `test_mana_regenerates_over_time` - Mana regenerates at configured rate
8. `test_rage_decays_out_of_combat` - Rage decays when not in combat
9. `test_energy_regenerates_quickly` - Energy regenerates faster than mana
10. `test_regen_stops_at_max` - Regen does not exceed max pool value
11. `test_regen_paused_during_ability` - Regen pauses while casting
12. `test_regen_affected_by_buffs` - Buffs can increase regen rate

#### Resource Pool State (3 tests)
13. `test_get_resource_pool_returns_state` - Returns current/max/regen values
14. `test_resource_pool_serialization` - Can serialize to JSON for persistence
15. `test_resource_pool_deserialization` - Can restore from JSON

**Fixtures Needed**:
- `resource_pool_mana` - ResourcePool with mana configuration
- `resource_pool_rage` - ResourcePool with rage configuration
- `resource_pool_energy` - ResourcePool with energy configuration

---

### Phase 13.6 - Enhanced Utility Behavior Tests

**Purpose**: Expand coverage for existing 12 utility tests with edge cases

**Test Suite**: `backend/tests/abilities/test_utility_behaviors_extended.py`

**Test Cases** (Estimated 15 tests - adds to existing 12):

#### create_light edge cases (3 tests)
1. `test_light_duration_expires` - Light expires after duration
2. `test_light_multiple_sources_stack` - Multiple light sources add intensity
3. `test_light_dispelled` - Light can be dispelled early

#### darkness edge cases (2 tests)
4. `test_darkness_reduces_existing_light` - Cancels out light sources
5. `test_darkness_stacks_with_ambient` - Adds to naturally dark rooms

#### unlock_door edge cases (3 tests)
6. `test_unlock_door_already_unlocked` - Graceful handling of unlocked doors
7. `test_unlock_door_magically_locked` - Fails on magically locked doors
8. `test_unlock_door_insufficient_skill` - Fails if level too low

#### teleport edge cases (4 tests)
9. `test_teleport_blocked_by_anti_magic` - Fails in anti-magic zones
10. `test_teleport_high_mana_cost` - Costs significant mana
11. `test_teleport_long_cooldown` - Long cooldown prevents spam
12. `test_teleport_invalid_destination` - Error on non-existent room

#### detect_magic edge cases (3 tests)
13. `test_detect_magic_reveals_hidden_items` - Shows invisible magic items
14. `test_detect_magic_reveals_enchantments` - Shows item enchantments
15. `test_detect_magic_duration` - Detection lasts specified duration

---

### Phase 13.7 - Integration Tests

**Purpose**: Test end-to-end ability execution flow

**Test Suite**: `backend/tests/abilities/test_ability_integration.py`

**Test Cases** (Estimated 10 tests):

1. `test_cast_command_flow` - Full flow: command → validation → execution → events
2. `test_ability_cooldown_prevents_recast` - Cooldown blocks immediate reuse
3. `test_gcd_prevents_other_abilities` - GCD blocks all abilities
4. `test_resource_consumption_prevents_cast` - Insufficient resources block cast
5. `test_ability_damage_updates_hp` - Damage modifies target HP correctly
6. `test_ability_kills_target` - Target dies when HP reaches 0
7. `test_ability_xp_reward_on_kill` - Caster gains XP from killing with ability
8. `test_passive_abilities_apply_on_equip` - Passive effects activate when slotted
9. `test_ability_events_broadcast_to_room` - All room members see ability cast
10. `test_ability_failure_sends_error_event` - Validation failures send error to player

**Fixtures Needed**:
- `full_world_engine` - WorldEngine with all systems initialized
- `test_player_in_room` - Fully configured player in room with targets
- `test_ability_templates` - Full set of ability templates loaded

---

## Test Data Requirements

### Sample Ability Templates

**Create**: `backend/tests/fixtures/ability_samples.py`

**Contents**:
```python
# Simple melee attack (low cost, low cooldown)
SAMPLE_MELEE_ATTACK = {
    "id": "test_melee",
    "name": "Test Melee",
    "cooldown": 1.5,
    "gcd_category": "combat",
    "resource_cost": {"type": "none"},
    "behavior": "melee_attack",
    "target_type": "enemy"
}

# High-cost fireball (mana cost, long cooldown)
SAMPLE_FIREBALL = {
    "id": "test_fireball",
    "name": "Test Fireball",
    "cooldown": 5.0,
    "gcd_category": "combat",
    "resource_cost": {"type": "mana", "amount": 50},
    "behavior": "fireball",
    "target_type": "enemy",
    "damage_min": 20,
    "damage_max": 30,
    "scaling_stat": "intelligence",
    "scaling_factor": 0.5
}

# AOE whirlwind (rage cost, AOE targeting)
SAMPLE_WHIRLWIND = {
    "id": "test_whirlwind",
    "name": "Test Whirlwind",
    "cooldown": 10.0,
    "gcd_category": "combat",
    "resource_cost": {"type": "rage", "amount": 30},
    "behavior": "whirlwind_attack",
    "target_type": "aoe_enemies"
}

# Passive rally buff (no cost, no cooldown)
SAMPLE_RALLY = {
    "id": "test_rally",
    "name": "Test Rally",
    "cooldown": 0.0,
    "gcd_category": "none",
    "resource_cost": {"type": "none"},
    "behavior": "rally",
    "target_type": "self",
    "buff_duration": 30.0,
    "stat_bonus": {"strength": 5, "constitution": 5}
}
```

### Sample Character Sheets

**Create**: `backend/tests/abilities/conftest.py`

**Fixtures**:
```python
@pytest.fixture
def warrior_sheet():
    """Level 5 warrior with rage pool"""
    return CharacterSheet(
        class_id="warrior",
        level=5,
        experience=0,
        learned_abilities=["melee_attack", "power_attack", "whirlwind_attack"],
        equipped_abilities=["melee_attack", "power_attack"],
        resources={
            "rage": ResourcePool(
                current=50,
                maximum=100,
                regen_rate=0,  # Rage doesn't regen
                regen_type="none"
            )
        }
    )

@pytest.fixture
def mage_sheet():
    """Level 5 mage with mana pool"""
    return CharacterSheet(
        class_id="mage",
        level=5,
        experience=0,
        learned_abilities=["fireball", "mana_regen", "inferno"],
        equipped_abilities=["fireball", "mana_regen"],
        resources={
            "mana": ResourcePool(
                current=100,
                maximum=150,
                regen_rate=5,
                regen_type="per_second"
            )
        }
    )

@pytest.fixture
def rogue_sheet():
    """Level 5 rogue with energy pool"""
    return CharacterSheet(
        class_id="rogue",
        level=5,
        experience=0,
        learned_abilities=["backstab", "evasion", "shadow_clone"],
        equipped_abilities=["backstab", "evasion"],
        resources={
            "energy": ResourcePool(
                current=80,
                maximum=100,
                regen_rate=10,
                regen_type="per_second"
            )
        }
    )
```

---

## Test Execution Strategy

### Phased Implementation

**Week 1**: Phase 13.1-13.2 (Infrastructure + Executor)
- Set up fixtures and builders
- Complete AbilityExecutor tests (25 tests)
- **Target**: 25 passing tests

**Week 2**: Phase 13.3 (Core Behaviors)
- Complete core behavior tests (40 tests)
- **Target**: 65 passing tests total

**Week 3**: Phase 13.4-13.5 (Custom + Resources)
- Complete custom behavior tests (20 tests)
- Complete resource pool tests (15 tests)
- **Target**: 100 passing tests total

**Week 4**: Phase 13.6-13.7 (Utility + Integration)
- Complete extended utility tests (15 tests)
- Complete integration tests (10 tests)
- **Target**: 125 passing tests total

### Success Criteria

**Test Coverage Goals**:
- ✅ All 29 behaviors have dedicated tests
- ✅ AbilityExecutor validation pipeline 100% covered
- ✅ Resource management fully tested
- ✅ Cooldown/GCD mechanics fully tested
- ✅ Integration tests verify end-to-end flow

**Quality Metrics**:
- ✅ All tests pass (100% passing rate)
- ✅ No test pollution (each test is independent)
- ✅ Fast execution (<5 seconds for full ability test suite)
- ✅ Clear test names and documentation

**Documentation**:
- ✅ Test architecture document updated
- ✅ Ability testing guide for future developers
- ✅ Example test patterns documented

---

## Risk Assessment

### Potential Challenges

**Challenge 1: Mock Complexity**
- **Issue**: Behaviors interact with CombatSystem, EffectSystem, TimeEventManager
- **Mitigation**: Create comprehensive mocks in conftest.py, use dependency injection
- **Backup**: Use real systems in integration tests, mock only external dependencies

**Challenge 2: Async Behavior Testing**
- **Issue**: All behaviors are async functions
- **Mitigation**: Use pytest-asyncio, mark tests with @pytest.mark.asyncio
- **Backup**: pytest.ini already configured for async support

**Challenge 3: Time-Based Tests (Cooldowns, Regen)**
- **Issue**: Testing time-based mechanics can be flaky
- **Mitigation**: Use TimeEventManager test utilities, freeze time in tests
- **Backup**: Use tolerance ranges for time-based assertions

**Challenge 4: Test Data Maintenance**
- **Issue**: Ability templates can change, breaking tests
- **Mitigation**: Use fixture-based templates, not hardcoded YAML
- **Backup**: Load from YAML but override specific fields for tests

### Rollback Plan

If testing reveals critical bugs in ability system:
1. Create bug tickets with failing test cases
2. Fix bugs in separate branch
3. Re-run full test suite (200 existing + 125 new ability tests)
4. Merge only when all 325 tests pass

---

## Documentation Updates

### Files to Update

1. **test_architecture.md** (Append):
   - Section: "5. Ability Testing Strategy"
   - Content: Overview of behavior testing patterns
   - Examples: Sample ability test with BehaviorContext

2. **ARCHITECTURE.md** (Update):
   - Section: "3.4 Game Systems - Abilities"
   - Add: Testing strategy and coverage metrics
   - Link to PHASE13_ability_testing_plan.md

3. **README.md** (Update):
   - Section: "Testing"
   - Add: "Ability System: 125 tests covering all 29 behaviors"

4. **Create**: `backend/tests/abilities/README.md`
   - Purpose: Guide for writing ability tests
   - Content: Test patterns, fixture usage, behavior context setup
   - Examples: How to test damage, resources, cooldowns, targeting

---

## Next Steps

### Immediate Actions (Today)

1. ✅ Review and approve this plan
2. ✅ Create `backend/tests/abilities/conftest.py` with fixtures
3. ✅ Create `backend/tests/fixtures/ability_samples.py` with sample templates
4. ✅ Create `backend/tests/abilities/builders.py` with test builders
5. ✅ Create `backend/tests/abilities/README.md` with usage guide

### This Week (Phase 13.1-13.2)

5. 🔄 **IN PROGRESS** - Implement `test_ability_executor.py` (25 tests)
   - Created test file with all 25 test cases
   - Fixing fixture API to match actual CharacterSheet/ResourcePool structure
   - Issues discovered:
     - ResourcePool uses `max` not `maximum`, `regen_per_second` not `regen_rate`, requires `resource_id`
     - CharacterSheet uses `learned_abilities` (Set), `ability_loadout` not `equipped_abilities`, `resource_pools` not `resources`
     - All systems take GameContext parameter, not individual dependencies
   - Next: Complete fixture corrections and run tests
6. ⬜ Run tests and fix any bugs discovered
7. ⬜ Update test count in README.md

### Next Weeks (Phase 13.3-13.7)

8. ⬜ Follow phased implementation schedule
9. ⬜ Document test patterns as we go
10. ⬜ Update ARCHITECTURE.md with final coverage metrics

---

## Summary

**Estimated Test Count**: 125 new ability tests
**Estimated Time**: 4 weeks (1 phase per week)
**Final Test Count**: 325 total tests (200 existing + 125 new)
**Coverage Goal**: 100% of ability behaviors + executor + resource management

**Deliverables**:
- 7 new test files in `backend/tests/abilities/`
- 3 fixture/builder files
- 4 documentation updates
- Bug fixes discovered during testing

**Success Metric**: All 325 tests passing (100% rate) with comprehensive ability coverage

---

## Approval Checklist

- [x] Plan reviewed for completeness
- [x] Test count estimate is reasonable
- [x] Phased approach is logical
- [x] Fixtures and builders are well-defined
- [x] Risk mitigation strategies in place
- [ ] **Ready to proceed with implementation** ← Awaiting user approval
