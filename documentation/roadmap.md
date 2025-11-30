# Roadmap

## Phase 0  Hardening **COMPLETE**

Before adding big systems, make the core loop solid.

**Goals**: No silent failures; predictable behavior under load.

### Backend tasks ✅

- ✅ Logging & observability
    - ✅ Structured logs for: player connect/disconnect, commands received, errors in engine/WS tasks
    - ✅ Metrics hooks and counters for active players
- ✅ Error handling
    - ✅ Graceful exception handling in _ws_sender / _ws_receiver
    - ✅ Graceful handling of bad JSON / unknown commands
- ✅ Protocol documentation
    - ✅ protocol.md: client→server commands and server→client event shapes



## Phase 1  Player stats and progression **COMPLETE**

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



## Phase 2  Time & tick system (for effects/debuffs)  **COMPLETE**

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

## Phase 3 - Items & inventory  **COMPLETE**

**Goals**: Physical objects in the world, inventory management, equipment.

### Backend Model ✅

- DB:
    - ✅ ItemTemplate (static: name, type, modifiers, description, keywords).
    - ✅ ItemInstance (dynamic: owner, location, durability, unique flags).
    - ✅ PlayerInventory (capacity limits, weight/slot tracking).

- World:
    - ✅ WorldItem for runtime representation.
    - ✅ ItemTemplate dataclass with full properties.
    - ✅ Attach items to:
        - ✅ rooms (ground items)
        - ✅ other items (containers)
        - ✅ players (inventory and equipment).

### YAML Content System ✅

- ✅ world_data/items/ directory structure (weapons/, armor/, consumables/, containers/)
- ✅ world_data/item_instances/ for spawn configurations
- ✅ Migration loads items from YAML files
- ✅ Example items: Rusty Sword, Wooden Staff, Iron Chestplate, Leather Cap, Health Potion, Scroll of Wisdom, Leather Backpack

### Engine Changes ✅

- Loader:
    - ✅ Load templates + instances into World.
    - ✅ Link items to players/rooms on startup.
    - ✅ Restore equipped items and apply stat effects.

- Core item mechanics:
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

- Stat interactions:
    - ✅ Equipment applies stat modifiers via Effect system.
    - ✅ On equip: create permanent effect with stat bonuses.
    - ✅ On unequip: remove effect, recalculate stats.
    - ✅ Consumables apply temporary effects (buffs, healing).

- Quality of Life:
    - ✅ Partial name matching ("lea" finds "leather backpack").
    - ✅ Keyword system (items can have multiple searchable names).
    - ✅ Stack handling (pick up one at a time).
    - ✅ Weight and slot-based inventory limits.
    - ✅ O(1) container contents lookup via index (not O(n) world scan).

### Events ✅

- Room broadcasts:
    - ✅ "Alice drops Rusty Sword."
    - ✅ "Bob picks up Health Potion."
    - ✅ "Alice gives Health Potion to Bob."
- Stat updates:
    - ✅ stat_update events on equip/unequip/consume.

### Persistence ✅

- ✅ Inventory saved on player disconnect.
- ✅ Item locations, quantities, durability persisted.
- ✅ Equipment state restored on reconnect.



## Phase 4 - NPCs & Combat System  **COMPLETE**

**Goals**: NPCs in rooms with real-time combat and AI behaviors.

### Backend Model ✅

- DB:
    - ✅ NpcTemplate with stats, behavior flags, loot tables, attack stats
    - ✅ NpcInstance for spawned NPCs
- World:
    - ✅ WorldEntity unified base class for players and NPCs
    - ✅ WorldNpc extends WorldEntity with NPC-specific fields
    - ✅ EntityType enum (PLAYER, NPC)
    - ✅ Targetable protocol for unified command targeting
    - ✅ NPCs attached to rooms via entities set

### Real-Time Combat System ✅

- Architecture:
    - ✅ Real-time combat (not turn-based) with weapon swing timers
    - ✅ CombatState dataclass tracking phase, target, timing
    - ✅ CombatPhase enum: IDLE → WINDUP → SWING → RECOVERY
    - ✅ WeaponStats: damage_min/max, swing_speed, damage_type
    - ✅ Auto-attack continues until target dies or combat cancelled

- Combat Flow:
    - ✅ `attack <target>` / `kill <target>` - Start attacking
    - ✅ `stop` - Disengage from combat
    - ✅ Movement blocked while in combat (must flee)
    - ✅ Player auto-retaliation when attacked
    - ✅ NPC retaliation via CombatSystem
    - ✅ Swing timer based on weapon speed
    - ✅ Damage calculation with strength modifier and armor reduction
    - ✅ Critical hit system (10% chance, 1.5x damage)

- Death & Rewards:
    - ✅ HP tracking and death detection
    - ✅ Death messages broadcast to room
    - ✅ XP rewards for killing NPCs
    - ✅ NPC respawn timers with area defaults and per-NPC overrides
    - ✅ Player respawn with countdown timer and area entry point
    - ✅ Loot drops from NPC drop tables

### Weapon & Equipment System ✅

- ItemTemplate weapon stats:
    - ✅ damage_min, damage_max, attack_speed, damage_type
    - ✅ Migration adds columns to item_templates
    - ✅ YAML weapon files updated with combat stats
- Equipment integration:
    - ✅ `get_weapon_stats(item_templates)` checks equipped weapon
    - ✅ Falls back to unarmed (base) stats if no weapon
    - ✅ Both players AND NPCs benefit from equipped weapons

### Behavior Script System ✅

- Modular architecture:
    - ✅ `backend/app/engine/behaviors/` package
    - ✅ Dynamic loading from directory (mod-friendly)
    - ✅ `@behavior` decorator for registration
    - ✅ BehaviorScript base class with async hooks

- Available hooks:
    - ✅ on_spawn, on_death
    - ✅ on_idle_tick, on_wander_tick
    - ✅ on_player_enter, on_player_leave
    - ✅ on_combat_start, on_damaged, on_combat_tick
    - ✅ on_talked_to, on_given_item

- Built-in behaviors:
    - ✅ Wandering: wanders_rarely, wanders_sometimes, wanders_frequently, wanders_nowhere
    - ✅ Combat: aggressive (attacks on sight), defensive (retaliates), pacifist
    - ✅ Flee: cowardly, cautious, brave, fearless
    - ✅ Social: calls_for_help, loner
    - ✅ Idle: talkative, chatty, quiet, silent
    - ✅ Roles: merchant, guard, patrol

- NPC AI:
    - ✅ Per-NPC timers (idle_event_id, wander_event_id)
    - ✅ Behaviors resolved from YAML tags at load time
    - ✅ Priority system for behavior execution
    - ✅ BehaviorResult controls movement, attacks, messages

### Events ✅

- Combat broadcasts:
    - ✅ "⚔️ Alice attacks Goblin!"
    - ✅ "Alice hits Goblin for 5 damage! **CRITICAL!**"
    - ✅ "💀 Goblin has been slain by Alice!"
- Stat updates:
    - ✅ HP changes via stat_update events
- Movement:
    - ✅ Arrival messages use "from above/below" for vertical movement
- Player death:
    - ✅ respawn_countdown event type for client UI
    - ✅ Flavorful death and respawn messages
- NPC reactions:
    - ✅ Aggressive NPCs attack when players enter room
    - ✅ NPCs call for help (allies join fight)
    - ✅ NPCs can flee when damaged

### YAML Content ✅

- NPC templates: goblin_scout, skeleton_warrior, ethereal_wisp, wandering_merchant
- NPC spawns configured per-area
- Behavior tags in YAML: `behaviors: [wanders_sometimes, aggressive, cowardly]`



## Phase 5 - World structure, triggers, and scripting  **COMPLETE**

**Goal**: Richer world behavior without hardcoding everything in Python.

### Phase 5.1 - Core Trigger Infrastructure ✅

- Trigger System Architecture:
    - ✅ TriggerSystem class following GameContext pattern
    - ✅ RoomTrigger dataclass: id, event, conditions, actions, cooldown, max_fires, enabled
    - ✅ TriggerCondition and TriggerAction dataclasses with type + params
    - ✅ TriggerState for runtime tracking (fire_count, last_fired_at, timer_event_id)
    - ✅ TriggerContext passed to all handlers with player, room, area, direction, command

- Core Event Types:
    - ✅ on_enter: Fires when player enters a room
    - ✅ on_exit: Fires when player leaves a room
    - ✅ Variable substitution: {player.name}, {room.name}, {direction}
    - ✅ Cooldown enforcement per player
    - ✅ max_fires enforcement with fire_count tracking

- Basic Conditions:
    - ✅ flag_set: Check room_flags for specific flag value
    - ✅ has_item: Check if player has item (by template_id or keywords)
    - ✅ level: Check player level (min_level, max_level)

- Basic Actions:
    - ✅ message_player: Send message to triggering player
    - ✅ message_room: Broadcast to all players in room
    - ✅ set_flag: Set room flag to value
    - ✅ toggle_flag: Toggle boolean room flag

### Phase 5.2 - Commands, Timers & Expanded Conditions ✅

- Command Triggers:
    - ✅ on_command: Fires on specific player commands
    - ✅ fnmatch pattern matching ("pull *", "open *door*", "press button")
    - ✅ Integrated into router as pre-command hook
    - ✅ Returns True to block further command processing

- Timer Triggers:
    - ✅ on_timer: Periodic automatic triggers
    - ✅ timer_interval and timer_initial_delay configuration
    - ✅ Integration with TimeEventManager
    - ✅ start_room_timers() called on player enter
    - ✅ Recurring=True for continuous operation

- Expanded Conditions:
    - ✅ health_percent: Check player health percentage (min, max)
    - ✅ in_combat: Check if player is in combat
    - ✅ has_effect: Check if player has specific effect
    - ✅ entity_present: Check for NPC by template_id in room
    - ✅ player_count: Check room player count (min, max)

- Expanded Actions:
    - ✅ damage: Deal damage to triggering player
    - ✅ heal: Heal triggering player
    - ✅ apply_effect: Apply effect to player (via EffectSystem)
    - ✅ spawn_npc: Spawn NPC from template in room
    - ✅ despawn_npc: Remove NPC from room

### Phase 5.3 - Dynamic World State ✅

- Exit Manipulation:
    - ✅ WorldRoom.dynamic_exits dict for runtime exit overrides
    - ✅ get_effective_exits() method combines base exits + dynamic
    - ✅ open_exit action: Opens an exit to destination room
    - ✅ close_exit action: Closes/removes an exit

- Description System:
    - ✅ WorldRoom.dynamic_description for runtime description override
    - ✅ get_effective_description() returns dynamic or base description
    - ✅ set_description action: Override room description
    - ✅ reset_description action: Restore original description

- Item Actions:
    - ✅ spawn_item: Create item instance in room
    - ✅ despawn_item: Remove item from room
    - ✅ give_item: Give item to player
    - ✅ take_item: Remove item from player

- Trigger Control:
    - ✅ enable_trigger: Enable a disabled trigger
    - ✅ disable_trigger: Disable a trigger
    - ✅ fire_trigger: Manually fire another trigger

- Engine Integration:
    - ✅ _look() uses get_effective_description()
    - ✅ Movement commands use get_effective_exits()

### Phase 5.4 - Area Enhancements & YAML Loading ✅

- WorldArea Extensions:
    - ✅ recommended_level, theme, area_flags fields
    - ✅ triggers and trigger_states for area-level triggers
    - ✅ Loaded from YAML area files

- Area Triggers:
    - ✅ on_area_enter: Fires when entering area from different area
    - ✅ on_area_exit: Fires when leaving area to different area
    - ✅ fire_area_event() with area state management
    - ✅ Area transition detection in _move_player()

- Timer Initialization:
    - ✅ initialize_all_timers() for room and area on_timer triggers
    - ✅ Called from start_time_system() at startup

- YAML Trigger Loading:
    - ✅ load_triggers_from_yaml() in loader.py
    - ✅ _parse_trigger() parses conditions/actions from YAML
    - ✅ Called from main.py after load_world()
    - ✅ Supports both room and area trigger definitions

- Example Content:
    - ✅ room_1_1_1.yaml: Central hub with welcome, meditate, touch, pulse triggers
    - ✅ room_0_0_0.yaml: Origin with conditional and level-gated triggers
    - ✅ ethereal_nexus.yaml: Area enter/exit triggers

## Phase X - Quest System and Narrative Progression ✅ COMPLETE

**Goals**: Structured narrative experiences, player-driven story progression, and meaningful rewards.

**Status**: ✅ All phases complete (X.1-X.4 including reconciliation)

### Core Quest Infrastructure ✅

- Quest System Architecture:
    - ✅ QuestSystem class following GameContext pattern
    - ✅ QuestTemplate dataclass: id, name, description, objectives, rewards, prerequisites
    - ✅ QuestStatus enum: NOT_AVAILABLE → AVAILABLE → ACCEPTED → IN_PROGRESS → COMPLETED → TURNED_IN
    - ✅ QuestProgress dataclass for player-specific quest state tracking
    - ✅ QuestObjective dataclass with type-specific parameters

- Objective Types:
    - ✅ KILL: Kill N of NPC template
    - ✅ COLLECT: Collect N of item template
    - ✅ DELIVER: Bring item to NPC
    - ✅ VISIT: Enter a specific room
    - ✅ INTERACT: Use command in room (trigger-based)
    - ✅ ESCORT: Keep NPC alive to destination
    - ✅ DEFEND: Prevent NPCs from reaching location
    - ✅ TALK: Speak to NPC
    - ✅ USE_ITEM: Use specific item

- Quest Rewards:
    - ✅ Experience points
    - ✅ Items (via ItemSystem.give_item())
    - ✅ Effects (via EffectSystem.apply_effect())
    - ✅ Flags (player and room)
    - Currency (future)
    - Reputation (future)

### NPC Dialogue System ✅

- Dialogue Data Structures:
    - ✅ DialogueTree: Complete dialogue for an NPC
    - ✅ DialogueNode: A node with text, options, conditions, actions
    - ✅ DialogueOption: Player response with conditions and quest integration
    - ✅ Variable substitution: {player.name}, {quest.progress}

- Dialogue Flow:
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

## Phase X.R - Reconciliation & Code Hygiene

**Goals**: Audit the codebase to eliminate dead code, redundant systems, and orphaned implementations left behind from iterative development. Ensure architectural consistency across all systems.

### Code Audit Checklist

- [x] **Time Systems**: Verify only one time management system is active ✅
  - ✅ Only `TimeEventManager` handles scheduling (single instance in WorldEngine)
  - ✅ Single game_loop in engine.py
  - ✅ No duplicate schedulers or tick loops

- [x] **Event Systems**: Confirm single source of truth for events ✅
  - ✅ `EventDispatcher` is the sole event router
  - ✅ All events flow through `_dispatch_events()`
  - ✅ No orphaned event types found

- [x] **Command Routing**: Single command dispatch path ✅
  - ✅ `CommandRouter` is the only entry point
  - ✅ All commands register via `@cmd` decorator
  - ✅ No duplicate handlers

- [x] **Trigger System**: No duplicate trigger mechanisms ✅
  - ✅ `TriggerSystem` is sole trigger handler
  - ✅ Quest actions use TriggerSystem for spawning/effects
  - ✅ No hardcoded trigger-like logic elsewhere

- [x] **NPC Behaviors**: Clean behavior hierarchy ✅
  - ⚠️ `example_mod.py` - example behavior (can keep as reference)
  - ✅ All behaviors properly registered via `@behavior` decorator
  - ✅ No duplicate logic across files

### Dead Code Detection

- [ ] **Unused Modules**: 
  - ⚠️ `look_helpers.py` - Not imported anywhere (candidate for removal or integration)
  - ⚠️ `debug_check.py` - Debug utility script (keep but document purpose)
  
- [x] **TODOs Found** (2 items):
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

## Phase 6 - Persistence & scaling  **COMPLETE**

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

## Phase 7 - Accounts, auth, and security **COMPLETE** ✅

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

## Phase 8 - Admin & content tools **COMPLETE**

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

## Phase 9 - Classes & Abilities **COMPLETE** ✅

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

### Phase 10 - Socializing and worldbuilding ✅ COMPLETE

**Phase 10.1: Groups, Tells, Follow** ✅ COMPLETE
- ✅ GroupSystem with O(1) lookups and auto-disband
- ✅ Group/tell/follow/yell commands with full subcommands
- ✅ Event routing for group/tell/follow scopes
- ✅ 80+ comprehensive tests
- ✅ Integration documentation

**Phase 10.2: Persistent Clans** ✅ COMPLETE
- ✅ Database migration with clans and clan_members tables
- ✅ Clan and ClanMember ORM models with relationships
- ✅ ClanSystem with async DB loading, CRUD operations
- ✅ Rank hierarchy (leader > officer > member > initiate)
- ✅ Clan commands (create, invite, join, leave, promote, members, info, disband)
- ✅ Clan message event routing to all members
- ✅ WorldEngine integration with async initialization
- ✅ 50+ comprehensive tests

**Phase 10.3: Factions with Reputation** ✅ COMPLETE
- ✅ Database migration with factions and faction_npc_members tables
- ✅ Faction and FactionNPCMember ORM models
- ✅ FactionSystem with YAML loading, reputation tracking, alignment tiers
- ✅ O(1) NPC faction lookups and behavior changes
- ✅ Faction commands (list, info, join, leave, standing)
- ✅ 4 faction YAML definitions (Silver Sanctum, Shadow Syndicate, Arcane Collective, Primal Circle)
- ✅ Faction message event routing to all members
- ✅ WorldEngine integration with YAML loading at startup
- ✅ 45+ comprehensive tests

### Phase 11 - Light and Vision System ✅ COMPLETE

**Goals**: Dynamic lighting system with visibility-based gameplay, environmental atmosphere, and light-dependent triggers.

**Phase 11.1: Core Light Calculation System** ✅
- ✅ LightingSystem class with 0-100 light scale
- ✅ 5 visibility levels: NONE (0-10), MINIMAL (11-25), PARTIAL (26-50), NORMAL (51-75), ENHANCED (76-100)
- ✅ Database migration k3l4m5n6o7p8_phase11_light_system.py
- ✅ Room.lighting_override field for room-specific light levels
- ✅ ItemTemplate light fields: provides_light, light_intensity, light_duration
- ✅ AMBIENT_LIGHTING_VALUES mapping: pitch_black(0), dark(10), dim(20), shadowed(35), normal(60), bright(85), prismatic(90)
- ✅ TIME_IMMUNE_BIOMES: underground, ethereal, void, planar

**Phase 11.2: Visibility Filtering** ✅
- ✅ Modified _look() command with light level checks
- ✅ Modified _look_at_target() requiring minimum light
- ✅ Entity filtering based on visibility thresholds
- ✅ Admin lightlevel debugging command showing:
  - Base ambient lighting from area
  - Time-of-day modifier calculation
  - Active light sources (spells/items)
  - Darkness penalties
  - Final effective light level

**Phase 11.3: System Integration** ✅
- Spell Integration:
  - ✅ create_light_behavior() calls lighting_system.update_light_source()
  - ✅ darkness_behavior() applies negative light intensity
  - ✅ Light/darkness spells affect room lighting
- Time Integration:
  - ✅ Time-of-day modifiers: Night(-20), Dawn/Dusk(-10), Day(0)
  - ✅ recalculate_all_rooms() triggered on time period changes
  - ✅ Batch updates during dawn/dusk transitions
- Item Light Sources:
  - ✅ Equip/unequip handlers activate/deactivate light sources
  - ✅ 4 sample light items: Torch (35, 30min), Lantern (45, permanent), Glowstone (50, permanent, +1 INT), Candle (20, 15min)
  - ✅ Duration tracking and automatic expiration

**Phase 11.4: Environmental Content** ✅
- Areas Created:
  - ✅ Dark Caves (ambient: dim, biome: underground, danger: 3)
  - ✅ Sunlit Meadow (ambient: bright, biome: grassland, danger: 1)
- Rooms Created (9 total):
  - ✅ Cave rooms: entrance(40), tunnel(5), bioluminescent chamber(65), deep cave(0)
  - ✅ Meadow rooms: center(95), shaded grove(70), open field(default), eastern rise(90), flower garden(default)
- ✅ All content loaded into database
- ✅ Demonstrates full range of lighting values (0-95)

**Phase 11.5: Trigger Conditions and Events** ✅
- New Trigger Conditions:
  - ✅ light_level: Check room light with comparison operators
  - ✅ visibility_level: Check specific visibility threshold (none/minimal/partial/normal/enhanced)
- New Trigger Actions:
  - ✅ stumble_in_darkness: Damage player in low light with room notification
- Sample Triggers:
  - ✅ darkness_stumble.yaml: Damage when entering very dark rooms
  - ✅ bright_light_secret.yaml: Reveal hidden passage in enhanced light
  - ✅ shadow_spawn_darkness.yaml: Spawn hostile NPCs in darkness
  - ✅ light_dependent_desc.yaml: Change room description based on light

**Testing and Validation** ✅
- ✅ Comprehensive test suite (test_phase11.py)
- ✅ 26/26 tests passing (100% pass rate)
- ✅ Tests cover: light calculation, time integration, light sources, visibility filtering, item properties, environmental content, trigger integration

---

## Phase 12 - CMS API Integration ⬜

**Goals**: Provide complete REST API endpoints for the Daemonswright CMS to create, read, update, and manage game content without direct file system access.

**Status**: Not Started | **Priority**: High (blocks CMS development)

### Phase 12.1 - Schema Registry API ⬜

**Purpose**: Enable CMS to dynamically fetch schema definitions for all content types

- [ ] **Core Endpoint**:
    - [ ] `GET /api/admin/schemas` - Return all `_schema.yaml` files with metadata
    - [ ] Response includes: content, last_modified, checksum (SHA256)
    - [ ] Optional filtering by content_type (rooms, items, npcs, etc.)
    - [ ] Version header with schema version number

- [ ] **Schema Metadata**:
    - [ ] `GET /api/admin/schemas/version` - Current schema version info
    - [ ] Response includes: version, engine_version, last_modified
    - [ ] Used for cache invalidation in CMS

- [ ] **Integration**:
    - [ ] SchemaRegistry class in `backend/app/engine/systems/`
    - [ ] Caches parsed schemas on server startup
    - [ ] Hot-reload support when schema files change

**Blocking**: Phase 1 of CMS development (TypeScript type generation)

### Phase 12.2 - YAML File Management API ⬜

**Purpose**: Enable CMS to upload, download, and list YAML content files

- [ ] **File Operations**:
    - [ ] `GET /api/admin/content/files` - List all YAML files in world_data/
    - [ ] Supports filtering by content_type
    - [ ] Optional git status inclusion (modified, untracked, etc.)
    - [ ] Returns file metadata: path, size, last_modified

- [ ] **Download Content**:
    - [ ] `GET /api/admin/content/download?file_path=<path>` - Download raw YAML
    - [ ] Returns content, checksum, last_modified
    - [ ] Supports all content types (rooms, items, npcs, etc.)

- [ ] **Upload/Update Content**:
    - [ ] `POST /api/admin/content/upload` - Create or update YAML file
    - [ ] Request: content_type, file_path, content (raw YAML string)
    - [ ] Optional `validate_only=true` for dry-run validation
    - [ ] Response: validation_errors, file_written, auto_reload_triggered
    - [ ] Atomic write operations (temp file + rename)

- [ ] **File Tree Structure**:
    - [ ] Maintain world_data/ directory hierarchy
    - [ ] Prevent path traversal attacks (validate file_path)
    - [ ] Respect .gitignore patterns

**Blocking**: Phase 2 of CMS development (File explorer and editor)

### Phase 12.3 - Enhanced Validation API ⬜

**Purpose**: Provide real-time validation feedback during content editing

- [ ] **Enhanced `/api/admin/content/validate`**:
    - [ ] Accept raw YAML string (not just file_path)
    - [ ] Validate syntax (YAML parser)
    - [ ] Validate schema conformance (required fields, types)
    - [ ] Validate references (foreign keys to rooms, items, NPCs)
    - [ ] Return detailed error locations (line/column numbers)

- [ ] **Reference Validation**:
    - [ ] `POST /api/admin/content/validate-references` - Check broken links
    - [ ] Detects: invalid room exits, missing item templates, non-existent NPCs
    - [ ] Returns: field path, referenced_id, error message
    - [ ] Cross-content validation (e.g., quest references NPC that exists)

- [ ] **Validation Response Format**:
    ```json
    {
      "valid": false,
      "errors": [
        {
          "type": "syntax_error",
          "line": 15,
          "column": 3,
          "message": "Invalid YAML: unexpected indentation"
        },
        {
          "type": "reference_error",
          "field": "exits.north",
          "value": "room_99_99_99",
          "message": "Room does not exist"
        }
      ],
      "warnings": [
        {
          "type": "best_practice",
          "field": "room_type",
          "message": "Consider using room_type_emoji for visual distinction"
        }
      ]
    }
    ```

- [ ] **Integration**:
    - [ ] ValidationService class with pluggable validators
    - [ ] Reference cache for O(1) lookups (refreshed on content reload)
    - [ ] Async validation for large files

**Blocking**: Phase 2A of CMS (real-time Monaco editor validation)

### Phase 12.4 - Content Querying API ⬜

**Purpose**: Enable CMS to query and search existing content for references and dependencies

- [ ] **Content Search**:
    - [ ] `GET /api/admin/content/search?q=<query>&type=<type>` - Full-text search
    - [ ] Search across: names, descriptions, IDs, keywords
    - [ ] Returns matching content with context snippets
    - [ ] Supports filtering by content_type

- [ ] **Dependency Graph**:
    - [ ] `GET /api/admin/content/dependencies?id=<id>&type=<type>` - Get dependencies
    - [ ] Returns: what references this entity, what this entity references
    - [ ] Example: Room depends on Area, spawns NPCs, contains Items
    - [ ] Used for "safe delete" checks and impact analysis

- [ ] **Content Statistics**:
    - [ ] `GET /api/admin/content/stats` - Content counts and metrics
    - [ ] Returns: total rooms, items, NPCs, quests by type
    - [ ] Broken reference counts
    - [ ] Orphaned content (no references to it)

**Blocking**: Phase 3A of CMS (dependency visualization, safe deletion)

### Phase 12.5 - Bulk Operations API ⬜

**Purpose**: Enable efficient bulk import/export for large content sets

- [ ] **Bulk Import**:
    - [ ] `POST /api/admin/content/bulk-import` - Import multiple entities
    - [ ] Accepts array of content objects (converted from CSV/JSON)
    - [ ] Validates all before writing any
    - [ ] Returns: success_count, error_count, detailed_errors
    - [ ] Transaction-like behavior (all or nothing option)

- [ ] **Bulk Export**:
    - [ ] `GET /api/admin/content/bulk-export?type=<type>&filter=<filter>` - Export content
    - [ ] Supports CSV, JSON, YAML formats
    - [ ] Optional filtering (e.g., all items in area X)
    - [ ] Streaming response for large datasets

- [ ] **Batch Validation**:
    - [ ] `POST /api/admin/content/batch-validate` - Validate multiple files at once
    - [ ] Returns validation results for each file
    - [ ] Used during bulk import preview

**Blocking**: Phase 4B of CMS (bulk import/export features)

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

### Implementation Phases

**Phase 12.1-12.3 (Critical Path)** - Blocks CMS Phase 1-2:
1. Schema Registry API
2. YAML File Management API  
3. Enhanced Validation API

**Phase 12.4-12.5 (Important)** - Blocks CMS Phase 3-4:
4. Content Querying API
5. Bulk Operations API

**Phase 12.6-12.7 (Optional)** - Nice-to-have features:
6. Git Integration (can be client-side)
7. Real-Time Preview (advanced feature)

### Technical Considerations

**Security**:
- All endpoints require `GAME_MASTER` or `ADMIN` role
- Path traversal prevention in file operations
- Content size limits (prevent DoS via huge YAML files)
- Rate limiting on validation endpoints

**Performance**:
- Schema caching with invalidation
- Reference cache for O(1) validation lookups
- Streaming responses for bulk operations
- Async file I/O for all operations

**Error Handling**:
- Detailed error messages with line/column info
- Validation errors vs warnings
- Graceful degradation if git operations fail
- Transaction rollback on bulk import failures

### Documentation Updates

- [ ] Update protocol.md with new endpoints
- [ ] API documentation with request/response examples
- [ ] CMS integration guide
- [ ] Schema versioning documentation

---

### Phase 13 - Abilities Audit ⬜
Ensure test engine is working
Make sure every ability produced does what it claims to do

### Phase Y - Player quality of life ⬜
In-game documentation: listing all commands, player role, etc
Stub client tweaks

### Phase 14 - Cybersecurity Audit ⬜
Ensure the engine server and database are protected from malicious actors, especially with regards to text sent to the server from the client

### Phase 15 - Knobs and Levers: comprehensive In-game commands and API Routes documentation
User-focused documentation for in-game commands and API routes for development

### Phase 16 - Mechanic's Manual: comprehensive guide for modders
Modder-focused guide to easily extending the engine codebase

## Phase Z - Backlogged Niceties & polish

- Rate limiting & abuse protection (spam commands, chat).
    - Localization hooks in text output.
- Protocol versioning:
    - Include an event version field when you start adding breaking changes.
- Save/restore partial sessions for mobile clients.
