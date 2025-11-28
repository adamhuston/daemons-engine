# Roadmap

## Phase 0 – Hardening

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
        - shape of client→server commands,
        - shape of server→client events (type, text, optional payload).



## Phase 1 – Player stats and progression

**Goals**: A player is more than just a name + room.

### Backend model changes

- Extend Player model:
    - Base stats: str, dex, int, vit, etc.
    - Derived stats: hp, max_hp, mp, max_mp, level, xp.
    - Class / archetype as a simple string/enum.
- World model:
    - Add those fields to WorldPlayer.
    - Add a payload section in events for stat updates.

### Engine changes

- New commands:
    - stats/sheet: prints current stats.
- Event types:
    - stat_update events:
        - {"type": "stat_update", "payload": {"hp": 10, "max_hp": 20, "level": 3}}
- Persistence policy:
    - Decide when you sync WorldPlayer → DB:
        - on disconnect,
        - periodically (every N ticks),
        - or on key events (level up, death, etc.).



## Phase 2 – Time & tick system (for effects/debuffs)

**Goals**: Server time becomes first-class; you can have timed buffs/debuffs, regen, DoTs, etc.

### Backend model

- Add a global “tick” concept to WorldEngine:
    - e.g. 10 ticks/second or 1 tick/second
- Status effect representation:
    - On WorldPlayer: list of effects (effects: dict[id, EffectState]).
    - An EffectState might include:
        - name, duration_ticks, interval_ticks, type (buff/debuff/dot/hot), magnitude.

### Engine changes

- Split game_loop into:
    - command_loop (what you have now),
    - tick_loop (periodic tasks).
- Each tick:
    - Decrement effect durations.
    - Apply periodic effects (DoT/HoT, regen).
- Emit events when:
    - an effect expires,
    - HP changes,
    - a major state change happens.

### Commands

- effects/status: list current effects on the player.


## Phase 3 – Items & inventory

**Goals**: Physical objects in the world, inventory management, equipment.

### Backend model

- DB:
    - ItemTemplate (static: name, type, modifiers, description).
    - ItemInstance (dynamic: owner, location, durability, unique flags).

- World:
    - WorldItem for runtime representation.
    - Attach items to either:
        - rooms
        - other items
        - players (player inventory, player equipment).

### Engine changes

- Loader:
    - Load templates + instances into World.
- Core item mechanics:
    - Pick up / drop / give:
        - get <item>, drop <item>, give <item> <player>.
    - Equip / unequip:
        - equip <item>, remove <item>.
- Stat interactions:
    - Items can modify stats (flat or percentage).
- On equip/unequip:
    - update derived stats,
    - emit stat_update event.

### Events

- Room broadcasts:
    - “Alice drops a rusty sword.”
    - “Bob picks up a healing potion.”



## Phase 4 – Enemies & combat

**Goals**: Basic PvE combat loop with NPCs in rooms.

### Backend model

- DB:
    - NpcTemplate with stats, behavior flags, loot tables.
    - NpcInstance
- World:
    - WorldNpc similar to WorldPlayer but with AI flags.
    - Attach NPCs to rooms.

### Engine changes

- Combat system:
    - Turn/round model:
        - simplest first: “immediate” attacks with a short cooldown.
        - next: per-tick initiative / action queue.
    - Damage formula and hit resolution:
        - based on attacker stats + weapon + defender stats/armor.
- States:
    - HP reduction, death state, respawn timers.
- Commands:
    - attack <target>, flee, maybe kill <target> alias.

### AI (Phase 4.1):

- Each tick, NPCs:
    - choose targets,
    - move,
    - cast, etc. (simple rule-based first).
- Loot:
    - On NPC death:
        - drop items to room,
        - or auto-assign to killer.
- Events
    - Per-player:
        - Damage/heal messages.
    - Room:
        - Combat broadcasts (“Orc swings at Alice.”, “Alice kills the orc.”).
- Stat updates:
    - HP/MP changes via stat_update.

## Phase 5 – World structure, triggers, and scripting

**Goal**: Richer world behavior without hardcoding everything in Python.

### Backend model

- World segmentation:
    - Zones/areas with metadata (recommended level, themes, spawn tables).
- Triggers:
    - Room-level triggers: on enter/exit, on command, on timer.
- Scripts:
    - Choose a strategy:
        - minimalist: table-driven triggers with types (“spawn npc”, “open door”, etc.).
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

## Phase 6 – Persistence & scaling

**Goals**: Don’t lose progress on restart. Support more players in the future.

### Backend tasks

- Persistence strategy:
    - Periodic snapshots of World state to DB.
    - Replay of essential state on startup (players, items, NPC states).
- Locking/concurrency:
    - Right now this is a single-process system: engine’s command queue already serializes state.
- For horizontal scaling:
    - Make WorldEngine a service (separate process),
    - Access it via a message bus (Redis/NATS/etc.),
    - Multiple FastAPI nodes talk to the same engine.
- Session handling:
    - One logical player → possibly multiple connections (mobile reconnect).
- Decide what happens on disconnect:
    - stay in world for N seconds,
    - vanish immediately,
    - AI autoplay, etc.

## Phase 7 – Accounts, auth, and security

**Goals**: Move from “just a player_id” to real accounts.

### Backend tasks

- Accounts:
    - UserAccount separate from Player (one user may have multiple characters).
- Auth:
    - Minimal JWT / token-based auth for API/WebSocket.
    - WebSocket handshake includes a token, backend attaches player_id based on it.
- Permissions:
    - Basic GM/Admin roles for in-game commands.

## Phase 8 – Admin & content tools

**Goals**: Operate and extend the game without editing code.

### Backend tasks

- Admin HTTP APIs:
    - Manage rooms, items, NPC templates, spawns.
    - Inspect live world state (who’s in which room, etc.).
- In-world admin commands:
    - Teleport, spawn/despawn NPCs, give items, inspect player stats.
- Monitoring:
    - Simple dashboards: current players, CPU load, command volume.

## Phase 9 – Niceties & polish

- Rate limiting & abuse protection (spam commands, chat).
    - Localization hooks in text output.
- Protocol versioning:
    - Include an event version field when you start adding breaking changes.
- Save/restore partial sessions for mobile clients.