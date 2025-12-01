# Phase 14 - Entity Abilities: Technical Design Document

---

## 1. Overview

This document analyzes the ability system architecture and outlines the technical changes required to extend ability support from players to **all entities** (players, NPCs, magic items, environmental objects).

**Previous Approach**: Only `WorldPlayer` entities could use the class/ability system (Phase 9).
**New Approach**: Move `character_sheet` to `WorldEntity` base class, enabling universal ability support.

**Why This Change**:
- **100% Code Reuse**: All entity types use the same ability mechanics
- **Magic Items**: Staffs with spell charges, weapons with special attacks
- **Environmental Objects**: Explosive barrels (AoE damage), healing fountains (periodic heal)
- **Destructible Objects**: Trigger abilities on death/activation
- **Future-Proof**: Any new entity type automatically has ability support

---

## 2. Current Architecture Analysis

### 2.1 Character Sheet Implementation (Phase 14.1 Refactored)

**Location**: `backend/app/engine/world.py`

```python
@dataclass
class WorldEntity:
    # ... core entity fields ...

    # Phase 14: Character class and abilities
    # Moved to WorldEntity to enable abilities on NPCs, magic items, and environment
    character_sheet: CharacterSheet | None = None  # Optional - backward compatible
```

**Helper Methods on WorldEntity** (inherited by all subclasses):
- `has_character_sheet() -> bool`
- `get_class_id() -> str | None`
- `get_resource_pool(resource_id: str) -> ResourcePool | None`
- `get_learned_abilities() -> set[str]`
- `get_ability_loadout() -> list[AbilitySlot]`
- `has_learned_ability(ability_id: str) -> bool`

**Current Usage**:
- Commands: `cast`, `abilities`, `resources` all work with any entity that has a character_sheet
- AbilityExecutor: Should be updated to accept `WorldEntity` instead of `WorldPlayer`
- Resource regen: Any entity with resource pools can regenerate

### 2.2 AbilityExecutor Assumptions (NEEDS UPDATE)

**Location**: `backend/app/engine/systems/abilities.py`

**Type Constraints** (TO BE REFACTORED):
```python
class AbilityExecutor:
    async def execute_ability(
        self,
        caster: WorldPlayer,  # ❌ Should be WorldEntity
        ability_id: str,
        target_id: Optional[str] = None,
        target_entity: Optional[WorldEntity] = None,
    ) -> AbilityExecutionResult:
```

**Other methods needing update**:
- `_validate_ability_use(caster: WorldPlayer, ability_id: str)` → `WorldEntity`
- `_resolve_targets(caster: WorldPlayer, ...)` → `WorldEntity`
- `_apply_cooldowns(caster: WorldPlayer, ability: AbilityTemplate)` → `WorldEntity`

**Cooldown Tracking**:
```python
# Uses player_id as key - already generic enough (uses entity_id)
self.cooldowns: Dict[str, Dict[str, Tuple[float, bool]]] = {}
self.gcd_state: Dict[str, Tuple[float, str]] = {}
```

### 2.3 Ability Behaviors (Already Entity-Agnostic!)

**Location**: `backend/app/engine/systems/ability_behaviors/`

**Good News**: Behaviors already use generic typing:
```python
async def melee_attack_behavior(
    caster,  # WorldEntity
    target,  # WorldEntity
    ability: AbilityTemplate,
    combat_system,
) -> BehaviorResult:
```

**Action Required**: Verify all behaviors accept `WorldEntity` in function signatures.

### 2.4 BehaviorScript vs ClassSystem (Complementary Systems!)

**BehaviorScript Pattern** (backend/app/engine/behaviors/):
- Used for NPC AI (wandering, aggression, idle messages)
- Event-driven hooks: `on_spawn`, `on_combat_tick`, `on_player_enter`, etc.
- Simple tag-based system: `behaviors: [aggressive, wanders_sometimes]`
- **AI Decision Layer**: "Should I attack? Should I wander?"

**ClassSystem Pattern** (backend/app/engine/systems/classes.py):
- Used for entity abilities (players, NPCs, items)
- Template-driven: YAML defines classes, abilities, resources
- Complex validation: cooldowns, resource costs, target resolution
- Managed by `AbilityExecutor`

**Integration Strategy**:
- Keep both systems separate but connected
- Add new BehaviorScript hooks for ability usage: `on_combat_action()`, `on_low_health()`
- Entities with `character_sheet` can use abilities via their behaviors
- Entities without `character_sheet` continue using existing behavior system (NPCs) or no abilities at all (items)

**Examples**:
- **NPC Mage**: BehaviorScript decides "attack player", ClassSystem executes "fireball" ability
- **Magic Staff**: Item pickup grants temporary character_sheet with "fire bolt" ability
- **Explosive Barrel**: Environmental object has "explode" ability triggered on destruction

---

## 3. Files Requiring Changes

### Phase 14.1 - Universal Entity Ability Support ✅ **COMPLETE**

| File | Changes Required | Status |
|------|-----------------|--------|
| `backend/app/engine/world.py` | Move `character_sheet` to WorldEntity base class<br>Move 6 helper methods to WorldEntity<br>Remove duplicates from WorldPlayer/WorldNpc<br>Update NpcTemplate with `class_id`, `default_abilities`, `ability_loadout` | ✅ Complete |
| `backend/app/models.py` | Add columns to NpcTemplate model | ✅ Complete |
| `backend/alembic/versions/l4m5n6o7p8q9_phase14_npc_abilities.py` | Create migration for NPC ability fields | ✅ Complete |

**Outcome**: All entities (players, NPCs, future items/environment) can now have abilities!

### Phase 14.2 - Ability System Generalization ✅ **COMPLETE**

| File | Changes Required | Status |
|------|-----------------|--------|
| `backend/app/engine/systems/abilities.py` | Change all `WorldPlayer` → `WorldEntity`<br>Update method type hints and docstrings | ✅ Complete |
| `backend/app/engine/systems/ability_behaviors/core.py` | Already entity-agnostic (untyped caster/target) | ✅ Verified |
| `backend/app/engine/systems/ability_behaviors/custom.py` | Already entity-agnostic (untyped caster/target) | ✅ Verified |
| `backend/app/engine/systems/ability_behaviors/utility.py` | Already entity-agnostic (untyped caster/target) | ✅ Verified |
| `backend/app/engine/engine.py` | Add resource regen for NPCs with character_sheet | ✅ Complete |

**Outcome**: AbilityExecutor now accepts any WorldEntity (players, NPCs, items) as caster! All 25 ability tests pass.

### Phase 14.3 - NPC AI Integration ✅ **COMPLETE**

| File | Changes Required | Status |
|------|-----------------|--------|
| `backend/app/engine/behaviors/base.py` | Add ability hooks to BehaviorScript<br>Extend BehaviorContext with ability helpers<br>Add `cast_ability` to BehaviorResult | ✅ Complete |
| `backend/app/engine/behaviors/combat_caster.py` | Create CasterAI, TacticalCasterAI behaviors (new file) | ✅ Complete |
| `backend/app/engine/behaviors/combat_brute.py` | Create BruteAI, BerserkerAI behaviors (new file) | ✅ Complete |
| `backend/app/engine/systems/combat.py` | Integrate ability casting into combat flow via on_combat_action hook | ✅ Complete |
| `backend/app/engine/engine.py` | Handle `cast_ability` in _process_behavior_result<br>Add _npc_cast_ability helper | ✅ Complete |

**Outcome**: NPCs can now use abilities during combat via pluggable AI behaviors! BehaviorContext provides ability introspection, and the combat system checks for ability usage before basic attacks.

### Phase 14.4 - Content & Loading ✅ **COMPLETE**

| File | Changes Required | Status |
|------|-----------------|--------|
| `backend/world_data/npcs/_schema.yaml` | Add class_id, default_abilities, ability_loadout, ai_behavior docs | ✅ Complete |
| `backend/app/engine/loader.py` | Add `create_npc_character_sheet()` helper function<br>Load Phase 14 fields into WorldNpcTemplate | ✅ Complete |
| `backend/app/main.py` | Initialize NPC character sheets after ClassSystem loads | ✅ Complete |
| `backend/app/engine/engine.py` | Restore character sheet on NPC respawn | ✅ Complete |
| `backend/world_data/npcs/goblin_shaman.yaml` | Mage NPC with fireball, arcane_bolt, mana_shield (CasterAI) | ✅ Complete |
| `backend/world_data/npcs/skeleton_champion.yaml` | Warrior NPC with power_attack, shield_bash, whirlwind (BruteAI) | ✅ Complete |
| `backend/world_data/npcs/forest_guardian.yaml` | Nature-themed mage NPC with TacticalCasterAI | ✅ Complete |

**Outcome**: Content creators can define NPCs with abilities via YAML! NPCs get CharacterSheets on spawn with full resources, and respawning restores their ability state.

### Phase 14.5 - Events & Admin Integration ✅ **COMPLETE**

| File | Changes Made | Status |
|------|-------------|--------|
| `backend/app/engine/systems/events.py` | Added `entity_type` param to `ability_cast()` and `ability_cast_complete()` | ✅ Complete |
| `backend/app/engine/systems/abilities.py` | Updated to pass `entity_type` ("player" or "npc") to ability events | ✅ Complete |
| `backend/app/engine/engine.py` | Added room broadcast for NPC ability casts (⚡ flavor messages) | ✅ Complete |
| `backend/app/routes/admin.py` | Extended `NpcSummary` with ability fields; added `verbose` mode to `GET /world/npcs` | ✅ Complete |

**Outcome**: Players see NPC ability casts via room messages and WebSocket events include entity_type! Admins can inspect NPC abilities via verbose mode.

### Phase 14.6 - Testing ✅ **COMPLETE**

| File | Changes Made | Priority | Status |
|------|-------------|----------|--------|
| `backend/tests/abilities/builders.py` | Added `with_character_sheet()` method to `WorldNpcBuilder` | High | ✅ Complete |
| `backend/tests/abilities/conftest.py` | Added `npc_mage_sheet` and `mock_npc_caster` fixtures | High | ✅ Complete |
| `backend/tests/abilities/test_npc_abilities.py` | Comprehensive NPC ability test suite (16 tests) | High | ✅ Complete |

**Test Coverage**:
- NPC ability casting with character_sheet
- NPC without character_sheet validation
- NPC ability learning validation
- NPC mana consumption
- NPC insufficient mana handling
- NPC cooldown tracking
- NPC and player independent cooldowns
- Entity type in ability_cast events
- Entity type in ability_cast_complete events
- Ability error event structure
- WorldNpcBuilder with/without character_sheet
- NPC targeting players
- NPC GCD application
- Multiple NPCs independent cooldowns

**Outcome**: Full test coverage for NPC ability system! All 16 tests pass.

---

## 4. Potential Breaking Changes

### 4.1 Type System Changes

**Risk**: Medium
**Impact**: Code that explicitly checks `isinstance(entity, WorldPlayer)` before ability operations

**Mitigation**:
- Instead of type checks, use `has_character_sheet()` method
- Update all `if isinstance(caster, WorldPlayer):` to `if caster.has_character_sheet():`

### 4.2 Cooldown Key Changes

**Risk**: Low
**Impact**: Existing player cooldowns might reset when switching from player_id to entity_id keys

**Mitigation**:
- Since cooldowns are runtime-only (not persisted), this is acceptable
- Players will just lose active cooldowns on server restart (already happens)

### 4.3 Event Payload Changes

**Risk**: Low
**Impact**: `ability_cast` events might need entity_type field for client UI

**Mitigation**:
- Events already include entity IDs
- Clients can look up entity type from their entity cache
- No breaking changes to event schema needed

### 4.4 Resource Persistence

**Risk**: Medium
**Impact**: NPCs with abilities need resource state management

**Mitigation Strategy** (see Section 5):
- NPCs respawn with full resources (don't persist like players)
- Simplifies implementation, avoids database bloat
- Resource pools reset on NPC respawn

---

## 5. Design Decisions

### 5.1 NPC Resource Regeneration

**Question**: Do NPCs use the same resource regen rates as players?

**Decision**: **Yes, NPCs use class-defined regen rates**

**Rationale**:
- Consistency: Same class = same mechanics
- Balance: Prevents exploiting slow-regen caster NPCs
- Simplicity: No special-casing needed

**Implementation**: Resource regen logic in engine.py works for all WorldEntity instances

---

### 5.2 Resource Persistence Across Respawns

**Question**: Should NPC resources persist when they respawn?

**Decision**: **No, NPCs respawn with full resources**

**Rationale**:
- **Simplicity**: Avoids database bloat from storing thousands of NPC resource states
- **Balance**: Players shouldn't be able to "drain" a boss's mana and wait for respawn
- **Consistency**: Respawn = fresh start (also true for HP)
- **Exception**: Persistent/companion NPCs (persist_state=True) MAY persist resources in future phase

**Implementation**:
- On NPC spawn, initialize resource pools from class template at max values
- On NPC death/respawn, discard old resource state

---

### 5.3 Starting Resources in Combat

**Question**: Do NPCs start combat with full resources or spawn values?

**Decision**: **NPCs spawn with full resources and maintain them between combats**

**Rationale**:
- NPCs regen resources passively like players
- Between combats, resources naturally regenerate
- Boss fights would be too easy if boss started low on mana
- Creates interesting dynamics (interrupt caster's mana regen before pull)

**Implementation**:
- NPCs spawn with resource pools at max
- Resources regen continuously (not just in/out of combat)
- Combat doesn't reset resources

---

### 5.4 Ability AI Complexity

**Question**: How intelligent should NPC ability usage be?

**Decision**: **Pluggable AI behaviors with increasing complexity**

**Tiers**:
1. **Simple**: Random ability from loadout when off cooldown
2. **Tactical**: Priority-based (defensive when low HP, offensive in combat)
3. **Strategic**: Threat-aware, resource-efficient, combo-aware

**Implementation**:
- Tier 1: `on_combat_action()` hook with random selection
- Tier 2: Priority scoring system based on NPC/target state
- Tier 3: Future enhancement (Phase 14+)

**Content Creator Control**:
- YAML tag: `ai_behavior: caster_simple` or `ai_behavior: caster_tactical`
- Default to simple if not specified

---

## 6. Backward Compatibility Strategy

### 6.1 Existing NPCs

**Guarantee**: NPCs without `class_id` work exactly as before

**Enforcement**:
- `character_sheet` is optional (defaults to None)
- All helper methods handle None gracefully
- Ability commands check `has_character_sheet()` before execution
- Behaviors without ability hooks continue working

### 6.2 Database Migration

**Safety**:
- All new columns are nullable or have defaults
- No data transformation required
- Downgrade path supported

### 6.3 Testing Strategy

**Validation**:
- Load existing NPC templates without errors
- Spawn NPCs without class_id → no crashes
- Mix NPC types in same room (with/without abilities)
- Ensure existing behaviors (aggressive, wanders_sometimes) still work

---

## 7. Implementation Order (Phase 14.1)

1. ✅ **Create this design document** (establishes architecture)
2. **Update WorldNpc dataclass** (add character_sheet field)
3. **Add helper methods to WorldNpc** (copy from WorldPlayer)
4. **Update NpcTemplate dataclass** (add class_id, default_abilities, ability_loadout)
5. **Create database migration** (add columns to npc_templates)
6. **Update ORM model** (models.py)
7. **Test backward compatibility** (verify existing NPCs work)
8. **Document resource strategies** (update this document)

---

## 8. Completed Phases Summary

### Phase 14.1 - Universal Entity Ability Support ✅ COMPLETE
- Moved character_sheet to WorldEntity base class
- Added helper methods for ability introspection
- Database migration for NPC ability fields
- Full backward compatibility with existing NPCs

### Phase 14.2 - Ability System Generalization ✅ COMPLETE
- Refactored AbilityExecutor for WorldEntity (all type hints updated)
- Verified all 24 ability behaviors are entity-agnostic
- Implemented NPC resource regeneration in engine.py
- All 25 ability tests pass

### Phase 14.3 - NPC AI Integration ✅ COMPLETE
- Created ability hooks in BehaviorScript (on_combat_action, etc.)
- Extended BehaviorContext with ability helpers
- Implemented CasterAI, TacticalCasterAI, BruteAI, BerserkerAI behaviors
- Integrated with combat system for intelligent ability usage

### Phase 14.4 - Content & Loading ✅ COMPLETE
- Updated NPC YAML schema with ability fields
- Created create_npc_character_sheet() loader helper
- Added 3 example NPCs with abilities (goblin_shaman, skeleton_champion, forest_guardian)
- Character sheets restored on NPC respawn

### Phase 14.5 - Events & Admin Integration ✅ COMPLETE
- Added `entity_type` field to `ability_cast` and `ability_cast_complete` events
- NPC ability casts broadcast flavor messages to room (⚡ format)
- Extended `NpcSummary` model with ability fields (class_id, has_abilities, resource_pools, etc.)
- Added `verbose=True` query param to `GET /world/npcs` for ability details

## 8.1 Future Phases

### Phase 14.6 - Testing ⬜
- Comprehensive test suite (test_npc_abilities.py)
- Integration tests for NPC ability events
- Documentation updates

---

## 9. Success Criteria (Phase 14 Complete)

- [x] NPCs can have character classes (warrior, mage, rogue)
- [x] NPCs can learn and equip abilities
- [x] NPCs cast abilities intelligently in combat
- [x] NPCs manage resources (mana, rage, energy)
- [x] Content creators can easily define NPCs with abilities in YAML
- [x] 100% backward compatible with existing NPCs
- [x] Players see NPC ability casts via WebSocket events (Phase 14.5)
- [x] Admin can inspect NPC abilities via API (Phase 14.5 - verbose mode)
- [ ] Comprehensive test coverage (>90%)

---

## Appendix A: Code Examples

### Example: NPC Template with Abilities (YAML)

```yaml
npc_id: goblin_shaman
name: Goblin Shaman
description: A wiry goblin crackling with arcane energy
level: 5
max_health: 60
npc_type: hostile

# New Phase 14 fields
class_id: mage
default_abilities:
  - fireball
  - mana_regen
  - frost_bolt
ability_loadout:
  - fireball
  - frost_bolt

behaviors:
  - aggressive
  - caster_ai  # New behavior that uses abilities
  - calls_for_help
```

### Example: NPC with Character Sheet (Runtime)

```python
# After loading from YAML + database
goblin = WorldNpc(
    id="goblin_001",
    name="Goblin Shaman",
    template_id="goblin_shaman",
    # ...
    character_sheet=CharacterSheet(
        class_id="mage",
        level=5,
        experience=0,
        learned_abilities={"fireball", "mana_regen", "frost_bolt"},
        ability_loadout=[
            AbilitySlot(slot_id=0, ability_id="fireball"),
            AbilitySlot(slot_id=1, ability_id="frost_bolt"),
        ],
        resource_pools={
            "mana": ResourcePool(
                resource_id="mana",
                current=100,
                max=100,
                regen_per_second=2.0
            )
        }
    )
)
```

### Example: Behavior Hook (Future Phase 14.3)

```python
@behavior(name="caster_ai", description="Intelligent spellcasting AI")
class CasterAI(BehaviorScript):
    async def on_combat_action(self, ctx: BehaviorContext) -> bool:
        """Choose and cast an ability based on situation."""
        npc = ctx.npc

        # Check if NPC has abilities
        if not npc.has_character_sheet():
            return False

        # Get available abilities (not on cooldown, enough resources)
        available = ctx.get_available_abilities()
        if not available:
            return False

        # Simple AI: Prioritize by situation
        if npc.current_health < npc.max_health * 0.3:
            # Low health: defensive abilities
            ability = self._choose_defensive(available)
        else:
            # Normal: offensive abilities
            ability = self._choose_offensive(available)

        # Cast the ability
        if ability:
            target = ctx.get_combat_target()
            await ctx.cast_ability(ability.ability_id, target)
            return True

        return False
```

---

## 8. Magic Items and Environmental Objects (Future Phases)

### 8.1 Magic Items with Abilities

**Concept**: Items (weapons, armor, consumables) can have character_sheet for ability mechanics

**Example: Staff of Fireball**

```yaml
# world_data/items/magic_staff.yaml
item_templates:
  staff_of_fireball:
    name: "Staff of Fireball"
    keywords: ["staff", "magic", "fire"]
    description: "A powerful staff imbued with fire magic. Has 10 charges."
    can_take: true
    can_drop: true

    # Item grants ability when equipped
    class_id: "staff_wielder"
    default_abilities: ["cast_fireball"]
    ability_loadout: ["cast_fireball"]

    # Uses charges instead of mana
    resource_pool:
      charges:
        current: 10
        max: 10
        regen_rate: 0.0  # Doesn't regenerate - must be recharged manually
```

**Implementation**:
- Extend `WorldItem` with `character_sheet` field (already on WorldEntity!)
- When item is equipped, grant player access to item's abilities
- "Use" command triggers item's ability
- Charges deplete on use, item becomes inactive at 0 charges

### 8.2 Environmental Objects with Abilities

**Concept**: World objects (barrels, fountains, traps) use abilities for interactions

**Example: Explosive Barrel**

```yaml
# world_data/objects/explosive_barrel.yaml
objects:
  explosive_barrel:
    name: "Explosive Barrel"
    keywords: ["barrel", "explosive", "cask"]
    description: "A wooden barrel filled with volatile black powder."

    # Object has "explode" ability
    class_id: "explosive_object"
    default_abilities: ["aoe_explosion"]
    ability_loadout: ["aoe_explosion"]

    # Triggered on destruction or player interaction
    on_destroy_ability: "aoe_explosion"

    # Stats for the object
    max_health: 20
    current_health: 20
```

**Behavior**:
- When barrel is destroyed (health reaches 0), triggers `aoe_explosion` ability
- Explosion deals damage to all entities in radius using standard ability mechanics
- Uses same targeting, damage calculation, and effects as player abilities

**Example: Healing Fountain**

```yaml
# world_data/objects/healing_fountain.yaml
objects:
  healing_fountain:
    name: "Healing Fountain"
    keywords: ["fountain", "well", "shrine"]
    description: "A mystical fountain that radiates healing energy."

    # Periodic AoE heal ability
    class_id: "healing_object"
    default_abilities: ["aoe_heal"]
    ability_loadout: ["aoe_heal"]

    # Automatic periodic casting
    auto_cast_interval: 10.0  # Cast every 10 seconds
    auto_cast_ability: "aoe_heal"
```

**Behavior**:
- Every 10 seconds, automatically casts `aoe_heal` ability
- Affects all entities in the same room
- Uses standard ability system for healing calculation
- Resource pools optional (infinite casts, or limited charges)

### 8.3 Implementation Strategy

**Phase 14.7+ (Future)**:

1. **Extend WorldItem** (if needed):
   - Already inherits from WorldEntity in future architecture
   - Add `on_use_ability` field to trigger abilities on "use" command

2. **Create Environmental Object System**:
   - New `WorldObject` dataclass extending `WorldEntity`
   - Auto-cast timer system for periodic abilities
   - Destruction triggers for on-death abilities

3. **Update Commands**:
   - `use <item>` → triggers item's ability if equipped
   - `activate <object>` → triggers object's ability
   - `destroy <object>` → triggers on-death ability

4. **Content Examples**:
   - Magic weapons (special attacks on cooldown)
   - Consumables (one-time spell scrolls)
   - Traps (triggered damage abilities)
   - Interactive shrines (buff/debuff zones)

**Benefits**:
- **100% Code Reuse**: All use existing ability system
- **No Special Cases**: Items/objects = entities with abilities
- **Content Creator Friendly**: Same YAML patterns as player/NPC abilities
- **Consistent Mechanics**: Damage, healing, buffs all work the same way

---
