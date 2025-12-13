# Roadmap

## Phase 0  Hardening ✅ COMPLETE

Before adding big systems, make the core loop solid.

**Goals**: No silent failures; predictable behavior under load.

### Backend tasks ✅ COMPLETE

- ✅ Logging & observability
    - ✅ Structured logs for: player connect/disconnect, commands received, errors in engine/WS tasks
    - ✅ Metrics hooks and counters for active players
- ✅ Error handling
    - ✅ Graceful exception handling in _ws_sender / _ws_receiver
    - ✅ Graceful handling of bad JSON / unknown commands
- ✅ Protocol documentation
    - ✅ protocol.md: client→server commands and server→client event shapes



## Phase 1  Player stats and progression ✅ COMPLETE

**Goals**: A player is more than just a name + room.

### Backend model changes ✅

- ✅ Extended Player model:
    - ✅ Base stats: str, dex, int, vit, con, wis, cha
    - ✅ Derived stats: hp, max_hp, mp, max_mp, level, xp
    - ✅ Class/archetype tracking
- ✅ Enhanced WorldPlayer with stat fields
- ✅ Stat update events with payloads

### Engine changes ✅

- ✅ Commands: stats/sheet/status - print current stats
- ✅ Event types: stat_update events with hp, max_hp, level, etc.
- ✅ Persistence: sync WorldPlayer stats to DB on disconnect and key events



## Phase 2  Time & tick system (for effects/debuffs)  ✅ COMPLETE

> 📄 **Documentation**: [phase2_time_NOTES.md](./build_docs/phase2_time_NOTES.md)

**Goals**: Server time becomes first-class; you can have timed buffs/debuffs, regen, DoTs, etc.

**Note**: The original design called for traditional "ticks" but we implemented an event-driven architecture instead.

### Phase 2a  Core Time System ✅
- ✅ Event-driven time system (not traditional ticks)
- ✅ TimeEvent dataclass with priority queue
- ✅ Async _time_loop() processes events at precise Unix timestamps
- ✅ schedule_event() and cancel_event() methods
- ✅ Supports one-shot and recurring events
- ✅ Dynamic sleep until next event
- ✅ testtimer command

### Phase 2b  Effect System ✅
- ✅ Effect dataclass with effect_id, name, effect_type (buff/debuff/dot/hot)
- ✅ stat_modifiers: Dict[str, int]
- ✅ duration, applied_at tracking
- ✅ interval, magnitude for periodic effects
- ✅ WorldPlayer active_effects: Dict[str, Effect]
- ✅ apply_effect(), remove_effect(), get_effective_stat() methods
- ✅ Commands: bless, poison, effects/status
- ✅ Stat integration with effective vs base values

### Phase 2c  World Time System ✅
- ✅ WorldTime dataclass tracking day/hour/minute
- ✅ advance() and get_current_time() methods
- ✅ WorldArea system with independent area_time
- ✅ time_scale attribute for different time speeds
- ✅ Environmental properties
- ✅ Time advancement every 30 seconds
- ✅ time command with area context
- ✅ Sample areas (Ethereal Nexus 4x, Temporal Rift 2x)

## Phase 3 - Items & inventory ✅ COMPLETE

**Goals**: Physical objects in the world, inventory management, equipment.

### Backend Model ✅

- ✅ DB:
    - ✅ ItemTemplate (static: name, type, modifiers, description, keywords).
    - ✅ ItemInstance (dynamic: owner, location, durability, unique flags).
    - ✅ PlayerInventory (capacity limits, weight/slot tracking).

- ✅ World:
    - ✅ WorldItem for runtime representation.
    - ✅ ItemTemplate dataclass with full properties.
    - ✅ Attach items to:
        - ✅ rooms (ground items)
        - ✅ other items (containers)
        - ✅ players (inventory and equipment).

### YAML Content System ✅ COMPLETE

- ✅ world_data/items/ directory structure (weapons/, armor/, consumables/, containers/)
- ✅ world_data/item_instances/ for spawn configurations
- ✅ Migration loads items from YAML files
- ✅ Example items: Rusty Sword, Wooden Staff, Iron Chestplate, Leather Cap, Health Potion, Scroll of Wisdom, Leather Backpack

### Engine Changes ✅

- ✅ Loader:
    - ✅ Load templates + instances into World.
    - ✅ Link items to players/rooms on startup.
    - ✅ Restore equipped items and apply stat effects.

- ✅ Core item mechanics:
    - ✅ inventory/inv/i: View inventory with weight/slots.
    - ✅ get/take/pickup <item>: Pick up from room (one at a time for stacks).
    - ✅ drop <item>: Drop to room.
    - ✅ give <item> <player>: Transfer to another player.
    - ✅ equip/wear/wield <item>: Equip to appropriate slot.
    - ✅ unequip/remove <item>: Unequip item.
    - ✅ use/consume/drink <item>: Use consumable items.
    - ✅ look <item>: Detailed item inspection with properties.
    - ✅ put <item> in <container>: Store items in containers.
    - ✅ get <item> from <container>: Retrieve from containers.

- ✅ Stat interactions:
    - ✅ Equipment applies stat modifiers via Effect system.
    - ✅ On equip: create permanent effect with stat bonuses.
    - ✅ On unequip: remove effect, recalculate stats.
    - ✅ Consumables apply temporary effects (buffs, healing).

- ✅ Quality of Life:
    - ✅ Partial name matching ("lea" finds "leather backpack").
    - ✅ Keyword system (items can have multiple searchable names).
    - ✅ Stack handling (pick up one at a time).
    - ✅ Weight and slot-based inventory limits.
    - ✅ O(1) container contents lookup via index (not O(n) world scan).

### Events ✅

- ✅ Room broadcasts:
    - ✅ "Alice drops Rusty Sword."
    - ✅ "Bob picks up Health Potion."
    - ✅ "Alice gives Health Potion to Bob."
- ✅ Stat updates:
    - ✅ stat_update events on equip/unequip/consume.

### Persistence ✅

- ✅ Inventory saved on player disconnect.
- ✅ Item locations, quantities, durability persisted.
- ✅ Equipment state restored on reconnect.



## Phase 4 - NPCs & Combat System  ✅ COMPLETE

**Goals**: NPCs in rooms with real-time combat and AI behaviors.

### Backend Model ✅

- ✅ DB:
    - ✅ NpcTemplate with stats, behavior flags, loot tables, attack stats
    - ✅ NpcInstance for spawned NPCs
- ✅ World:
    - ✅ WorldEntity unified base class for players and NPCs
    - ✅ WorldNpc extends WorldEntity with NPC-specific fields
    - ✅ EntityType enum (PLAYER, NPC)
    - ✅ Targetable protocol for unified command targeting
    - ✅ NPCs attached to rooms via entities set

### Real-Time Combat System ✅

- ✅ Architecture:
    - ✅ Real-time combat (not turn-based) with weapon swing timers
    - ✅ CombatState dataclass tracking phase, target, timing
    - ✅ CombatPhase enum: IDLE → WINDUP → SWING → RECOVERY
    - ✅ WeaponStats: damage_min/max, swing_speed, damage_type
    - ✅ Auto-attack continues until target dies or combat cancelled

- ✅ Combat Flow:
    - ✅ `attack <target>` / `kill <target>` - Start attacking
    - ✅ `stop` - Disengage from combat
    - ✅ Movement blocked while in combat (must flee)
    - ✅ Player auto-retaliation when attacked
    - ✅ NPC retaliation via CombatSystem
    - ✅ Swing timer based on weapon speed
    - ✅ Damage calculation with strength modifier and armor reduction
    - ✅ Critical hit system (10% chance, 1.5x damage)

- ✅ Death & Rewards:
    - ✅ HP tracking and death detection
    - ✅ Death messages broadcast to room
    - ✅ XP rewards for killing NPCs
    - ✅ NPC respawn timers with area defaults and per-NPC overrides
    - ✅ Player respawn with countdown timer and area entry point
    - ✅ Loot drops from NPC drop tables

### Weapon & Equipment System ✅

- ✅ ItemTemplate weapon stats:
    - ✅ damage_min, damage_max, attack_speed, damage_type
    - ✅ Migration adds columns to item_templates
    - ✅ YAML weapon files updated with combat stats
- ✅ Equipment integration:
    - ✅ `get_weapon_stats(item_templates)` checks equipped weapon
    - ✅ Falls back to unarmed (base) stats if no weapon
    - ✅ Both players AND NPCs benefit from equipped weapons

### Behavior Script System ✅

- ✅ Modular architecture:
    - ✅ `backend/app/engine/behaviors/` package
    - ✅ Dynamic loading from directory (mod-friendly)
    - ✅ `@behavior` decorator for registration
    - ✅ BehaviorScript base class with async hooks

- ✅ Available hooks:
    - ✅ on_spawn, on_death
    - ✅ on_idle_tick, on_wander_tick
    - ✅ on_player_enter, on_player_leave
    - ✅ on_combat_start, on_damaged, on_combat_tick
    - ✅ on_talked_to, on_given_item

- ✅ Built-in behaviors:
    - ✅ Wandering: wanders_rarely, wanders_sometimes, wanders_frequently, wanders_nowhere
    - ✅ Combat: aggressive (attacks on sight), defensive (retaliates), pacifist
    - ✅ Flee: cowardly, cautious, brave, fearless
    - ✅ Social: calls_for_help, loner
    - ✅ Idle: talkative, chatty, quiet, silent
    - ✅ Roles: merchant, guard, patrol

- ✅ NPC AI:
    - ✅ Per-NPC timers (idle_event_id, wander_event_id)
    - ✅ Behaviors resolved from YAML tags at load time
    - ✅ Priority system for behavior execution
    - ✅ BehaviorResult controls movement, attacks, messages

### Events ✅

- ✅ Combat broadcasts:
    - ✅ "⚔️ Alice attacks Goblin!"
    - ✅ "Alice hits Goblin for 5 damage! **CRITICAL!**"
    - ✅ "💀 Goblin has been slain by Alice!"
- ✅ Stat updates:
    - ✅ HP changes via stat_update events
- ✅ Movement:
    - ✅ Arrival messages use "from above/below" for vertical movement
- ✅ Player death:
    - ✅ respawn_countdown event type for client UI
    - ✅ Flavorful death and respawn messages
- ✅ NPC reactions:
    - ✅ Aggressive NPCs attack when players enter room
    - ✅ NPCs call for help (allies join fight)
    - ✅ NPCs can flee when damaged

### YAML Content ✅

- ✅ NPC templates: goblin_scout, skeleton_warrior, ethereal_wisp, wandering_merchant
- ✅ NPC spawns configured per-area
- ✅ Behavior tags in YAML: `behaviors: [wanders_sometimes, aggressive, cowardly]`



## Phase 5 - World structure, triggers, and scripting  ✅ COMPLETE

> 📄 **Documentation**: [phase5_triggers.md](./build_docs/phase5_triggers.md)

**Goal**: Richer world behavior without hardcoding everything in Python.

### Phase 5.1 - Core Trigger Infrastructure ✅

- ✅ Trigger System Architecture:
    - ✅ TriggerSystem class following GameContext pattern
    - ✅ RoomTrigger dataclass: id, event, conditions, actions, cooldown, max_fires, enabled
    - ✅ TriggerCondition and TriggerAction dataclasses with type + params
    - ✅ TriggerState for runtime tracking (fire_count, last_fired_at, timer_event_id)
    - ✅ TriggerContext passed to all handlers with player, room, area, direction, command

- ✅ Core Event Types:
    - ✅ on_enter: Fires when player enters a room
    - ✅ on_exit: Fires when player leaves a room
    - ✅ Variable substitution: {player.name}, {room.name}, {direction}
    - ✅ Cooldown enforcement per player
    - ✅ max_fires enforcement with fire_count tracking

- ✅ Basic Conditions:
    - ✅ flag_set: Check room_flags for specific flag value
    - ✅ has_item: Check if player has item (by template_id or keywords)
    - ✅ level: Check player level (min_level, max_level)

- ✅ Basic Actions:
    - ✅ message_player: Send message to triggering player
    - ✅ message_room: Broadcast to all players in room
    - ✅ set_flag: Set room flag to value
    - ✅ toggle_flag: Toggle boolean room flag

### Phase 5.2 - Commands, Timers & Expanded Conditions ✅

- ✅ Command Triggers:
    - ✅ on_command: Fires on specific player commands
    - ✅ fnmatch pattern matching ("pull *", "open *door*", "press button")
    - ✅ Integrated into router as pre-command hook
    - ✅ Returns True to block further command processing

- ✅ Timer Triggers:
    - ✅ on_timer: Periodic automatic triggers
    - ✅ timer_interval and timer_initial_delay configuration
    - ✅ Integration with TimeEventManager
    - ✅ start_room_timers() called on player enter
    - ✅ Recurring=True for continuous operation

- ✅ Expanded Conditions:
    - ✅ health_percent: Check player health percentage (min, max)
    - ✅ in_combat: Check if player is in combat
    - ✅ has_effect: Check if player has specific effect
    - ✅ entity_present: Check for NPC by template_id in room
    - ✅ player_count: Check room player count (min, max)

- ✅ Expanded Actions:
    - ✅ damage: Deal damage to triggering player
    - ✅ heal: Heal triggering player
    - ✅ apply_effect: Apply effect to player (via EffectSystem)
    - ✅ spawn_npc: Spawn NPC from template in room
    - ✅ despawn_npc: Remove NPC from room

### Phase 5.3 - Dynamic World State ✅

- ✅ Exit Manipulation:
    - ✅ WorldRoom.dynamic_exits dict for runtime exit overrides
    - ✅ get_effective_exits() method combines base exits + dynamic
    - ✅ open_exit action: Opens an exit to destination room
    - ✅ close_exit action: Closes/removes an exit

- ✅ Description System:
    - ✅ WorldRoom.dynamic_description for runtime description override
    - ✅ get_effective_description() returns dynamic or base description
    - ✅ set_description action: Override room description
    - ✅ reset_description action: Restore original description

- ✅ Item Actions:
    - ✅ spawn_item: Create item instance in room
    - ✅ despawn_item: Remove item from room
    - ✅ give_item: Give item to player
    - ✅ take_item: Remove item from player

- ✅ Trigger Control:
    - ✅ enable_trigger: Enable a disabled trigger
    - ✅ disable_trigger: Disable a trigger
    - ✅ fire_trigger: Manually fire another trigger

- ✅ Engine Integration:
    - ✅ _look() uses get_effective_description()
    - ✅ Movement commands use get_effective_exits()

### Phase 5.4 - Area Enhancements & YAML Loading ✅

- ✅ WorldArea Extensions:
    - ✅ recommended_level, theme, area_flags fields
    - ✅ triggers and trigger_states for area-level triggers
    - ✅ Loaded from YAML area files

- ✅ Area Triggers:
    - ✅ on_area_enter: Fires when entering area from different area
    - ✅ on_area_exit: Fires when leaving area to different area
    - ✅ fire_area_event() with area state management
    - ✅ Area transition detection in _move_player()

- ✅ Timer Initialization:
    - ✅ initialize_all_timers() for room and area on_timer triggers
    - ✅ Called from start_time_system() at startup

- ✅ YAML Trigger Loading:
    - ✅ load_triggers_from_yaml() in loader.py
    - ✅ _parse_trigger() parses conditions/actions from YAML
    - ✅ Called from main.py after load_world()
    - ✅ Supports both room and area trigger definitions

- ✅ Example Content:
    - ✅ room_1_1_1.yaml: Central hub with welcome, meditate, touch, pulse triggers
    - ✅ room_0_0_0.yaml: Origin with conditional and level-gated triggers
    - ✅ ethereal_nexus.yaml: Area enter/exit triggers

## Phase X - Quest System and Narrative Progression ✅ COMPLETE

> 📄 **Documentation**: [phaseX_quests.md](./build_docs/phaseX_quests.md)

**Goals**: Structured narrative experiences, player-driven story progression, and meaningful rewards.

### Core Quest Infrastructure ✅

- ✅ Quest System Architecture:
    - ✅ QuestSystem class following GameContext pattern
    - ✅ QuestTemplate dataclass: id, name, description, objectives, rewards, prerequisites
    - ✅ QuestStatus enum: NOT_AVAILABLE → AVAILABLE → ACCEPTED → IN_PROGRESS → COMPLETED → TURNED_IN
    - ✅ QuestProgress dataclass for player-specific quest state tracking
    - ✅ QuestObjective dataclass with type-specific parameters

- ✅ Objective Types:
    - ✅ KILL: Kill N of NPC template
    - ✅ COLLECT: Collect N of item template
    - ✅ DELIVER: Bring item to NPC
    - ✅ VISIT: Enter a specific room
    - ✅ INTERACT: Use command in room (trigger-based)
    - ✅ ESCORT: Keep NPC alive to destination
    - ✅ DEFEND: Prevent NPCs from reaching location
    - ✅ TALK: Speak to NPC
    - ✅ USE_ITEM: Use specific item

- ✅ Quest Rewards:
    - ✅ Experience points
    - ✅ Items (via ItemSystem.give_item())
    - ✅ Effects (via EffectSystem.apply_effect())
    - ✅ Flags (player and room)
    - ✅ Currency (future)
    - ✅ Reputation (future)

### NPC Dialogue System ✅

- ✅ Dialogue Data Structures:
    - ✅ DialogueTree: Complete dialogue for an NPC
    - ✅ DialogueNode: A node with text, options, conditions, actions
    - ✅ DialogueOption: Player response with conditions and quest integration
    - ✅ Variable substitution: {player.name}, {quest.progress}

- ✅ Dialogue Flow:
    - ✅ `talk <npc>` command initiates dialogue
    - ✅ Numbered option selection (1, 2, 3...)
    - ✅ Condition evaluation for available options
    - ✅ Context-sensitive entry points based on quest status
    - ✅ Quest accept/turn-in integration

### Player Commands ✅

- ✅ `talk <npc>`: Initiate dialogue with NPC
- ✅ `1`, `2`, `3`...: Select dialogue option by number
- ✅ `bye`, `farewell`: End dialogue
- ✅ `journal`, `quests`, `quest log`: View quest journal
- ✅ `quest <name>`: View specific quest details
- ✅ `abandon <quest>`: Abandon a quest

### Engine Integration ✅

- ✅ Combat System hooks: on_npc_killed → KILL objectives
- ✅ Item System hooks: on_item_acquired → COLLECT objectives
- ✅ Movement hooks: on_room_entered → VISIT objectives
- ✅ CommandRouter: Dialogue state handling before command dispatch

### YAML Content System (Phase X.3) ✅

- ✅ `world_data/quests/` directory for quest definitions
- ✅ `world_data/dialogues/` directory for NPC dialogue trees
- ✅ Quest YAML loader with full objective/reward parsing
- ✅ Dialogue YAML loader with conditions, actions, and entry overrides
- ✅ Quest chains for multi-part storylines (Phase X.4)
- ✅ Repeatable quests with cooldown support (Phase X.4)
- ✅ Timed quests with failure conditions (Phase X.4)

### Database Extensions (Phase X.3) ✅

- ✅ `player_flags` column in Player model for persistent state
- ✅ `quest_progress` column in Player model for quest tracking
- ✅ `completed_quests` column in Player model for completion history
- ✅ Quest state serialization/deserialization in save_player_stats
- ✅ Quest state restoration on player load

### Advanced Quest Features (Phase X.4) ✅

- ✅ QuestChain dataclass for linked quest series
- ✅ Chain loading from `world_data/quest_chains/` YAML files
- ✅ Chain completion tracking with bonus rewards
- ✅ `get_chain_progress()` and `list_available_chains()` methods
- ✅ `fail_quest()` method for timed quest expiration
- ✅ `check_timed_quests()` for periodic timeout checking
- ✅ Repeatable quest cooldown logic in `check_availability()`
- ✅ `on_accept_actions`, `on_complete_actions`, `on_turn_in_actions` trigger integration
- ✅ `_execute_quest_actions()` helper for quest-triggered behaviors

### Sample Content ✅

- ✅ `wisp_investigation` - Exploration-focused starter quest (VISIT, TALK objectives)
- ✅ `goblin_threat` - Combat-focused follow-up quest (KILL, COLLECT objectives)
- ✅ `wandering_merchant` dialogue tree with quest integration and context-sensitive greetings
- ✅ `ethereal_mystery` quest chain linking the two starter quests with bonus rewards

### Code Reconciliation (Phase X.R) ✅

- ✅ Removed orphaned `look_helpers.py` module
- ✅ Removed 3 unused functions from `load_yaml.py`
- ✅ Updated ARCHITECTURE.md with Game Systems section (3.4)
- ✅ Verified single time management system (TimeEventManager only)
- ✅ Verified single event dispatcher (EventDispatcher only)
- ✅ Verified single command router (CommandRouter only)
- ✅ Verified single trigger system (TriggerSystem only)
- ✅ Clean behavior hierarchy with proper `@behavior` decorator registration

### Future Considerations

- Reputation system with faction standings (implemented in Phase 10.3)
- Dynamic quest generation based on world state
- Party quests with shared objectives

---

## Phase X.R - Reconciliation & Code Hygiene ✅ COMPLETE

**Goals**: Audit the codebase to eliminate dead code, redundant systems, and orphaned implementations left behind from iterative development. Ensure architectural consistency across all systems.

### Code Audit Checklist

- ✅ **Time Systems**: Verify only one time management system is active ✅
  - ✅ Only `TimeEventManager` handles scheduling (single instance in WorldEngine)
  - ✅ Single game_loop in engine.py
  - ✅ No duplicate schedulers or tick loops

- ✅ **Event Systems**: Confirm single source of truth for events ✅
  - ✅ `EventDispatcher` is the sole event router
  - ✅ All events flow through `_dispatch_events()`
  - ✅ No orphaned event types found

- ✅ **Command Routing**: Single command dispatch path ✅
  - ✅ `CommandRouter` is the only entry point
  - ✅ All commands register via `@cmd` decorator
  - ✅ No duplicate handlers

- ✅ **Trigger System**: No duplicate trigger mechanisms ✅
  - ✅ `TriggerSystem` is sole trigger handler
  - ✅ Quest actions use TriggerSystem for spawning/effects
  - ✅ No hardcoded trigger-like logic elsewhere

- ✅ **NPC Behaviors**: Clean behavior hierarchy ✅
  - ⚠️ `example_mod.py` - example behavior (can keep as reference)
  - ✅ All behaviors properly registered via `@behavior` decorator
  - ✅ No duplicate logic across files

### Dead Code Detection

- [ ] **Unused Modules**:
  - ⚠️ `look_helpers.py` - Not imported anywhere (candidate for removal or integration)
  - ⚠️ `debug_check.py` - Debug utility script (keep but document purpose)

- ✅ **TODOs Found** (2 items):
  - `world.py:663` - Instance-specific weapon stats (future enhancement)
  - `quests.py:637` - ItemSystem integration for quest rewards (future enhancement)

- [ ] **Debug Print Statements**: 50+ print statements for debugging
  - Should convert to proper `logging` module usage

### System Consolidation

- [✅] **Loader Functions**: Clarify responsibilities
  - `load_yaml.py` - Standalone script for initial DB population
  - `loader.py` - Runtime loading into World/QuestSystem
  - ⚠️ Duplicate quest/dialogue loading logic (load_yaml.py has unused functions)

- [✅] **Model Definitions**:
  - Database models in `models.py`
  - In-memory dataclasses in `world.py` and system files
  - Clear separation maintained

### Documentation Sync

- [ ] **Docstrings**: Generally good, some systems need updates
- [ ] **Type Hints**: Most files have complete annotations
- [ ] **Architecture Docs**: Update `ARCHITECTURE.md` to reflect Phase X additions

### Items to Clean Up

1. ✅ Remove or integrate `look_helpers.py` (orphaned module) - REMOVED
2. ⬜ Convert print statements to logging (deferred - many are useful debug info)
3. ✅ Remove unused functions from `load_yaml.py` - REMOVED 3 unused functions
4. ✅ Update ARCHITECTURE.md with quest system - ADDED Game Systems section (3.4)
- [ ] Create integration tests for cross-system interactions
- [ ] Add regression tests for fixed bugs

---

## Phase 6 - Persistence & scaling  ✅ COMPLETE

> 📄 **Documentation**: [phase6_persistence.md](./build_docs/phase6_persistence.md)

**Goals**: Don't lose progress on restart. Support more players in the future.

### Implementation Summary

#### StateTracker System (persistence.py)
- ✅ Dirty entity tracking with `mark_dirty()` and `mark_dirty_sync()`
- ✅ Periodic saves every 60 seconds via TimeEventManager integration
- ✅ Critical saves (immediate) for player death, quest completion
- ✅ Graceful shutdown saves all dirty entities
- ✅ Entity types: players, rooms, NPCs, items, triggers

#### Database Migrations (e1f2a3b4c5d6_phase6_persistence.py)
- ✅ `player_effects` table - stores active effects for offline tick calculation
- ✅ `ground_items` table - tracks dropped items with decay timers
- ✅ `trigger_state` table - persists permanent trigger fire counts
- ✅ `npc_state` table - persists companion/persistent NPC positions and health
- ✅ Added `persist_state` column to `npc_templates`
- ✅ Added `dropped_at` column to `item_instances`

#### Effect Persistence (effects.py)
- ✅ `save_player_effects()` - saves effects with remaining duration
- ✅ `restore_player_effects()` - restores effects on login
- ✅ Offline tick calculation for DoT/HoT effects
- ✅ Integrated with player connect/disconnect lifecycle

#### Item Decay System
- ✅ `dropped_at` timestamp on WorldItem dataclass
- ✅ Items dropped set timestamp for decay tracking
- ✅ Periodic decay check (every 5 minutes)
- ✅ Default 1-hour decay time for ground items

#### Trigger State Persistence (triggers.py)
- ✅ `permanent` flag on RoomTrigger dataclass
- ✅ `save_permanent_trigger_states()` - saves fire counts to DB
- ✅ `restore_permanent_trigger_states()` - restores on startup

#### NPC State Persistence
- ✅ `persist_state` flag on NpcTemplate dataclass
- ✅ Persistent NPCs (companions) save position and health
- ✅ `restore_persistent_npcs()` - restores NPC state on startup

#### Disconnect Handling
- ✅ Player stats saved on disconnect (existing)
- ✅ Player effects saved on disconnect (new)
- ✅ "Stasis" visual feedback for other players

### Future Enhancements
- Horizontal scaling via message bus (Redis/NATS)
- Session handling for mobile reconnect
- Multiple connections per player

## Phase 7 - Accounts, auth, and security ✅ COMPLETE ✅

> 📄 **Documentation**: [phase7_auth.md](./build_docs/phase7_auth.md)

**Goals**: Move from "just a player_id" to real accounts.

### Implementation Complete ✅

**Database Schema** ✅
-  ✅ `user_accounts` table: username, email, password_hash, role, active_character_id
-  ✅ `refresh_tokens` table: token rotation for session management
-  ✅ `security_events` table: audit log for logins, logouts, role changes
-  ✅ `players.account_id` foreign key linking characters to accounts

**AuthSystem (systems/auth.py)** ✅
-  ✅ UserRole enum: PLAYER, MODERATOR, GAME_MASTER, ADMIN
-  ✅ Permission enum: granular permissions (MODIFY_STATS, SPAWN_ITEM, etc.)
-  ✅ JWT-based authentication with 1-hour access tokens
-  ✅ Refresh token rotation with 7-day expiry
-  ✅ Argon2 password hashing via passlib
-  ✅ `requires_role()` and `requires_permission()` decorators

**HTTP Endpoints** ✅
-  ✅ POST `/auth/register` - Create new account
-  ✅ POST `/auth/login` - Get access + refresh tokens
-  ✅ POST `/auth/refresh` - Rotate tokens
-  ✅ POST `/auth/logout` - Revoke refresh token
-  ✅ GET `/auth/me` - Get current user info

**Character Management** ✅
-  ✅ POST `/characters` - Create character (max 3 per account)
-  ✅ GET `/characters` - List account's characters
-  ✅ POST `/characters/{id}/select` - Set active character
-  ✅ DELETE `/characters/{id}` - Delete character

**WebSocket Authentication** ✅
-  ✅ `/ws/game/auth?token=<access_token>` - Authenticated endpoint
-  ✅ Verifies JWT and loads active character
-  ✅ Sets auth_info in context for permission checks
-  ✅ Legacy `/ws/game?player_id=` still works (deprecated)

**Permission Enforcement** ✅
-  ✅ Admin commands (heal, hurt) require GAME_MASTER role
-  ✅ `_check_permission()` method in WorldEngine
-  ✅ Denied commands return error message

**Client Updates** ✅
-  ✅ Login/Register UI with httpx
-  ✅ Authenticated WebSocket connection flow
-  ✅ Legacy mode toggle for backward compatibility

## Phase 8 - Admin & content tools ✅ COMPLETE

> 📄 **Documentation**: [phase8_admin.MD](./build_docs/phase8_admin.MD)

**Goals**: Operate and extend the game without editing code.

### Admin API Foundation ✅

- Route setup:
    - ✅ `backend/app/routes/admin.py` - Dedicated admin router
    - ✅ JWT-based auth with role checking (MODERATOR, GAME_MASTER, ADMIN)
    - ✅ `require_permission()` and `require_role()` dependencies
    - ✅ Registered at `/api/admin` prefix

### Server Status & Monitoring ✅

- GET `/api/admin/server/status`:
    - ✅ Uptime, players online, players in combat
    - ✅ NPCs alive, rooms occupied, total areas
    - ✅ Scheduled events count, next event timing
    - ✅ Maintenance mode flag

### World Inspection APIs ✅

- Player inspection:
    - ✅ GET `/world/players` - List online players with health, location, combat status
    - ✅ GET `/world/players/{id}` - Detailed player info
- World state:
    - ✅ GET `/world/rooms` - List rooms with player/NPC/item counts (filterable by area)
    - ✅ GET `/world/rooms/{id}` - Room details with entities, triggers, flags
    - ✅ GET `/world/areas` - List areas with time scale, room/player counts
    - ✅ GET `/world/npcs` - List NPCs (filterable by room, alive status)
    - ✅ GET `/world/items` - List items (filterable by room, player)

### Player Manipulation APIs ✅

- ✅ POST `/players/{id}/teleport` - Move player to room (TELEPORT permission)
- ✅ POST `/players/{id}/heal` - Heal player (MODIFY_STATS permission)
- ✅ POST `/players/{id}/kick` - Disconnect player (KICK_PLAYER permission)
- ✅ POST `/players/{id}/give` - Give item to player (SPAWN_ITEM permission)
- ✅ POST `/players/{id}/effect` - Apply effect (MODIFY_STATS permission)

### Spawn/Despawn APIs ✅

- ✅ POST `/npcs/spawn` - Spawn NPC from template (SPAWN_NPC permission)
- ✅ DELETE `/npcs/{id}` - Despawn NPC (SPAWN_NPC permission)
- ✅ POST `/items/spawn` - Spawn item in room (SPAWN_ITEM permission)
- ✅ DELETE `/items/{id}` - Despawn item (SPAWN_ITEM permission)

### Broadcast System ✅

- ✅ POST `/server/broadcast` - Send message to all players (ADMIN only)

### Content Hot-Reload System ✅

- ContentReloader class:
    - ✅ `reload_item_templates()` - Reload item definitions from YAML
    - ✅ `reload_npc_templates()` - Reload NPC definitions from YAML
    - ✅ `reload_rooms()` - Update room descriptions and exits
    - ✅ `reload_areas()` - Update area configurations
    - ✅ `reload_all()` - Reload all content types

- Validation before reload:
    - ✅ `validate_yaml_file()` - Check YAML syntax and required fields
    - ✅ Validation for each content type (areas, rooms, items, NPCs)
    - ✅ Returns detailed error/warning lists

- Endpoints:
    - ✅ POST `/content/reload` - Hot-reload content (ADMIN only)
    - ✅ POST `/content/validate` - Validate YAML files (GAME_MASTER+)

### In-World Admin Commands ✅

- MODERATOR commands:
    - ✅ `who` - List online players with locations
    - ✅ `where <player>` - Show specific player's location
    - ✅ `kick <player> [reason]` - Disconnect player

- GAME_MASTER commands:
    - ✅ `goto <room_id>` or `goto <player>` - Teleport self
    - ✅ `summon <player>` - Teleport player to you
    - ✅ `teleport <player> <room_id>` - Teleport player to room
    - ✅ `spawn <npc|item> <template_id>` - Spawn entity in current room
    - ✅ `despawn <npc> <id>` - Remove NPC
    - ✅ `give <player> <item_template_id> [quantity]` - Give item to player
    - ✅ `setstat <player> <stat> <value>` - Modify player stat
    - ✅ `heal <player> [amount]` - Heal player (existing)
    - ✅ `hurt <player> <amount>` - Damage player (existing)

- ADMIN commands:
    - ✅ `broadcast <message>` - Send message to all players

### Structured Logging ✅

- `backend/app/logging.py`:
    - ✅ structlog configuration (JSON for prod, pretty for dev)
    - ✅ Custom processors: timestamp, service name, sensitive data redaction
    - ✅ AdminAuditLogger - Specialized logging for admin actions
    - ✅ GameEventLogger - Combat, player connect/disconnect, deaths
    - ✅ PerformanceLogger - Command timing, tick duration, DB queries

- Audit logging integrated:
    - ✅ All admin API endpoints log to AdminAuditLogger
    - ✅ Teleport, kick, give, spawn, despawn actions tracked
    - ✅ Content reload operations logged

### Database Audit Tables ✅

- Migration `a1b2c3d4e5f6_phase8_admin_audit.py`:
    - ✅ `admin_actions` table - All admin action audit logs
    - ✅ `server_metrics` table - Historical performance metrics
    - ✅ Proper indexes for time-series queries

### Models Added ✅

- ✅ `AdminAction` - Audit log entry for admin actions
- ✅ `ServerMetric` - Performance metric snapshot

### Dependencies ✅

- ✅ Added `structlog==25.3.0` to requirements.txt

## Phase 9 - Classes & Abilities ✅ COMPLETE ✅

> 📄 **Documentation**: [phase9_classes_design.md](./build_docs/phase9_classes_design.md) | [phase9_classes_implementation.md](./build_docs/phase9_classes_implementation.md)

**Goals**: Extensible character class system with unique abilities, resource management, and progression paths.

**Status:** ✅ **9a-9h All Complete** | ⬜ 9i-9j (Future Enhancement)

### Phase 9a - Domain Models & Database ✅

- ✅ **Core Dataclasses** (backend/app/engine/world.py):
    - ✅ `ResourceDef`: Defines resource pools (mana, rage, energy) with regen mechanics
    - ✅ `StatGrowth`: Tracks stat scaling per level with milestone bonuses
    - ✅ `ResourcePool`: Runtime state for character resources
    - ✅ `AbilitySlot`: Equipped ability with cooldown tracking
    - ✅ `CharacterSheet`: Character class, level, experience, learned abilities, resources

- ✅ **Enhanced WorldPlayer**:
    - ✅ Optional `character_sheet: CharacterSheet | None` field
    - ✅ Helper methods: has_character_sheet(), get_class_id(), get_resource_pool(), etc.

- ✅ **Database Migration**:
    - ✅ Backward-compatible with existing player data
    - ✅ Phase 9a migration script ready

### Phase 9b - Content Files & Loaders ✅

- ✅ **YAML Loaders** (backend/app/engine/systems/abilities.py):
    - ✅ `ClassTemplate` dataclass with base_stats, stat_growth, resources, abilities
    - ✅ `AbilityTemplate` dataclass with cooldown, effects, scaling, targeting
    - ✅ `load_classes_from_yaml()` with error handling
    - ✅ `load_abilities_from_yaml()` with duplicate ID detection

- ✅ **Example Content**:
    - ✅ 3 Classes: warrior.yaml, mage.yaml, rogue.yaml (stat-based specialization)
    - ✅ 15 Abilities: 3 core + 2 warrior + 5 mage + 5 rogue
    - ✅ Schema files: `_schema.yaml` for content creators

### Phase 9c - ClassSystem Runtime Manager ✅

- ✅ **Implemented `ClassSystem` in `app/engine/systems/classes.py`**:
    - ✅ `__init__()` - Initialize templates and behavior registry
    - ✅ `load_content()` - Load YAML classes and abilities
    - ✅ `get_class()` - Retrieve class by ID
    - ✅ `get_ability()` - Retrieve ability by ID
    - ✅ `register_behavior()` - Register behavior functions
    - ✅ `get_behavior()` - Retrieve registered behavior
    - ✅ `_register_core_behaviors()` - Register 24 built-in behaviors
    - ✅ `reload_behaviors()` - Hot-reload custom behaviors

- ✅ **Integrated into `WorldEngine` and `GameContext`**:
    - ✅ ClassSystem instance created in engine
    - ✅ Content loaded at startup

### Phase 9d - Core Ability Behaviors ✅

- ✅ **Behavior Infrastructure** (backend/app/engine/systems/ability_behaviors/):
    - ✅ `BehaviorResult` dataclass: success, damage_dealt, targets_hit, effects_applied, cooldown_applied
    - ✅ Package structure with `__init__.py`, `core.py`, `custom.py`, `utility.py`

- ✅ **11 Core Behaviors** (core.py):
    - ✅ melee_attack, power_attack, rally (passive), aoe_attack, stun_effect
    - ✅ mana_regen, fireball, polymorph, backstab, evasion (passive), damage_boost

- ✅ **5 Custom Behaviors** (custom.py):
    - ✅ Warrior: whirlwind_attack, shield_bash
    - ✅ Mage: inferno, arcane_missiles
    - ✅ Rogue: shadow_clone

- ✅ **8 Utility Behaviors** (utility.py):
    - ✅ create_light, darkness, unlock_door, unlock_container, detect_magic, true_sight, teleport, create_passage

- ✅ **Behavior Registration**:
    - ✅ All 24 behaviors registered in ClassSystem._register_core_behaviors()
    - ✅ Each behavior handles hit/miss, damage calculation, stat scaling
    - ✅ Server imports and starts correctly

### Phase 9e - Ability Executor & Validation ✅

- ✅ **Implemented `AbilityExecutor` in `app/engine/systems/abilities.py`**:
    - ✅ `execute_ability()` - Main entry point with full async support
    - ✅ `_validate_ability_use()` - Check learned, level, resources, cooldown, GCD
    - ✅ `_resolve_targets()` - Interpret target_type and resolve targets
    - ✅ `_apply_cooldowns()` - Set personal cooldown + GCD
    - ✅ `get_ability_cooldown()` - Query remaining cooldown
    - ✅ `get_gcd_remaining()` - Query remaining GCD
    - ✅ `clear_cooldown()` / `clear_gcd()` - Admin debug methods

- ✅ **Cooldown/GCD Logic**:
    - ✅ Personal cooldown per ability (tracked independently)
    - ✅ Global cooldown by category (shared across abilities)
    - ✅ Full validation pipeline (all paths tested)
    - ✅ Integrated into `WorldEngine`

### Phase 9f - Commands & Router Integration ✅

- ✅ **Commands Added** (backend/app/engine/engine.py):
    - ✅ `cast <ability_name> [target]` - Execute ability
    - ✅ `ability <ability_name> [target]` - Alias for cast
    - ✅ `abilities` / `skills` - List equipped abilities and cooldowns
    - ✅ `resources` - Show current resource pools

- ✅ **Command Handler Implementation**:
    - ✅ Case-insensitive ability name matching
    - ✅ Target resolution by name in current room
    - ✅ Error messages for validation failures
    - ✅ Full integration with routing system

### Phase 9g - Admin API Endpoints ✅

- ✅ **Endpoints in `app/routes/admin.py`**:
    - ✅ `GET /api/admin/classes` - List all classes with metadata
    - ✅ `GET /api/admin/abilities` - List all abilities with metadata
    - ✅ `POST /api/admin/classes/reload` - Hot-reload classes, abilities, and behaviors

- ✅ **Admin Functionality**:
    - ✅ Hot-reload YAML without server restart
    - ✅ Return counts of loaded classes/abilities
    - ✅ Error handling and validation
    - ✅ Permission checks (GAME_MASTER+)

### Phase 9h - WebSocket Protocol & Events ✅

- ✅ **Event Types** (backend/app/engine/systems/events.py):
    - ✅ `ability_cast` - Broadcast when ability used
    - ✅ `ability_error` - Send when validation fails
    - ✅ `ability_cast_complete` - After behavior executes
    - ✅ `cooldown_update` - Remaining cooldown for ability
    - ✅ `resource_update` - Current/max resource amounts

- ✅ **Event Implementation**:
    - ✅ Events emitted from AbilityExecutor
    - ✅ Broadcast to room (combat) or player (personal)
    - ✅ Full payload with damage, targets, effects
    - ✅ Integrated with EventDispatcher

### Phase 9i - Persistence & Offline Regen ⬜

- [ ] `save_player_resources()` - Serialize pools to player.data JSON (deferred to Phase 9j)
- [ ] `restore_player_resources()` - Deserialize from JSON (deferred to Phase 9j)
- [ ] Offline regen calculation (time_offline × regen_rate) (deferred to Phase 9j)
- [ ] Integrate into disconnect/reconnect handlers (deferred to Phase 9j)

### Phase 9j - Polish & Testing ⬜

- [ ] Unit tests: ClassSystem, AbilityExecutor, resources, targeting (future)
- [ ] Integration tests: end-to-end ability casting flow (future)
- [ ] Documentation: ARCHITECTURE.md updates, content creator guide (future)
- [ ] Performance profiling (future)

## Phase 10 - Socializing and worldbuilding ✅ COMPLETE

> 📄 **Documentation**: [phase10_socials.md](./build_docs/phase10_socials.md) | [phase10_socials_design.md](./build_docs/phase10_socials_design.md) | [phase10_socials_implementation.md](./build_docs/phase10_socials_implementation.md) | [phase10_socials_research_summary.md](./build_docs/phase10_socials_research_summary.md)

### Phase 10.1: Groups, Tells, Follow ✅ COMPLETE
- ✅ GroupSystem with O(1) lookups and auto-disband
- ✅ Group/tell/follow/yell commands with full subcommands
- ✅ Event routing for group/tell/follow scopes
- ✅ 80+ comprehensive tests
- ✅ Integration documentation

### Phase 10.2: Persistent Clans ✅ COMPLETE
- ✅ Database migration with clans and clan_members tables
- ✅ Clan and ClanMember ORM models with relationships
- ✅ ClanSystem with async DB loading, CRUD operations
- ✅ Rank hierarchy (leader > officer > member > initiate)
- ✅ Clan commands (create, invite, join, leave, promote, members, info, disband)
- ✅ Clan message event routing to all members
- ✅ WorldEngine integration with async initialization
- ✅ 50+ comprehensive tests

### Phase 10.3: Factions with Reputation
- ✅ Database migration with factions and faction_npc_members tables
- ✅ Faction and FactionNPCMember ORM models
- ✅ FactionSystem with YAML loading, reputation tracking, alignment tiers
- ✅ O(1) NPC faction lookups and behavior changes
- ✅ Faction commands (list, info, join, leave, standing)
- ✅ 4 faction YAML definitions (Silver Sanctum, Shadow Syndicate, Arcane Collective, Primal Circle)
- ✅ Faction message event routing to all members
- ✅ WorldEngine integration with YAML loading at startup
- ✅ 45+ comprehensive tests

## Phase 11 - Light and Vision System ✅ COMPLETE

> 📄 **Documentation**: [phase11_lighting_design.md](./build_docs/phase11_lighting_design.md)

**Goals**: Dynamic lighting system with visibility-based gameplay, environmental atmosphere, and light-dependent triggers.

### Phase 11.1: Core Light Calculation System
- ✅ LightingSystem class with 0-100 light scale
- ✅ 5 visibility levels: NONE (0-10), MINIMAL (11-25), PARTIAL (26-50), NORMAL (51-75), ENHANCED (76-100)
- ✅ Database migration k3l4m5n6o7p8_phase11_light_system.py
- ✅ Room.lighting_override field for room-specific light levels
- ✅ ItemTemplate light fields: provides_light, light_intensity, light_duration
- ✅ AMBIENT_LIGHTING_VALUES mapping: pitch_black(0), dark(10), dim(20), shadowed(35), normal(60), bright(85), prismatic(90)
- ✅ TIME_IMMUNE_BIOMES: underground, ethereal, void, planar

### Phase 11.2: Visibility Filtering
- ✅ Modified _look() command with light level checks
- ✅ Modified _look_at_target() requiring minimum light
- ✅ Entity filtering based on visibility thresholds
- ✅ Admin lightlevel debugging command showing:
  - ✅ Base ambient lighting from area
  - ✅ Time-of-day modifier calculation
  - ✅ Active light sources (spells/items)
  - ✅ Darkness penalties
  - ✅ Final effective light level

### Phase 11.3: System Integration
- ✅ Spell Integration:
  - ✅ create_light_behavior() calls lighting_system.update_light_source()
  - ✅ darkness_behavior() applies negative light intensity
  - ✅ Light/darkness spells affect room lighting
- ✅ Time Integration:
  - ✅ Time-of-day modifiers: Night(-20), Dawn/Dusk(-10), Day(0)
  - ✅ recalculate_all_rooms() triggered on time period changes
  - ✅ Batch updates during dawn/dusk transitions
- ✅ Item Light Sources:
  - ✅ Equip/unequip handlers activate/deactivate light sources
  - ✅ 4 sample light items: Torch (35, 30min), Lantern (45, permanent), Glowstone (50, permanent, +1 INT), Candle (20, 15min)
  - ✅ Duration tracking and automatic expiration

### Phase 11.4: Environmental Content
- ✅ Areas Created:
  - ✅ Dark Caves (ambient: dim, biome: underground, danger: 3)
  - ✅ Sunlit Meadow (ambient: bright, biome: grassland, danger: 1)
- ✅ Rooms Created (9 total):
  - ✅ Cave rooms: entrance(40), tunnel(5), bioluminescent chamber(65), deep cave(0)
  - ✅ Meadow rooms: center(95), shaded grove(70), open field(default), eastern rise(90), flower garden(default)
- ✅ All content loaded into database
- ✅ Demonstrates full range of lighting values (0-95)

### Phase 11.5: Trigger Conditions and Events
- ✅ New Trigger Conditions:
  - ✅ light_level: Check room light with comparison operators
  - ✅ visibility_level: Check specific visibility threshold (none/minimal/partial/normal/enhanced)
- ✅ New Trigger Actions:
  - ✅ stumble_in_darkness: Damage player in low light with room notification
- ✅ Sample Triggers:
  - ✅ darkness_stumble.yaml: Damage when entering very dark rooms
  - ✅ bright_light_secret.yaml: Reveal hidden passage in enhanced light
  - ✅ shadow_spawn_darkness.yaml: Spawn hostile NPCs in darkness
  - ✅ light_dependent_desc.yaml: Change room description based on light

### Testing and Validation
- ✅ Comprehensive test suite (test_phase11.py)
- ✅ 26/26 tests passing (100% pass rate)
- ✅ Tests cover: light calculation, time integration, light sources, visibility filtering, item properties, environmental content, trigger integration

---

## Phase 12 - CMS API Integration ✅ COMPLETE

> 📄 **Documentation**: [cms_gaps.md](./build_docs/cms_gaps.md)
> 📄 **Documentation**: [CMS_DEVELOPMENT_GUIDE.md](./build_docs/CMS_DEVELOPMENT_GUIDE.md)

**Goals**: Provide complete REST API endpoints for the Daemonswright CMS to create, read, update, and manage game content without direct file system access.

**Status**: All phases complete ✅ | **Priority**: High (blocks CMS development)

### Phase 12.1 - Schema Registry API ✅ COMPLETE

**Purpose**: Enable CMS to dynamically fetch schema definitions for all content types

- ✅ **Core Endpoint**:
    - ✅ `GET /api/admin/schemas` - Return all `_schema.yaml` files with metadata
    - ✅ Response includes: content, last_modified, checksum (SHA256)
    - ✅ Optional filtering by content_type (rooms, items, npcs, etc.)
    - ✅ Proper JSON formatting with schema count and success status

- ✅ **Schema Metadata**:
    - ✅ `GET /api/admin/schemas/version` - Current schema version info
    - ✅ Response includes: version, engine_version, last_modified, schema_count
    - ✅ Used for cache invalidation in CMS

- ✅ **Integration**:
    - ✅ SchemaRegistry class in `backend/app/engine/systems/schema_registry.py`
    - ✅ Caches parsed schemas on server startup (13 schemas loaded)
    - ✅ Hot-reload support via `POST /api/admin/schemas/reload` endpoint
    - ✅ SHA256 checksums for content validation
    - ✅ Integrated with WorldEngine and GameContext

- ✅ **Testing**:
    - ✅ All schemas load correctly from world_data subdirectories
    - ✅ Filtering by content type works properly
    - ✅ Checksums computed correctly
    - ✅ Version metadata tracks most recent schema update
    - ✅ Reload functionality verified

**Status**: ✅ Complete - Ready for CMS Phase 1 (TypeScript type generation)

### Phase 12.2 - YAML File Management API ✅ COMPLETE

**Purpose**: Enable CMS to upload, download, and list YAML content files

- ✅ **File Operations**:
    - ✅ `GET /api/admin/content/files` - List all YAML files in world_data/
    - ✅ Supports filtering by content_type
    - ✅ Optional include_schema_files parameter
    - ✅ Returns file metadata: path, size, last_modified, content_type
    - ✅ Includes file statistics per content type

- ✅ **Download Content**:
    - ✅ `GET /api/admin/content/download?file_path=<path>` - Download raw YAML
    - ✅ Returns content, checksum, last_modified
    - ✅ Supports all content types (rooms, items, npcs, etc.)
    - ✅ Path traversal attack prevention

- ✅ **Upload/Update Content**:
    - ✅ `POST /api/admin/content/upload` - Create or update YAML file
    - ✅ Request: file_path, content (raw YAML string), validate_only flag
    - ✅ Optional `validate_only=true` for dry-run validation
    - ✅ Response: validation_errors, file_written, checksum
    - ✅ Atomic write operations (temp file + rename)
    - ✅ YAML syntax validation before writing

- ✅ **File Management**:
    - ✅ `DELETE /api/admin/content/file` - Delete YAML files
    - ✅ `GET /api/admin/content/stats` - File counts per content type
    - ✅ Schema file deletion protection

- ✅ **Security Features**:
    - ✅ Path traversal attack prevention (all unsafe paths blocked)
    - ✅ File path validation relative to world_data root
    - ✅ Atomic file operations prevent partial writes
    - ✅ Schema files protected from deletion

- ✅ **Integration**:
    - ✅ FileManager class in `backend/app/engine/systems/file_manager.py`
    - ✅ Integrated with WorldEngine and GameContext
    - ✅ 73 YAML files managed across 13 content types
    - ✅ Comprehensive test suite with security validation

**Status**: ✅ Complete - Ready for CMS Phase 2 (File explorer and editor)

### Phase 12.3 - Enhanced Validation API ✅

**Purpose**: Provide real-time validation feedback during content editing

- ✅ **Enhanced Validation Endpoints**:
    - ✅ `POST /api/admin/content/validate-enhanced` - Full validation with line/column errors
    - ✅ `POST /api/admin/content/validate-references` - Reference-only validation
    - ✅ `POST /api/admin/content/rebuild-reference-cache` - Cache rebuild after bulk changes
    - ✅ Accepts raw YAML string (not just file_path)
    - ✅ Validates syntax with YAML parser (line/column extraction)
    - ✅ Validates schema conformance (required fields, types)
    - ✅ Validates references (foreign keys to rooms, items, NPCs, etc.)

- ✅ **Validation Features**:
    - ✅ Syntax validation: Line/column error positions from YAMLError
    - ✅ Schema validation: Required field checking for 11 content types
    - ✅ Reference validation: Cross-content link checking (exits, abilities, factions, etc.)
    - ✅ Error severity: Errors (blocking) and warnings (non-blocking)
    - ✅ Helpful suggestions: Fix hints for common errors

- ✅ **Reference Validation**:
    - ✅ Detects: invalid room exits, missing abilities, non-existent factions/dialogues
    - ✅ Returns: field path, line/column, error message, suggestion
    - ✅ Cross-content validation (e.g., quest references NPC that exists)
    - ✅ Reference cache with O(1) lookups for all entity types

- ✅ **Validation Response Format**:
    ```json
    {
      "valid": false,
      "success": false,
      "errors": [
        {
          "severity": "error",
          "message": "YAML syntax error: mapping values are not allowed here",
          "line": 15,
          "column": 3,
          "field_path": null,
          "error_type": "syntax",
          "suggestion": "Check YAML indentation and special characters"
        },
        {
          "severity": "error",
          "message": "Exit 'north' points to non-existent room 'room_99'",
          "line": null,
          "column": null,
          "field_path": "exits.north",
          "error_type": "reference",
          "suggestion": "Create room 'room_99' or fix the exit destination"
        }
      ],
      "warnings": [
        {
          "message": "Schema registry not available - using basic field validation only",
          "line": null,
          "column": null,
          "field_path": null,
          "warning_type": "general",
          "suggestion": null
        }
      ],
      "content_type": "rooms",
      "file_path": "rooms/tavern.yaml",
      "error_count": 2,
      "warning_count": 1
    }
    ```

- ✅ **Integration**:
    - ✅ ValidationService class in `backend/app/engine/systems/validation_service.py`
    - ✅ ReferenceCache indexes 11 entity types (rooms, items, NPCs, abilities, etc.)
    - ✅ Integrated with WorldEngine and GameContext
    - ✅ Works with SchemaRegistry and FileManager
    - ✅ Comprehensive test suite (6 test suites, all passing)

**Status**: ✅ Complete - Ready for CMS Phase 2A (Monaco editor with real-time validation)

### Phase 12.4 - Content Querying API ✅

**Purpose**: Enable CMS to query and search existing content for references and dependencies

- ✅ **Content Search**:
    - ✅ `GET /api/admin/content/search?q=<query>&type=<type>` - Full-text search
    - ✅ Search across: IDs, names, descriptions, content-specific fields
    - ✅ Returns matching content with context snippets and relevance scores
    - ✅ Supports filtering by content_type
    - ✅ Exact ID matches score highest (10.0), partial matches lower

- ✅ **Dependency Graph**:
    - ✅ `GET /api/admin/content/dependencies?entity_type=<type>&entity_id=<id>` - Get dependencies
    - ✅ Returns: what this entity references (outgoing), what references it (incoming)
    - ✅ Bidirectional tracking: rooms→exits, classes→abilities, NPCs→factions, etc.
    - ✅ Safe delete checking with blocking reference list
    - ✅ Orphaned entity detection

- ✅ **Content Analytics**:
    - ✅ `GET /api/admin/content/analytics` - Comprehensive health metrics
    - ✅ Entity counts by type (rooms, items, NPCs, quests, etc.)
    - ✅ Broken reference detection and reporting
    - ✅ Orphaned content identification
    - ✅ Most referenced entities ranking
    - ✅ Average references per entity

- ✅ **Graph Management**:
    - ✅ `POST /api/admin/content/rebuild-dependency-graph` - Rebuild after bulk changes
    - ✅ Automatic bidirectional indexing

- ✅ **Integration**:
    - ✅ QueryService class in `backend/app/engine/systems/query_service.py`
    - ✅ Integrated with FileManager and ValidationService
    - ✅ 6 test suites, all passing
    - ✅ O(1) dependency lookups via graph indexing

**Status**: ✅ Complete - Ready for CMS Phase 3A (dependency visualization, safe deletion)

### Phase 12.5 - Bulk Operations API ✅ COMPLETE

**Purpose**: Enable efficient bulk import/export for large content sets

- ✅ **Bulk Import**:
    - ✅ `POST /api/admin/content/bulk-import` - Import multiple YAML files
    - ✅ Accepts: {file_path: yaml_content} dictionary
    - ✅ Pre-validates all files before writing any (atomic operations)
    - ✅ Returns: total_files, files_validated, files_written, files_failed, detailed results per file
    - ✅ Transaction-like behavior: rollback_on_error option (all or nothing)
    - ✅ validate_only mode for dry-run testing
    - ✅ Automatic backup of existing files before import
    - ✅ Full rollback capability on validation failures

- ✅ **Bulk Export**:
    - ✅ `POST /api/admin/content/bulk-export` - Export content to ZIP archive
    - ✅ Filters: content_type, include_schema_files, specific file_paths
    - ✅ ZIP format with manifest.json metadata
    - ✅ Manifest includes: export timestamp, file count, content types, engine version
    - ✅ Preserves directory structure (rooms/, items/, npcs/, etc.)
    - ✅ Streaming ZIP response for large datasets

- ✅ **Batch Validation**:
    - ✅ `POST /api/admin/content/batch-validate` - Validate multiple files at once
    - ✅ Returns: total_files, valid_files, invalid_files, detailed ValidationResult per file
    - ✅ Parallel validation for performance
    - ✅ Used during bulk import preview

- ✅ **Async Architecture Refactor**:
    - ✅ Converted FileManager to fully async (aiofiles for non-blocking I/O)
    - ✅ Converted QueryService to async (search, build_dependency_graph, get_analytics, get_dependencies)
    - ✅ Converted ValidationService to async (validate_full, validate_references, build_reference_cache)
    - ✅ All admin route endpoints properly await async service calls
    - ✅ Eliminates event loop blocking throughout CMS API
    - ✅ Enables proper concurrent I/O operations

- ✅ **Integration**:
    - ✅ BulkService class in `backend/app/engine/systems/bulk_service.py`
    - ✅ Integrated with FileManager, ValidationService, SchemaRegistry
    - ✅ Works with WorldEngine and GameContext
    - ✅ Comprehensive test suite (17 tests, 9 core tests passing)

**Status**: ✅ Complete - Ready for CMS Phase 4 (bulk import/export features)

### Phase 12.6 - Git Integration (Optional) ⬜

**Purpose**: Provide server-side git operations for version control

- [ ] **Git Status**:
    - [ ] `GET /api/admin/git/status` - Current git status
    - [ ] Returns: branch, uncommitted changes, untracked files
    - [ ] Used for UI indicators in CMS

- [ ] **Commit Operations**:
    - [ ] `POST /api/admin/git/commit` - Commit specified files
    - [ ] Request: message, files (array of paths)
    - [ ] Returns: commit hash, timestamp

- [ ] **Push/Pull** (Future):
    - [ ] `POST /api/admin/git/push` - Push to remote
    - [ ] `POST /api/admin/git/pull` - Pull from remote
    - [ ] Conflict detection and resolution UI

**Note**: This is optional - CMS can manage local git clone instead. Server-side git is cleaner but adds complexity.

**Priority**: Low (CMS can handle git client-side)

### Phase 12.7 - Real-Time Preview API ⬜

**Purpose**: Enable CMS to preview content changes without committing to database

- [ ] **Preview Mode**:
    - [ ] `POST /api/admin/content/preview` - Load content into temporary sandbox
    - [ ] Creates isolated WorldEngine instance
    - [ ] Returns: preview_session_id, expires_at

- [ ] **Preview Queries**:
    - [ ] `GET /api/admin/preview/{session_id}/room/{room_id}` - Preview room state
    - [ ] `GET /api/admin/preview/{session_id}/validate` - Validate preview state
    - [ ] Preview expires after 15 minutes or manual cleanup

- [ ] **Preview WebSocket** (Future):
    - [ ] Connect to preview session with test player
    - [ ] Walk through content changes in real-time
    - [ ] Full game engine in sandbox mode

**Priority**: Medium (nice-to-have for Phase 5 CMS preview features)

---

## Phase 13 - Test Engine & CI/CD ✅ COMPLETE

> 📄 **Documentation**: [phase13_abilities_testing_plan.md](./build_docs/phase13_abilities_testing_plan.md)

**Goals**: Build robust testing infrastructure and continuous integration pipeline before auditing ability behaviors.

**Status**: ✅ All immediate actions complete

**Rationale**: Deferred the ability audit to a later phase. Before locking down default ability behaviors, we want to give content creators maximum flexibility. The ability system is mature and stable; a comprehensive audit will be more valuable once we better understand content creation patterns.

**Completed Work**:
- ✅ Comprehensive test fixtures (conftest.py, ability_samples.py)
- ✅ Coverage reporting (.coveragerc, coverage.xml)
- ✅ GitHub Actions CI/CD (test.yml)
- ✅ Pre-commit hooks for code quality
- ✅ Fixed existing test failures

**Future Work** (Deferred):
- [ ] Systematic testing of all 29 ability behaviors
- [ ] Validate AbilityExecutor execution pipeline
- [ ] Comprehensive edge case testing
- [ ] Performance profiling of ability system

---

---

## Phase 14 - Entity Abilities ✅ COMPLETE

> 📄 **Documentation**: [phase14_entity_abilities_DESIGN.md](./build_docs/phase14_entity_abilities_DESIGN.md) | [phase14_entity_abilities_1_COMPLETE.md](./build_docs/phase14_entity_abilities_1_COMPLETE.md) | [phase14_entity_abilities_1_REFACTOR.md](./build_docs/phase14_entity_abilities_1_REFACTOR.md) | [phase14_entity_abilities_world_entity_changes.md](./build_docs/phase14_entity_abilities_world_entity_changes.md)

**Goals**: Extend the ability system from players to all entities (NPCs, magic items, environmental objects).

### Phase 14.1: Universal Entity Ability Support ✅
- ✅ Moved `character_sheet` to WorldEntity base class
- ✅ Moved 6 helper methods to WorldEntity (has_character_sheet, get_class_id, etc.)
- ✅ Updated NpcTemplate with class_id, default_abilities, ability_loadout fields
- ✅ Database migration l4m5n6o7p8q9_phase14_npc_abilities.py
- ✅ Updated ORM model in models.py

### Phase 14.2: Ability System Generalization ✅
- ✅ Refactored AbilityExecutor to accept WorldEntity instead of WorldPlayer
- ✅ Updated all method type hints and docstrings
- ✅ Verified all 24 ability behaviors are entity-agnostic
- ✅ Implemented NPC resource regeneration in engine.py
- ✅ All 25 ability tests pass

### Phase 14.3: NPC AI Integration ✅
- ✅ Added ability hooks to BehaviorScript base class
- ✅ Extended BehaviorContext with ability helpers (get_available_abilities, etc.)
- ✅ Added `cast_ability` to BehaviorResult
- ✅ Created CasterAI and TacticalCasterAI behaviors (combat_caster.py)
- ✅ Created BruteAI and BerserkerAI behaviors (combat_brute.py)
- ✅ Integrated ability casting into combat flow via on_combat_action hook
- ✅ Added _npc_cast_ability helper to WorldEngine

### Phase 14.4: Content & Loading ✅
- ✅ Updated NPC YAML schema with class_id, default_abilities, ability_loadout, ai_behavior
- ✅ Added create_npc_character_sheet() helper in loader.py
- ✅ NPC character sheets initialized after ClassSystem loads
- ✅ Character sheet restored on NPC respawn
- ✅ Created example NPCs:
  - ✅ goblin_shaman.yaml (Mage with CasterAI)
  - ✅ skeleton_champion.yaml (Warrior with BruteAI)
  - ✅ forest_guardian.yaml (Nature mage with TacticalCasterAI)

### Phase 14.5: Events & Admin Integration ✅
- ✅ Added `entity_type` field to `ability_cast` and `ability_cast_complete` events
- ✅ NPC ability casts broadcast flavor messages to room (⚡ format)
- ✅ Extended `NpcSummary` model with ability fields (class_id, has_abilities, resource_pools, etc.)
- ✅ Added `verbose=True` query param to `GET /world/npcs` for ability details

### Phase 14.6: Testing ✅
- ✅ Added `with_character_sheet()` method to WorldNpcBuilder
- ✅ Added `npc_mage_sheet` and `mock_npc_caster` fixtures
- ✅ Comprehensive test suite (test_npc_abilities.py - 16 tests):
  - ✅ NPC ability casting with character_sheet
  - ✅ NPC without character_sheet validation
  - ✅ NPC ability learning validation
  - ✅ NPC mana consumption
  - ✅ NPC cooldown tracking (independent from players)
  - ✅ Entity type in ability events
  - ✅ Builder pattern tests
  - ✅ Integration tests (NPC targeting players, GCD, multiple NPCs)

### Future Enhancements

**NPC AI**:
- Dynamic difficulty scaling (NPCs use more abilities on higher difficulty)
- NPC ability combos (coordinated ability usage between allied NPCs)
- Learning AI (NPCs adapt ability usage based on player behavior)
- Ability teaching (NPCs can teach players new abilities via dialogue/quests)

**Magic Items** (Phase 14+ enabled):
- Staffs/wands with charged spell abilities
- Weapons with special attack abilities (whirlwind, cleave)
- Armor with defensive abilities (shield block, dodge)
- Consumables that grant temporary abilities
- Items that recharge abilities via rest/mana transfer

**Environmental Objects** (Phase 14+ enabled):
- Explosive barrels (AoE damage ability on destruction)
- Healing fountains (periodic AoE heal ability)
- Magical traps (spike/poison abilities triggered by proximity)
- Ballistas/cannons (mounted weapon abilities)
- Cursed totems (debuff aura abilities)
- Interactive objects (lockpick triggers "unlock" ability)

---

## Phase π - PyPI Distribution ✅

**Goals**: Make the engine easily installable via pip and provide CLI commands for running the server and client.

### Package Refactoring ✅
- ✅ Restructured codebase for PyPI compatibility
- ✅ Created proper package structure with `pyproject.toml`
- ✅ Published to PyPI as `daemons-engine`
- ✅ Easy installation: `pip install daemons-engine`

### CLI Commands ✅
- ✅ `daemons server` - Start the game server
- ✅ `daemons client` - Launch the game client
- ✅ Unified entry point for all engine functionality

---

## Phase 15 - Player quality of life ⬜
In-game documentation: listing all commands, player role, etc
Stub client tweaks


## Phase 16 - Cybersecurity Audit and Hardening ✅

**Goals**: Harden the engine against common web attacks, ensure secure authentication, and protect against malicious input from clients.

### Existing Strengths:
- ✅ SQLAlchemy ORM (parameterized queries prevent SQL injection)
- ✅ Argon2 password hashing (OWASP recommended)
- ✅ JWT with refresh token rotation
- ✅ Role-based access control
- ✅ Path traversal protection in FileManager
- ✅ Safe YAML loading (yaml.safe_load)
- ✅ Security event logging (SecurityEvent table)

### Phase 16.1 - Rate Limiting ✅

**Purpose**: Prevent brute-force attacks and API abuse

- ✅ Integrated `slowapi` library for HTTP rate limiting
- ✅ Rate limit auth endpoints:
    - ✅ `POST /auth/login` - 5 attempts per minute per IP
    - ✅ `POST /auth/register` - 3 attempts per minute per IP
    - ✅ `POST /auth/refresh` - 10 attempts per minute per token
    - ✅ `POST /auth/logout` - 10 attempts per minute per IP
- ✅ Rate limit WebSocket messages:
    - ✅ Commands per second limit (30/sec)
    - ✅ Chat message throttling (5/sec)
- ✅ Created `rate_limit.py` module with:
    - ✅ `WebSocketRateLimiter` class for connection-based throttling
    - ✅ Sliding window algorithm for accurate rate tracking
    - ✅ Configurable limits via `RATE_LIMITS` dictionary
- ✅ Return `429 Too Many Requests` with `Retry-After` header
- ✅ X-Forwarded-For header support for reverse proxy setups

### Phase 16.2 - Account Lockout ✅

**Purpose**: Prevent credential stuffing and brute-force password attacks

- ✅ Add `failed_login_attempts` column to `UserAccount`
- ✅ Add `locked_until` timestamp column to `UserAccount`
- ✅ Created Alembic migration `n6o7p8q9r0s1_phase16_2_account_lockout.py`
- ✅ Implement lockout logic in `AuthSystem.login()`:
    - ✅ Lock account after 5 failed attempts (`MAX_FAILED_LOGIN_ATTEMPTS`)
    - ✅ 15-minute lockout duration (`LOCKOUT_DURATION_SECONDS`)
    - ✅ Reset counter on successful login
    - ✅ Auto-unlock when lockout expires
- ✅ Log lockout events to `SecurityEvent` table:
    - ✅ Added `ACCOUNT_LOCKED` event type
    - ✅ Added `ACCOUNT_UNLOCKED` event type
- ✅ Admin endpoint `POST /admin/unlock-account` to unlock accounts manually
- ⏭️ CAPTCHA integration skipped (can be added later if needed)

### Phase 16.3 - JWT Hardening ✅

**Purpose**: Secure token handling and prevent token-based attacks

- ✅ Production mode SECRET_KEY enforcement:
    - ✅ `DAEMONS_ENV=production` triggers production mode
    - ✅ Startup error if `JWT_SECRET_KEY` not set in production
    - ✅ Helpful error message with key generation command
- ✅ CLI `--production` flag for `daemons run`:
    - ✅ Sets `DAEMONS_ENV=production` automatically
    - ✅ Prompts user to generate secret key if not set
    - ✅ Option to set key for current session interactively
    - ✅ Shows commands for PowerShell, Bash, and .env file
- ✅ Add token claims validation:
    - ✅ `iss` (issuer) claim: configurable via `JWT_ISSUER` env var
    - ✅ `aud` (audience) claim: configurable via `JWT_AUDIENCE` env var
    - ✅ `exp` validation with 30-second clock skew tolerance (`CLOCK_SKEW_TOLERANCE_SECONDS`)
    - ✅ Required claims: `iat`, `exp`, `sub`
- ✅ Move token from URL query string to header for authenticated WebSocket:
    - ✅ `Sec-WebSocket-Protocol: access_token, <token>` header support
    - ✅ Query string still works (deprecated, logs warning)
    - ✅ Server responds with `access_token` subprotocol
- ⏭️ Token binding (fingerprint) - Deferred (optional, adds complexity)
- ⏭️ Token revocation list - Deferred (existing refresh token revocation sufficient)

### Phase 16.4 - WebSocket Security ✅

**Purpose**: Harden WebSocket connections against abuse and attacks

- ✅ Add message size limits:
    - ✅ Configure `max_size` parameter (64KB default, configurable via `WS_MAX_MESSAGE_SIZE`)
    - ✅ Reject oversized messages gracefully with informative error response
- ✅ Implement origin validation:
    - ✅ Check `Origin` header against allowed list
    - ✅ Configurable allowed origins via `WS_ALLOWED_ORIGINS` environment variable
    - ✅ Wildcard pattern support (e.g., `*.example.com`)
    - ✅ Can be disabled via `WS_ORIGIN_VALIDATION_ENABLED=false`
- ✅ Connection limits:
    - ✅ Max connections per IP (default 10, configurable via `WS_MAX_CONNECTIONS_PER_IP`)
    - ✅ Max connections per account (default 3, configurable via `WS_MAX_CONNECTIONS_PER_ACCOUNT`)
    - ✅ Automatic cleanup on disconnect
- ✅ Message validation:
    - ✅ JSON schema validation for incoming messages
    - ✅ Command text length limit (500 chars)
    - ✅ Control character filtering
    - ✅ Reject malformed payloads early with informative errors
- ✅ Add heartbeat/ping-pong for connection health:
    - ✅ `HeartbeatManager` tracks connection health
    - ✅ Configurable interval and timeout
    - ✅ Clients can send `{"type": "ping"}`, server responds with `{"type": "pong"}`
- ✅ Unified `WebSocketSecurityManager` coordinates all features
- ✅ Comprehensive unit tests (56 tests)

### Phase 16.5 - Input Sanitization ✅

**Purpose**: Protect against exploits, code injections, and server crashes from malformed input

- ✅ Command input validation:
    - ✅ Maximum command length (500 chars, configurable)
    - ✅ Strip control characters (null bytes, escape sequences, C1 controls)
    - ✅ Remove bidirectional text overrides (RTL/LTR exploits)
    - ✅ Remove invisible/zero-width characters
    - ✅ Normalize Unicode whitespace
    - ✅ Limit combining marks (Zalgo text prevention)
- ✅ Chat/text sanitization:
    - ✅ Prevent Unicode exploits (RTL override, zero-width chars)
    - ✅ Limit combining marks to prevent visual disruption
    - ✅ Maximum chat length (1000 chars)
    - ✅ Preserve emoji and normal punctuation
- ✅ Player name validation:
    - ✅ Alphanumeric + spaces, hyphens, apostrophes only
    - ✅ Length limits (2-24 characters)
    - ✅ Must start with letter, no consecutive special chars
    - ✅ Homoglyph/confusable character normalization (Cyrillic, Greek, fullwidth)
    - ✅ Remove invisible characters that could hide content
- ✅ Integrated into:
    - ✅ `engine.handle_command()` - all commands sanitized
    - ✅ `POST /characters` - character names validated
- ✅ Comprehensive unit tests (65 tests)
- ⏭️ YAML content validation - Deferred (admin content, covered by schema validation)
- ⏭️ Profanity filter - Deferred (game design decision, not security)

### Phase 16.6 - Legacy Endpoint Deprecation ✅

**Purpose**: Remove security risks from deprecated authentication paths

- ✅ Add deprecation warnings to `/ws/game?player_id=`:
    - ✅ Log warning on each connection (with metrics tracking)
    - ✅ Send deprecation warning message to clients on connect
- ✅ Implement sunset timeline via `WS_LEGACY_DEPRECATION_PHASE`:
    - ✅ Phase 1 (WARN): Warnings only, normal operation
    - ✅ Phase 2 (THROTTLE): Heavy rate limits (10 cmd/min, 5 chat/min)
    - ✅ Phase 3 (DISABLED): Endpoint completely disabled
- ✅ Document migration path in deprecation message (points to `/ws/game/auth`)
- ✅ Add feature flag `WS_LEGACY_AUTH_ENABLED` to disable legacy auth
- ✅ Stricter connection limits for legacy (3/IP vs 10/IP for authenticated)
- ✅ Created `legacy_deprecation.py` with:
    - ✅ `LegacyDeprecationConfig` - env-based configuration
    - ✅ `LegacyDeprecationManager` - connection tracking and validation
    - ✅ `DeprecationPhase` enum (WARN, THROTTLE, DISABLED)
- ✅ Integrated into `main.py` legacy WebSocket endpoint
- ✅ Comprehensive unit tests (43 tests)

### Security Testing & Validation

- [ ] Run `bandit` static analysis on codebase
- [ ] Run `safety check` for dependency vulnerabilities
- [ ] Add security checks to CI/CD pipeline
- [ ] Consider OWASP ZAP automated scanning
- [ ] Document security practices in SECURITY.md

## Phase 17 - Areas Engine Update ✅ COMPLETE

> 📄 **Documentation**: [phase17_environment_implementation.md](./build_docs/phase17_environment_implementation.md)

**Goals**: Expand environmental simulation with dynamic weather, temperature, flora/fauna ecosystems, biome coherence, and terrain features like roads and paths.

**Status**: Not Started | **Priority**: Medium (worldbuilding enhancement)

### Existing Foundation:
- ✅ Areas have: `biome`, `climate`, `weather_profile`, `ambient_lighting`, `time_scale`
- ✅ LightingSystem with time-of-day modifiers and biome immunity
- ✅ NPC respawn system with area-wide defaults and per-NPC overrides
- ✅ Trigger system for condition-based events (light_level, visibility_level)
- ✅ Item templates with environmental properties (provides_light, etc.)
- ✅ Room `room_type` field for terrain classification

---

### Phase 17.1 - Temperature System ✅

**Purpose**: Add temperature as a gameplay mechanic affecting players, NPCs, and spawn conditions

- ✅ **Database Schema**:
    - ✅ Add `base_temperature` to areas table (int, -50 to 150°F, default 70)
    - ✅ Add `temperature_variation` to areas (int, daily variance, default 20)
    - ✅ Add `temperature_override` to rooms table (nullable int)
    - ✅ Create Alembic migration `phase17_1_temperature.py`

- ✅ **TemperatureSystem Class** (`backend/daemons/engine/systems/temperature.py`):
    - ✅ `calculate_room_temperature(room, current_time)` → int
    - ✅ Base = area.base_temperature ± time-of-day modifier
    - ✅ Time modifiers: night(-15), dawn(-5), day(0), dusk(-5)
    - ✅ Room override replaces calculation (like lighting_override)
    - ✅ Biome modifiers: arctic(-40), desert(+30), underground(constant)

- ✅ **Temperature Thresholds**:
    - ✅ FREEZING (< 32°F): Cold damage tick, movement penalty
    - ✅ COLD (32-50°F): Stamina regen reduced
    - ✅ COMFORTABLE (50-80°F): No effect
    - ✅ HOT (80-100°F): Stamina regen reduced
    - ✅ SCORCHING (> 100°F): Heat damage tick, movement penalty

- ✅ **WorldArea/WorldRoom Updates**:
    - ✅ Add `base_temperature` and `temperature_variation` to WorldArea
    - ✅ Add `temperature_override` to WorldRoom
    - ✅ Integrate with loader.py for YAML loading

- ✅ **Trigger Conditions**:
    - ✅ `temperature_above`: Fire when room temp > threshold
    - ✅ `temperature_below`: Fire when room temp < threshold
    - ✅ `temperature_range`: Fire when temp within range

- ✅ **Player Effects**:
    - ✅ Temperature damage ticks (configurable in d20.py)
    - ✅ `temperature` command to check current temperature
    - ✅ Temperature shown in `look` output for extreme conditions

- ✅ **Testing**:
    - ✅ Unit tests for TemperatureSystem calculations
    - ✅ Integration tests for temperature triggers
    - ✅ Test biome modifiers and time-of-day variations

---

### Phase 17.2 - Weather System ✅

**Purpose**: Dynamic weather that changes over time and affects gameplay

- ✅ **Database Schema**:
    - ✅ Create `weather_states` table (id, area_id, weather_type, intensity, started_at, duration)
    - ✅ Expand areas `weather_profile` into `weather_profile_data` JSON field
    - ✅ Add `weather_immunity` boolean to areas (for underground, indoor, etc.)
    - ✅ Create Alembic migration `q9r0s1t2u3v4_phase17_2_weather.py`

- ✅ **Weather Types** (enum):
    - ✅ CLEAR, CLOUDY, OVERCAST
    - ✅ RAIN, STORM (thunderstorm)
    - ✅ SNOW
    - ✅ FOG
    - ✅ WIND

- ✅ **WeatherSystem Class** (`backend/daemons/engine/systems/weather.py`):
    - ✅ `get_current_weather(area_id)` → WeatherState
    - ✅ `advance_weather(area_id)` → WeatherState (transition logic)
    - ✅ Weather transitions based on climate + randomness
    - ✅ Markov chain for realistic progression (WEATHER_TRANSITIONS)
    - ✅ `get_forecast(area_id)` → WeatherForecast
    - ✅ `check_weather_condition()` for trigger integration

- ✅ **Weather Effects**:
    - ✅ Visibility modifiers (fog/rain reduce visibility)
    - ✅ Temperature modifiers (rain cools, clear sun heats) - integrated with TemperatureSystem
    - ✅ Movement modifiers (storm/snow = slower travel)
    - ✅ Combat modifiers (ranged_penalty, casting_penalty)

- ✅ **Weather Patterns by Climate**:
    - ✅ Weather-immune biomes: underground, cave, ethereal, void, planar
    - ✅ Markov transitions ensure realistic weather progression

- ✅ **Integration**:
    - ✅ Weather shown in `look` output (when notable)
    - ✅ `weather` / `w` command for detailed forecast
    - ✅ Trigger conditions: `weather_is`, `weather_intensity`, `weather_not`
    - ✅ Temperature system reads weather temperature_modifier

- ✅ **Area YAML Schema Update**:
    - ✅ Added `weather_profile_data` and `weather_immunity` fields to `_schema.yaml`

---

### Phase 17.3 - Biome Coherence System ✅

**Purpose**: Define biomes as coherent combinations of temperature + weather + climate + flora + fauna

- ✅ **Database Schema**:
    - ✅ Add `current_season` to areas table (string, default "spring")
    - ✅ Add `days_per_season` to areas table (int, default 7)
    - ✅ Add `season_day`, `season_locked`, `seasonal_modifiers` to areas
    - ✅ Create Alembic migration `r0s1t2u3v4w5_phase17_3_biomes.py`

- ✅ **Biome Definition Schema** (`world_data/biomes/_schema.yaml`):
    - ✅ id, name, description
    - ✅ temperature_range: [min, max]
    - ✅ climate_types: [list]
    - ✅ weather_patterns: dict
    - ✅ seasonal_temperature_modifiers, seasonal_weather_modifiers
    - ✅ flora_tags, fauna_tags for compatibility
    - ✅ spawn_modifiers for creature spawning
    - ✅ danger_modifier, magic_affinity, movement_modifier, visibility_modifier

- ✅ **Predefined Biomes** (`world_data/biomes/`):
    - ✅ `temperate_forest.yaml`: 40-85°F, deciduous, deer/wolves/bears
    - ✅ `desert.yaml`: 35-120°F, arid, snakes/lizards/vultures
    - ✅ `arctic.yaml`: -50-45°F, frozen, polar bears/seals/arctic foxes
    - ✅ `swamp.yaml`: 50-95°F, wetland, gators/herons/snakes
    - ✅ `mountain.yaml`: 10-70°F, alpine, goats/eagles/bears
    - ✅ `tropical.yaml`: 70-95°F, rainforest, monkeys/jaguars/parrots
    - ✅ `underground.yaml`: 50-65°F constant, cave, bats/spiders/oozes

- ✅ **BiomeSystem Class** (`backend/daemons/engine/systems/biome.py`):
    - ✅ Load biome definitions from YAML files
    - ✅ `get_biome(biome_id)` → BiomeDefinition
    - ✅ `get_biome_for_area(area)` → BiomeDefinition
    - ✅ `validate_area(area)` → warnings for incompatible settings
    - ✅ `get_compatible_flora_tags(area)` → set of flora tags
    - ✅ `get_compatible_fauna_tags(area)` → set of fauna tags
    - ✅ `get_spawn_modifier(area, modifier_key, season)` → float
    - ✅ `get_movement_modifier(area)`, `get_visibility_modifier(area)`, `get_danger_modifier(area)`

- ✅ **SeasonSystem Class** (`backend/daemons/engine/systems/biome.py`):
    - ✅ `get_season(area)` → Season enum
    - ✅ `get_season_state(area)` → SeasonState
    - ✅ `advance_day(area)` → bool (True if season changed)
    - ✅ `get_next_season(current)` → Season
    - ✅ `get_temperature_modifier(area)` → int
    - ✅ `get_weather_modifiers(area)` → dict
    - ✅ Season-immune biomes: underground, cave, ethereal, void, planar

- ✅ **Integration with Temperature/Weather**:
    - ✅ TemperatureSystem accepts BiomeSystem and applies seasonal_modifier
    - ✅ TemperatureState includes seasonal_modifier field
    - ✅ Temperature command displays seasonal modifier breakdown
    - ✅ Season modifiers affect weather probabilities

- ✅ **Player Commands**:
    - ✅ `season` / `seasons` command to check current season
    - ✅ Displays current season, biome, seasonal effects

- ✅ **Trigger Conditions**:
    - ✅ `season_is`: Fire when season matches (spring, summer, fall, winter)
    - ✅ `season_not`: Fire when season does NOT match
    - ✅ `biome_is`: Fire when area biome matches
    - ✅ `biome_has_tag`: Fire when biome has specific tag

- ✅ **Testing**:
    - ✅ Unit tests for BiomeSystem (43 tests)
    - ✅ Tests for SeasonSystem including seasonal cycle
    - ✅ Tests for temperature/weather integration

---

### Phase 17.4 - Flora System ✅

**Purpose**: Define plants, trees, and vegetation as interactive world objects

- ✅ **Flora Template Schema** (`world_data/flora/_schema.yaml`):
    ```yaml
    id: string                      # e.g., "flora_oak_tree"
    name: string                    # "Oak Tree"
    description: string             # Flavor text
    flora_type: enum                # tree, shrub, grass, flower, fungus

    # Environmental requirements
    biome_tags: [list]              # Compatible biomes
    temperature_range: [min, max]   # Survival range
    light_requirement: enum         # full_sun, partial_shade, shade, any

    # Interaction
    harvestable: bool               # Can players gather from it?
    harvest_items: [list]           # Items gained: [{item_id, quantity, chance}]
    harvest_cooldown: int           # Seconds until re-harvestable

    # Visual/Seasonal
    seasonal_variants: dict         # {spring: desc, summer: desc, fall: desc, winter: desc}
    provides_cover: bool            # Affects visibility/stealth
    blocks_movement: bool           # Large trees might block some directions
    ```

- ✅ **Flora Templates** (7 initial templates):
    - ✅ oak_tree.yaml - Large deciduous tree
    - ✅ wild_berries.yaml - Harvestable shrub
    - ✅ healing_herbs.yaml - Medicinal flowers
    - ✅ glowing_mushrooms.yaml - Cave fungi
    - ✅ desert_cactus.yaml - Arid biome plant
    - ✅ swamp_reeds.yaml - Wetland grass
    - ✅ frost_flower.yaml - Tundra flower

- ✅ **FloraSystem Class** (`backend/daemons/engine/systems/flora.py`):
    - ✅ FloraType, LightRequirement, Rarity enums
    - ✅ FloraTemplate, FloraInstance dataclasses
    - ✅ Template loading from YAML files
    - ✅ `get_templates_for_biome(biome)` - filter by biome tags
    - ✅ `spawn_flora(room_id, template_id)` - create instance
    - ✅ `can_exist_in_room(template, room)` - check conditions
    - ✅ Seasonal variant descriptions

- ✅ **Room Flora System**:
    - ✅ Flora instances stored in database (FloraInstance model)
    - ✅ Flora instances track: template_id, room_id, last_harvested, quantity
    - ✅ Flora shown in room descriptions via `format_room_flora()`

- ✅ **Harvest Command**:
    - ✅ `harvest <plant>` (aliases: gather, pick) - gather resources
    - ✅ Cooldown per-player-per-flora instance
    - ✅ Quantity tracking (depletes, respawns)
    - ✅ HarvestResult dataclass with items and messages

- ✅ **Flora Respawn System**:
    - ✅ Hybrid passive + event-triggered respawns (Design Decision #1)
    - ✅ FloraRespawnConfig with customizable rates
    - ✅ `process_respawns(session, area_id)` for tick-based respawns
    - ✅ Integration with ecosystem tick

- ✅ **Unit Tests** (`test_flora.py`):
    - ✅ Flora enum tests
    - ✅ Template loading tests
    - ✅ Instance management tests
    - ✅ Harvest mechanics tests
    - ✅ Respawn logic tests
    - ✅ Seasonal variant tests
    - ✅ Room formatting tests

---

### Phase 17.5 - Fauna System ✅

**Purpose**: Extend NPC templates with fauna-specific properties for wildlife behavior

- ✅ **FaunaProperties Dataclass** (NPC extension):
    ```yaml
    template_id: string
    fauna_type: enum                # mammal, bird, reptile, amphibian, fish, insect
    biome_tags: [list]              # Where this creature naturally spawns
    temperature_tolerance: [min, max]  # Survival range
    activity_period: enum           # diurnal, nocturnal, crepuscular, always
    diet: enum                      # herbivore, carnivore, omnivore, scavenger
    prey_tags: [list]               # What it hunts (other fauna_tags)
    predator_tags: [list]           # What hunts it
    fauna_tags: [list]              # Tags for matching
    pack_size: [min, max]           # Spawns in groups
    pack_leader_template: string    # Alpha template for packs
    territorial: bool               # Attacks intruders
    territory_radius: int           # Rooms from spawn point
    migratory: bool                 # Moves between areas seasonally
    migration_seasons: [list]       # Seasons when migrated away
    migration_tendency: float       # Chance to explore per tick
    aggression: float               # 0.0-1.0 attack likelihood
    flee_threshold: float           # Health % to flee
    ```

- ✅ **FaunaSystem Class** (`backend/daemons/engine/systems/fauna.py`):
    - ✅ ActivityPeriod, Diet, FaunaType, TimeOfDay enums
    - ✅ FaunaProperties.from_npc_template() extraction
    - ✅ `get_fauna_properties(template_id)` with caching
    - ✅ `is_fauna(npc)` check
    - ✅ `is_active_now(fauna, area_id)` activity period check
    - ✅ `is_migrated(fauna, area_id)` seasonal migration
    - ✅ `can_survive_temperature(fauna, room_id, area_id)`
    - ✅ `calculate_pack_size(fauna)` for pack spawning
    - ✅ `spawn_pack(template_id, room_id, session)` async
    - ✅ `find_prey_in_room(predator_id, room_id)` predator-prey
    - ✅ `find_predators_in_room(prey_id, room_id)`
    - ✅ `handle_fauna_death(npc, cause, session)` - abstract death (Design Decision #2)
    - ✅ `consider_migration(npc, room_id, session)` - biome-aware (Design Decision #4)
    - ✅ `get_fauna_in_area(area_id)` utility
    - ✅ `get_population_snapshot(area_id)` statistics

- ✅ **Fauna AI Behaviors** (`backend/daemons/engine/systems/fauna_behaviors.py`):
    - ✅ BehaviorResult, BehaviorContext dataclasses
    - ✅ BaseBehavior with on_tick, on_player_enter, on_damage_taken hooks
    - ✅ GrazingBehavior: Herbivores wander and "eat" flora
    - ✅ HuntingBehavior: Carnivores seek prey NPCs
    - ✅ FleeingBehavior: Prey flees from predator NPCs
    - ✅ TerritorialBehavior: Attacks NPCs entering territory
    - ✅ BiomeAwareMigration: Cross-area movement with biome checks

- ✅ **Unit Tests** (`test_fauna.py`):
    - ✅ Fauna enum tests
    - ✅ FaunaProperties dataclass tests
    - ✅ FaunaSystem basic tests
    - ✅ Activity period tests
    - ✅ Migration tests
    - ✅ Temperature tolerance tests
    - ✅ Pack spawning tests
    - ✅ Predator-prey dynamics tests
    - ✅ Death handling tests
    - ✅ Population snapshot tests

---

### Phase 17.6 - Condition-Dependent Spawn Cycles ✅

**Purpose**: Flora and fauna spawn based on environmental conditions

- ✅ **SpawnConditions Dataclass** (`backend/daemons/engine/systems/spawn_conditions.py`):
    - ✅ time_of_day: [dawn, day, dusk, night]
    - ✅ temperature_range: [min, max]
    - ✅ weather_is: [list] / weather_not: [list]
    - ✅ weather_intensity_min/max
    - ✅ season_is: [list] / season_not: [list]
    - ✅ biome_is: [list] / biome_match: bool
    - ✅ light_level_min/max (0-100)
    - ✅ max_in_room / max_in_area population limits
    - ✅ requires_flora: [list] - flora dependencies
    - ✅ requires_fauna: [list] - prey must be present
    - ✅ excludes_fauna: [list] - predators prevent spawn
    - ✅ `from_dict(data)` parser from YAML
    - ✅ `has_conditions()` check

- ✅ **SpawnConditionEvaluator Class**:
    - ✅ Integrates with all environmental systems
    - ✅ `evaluate(conditions, room_id, area_id, template_id, session)` async
    - ✅ EvaluationResult with can_spawn, failed_conditions, warnings
    - ✅ Time condition checks via TimeManager
    - ✅ Temperature checks via TemperatureSystem
    - ✅ Weather checks via WeatherSystem
    - ✅ Season checks via BiomeSystem
    - ✅ Biome compatibility checks
    - ✅ Light level calculation (time + weather + room type)
    - ✅ Population limit checks (room and area)
    - ✅ Flora/fauna dependency checks
    - ✅ `evaluate_all_spawns(spawn_defs, area_id, session)` batch

- ✅ **PopulationManager Class** (`backend/daemons/engine/systems/population.py`):
    - ✅ PopulationConfig per-area settings
    - ✅ PopulationSnapshot current state tracking
    - ✅ PredationResult, SpawnResult dataclasses
    - ✅ `get_population_snapshot(area_id)` with caching
    - ✅ `calculate_spawn_rate(template_id, area_id)` ecological dynamics
    - ✅ Herbivore spawn rate depends on flora
    - ✅ Carnivore spawn rate depends on prey
    - ✅ Critical recovery rate when population < 25%
    - ✅ Recent death tracking boosts respawn rate
    - ✅ `apply_predation(area_id, session)` - abstract kills (Design Decision #2)
    - ✅ `apply_population_control(area_id, session)` - excess culling
    - ✅ `record_death(template_id, room_id)` for tracking
    - ✅ `get_area_health(area_id)` ecological metrics

- ✅ **Engine Integration** (`backend/daemons/engine/engine.py`):
    - ✅ Initialize FaunaSystem with all dependencies
    - ✅ Initialize SpawnConditionEvaluator
    - ✅ Initialize PopulationManager
    - ✅ Connect FaunaSystem to PopulationManager
    - ✅ `_ecosystem_tick_interval` config (Design Decision #5)
    - ✅ `_schedule_ecosystem_tick()` recurring event
    - ✅ `_process_flora_respawns(area_id, session)` every tick
    - ✅ `_process_fauna_spawns(area_id, session)` every 3rd tick
    - ✅ `_process_population_dynamics(area_id, session)` every 5th tick
    - ✅ `_process_fauna_migration(area_id, session)` every 10th tick
    - ✅ Player presence optimization (skip empty areas)

- ✅ **Unit Tests** (`test_spawn_population.py`):
    - ✅ SpawnConditions parsing tests
    - ✅ SpawnConditionEvaluator condition tests
    - ✅ PopulationConfig tests
    - ✅ PopulationSnapshot tests
    - ✅ PopulationManager spawn rate tests
    - ✅ Death recording and recovery tests
    - ✅ Light level calculation tests

**Design Decisions Implemented**:
1. ✅ Flora respawn: Hybrid passive + event-triggered
2. ✅ Fauna death: Abstract model, no loot/corpses
3. ✅ Player impact: No default, extensible system
4. ✅ Cross-area migration: Biome-aware
5. ✅ Performance: Single adjustable tick interval

---

### Phase 17.7 - Seasonal Spawning ⬜

**Purpose**: Future enhancement for seasonal spawn variations
    - [ ] Some fauna only in certain seasons
    - [ ] Migration patterns between areas
    - [ ] Breeding seasons = more spawns

---

### Phase 17.7 - Roads and Paths System ⬜

**Purpose**: Track player movement patterns, create dynamic trails, and define road networks

- [ ] **Road/Path Types**:
    - [ ] `road`: Paved/maintained, fast travel, safe
    - [ ] `trail`: Worn path, moderate speed, some danger
    - [ ] `track`: Faint path, normal speed, more danger
    - [ ] `wilderness`: No path, slower travel, maximum danger

- [ ] **Database Schema**:
    - [ ] Add `path_type` to rooms (enum, nullable, default wilderness)
    - [ ] Create `room_connections` table for path metadata:
        - [ ] from_room_id, to_room_id, direction
        - [ ] path_type, travel_time_modifier, danger_modifier
        - [ ] discovered_by_players (JSON array)
    - [ ] Create Alembic migration `phase17_7_roads.py`

- [ ] **Movement Integration**:
    - [ ] Path type affects travel time (roads = faster)
    - [ ] Path type affects encounter chance
    - [ ] Hidden paths require discovery (search command, quests)

- [ ] **Tracking System**:
    - [ ] Record movement patterns: who went where, when
    - [ ] `tracks` command: "You see footprints heading north"
    - [ ] Track decay over time (rain washes away tracks)
    - [ ] Skill-based tracking (future: ranger abilities)

- [ ] **Trail Formation** (dynamic paths):
    - [ ] High-traffic routes become worn (wilderness → track → trail)
    - [ ] Track "traffic_count" per connection
    - [ ] Periodic evaluation upgrades/downgrades paths
    - [ ] Player actions can create shortcuts

- [ ] **Road Network Features**:
    - [ ] Named roads (e.g., "King's Highway")
    - [ ] Road signs at intersections
    - [ ] Waypoints and milestones
    - [ ] `roads` command to list known roads

---

### Phase 17.8 - Integration & Polish ⬜

- [ ] **YAML Schema Updates**:
    - [ ] Update `areas/_schema.yaml` with new fields
    - [ ] Create `biomes/_schema.yaml`
    - [ ] Create `flora/_schema.yaml`
    - [ ] Update `npcs/_schema.yaml` with fauna fields
    - [ ] Update `npc_spawns/_schema.yaml` with conditions

- [ ] **CMS Integration**:
    - [ ] Add biome selector to area editor
    - [ ] Flora placement in room editor
    - [ ] Spawn condition builder UI
    - [ ] Path type selector for connections

- [ ] **Commands Summary**:
    - [ ] `temperature` - Check current temperature
    - [ ] `weather` - Check current weather and forecast
    - [ ] `harvest <plant>` - Gather from flora
    - [ ] `tracks` - Look for animal/player tracks
    - [ ] `roads` - List known roads in area

- [ ] **Documentation**:
    - [ ] Update ARCHITECTURE.md with new systems
    - [ ] Update DATABASE_SCHEMA.md
    - [ ] Content creator guide for biomes/flora/fauna
    - [ ] Example content: complete biome with flora/fauna

- [ ] **Testing**:
    - [ ] Unit tests for each new system
    - [ ] Integration tests for spawn conditions
    - [ ] Performance tests for weather ticks
    - [ ] Sample biomes with full content

---

## Phase Q - The Great Bug Hunt
A human playtests all functions. The human tells the bot everything it got wrong. The bot systematically fixes all errors.

See [QA Todos](docs/build_docs/qa_todos.md)

## Mechanic's Manual: comprehensive guide for modders
Modder-focused guide to easily extending the engine codebase

## Phase Z - Backlogged Niceties & polish

- Rate limiting & abuse protection (spam commands, chat).
    - Localization hooks in text output.
- Protocol versioning:
    - Include an event version field when you start adding breaking changes.
- Save/restore partial sessions for mobile clients.
