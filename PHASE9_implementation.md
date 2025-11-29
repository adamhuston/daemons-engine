# Phase 9 Implementation Plan – Succinct Roadmap

This document breaks Phase 9 into actionable sub-phases with clear deliverables and dependencies.

---

## Phase 9a – Domain Models & Database

**Goal:** Establish data structures and storage layer. Foundation for all subsequent phases.

**Status:** ✅ COMPLETE

### Tasks

1. **Add dataclasses to `app/engine/world.py`**
   - [x] `ResourceDef` ([Resource Definition](PHASE9.md#resource-definition))
   - [x] `StatGrowth` ([Stat Growth](PHASE9.md#stat-growth))
   - [x] `ResourcePool` ([Enhanced WorldPlayer](PHASE9.md#enhanced-worldplayer))
   - [x] `AbilitySlot` ([Enhanced WorldPlayer](PHASE9.md#enhanced-worldplayer))
   - [x] `CharacterSheet` (optional, backward-compatible) ([Enhanced WorldPlayer](PHASE9.md#enhanced-worldplayer))
   - [x] Update `WorldPlayer` to include optional `character_sheet` field

2. **Create domain models in `app/engine/systems/classes.py`**
   - [ ] `ClassTemplate` dataclass ([Class Template](PHASE9.md#class-template)) [Deferred to Phase 9b]
   - [ ] `AbilityTemplate` dataclass ([Ability Template](PHASE9.md#ability-template)) [Deferred to Phase 9b]

3. **Database migration (Alembic)**
   - [x] No new tables needed (use existing `Player.data` JSON column)
   - [x] Document schema in comments ([Database Schema](PHASE9.md#database-schema-migrations))
   - [x] Create migration to add JSON schema documentation

4. **Create migration script**
   - [x] Write one-time migration function for existing players ([Player Migration Path](PHASE9.md#player-migration-path-from-old-to-new-system))
   - [x] Assign default class ("adventurer") to players missing class_id
   - [x] Initialize resource pools and ability loadouts

**Deliverable:** Type-safe domain models, backward-compatible player schema, migration script ready. ✅

**Blockers:** None.

### Implementation Summary

**Files Created/Modified:**
1. `backend/app/engine/world.py` - Added 5 new dataclasses:
   - `ResourceDef`: Defines resource pools (mana, rage, energy, etc.) with regen mechanics
   - `StatGrowth`: Tracks stat scaling per level with milestone bonuses
   - `ResourcePool`: Runtime state for character resources
   - `AbilitySlot`: Equipped ability with cooldown tracking
   - `CharacterSheet`: Character class, level, experience, learned abilities, and resources

2. `backend/app/engine/world.py` - Enhanced WorldPlayer:
   - Added optional `character_sheet: CharacterSheet | None` field
   - Added helper methods: `has_character_sheet()`, `get_class_id()`, `get_resource_pool()`, `get_learned_abilities()`, `get_ability_loadout()`, `has_learned_ability()`

3. `backend/alembic/versions/g8h9i0j1k2l3_phase9_character_classes.py` - Created migration:
   - Documents JSON schema for Phase 9 character data
   - No database changes (uses existing `Player.data` JSON column)
   - Fully backward compatible

4. `backend/migrate_players_phase9.py` - Created migration script:
   - Converts existing players to Phase 9 schema
   - Assigns default class ("adventurer")
   - Initializes resource pools and ability loadouts
   - Run once after deploying Phase 9a

---

## Phase 9b – Content Files & Loaders

**Goal:** YAML parsing infrastructure and example content.

### Tasks

1. **Create YAML loader functions in `app/engine/systems/abilities.py`**
   - [ ] `load_classes_from_yaml()` ([Class Loader](PHASE9.md#class-loader))
   - [ ] `load_abilities_from_yaml()` ([Ability Loader](PHASE9.md#ability-loader))
   - [ ] Error handling for invalid YAML (missing required fields, duplicate IDs)

2. **Create example YAML files in `world_data/`**
   - [ ] `world_data/classes/warrior.yaml` ([Example YAML](PHASE9.md#example-yaml-worlddataclasseswarrioryaml))
   - [ ] `world_data/classes/mage.yaml` (similar structure, different stats)
   - [ ] `world_data/classes/rogue.yaml` (similar structure, different stats)
   - [ ] `world_data/abilities/core.yaml` (shared abilities)
   - [ ] `world_data/abilities/warrior.yaml` ([Example YAML](PHASE9.md#example-yaml-worlddataabilitieswarrioryaml))
   - [ ] `world_data/abilities/mage.yaml`
   - [ ] `world_data/abilities/rogue.yaml`
   - [ ] `world_data/_schema.yaml` (reference documentation for content creators)

3. **Update `app/engine/loader.py`**
   - [ ] Integrate class/ability loaders into `startup()` flow
   - [ ] Load content before creating WorldEngine

**Deliverable:** Loaders work, example classes and abilities load without errors.

**Blockers:** Phase 9a must be complete.

---

## Phase 9c – ClassSystem Runtime Manager

**Goal:** Manage in-memory class/ability templates and behavior registration.

### Tasks

1. **Implement `ClassSystem` in `app/engine/systems/classes.py`** ([ClassSystem](PHASE9.md#classsystem-runtime-manager))
   - [ ] `__init__()` – Initialize empty templates and registry
   - [ ] `load_content()` – Call loaders for YAML
   - [ ] `get_class()` – Retrieve by class_id
   - [ ] `get_ability()` – Retrieve by ability_id
   - [ ] `register_behavior()` – Add behavior handler
   - [ ] `get_behavior()` – Retrieve handler by ID
   - [ ] `_register_core_behaviors()` – Register built-in behaviors
   - [ ] `reload_behaviors()` – Hot-reload custom.py (Phase 8 integration)

2. **Integrate into `WorldEngine`** ([Integration Points](PHASE9.md#integration-points))
   - [ ] Create `self.class_system = ClassSystem(context)` in `__init__()`
   - [ ] Call `await self.class_system.load_content()` in `startup()`

3. **Create `GameContext` field for ClassSystem**
   - [ ] Add `class_system: ClassSystem` to `GameContext` (shared with all systems)

**Deliverable:** ClassSystem loads and serves templates; behaviors can be registered.

**Blockers:** Phase 9b must be complete.

---

## Phase 9d – Core Ability Behaviors

**Goal:** Implement basic ability execution logic.

### Tasks

1. **Create behavior infrastructure in `app/engine/systems/ability_behaviors/`**
   - [ ] Create package with `__init__.py`, `core.py`, `custom.py`
   - [ ] Define `BehaviorContext` dataclass ([Ability Behaviors](PHASE9.md#ability-behaviors-extensibility))

2. **Implement core behaviors in `core.py`** ([Core Behaviors](PHASE9.md#core-behaviors))
   - [ ] `melee_attack_behavior()` – Basic physical attack with scaling
   - [ ] `power_attack_behavior()` – Higher damage, costs rage
   - [ ] `rally_passive_behavior()` – Passive buff when above 50% health
   - [ ] Test each behavior in isolation (unit tests)

3. **Create `custom.py` stub**
   - [ ] Add example `fireball_behavior()` (commented out, for reference)
   - [ ] Document how admins add custom behaviors

4. **Register behaviors in ClassSystem**
   - [ ] Call `self.register_behavior()` for each core behavior in `_register_core_behaviors()`

**Deliverable:** Core behaviors work; behavior signature established for custom behaviors.

**Blockers:** Phase 9c must be complete.

---

## Phase 9e – Ability Executor & Validation

**Goal:** Validate ability use, manage cooldowns/GCD, execute behaviors.

### Tasks

1. **Implement `AbilityExecutor` in `app/engine/systems/abilities.py`** ([Ability Executor](PHASE9.md#ability-executor))
   - [ ] `execute_ability()` – Main entry point
   - [ ] `_validate_ability_use()` – Check learned, level, resources, cooldown
   - [ ] `_resolve_targets()` – Interpret target_type and resolve targets
   - [ ] `_apply_cooldowns()` – Set personal cooldown + GCD
   - [ ] `_error_event()` – Generate error messages

2. **Test cooldown/GCD logic** ([Cooldown/GCD mechanics](PHASE9.md#ability-executor))
   - [ ] Personal cooldown (per ability)
   - [ ] GCD (shared cooldown by category)
   - [ ] Test all validation paths (fail cases, success cases)

3. **Integrate into `WorldEngine`**
   - [ ] Create `self.ability_executor = AbilityExecutor(context)` in `__init__()`

**Deliverable:** Abilities can be executed with full validation; cooldowns tracked.

**Blockers:** Phase 9d must be complete.

---

## Phase 9f – Commands & Router Integration

**Goal:** Players can cast abilities via chat commands.

### Tasks

1. **Add commands to `app/engine/systems/router.py`** ([CommandRouter Extensions](PHASE9.md#commandrouter-extensions))
   - [ ] `cast <ability_name> [target]` – Execute ability
   - [ ] `ability <ability_name> [target]` – Alias for cast
   - [ ] `abilities` – List equipped abilities and cooldowns
   - [ ] `skills` – Alias for abilities

2. **Test command parsing**
   - [ ] Case-insensitive ability name matching
   - [ ] Target resolution (by name in room)
   - [ ] Error messages for unknown abilities, missing targets, etc.

3. **Integration test**
   - [ ] Player learns class → casts ability → sees cooldown feedback

**Deliverable:** Players can cast abilities from game commands.

**Blockers:** Phase 9e must be complete.

---

## Phase 9g – Admin API Endpoints

**Goal:** Admins can manage classes/abilities and hot-reload content.

### Tasks

1. **Add endpoints to `app/routes/admin.py`** ([Admin API Endpoints](PHASE9.md#admin-api-endpoints))
   - [ ] `GET /api/admin/classes` – List all classes
   - [ ] `GET /api/admin/abilities` – List all abilities
   - [ ] `POST /api/admin/classes/reload` – Hot-reload classes + abilities + behaviors

2. **Implement hot-reload logic**
   - [ ] Re-call `load_content()` to refresh class/ability templates
   - [ ] Call `reload_behaviors()` to reimport custom.py
   - [ ] Return success/error with counts loaded

3. **Test hot-reload**
   - [ ] Modify a YAML file, call reload endpoint
   - [ ] Verify new data is loaded without server restart

**Deliverable:** Admins can reload content without restart.

**Blockers:** Phase 9f must be complete.

---

## Phase 9h – WebSocket Protocol & Events

**Goal:** Clients receive ability events and resource updates.

### Tasks

1. **Extend event types in `app/engine/systems/events.py`** ([WebSocket Protocol Extension](PHASE9.md#websocket-protocol-extension))
   - [ ] `ability_cast` – Broadcast when ability used
   - [ ] `ability_error` – Send when ability fails validation
   - [ ] `ability_cast_complete` – After behavior executes
   - [ ] `ability_learned` – When player learns new ability
   - [ ] `resource_update` – Current/max resource amounts
   - [ ] `cooldown_update` – Cooldown remaining for ability

2. **Modify `AbilityExecutor` to emit events**
   - [ ] Each event generated during `execute_ability()` flows to dispatcher
   - [ ] Test that events broadcast to room (combat events) or player (personal events)

3. **Test on client**
   - [ ] Flet client displays resource updates
   - [ ] Cooldown timer displayed (if UI supports)

**Deliverable:** Clients see ability events and resource state.

**Blockers:** Phase 9g must be complete.

---

## Phase 9i – Persistence & Offline Regen

**Goal:** Character data saved/restored; resources regen while offline.

### Tasks

1. **Implement save/restore in `app/engine/systems/persistence.py`** ([Resource Pool Persistence](PHASE9.md#resource-pool-persistence))
   - [ ] `save_player_resources()` – Serialize pools to player.data JSON on disconnect
   - [ ] `restore_player_resources()` – Deserialize from JSON on reconnect
   - [ ] Offline regen calculation (time offline × regen_rate)

2. **Integrate into connection lifecycle**
   - [ ] Call `save_player_resources()` in disconnect handler
   - [ ] Call `restore_player_resources()` in reconnect/load handler

3. **Test offline regen**
   - [ ] Player disconnects with low mana
   - [ ] Player reconnects after delay
   - [ ] Mana should have partially regenerated

**Deliverable:** Character resources persisted and regenerate offline.

**Blockers:** Phase 9g must be complete (resource tracking stable).

---

## Phase 9j – Polish & Testing

**Goal:** Fix bugs, optimize, document.

### Tasks

1. **Unit tests**
   - [ ] ClassSystem: load, get, register behaviors
   - [ ] AbilityExecutor: validation, cooldown, GCD
   - [ ] Resource calculations (regen with stat modifiers)
   - [ ] Target resolution (self, enemy, ally, room)

2. **Integration tests**
   - [ ] End-to-end: player picks class → learns ability → casts → cooldown → regen
   - [ ] Multiple classes/abilities in same room
   - [ ] Error cases (invalid target, insufficient resources, etc.)

3. **Documentation**
   - [ ] Update [ARCHITECTURE.md](ARCHITECTURE.md) with Phase 9 sections
   - [ ] Add code comments referencing [PHASE9.md](PHASE9.md) sections
   - [ ] Create content creator quick-start guide

4. **Performance**
   - [ ] Profile ability execution time
   - [ ] Ensure hot-reload doesn't leak memory

**Deliverable:** Polished, tested, documented system ready for Phase 10.

**Blockers:** Phase 9i must be complete.

---

## Dependency Graph

```
Phase 9a (Models)
    ↓
Phase 9b (YAML loaders)
    ↓
Phase 9c (ClassSystem)
    ↓
Phase 9d (Core behaviors)
    ↓
Phase 9e (AbilityExecutor)
    ├─→ Phase 9f (Commands)
    ├─→ Phase 9g (Admin API)
    ├─→ Phase 9h (WebSocket)
    └─→ Phase 9i (Persistence)
         ↓
    Phase 9j (Polish & testing)
```

---

## Quick Reference: Key Sections to Implement From

| Phase | Implementation | PHASE9.md Link |
|-------|-----------------|-----------------|
| 9a | WorldPlayer, CharacterSheet, ResourcePool | [Domain Models](PHASE9.md#domain-models-dataclasses) |
| 9b | YAML loaders | [Loaders](PHASE9.md#loaders-yaml-parsing) |
| 9c | ClassSystem manager | [ClassSystem](PHASE9.md#classsystem-runtime-manager) |
| 9d | Core ability logic | [Ability Behaviors](PHASE9.md#ability-behaviors-extensibility) |
| 9e | Execute + validate | [Ability Executor](PHASE9.md#ability-executor) |
| 9f | Cast commands | [CommandRouter Extensions](PHASE9.md#commandrouter-extensions) |
| 9g | Admin endpoints | [Admin API Endpoints](PHASE9.md#admin-api-endpoints) |
| 9h | Event types | [WebSocket Protocol](PHASE9.md#websocket-protocol-extension) |
| 9i | Save/restore | [Resource Pool Persistence](PHASE9.md#resource-pool-persistence) |
| 9j | Tests + docs | [Content Creator Workflow](PHASE9.md#content-creator-workflow) |

---

## Success Criteria

Phase 9 is complete when:

✅ Players can select a class  
✅ Players can learn and equip abilities  
✅ Players can cast abilities with full validation  
✅ Cooldowns and GCD prevent spam  
✅ Resources (mana, rage, etc.) track and regenerate  
✅ Abilities persist across disconnect/reconnect  
✅ Admins can hot-reload classes/abilities without restart  
✅ All events broadcast to clients  
✅ New content creators can add classes/abilities without code changes  

---

## Notes

- **Backward compatibility:** Existing players without classes continue to work (no breaking changes)
- **Extensibility:** Content creators add new classes/abilities via YAML + optional Python behavior functions
- **Testability:** Each phase is independently testable; integration happens incrementally
- **Documentation:** Link back to [PHASE9.md](PHASE9.md) in code comments for future reference

Ready to begin Phase 9a?