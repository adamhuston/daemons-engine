# Roadmap

## Phase 0  Hardening

Before adding big systems, make the core loop solid.

**Goals**: No silent failures; predictable behavior under load.

### Backend tasks

- Logging & observability
    - Structured logs for:
        - player connect/disconnect,
        - commands received,
        - errors in engine / WS tasks.
    - Simple metrics hooks (counters for active players, commands/sec).
- Error handling
    - Make sure _ws_sender / _ws_receiver never kill the app on exceptions.
    - Graceful handling of bad JSON / unknown commands.
- Protocol doc
    - Write a short protocol.md:
        - shape of clientserver commands,
        - shape of serverclient events (type, text, optional payload).



## Phase 1  Player stats and progression

**Goals**: A player is more than just a name + room.

### Backend model changes

-  Extend Player model:
    -  Base stats: str, dex, int, vit, etc.
    -  Derived stats: hp, max_hp, mp, max_mp, level, xp.
    -  Class / archetype as a simple string/enum.
-  World model:
    -  Add those fields to WorldPlayer.
    -  Add a payload section in events for stat updates.

### Engine changes

-  New commands:
    -  stats/sheet: prints current stats.
-  Event types:
    -  stat_update events:
        - {"type": "stat_update", "payload": {"hp": 10, "max_hp": 20, "level": 3}}
-  Persistence policy:
    -  Implemented: sync WorldPlayer  DB on disconnect
    -  Future: periodically (can now use time event system from Phase 2)
    -  Future: on key events (level up, death, etc.).



## Phase 2  Time & tick system (for effects/debuffs)  **COMPLETE**

**Goals**: Server time becomes first-class; you can have timed buffs/debuffs, regen, DoTs, etc.

**Note**: The original design called for traditional "ticks" but we implemented an event-driven architecture instead.

### Phase 2a  Core Time System 
- Event-driven time system (not traditional ticks)
- TimeEvent dataclass with priority queue
- Async _time_loop() processes events at precise Unix timestamps
- schedule_event() and cancel_event() methods
- Supports one-shot and recurring events
- Dynamic sleep until next event
- testtimer command

### Phase 2b  Effect System 
- Effect dataclass with effect_id, name, effect_type (buff/debuff/dot/hot)
- stat_modifiers: Dict[str, int]
- duration, applied_at tracking
- interval, magnitude for periodic effects
- WorldPlayer active_effects: Dict[str, Effect]
- apply_effect(), remove_effect(), get_effective_stat() methods
- Commands: bless, poison, effects/status
- Stat integration with effective vs base values

### Phase 2c  World Time System 
- WorldTime dataclass tracking day/hour/minute
- advance() and get_current_time() methods
- WorldArea system with independent area_time
- time_scale attribute for different time speeds
- Environmental properties
- Time advancement every 30 seconds
- time command with area context
- Sample areas (Ethereal Nexus 4x, Temporal Rift 2x)

## Phase 3 - Items & inventory  **COMPLETE**

**Goals**: Physical objects in the world, inventory management, equipment.

### Backend Model 

- DB:
    -  ItemTemplate (static: name, type, modifiers, description, keywords).
    -  ItemInstance (dynamic: owner, location, durability, unique flags).
    -  PlayerInventory (capacity limits, weight/slot tracking).

- World:
    -  WorldItem for runtime representation.
    -  ItemTemplate dataclass with full properties.
    -  Attach items to:
        -  rooms (ground items)
        -  other items (containers)
        -  players (inventory and equipment).

### YAML Content System 

-  world_data/items/ directory structure (weapons/, armor/, consumables/, containers/)
-  world_data/item_instances/ for spawn configurations
-  Migration loads items from YAML files
-  Example items: Rusty Sword, Wooden Staff, Iron Chestplate, Leather Cap, Health Potion, Scroll of Wisdom, Leather Backpack

### Engine Changes 

- Loader:
    -  Load templates + instances into World.
    -  Link items to players/rooms on startup.
    -  Restore equipped items and apply stat effects.

- Core item mechanics:
    -  inventory/inv/i: View inventory with weight/slots.
    -  get/take/pickup <item>: Pick up from room (one at a time for stacks).
    -  drop <item>: Drop to room.
    -  give <item> <player>: Transfer to another player.
    -  equip/wear/wield <item>: Equip to appropriate slot.
    -  unequip/remove <item>: Unequip item.
    -  use/consume/drink <item>: Use consumable items.
    -  look <item>: Detailed item inspection with properties.
    -  put <item> in <container>: Store items in containers.
    -  get <item> from <container>: Retrieve from containers.

- Stat interactions:
    -  Equipment applies stat modifiers via Effect system.
    -  On equip: create permanent effect with stat bonuses.
    -  On unequip: remove effect, recalculate stats.
    -  Consumables apply temporary effects (buffs, healing).

- Quality of Life:
    -  Partial name matching ("lea" finds "leather backpack").
    -  Keyword system (items can have multiple searchable names).
    -  Stack handling (pick up one at a time).
    -  Weight and slot-based inventory limits.
    -  O(1) container contents lookup via index (not O(n) world scan).

### Events 

- Room broadcasts:
    -  "Alice drops Rusty Sword."
    -  "Bob picks up Health Potion."
    -  "Alice gives Health Potion to Bob."
- Stat updates:
    -  stat_update events on equip/unequip/consume.

### Persistence 

-  Inventory saved on player disconnect.
-  Item locations, quantities, durability persisted.
-  Equipment state restored on reconnect.



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

## Phase X - Quest System and Narrative Progression

**Goals**: Structured narrative experiences, player-driven story progression, and meaningful rewards.

### Core Quest Infrastructure

- Quest System Architecture:
    - QuestSystem class following GameContext pattern
    - QuestTemplate dataclass: id, name, description, objectives, rewards, prerequisites
    - QuestStatus enum: NOT_AVAILABLE → AVAILABLE → ACCEPTED → IN_PROGRESS → COMPLETED → TURNED_IN
    - QuestProgress dataclass for player-specific quest state tracking
    - QuestObjective dataclass with type-specific parameters

- Objective Types:
    - KILL: Kill N of NPC template
    - COLLECT: Collect N of item template
    - DELIVER: Bring item to NPC
    - VISIT: Enter a specific room
    - INTERACT: Use command in room (trigger-based)
    - ESCORT: Keep NPC alive to destination
    - DEFEND: Prevent NPCs from reaching location
    - TALK: Speak to NPC
    - USE_ITEM: Use specific item

- Quest Rewards:
    - Experience points
    - Items (via ItemSystem.give_item())
    - Effects (via EffectSystem.apply_effect())
    - Flags (player and room)
    - Currency (future)
    - Reputation (future)

### NPC Dialogue System

- Dialogue Data Structures:
    - DialogueTree: Complete dialogue for an NPC
    - DialogueNode: A node with text, options, conditions, actions
    - DialogueOption: Player response with conditions and quest integration
    - Variable substitution: {player.name}, {quest.progress}

- Dialogue Flow:
    - `talk <npc>` command initiates dialogue
    - Numbered option selection (1, 2, 3...)
    - Condition evaluation for available options
    - Context-sensitive entry points based on quest status
    - Quest accept/turn-in integration

### Player Commands

- `talk <npc>`: Initiate dialogue with NPC
- `1`, `2`, `3`...: Select dialogue option by number
- `bye`, `farewell`: End dialogue
- `journal`, `quests`, `quest log`: View quest journal
- `quest <name>`: View specific quest details
- `abandon <quest>`: Abandon a quest

### Engine Integration

- Combat System hooks: on_npc_killed → KILL objectives
- Item System hooks: on_item_acquired → COLLECT objectives
- Movement hooks: on_room_entered → VISIT objectives
- CommandRouter: Dialogue state handling before command dispatch

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

### Sample Content

- ✅ `wisp_investigation` - Exploration-focused starter quest (VISIT, TALK objectives)
- ✅ `goblin_threat` - Combat-focused follow-up quest (KILL, COLLECT objectives)
- ✅ `wandering_merchant` dialogue tree with quest integration and context-sensitive greetings
- ✅ `ethereal_mystery` quest chain linking the two starter quests with bonus rewards

### Future Considerations

- Reputation system with faction standings
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

## Phase 7 - Accounts, auth, and security **COMPLETE**

**Goals**: Move from "just a player_id" to real accounts.

### Implementation Complete

**Database Schema**
-  `user_accounts` table: username, email, password_hash, role, active_character_id
-  `refresh_tokens` table: token rotation for session management
-  `security_events` table: audit log for logins, logouts, role changes
-  `players.account_id` foreign key linking characters to accounts

**AuthSystem (systems/auth.py)**
-  UserRole enum: PLAYER, MODERATOR, GAME_MASTER, ADMIN
-  Permission enum: granular permissions (MODIFY_STATS, SPAWN_ITEM, etc.)
-  JWT-based authentication with 1-hour access tokens
-  Refresh token rotation with 7-day expiry
-  Argon2 password hashing via passlib
-  `requires_role()` and `requires_permission()` decorators

**HTTP Endpoints**
-  POST `/auth/register` - Create new account
-  POST `/auth/login` - Get access + refresh tokens
-  POST `/auth/refresh` - Rotate tokens
-  POST `/auth/logout` - Revoke refresh token
-  GET `/auth/me` - Get current user info

**Character Management**
-  POST `/characters` - Create character (max 3 per account)
-  GET `/characters` - List account's characters
-  POST `/characters/{id}/select` - Set active character
-  DELETE `/characters/{id}` - Delete character

**WebSocket Authentication**
-  `/ws/game/auth?token=<access_token>` - Authenticated endpoint
-  Verifies JWT and loads active character
-  Sets auth_info in context for permission checks
-  Legacy `/ws/game?player_id=` still works (deprecated)

**Permission Enforcement**
-  Admin commands (heal, hurt) require GAME_MASTER role
-  `_check_permission()` method in WorldEngine
-  Denied commands return error message

**Client Updates**
-  Login/Register UI with httpx
-  Authenticated WebSocket connection flow
-  Legacy mode toggle for backward compatibility

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

## Phase 9 - Classes & Abilities

**Goals**: Extensible character class system with unique abilities, resource management, and progression paths.

### Class System Architecture

- ClassTemplate dataclass:
    - `class_id`, `name`, `description`
    - `base_stats` - Starting stat modifiers
    - `stat_growth` - Per-level stat gains
    - `resource_type` - Primary resource (mana, rage, energy, focus)
    - `abilities` - List of ability IDs unlocked by class
    - `passive_effects` - Always-active class bonuses

- YAML-driven class definitions:
    - `world_data/classes/` directory
    - Easy to add new classes without code changes

### Ability System

- AbilityTemplate dataclass:
    - `ability_id`, `name`, `description`
    - `resource_cost` - Cost to use
    - `cooldown` - Seconds between uses
    - `cast_time` - Channel/cast duration (0 = instant)
    - `range` - self, target, room, area
    - `effects` - List of effects to apply
    - `requirements` - Level, class, equipment, etc.

- Ability Types:
    - Active: Explicitly triggered by player command
    - Passive: Always active, modifies stats or triggers on events
    - Reactive: Triggers on specific conditions (on_hit, on_kill, etc.)

- Ability effects:
    - Damage (direct, DoT)
    - Healing (direct, HoT)
    - Buff/Debuff application
    - Movement (teleport, dash)
    - Summon (temporary NPCs)
    - Custom script hooks

### Resource System

- Resource types:
    - Mana: Regenerates over time
    - Rage: Builds from combat, decays out of combat
    - Energy: Fast regen, low max
    - Focus: Builds from specific actions

- ResourceManager integration with EffectSystem:
    - Regen rates modified by stats/effects
    - Resource costs modified by talents/gear

### Talent/Specialization Trees (Future)

- Talent points earned on level-up
- Specialization paths within each class
- Talent effects: ability upgrades, new passives, stat bonuses

### Commands

- `abilities` / `skills`: List available abilities
- `use <ability>` / `cast <ability>`: Activate an ability
- `use <ability> <target>`: Targeted abilities
- `class`: View current class info and progression

### YAML Content

- `world_data/classes/warrior.yaml`, `mage.yaml`, `rogue.yaml`, etc.
- `world_data/abilities/` directory organized by class

### Database Extensions

- `players.class_id` - Selected class
- `players.ability_cooldowns` (JSON) - Active cooldown tracking
- `players.resource_current` - Current resource value
- `class_templates` table (optional, can be YAML-only)

## Phase 10 - Niceties & polish

- Rate limiting & abuse protection (spam commands, chat).
    - Localization hooks in text output.
- Protocol versioning:
    - Include an event version field when you start adding breaking changes.
- Save/restore partial sessions for mobile clients.
