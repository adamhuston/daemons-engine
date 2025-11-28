# Dungeon Crawler – Architecture & Goals

_Last updated: 2025-11-28_

This document is the high-level specification and context for the dungeon crawler project.  
It is written to be friendly to both humans and LLMs reading the repository.

---

## 1. Project Overview

This project is a real-time, text-based dungeon crawler inspired by classic MUDs.

**Key properties:**

- **Terminal-like UX** (retro, text-first), even on mobile.
- **Real-time, multi-player** interactions in a shared world.
- **Client-agnostic backend**:
  - Backend exposes a WebSocket protocol and HTTP APIs.
  - Any client (Flet, React, native, etc.) can implement the protocol.
- **Long-term goal**: fully-featured dungeon with:
  - stats and progression,
  - time-based buffs/debuffs,
  - items and equipment,
  - enemies and combat,
  - world scripting and triggers.

---

## 2. High-Level Architecture

### 2.1 Stack

**Backend**

- Python
- FastAPI (HTTP + WebSocket)
- Uvicorn (ASGI server)
- SQLAlchemy (async) with SQLite (for now)
- In-memory game engine (`WorldEngine`) on top of DB-backed world

**Client (current stub)**

- Flet (Python) desktop client
- Connects via WebSocket to `/ws/game`
- Minimal “terminal-style” view to send commands and display messages

### 2.2 Core Concepts

- **Room-based world**:
  - The world is made of rooms (nodes) with up to 6 exits:
    - `north`, `south`, `east`, `west`, `up`, `down`
  - Each room has: `id`, `name`, `description`, exits to other rooms.

- **Players**:
  - Identified by UUID (`player_id`).
  - Have a current room and (later) stats, inventory, etc.

- **WorldEngine (in-memory)**:
  - Holds the runtime `World` (rooms, players, and later NPCs/items).
  - Processes commands from players.
  - Generates events and routes them to connected clients.

- **Event-driven server**:
  - Clients send `command` messages (JSON) over WebSocket.
  - Server emits `event` messages (JSON) back (e.g., room descriptions, chat).

---

## 3. Current Code Layout (Backend)

> Paths are relative to the `backend/` directory.

### 3.1 Application entry

`app/main.py`

- Creates the FastAPI app.
- Startup:
  - Creates DB tables.
  - Seeds a minimal test world (2 rooms + 1 player).
  - Loads world data from DB into in-memory `World`.
  - Instantiates a single `WorldEngine` and starts its async game loop.
- HTTP endpoints:
  - `GET /` – health/hello check.
  - `GET /players` – returns current players from DB for debugging/testing.
- WebSocket endpoint:
  - `GET /ws/game?player_id=...`:
    - Accepts a WS connection for a given player.
    - Registers the player with `WorldEngine`.
    - Starts:
      - `_ws_receiver`: reads client commands and passes them to `WorldEngine`.
      - `_ws_sender`: reads server events from a queue and sends them to client.

The `WorldEngine` instance is stored in `app.state` (or a global), and all WS connections share this single engine.

### 3.2 Database layer

`app/db.py`

- Defines `engine` and `AsyncSessionLocal` via SQLAlchemy async APIs.
- Exposes `get_session()` dependency for FastAPI endpoints.

`app/models.py`

- `Room` model:
  - `id`, `name`, `description`
  - `room_type` - Type category with emoji indicators (forest, urban, underground, etc.)
  - Exit fields: `north_id`, `south_id`, `east_id`, `west_id`, `up_id`, `down_id`.
  - Self-referential `ForeignKey` to `rooms.id`.
  - Movement effects: `on_enter_effect`, `on_exit_effect`
- `Player` model:
  - `id` (UUID string)
  - `name`
  - `current_room_id` (FK to `Room.id`)
  - **Character progression:**
    - `character_class` - Class/archetype (adventurer, etc.)
    - `level` - Character level (default: 1)
    - `experience` - Experience points (default: 0)
  - **Base stats (primary attributes):**
    - `strength`, `dexterity`, `intelligence`, `vitality` (default: 10)
  - **Derived stats (combat/survival):**
    - `max_health`, `current_health` (default: 100)
    - `armor_class` (default: 10)
    - `max_energy`, `current_energy` (default: 50)
  - `data` JSON field for misc data (flags, temporary effects, etc.)
- `ItemTemplate` model:
  - `id`, `name`, `description`
  - `item_type`, `item_subtype`, `equipment_slot`
  - `stat_modifiers` (JSON) - Stat bonuses when equipped
  - **Weapon stats:** `damage_min`, `damage_max`, `attack_speed`, `damage_type`
  - `weight`, `max_stack_size`, `has_durability`, `max_durability`
  - `is_container`, `container_capacity`, `is_consumable`, `consume_effect`
  - `rarity`, `value`, `flags`, `keywords`
- `ItemInstance` model:
  - `id`, `template_id` (FK to ItemTemplate)
  - Location: `room_id`, `player_id`, or `container_id`
  - `quantity`, `current_durability`, `equipped_slot`
- `NpcTemplate` model:
  - `id`, `name`, `description`
  - `npc_type` (hostile, neutral, friendly, merchant)
  - Stats: `level`, `max_health`, `armor_class`, `strength`, `dexterity`, `intelligence`
  - Combat: `attack_damage_min`, `attack_damage_max`, `attack_speed`, `experience_reward`
  - `behaviors` (JSON) - List of behavior tags
  - `drop_table` (JSON), `idle_messages`, `keywords`
- `NpcInstance` model:
  - `id`, `template_id` (FK to NpcTemplate)
  - `room_id`, `spawn_room_id`, `respawn_time`
  - `instance_data` (JSON) for overrides

### 3.3 In-memory world model

`app/engine/world.py`

- Defines pure Python dataclasses for the runtime world:

  - `WorldPlayer`:
    - `id`, `name`, `room_id`
    - `is_connected` - Connection status (False = in stasis)
    - **Character stats:** `character_class`, `level`, `experience`
    - **Primary attributes:** `strength`, `dexterity`, `intelligence`, `vitality`
    - **Combat stats:** `max_health`, `current_health`, `armor_class`, `max_energy`, `current_energy`
    - **Effects:** `active_effects: Dict[str, Effect]` - Active buffs/debuffs
    - **Effect methods:** `apply_effect()`, `remove_effect()`, `get_effective_stat()`
    - `inventory` (currently a simple list; future hook for items)
  - `WorldRoom`:
    - `id`, `name`, `description`
    - `room_type`, `emoji` - Room categorization with visual indicator
    - `exits: dict[Direction, RoomId]`
    - `players: set[PlayerId]` – IDs of players currently in the room
    - `effects` - Movement effects (future hook)
  - `Effect`:
    - `effect_id`, `name`, `effect_type` (buff/debuff/dot/hot)
    - `stat_modifiers: Dict[str, int]` - Stat changes while active
    - `duration`, `applied_at` - Timing tracking
    - `interval`, `magnitude` - For periodic effects (DoT/HoT)
    - `expiration_event_id`, `periodic_event_id` - Time event references
  - `TimeEvent`:
    - `event_id`, `execute_at` (Unix timestamp)
    - `callback` - Async function to execute
    - `recurring` - Whether to reschedule after execution
  - `WorldTime`:
    - `day`, `hour`, `minute` - In-game time tracking
    - `last_update` - Unix timestamp of last advancement
    - `advance()` - Updates time based on real seconds elapsed
    - `get_current_time()` - Calculates current time dynamically
    - Time conversion: 24 game hours = 12 real minutes
  - `WorldArea`:
    - `area_id`, `name`, `description`
    - `area_time: WorldTime` - Independent time for this area
    - `time_scale` - Time flow multiplier (e.g., 4.0 = 4x faster)
    - Environmental properties: `biome`, `climate`, `ambient_lighting`, `weather_profile`
    - `time_phases` - Custom flavor text for different times of day
    - `ambient_sound` - Area-specific ambient audio description
  - `World`:
    - `rooms: dict[RoomId, WorldRoom]`
    - `players: dict[PlayerId, WorldPlayer]`
    - `areas: dict[AreaId, WorldArea]`
    - `world_time: WorldTime` - Global time for rooms not in areas

This layer is framework-agnostic (no FastAPI/SQLAlchemy here).  
It represents the “live world” in memory.

### 3.4 World loader

`app/engine/loader.py`

- `load_world(session: AsyncSession) -> World`:
  - Loads all `Room` rows → creates `WorldRoom` instances.
  - Loads all `Player` rows → creates `WorldPlayer` instances.
  - Adds players to the `players` set of their current room.
  - Returns a fully-populated `World` object.

Called on backend startup, after initial seeding, to initialize `WorldEngine`.

### 3.5 Game engine

`app/engine/engine.py`

- Holds the `WorldEngine` class and event logic.

Core responsibilities:

- Maintain the in-memory `World`.
- Process incoming commands from players.
- Produce high-level events (room descriptions, chat, movement feedback).
- Route events to the right players via per-player queues.

Key pieces:

- **Command queue**:
  - `self._command_queue: asyncio.Queue[(player_id, command_text)]`
  - `_ws_receiver` pushes commands into this queue.
- **Listeners map**:
  - `self._listeners: dict[player_id, asyncio.Queue[event]]`
  - Each connected player has a queue of outgoing events.
  - `_ws_sender` reads from these queues and sends messages to clients.
- **Time event system**:
  - `self._time_events: list[TimeEvent]` - Min-heap priority queue
  - `self._time_loop()`: Background async task processing due events
  - `schedule_event()` - Schedule one-shot or recurring events
  - `cancel_event()` - Cancel scheduled events by ID
  - Events execute at precise Unix timestamps (not tick-quantized)
  - Dynamic sleep until next event (efficient, no wasted CPU)
- **World time advancement**:
  - Recurring time event every 30 seconds
  - Advances `area_time` for each WorldArea based on `time_scale`
  - Each area progresses independently
- **Game loop**:
  - `game_loop()`:
    - Runs forever in the background (async task).
    - Pulls `(player_id, command)` from `_command_queue`.
    - Calls `handle_command(...)`.
    - Calls `_dispatch_events(events)` to deliver events.

Supported commands (current):

- **Movement:** `n/s/e/w/u/d` and `north/south/east/west/up/down`
- **Look:** `look` / `l`
- **Chat:** `say <message>`
- **Stats:** `stats` / `sheet` / `status` - View character sheet
- **Effects:** `effects` / `status` - View active buffs/debuffs
- **Emotes:** `smile`, `nod`, `laugh`, `cringe`, `smirk`, `frown`, `wink`, `lookaround`
- **Time:** `time` - View current in-game time with area context
- **Debug/Admin:** 
    - `heal <player>`, `hurt <player>` - Modify player health
    - `bless <player>` - Apply +5 AC buff for 30 seconds
    - `poison <player>` - Apply DoT (5 damage every 3s for 15s)
    - `testtimer [seconds]` - Test time event system
- **Keyword substitution:** `self` → auto-replaced with player name

Event model (current):

- Internally, engine uses events as `dict`s with fields like:
  - `type`: `"message"` or `"stat_update"`
  - `scope`: `"player"`, `"room"`, or `"all"` (internal routing only)
  - `player_id`: target player (for player-scoped events)
  - `room_id`: source/target room (for room-scoped events)
  - `text`: message text (for message events)
  - `payload`: structured data (for stat_update events)
  - `exclude`: list of player IDs to exclude from room/all broadcasts

- `_dispatch_events`:
  - Uses `scope` and `exclude` to decide which player queues to push to.
  - Strips internal fields (`scope`, `exclude`) before events are sent to clients.
  - The client sees:
    - `{"type": "message", "player_id": "...", "text": "..."}`
    - `{"type": "stat_update", "player_id": "...", "payload": {...}}`

**Persistence:**
- `WorldEngine` has `save_player_stats()` method to sync in-memory stats to database
- Called automatically on player disconnect
- Extensible for periodic auto-saves (Phase 2) or event-triggered saves
- Persisted fields: `current_health`, `current_energy`, `level`, `experience`, `current_room_id`

---

## 4. WebSocket Protocol (Summary)

Full details are in `protocol.md`. This section is a condensed summary for LLMs.

### 4.1 Connection

- URL: `ws://{host}:{port}/ws/game?player_id={player_id}`
- `player_id`:
  - UUID string for an existing player.
  - Backend may reject unknown IDs.

### 4.2 Client → Server

Message shape (command):

```json
{
  "type": "command",
  "text": "<command-string>"
}
```

Supported commands (current):

- `look` / `l`
- `north`, `south`, `east`, `west`, `up`, `down`
- `n`, `s`, `e`, `w`, `u`, `d`
- `say <message>`

Unknown commands produce a `"message"` event explaining the error.

### 4.3 Server → Client

Message shape (printable output):

``` 
{
  "type": "message",
  "player_id": "uuid-string",
  "text": "Some text...\nMore text..."
}
```

Used for:
- Room descriptions (look, movement).
- Movement feedback (“You move north…”, “You can’t go that way.”).
- Chat (“You say: ...”, “Alice says: ...”).
- Flavor/error messages.

Future events (planned, not implemented yet):
- stat_update
- combat
- inventory
- quest
- effect
- error (structured error messages)

## 5. Design Goals & Principles
### 5.1 Backend goals

- **Client-agnostic**:
    - Backend exposes a stable WebSocket/JSON protocol and HTTP APIs.
    - No coupling to any specific UI tech (Flet, React, etc.).
- **Authoritative server**:
    - All game logic lives server-side.
    - Clients are thin: they send commands and render events.
- **In-memory world + DB**:
    - DB stores persistent data: rooms, players, etc.
    - On startup, data is loaded into `World`.
    - The `WorldEngine` mutates this in-memory state.
    - Persistence back to DB can be periodic or event-driven.
    - **Phase 1 implemented:** Stats saved to DB on player disconnect via `save_player_stats()`.
    - **Phase 2 planned:** Periodic auto-saves via tick system.

- **Event-driven, serial command processing**:
    - Single WorldEngine instance per process.
    - Commands are serialized through a single async queue.
    - This simplifies concurrency: no shared-state races inside the engine.
- **Extensibility**:
    - Event format has a payload field reserved for structured data.
    - Models (Player, items, NPCs, etc.) are designed to be extended incrementally.

###  5.2 Future roadmap

See `roadmap.md` for detailed phase tracking and progress.

## 6. Client Notes (for future UIs)

Current stub: client_flet/client.py
- Single-player debug client to:
    - connect a specific player_id,
    - send commands,
    - display type="message" events in a scrollable log.
- Client expectations:
    - Send commands as described in the protocol.
    - For now, interpret:
        - event.type === "message" → print event.text.
    - Be tolerant of:
        - extra fields in events,
        - new event type values,
        - future payload data.
Long-term, we may have:
    - A React-based PWA client for browsers and mobile (via installable PWA).
    - A Flet-based native-like client optionally used for desktop/mobile apps.

## 7. How LLMs Should Use This File

If you (an LLM) are reading this file as context:
- Treat this document as the source of truth for:
    - high-level goals,
    - current architecture design,
    - the WebSocket protocol.
- Prefer architectural consistency with:
    - FastAPI + WorldEngine pattern,
    - World/Engine separation (DB vs in-memory),
    - command/event JSON protocol.

When generating new code or features:
- Do not tightly couple backend logic to a specific frontend.
- Keep the in-memory World and WorldEngine as the core domain model.
- Extend the protocol in backwards-compatible ways (add new event types/fields rather than changing existing ones, where possible).
- Remember that this documentation may be out of date with the current implementation, and you should confirm if dependencies do or not exist by looking for the required files