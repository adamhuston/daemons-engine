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



## Phase 5 - World structure, triggers, and scripting

**Goal**: Richer world behavior without hardcoding everything in Python.

### Backend model

- World segmentation:
    - Zones/areas with metadata (recommended level, themes, spawn tables).
- Triggers:
    - Room-level triggers: on enter/exit, on command, on timer.
- Scripts:
    - Choose a strategy:
        - minimalist: table-driven triggers with types ("spawn npc", "open door", etc.).
        - scriptable: embedded DSL or sandboxed Python scripts (more powerful, more complexity).

### Engine changes
- Trigger evaluation:
    - On events like:
        - player entering/leaving a room,
        - specific commands (pull lever, press button),
        - ticks.
- Event injection:
    - Triggers can:
        - alter world state (spawn NPC, open exit),
        - emit messages/events,
        - apply effects / teleport players.

## Phase 6 - Persistence & scaling

**Goals**: Don't lose progress on restart. Support more players in the future.

### Backend tasks

- Persistence strategy:
    - Periodic snapshots of World state to DB.
    - Replay of essential state on startup (players, items, NPC states).
- Locking/concurrency:
    - Right now this is a single-process system: engine's command queue already serializes state.
- For horizontal scaling:
    - Make WorldEngine a service (separate process),
    - Access it via a message bus (Redis/NATS/etc.),
    - Multiple FastAPI nodes talk to the same engine.
- Session handling:
    - One logical player  possibly multiple connections (mobile reconnect).
- Decide what happens on disconnect:
    - stay in world for N seconds,
    - vanish immediately,
    - AI autoplay, etc.

## Phase 7 - Accounts, auth, and security

**Goals**: Move from "just a player_id" to real accounts.

### Backend tasks

- Accounts:
    - UserAccount separate from Player (one user may have multiple characters).
- Auth:
    - Minimal JWT / token-based auth for API/WebSocket.
    - WebSocket handshake includes a token, backend attaches player_id based on it.
- Permissions:
    - Basic GM/Admin roles for in-game commands.

## Phase 8 - Admin & content tools

**Goals**: Operate and extend the game without editing code.

### Backend tasks

- Admin HTTP APIs:
    - Manage rooms, items, NPC templates, spawns.
    - Inspect live world state (who's in which room, etc.).
- In-world admin commands:
    - Teleport, spawn/despawn NPCs, give items, inspect player stats.
- Monitoring:
    - Simple dashboards: current players, CPU load, command volume.

## Phase 9 - Niceties & polish

- Rate limiting & abuse protection (spam commands, chat).
    - Localization hooks in text output.
- Protocol versioning:
    - Include an event version field when you start adding breaking changes.
- Save/restore partial sessions for mobile clients.
