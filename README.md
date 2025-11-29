# Daemons

**A modern MUD engine.**

Headless game engine for real-time, text-based multiplayer worlds. Python/FastAPI backend exposing a WebSocket API. Handles game state, persistence, and authentication—bring your own frontend.

**Ecosystem (planned):**
- **Daemonswright** — Visual content management for Daemons worlds
- **Scry** — Cross-platform game client

## Architecture Highlights

### Unified Entity Model
All game entities share a common `WorldEntity` base class with consistent stat systems, effects, and behaviors. Players and NPCs are structurally identical—they can both level up, equip items, receive buffs, and die. This eliminates the awkward special-casing common in classic MUD codebases.

```python
class WorldEntity:
    stats: Stats           # strength, dexterity, intelligence, vitality
    current_health: int
    effects: list[Effect]  # buffs, debuffs, DoTs
    equipment: Equipment   # weapon, armor slots
```

### Targetable Protocol
The `Targetable` protocol provides unified command targeting across entity types. Commands like `attack`, `look`, and `give` resolve targets by name without knowing whether they're addressing a player, NPC, or item:

```python
class Targetable(Protocol):
    id: str
    name: str
    keywords: list[str]
    def get_description(self) -> str: ...
    def get_targetable_type(self) -> TargetableType: ...
```

### Event-Driven Time
Priority-queue scheduling instead of fixed ticks. Events fire at precise Unix timestamps with dynamic sleep until the next scheduled event—no wasted CPU cycles. Effects store their own `expiration_event_id` and `periodic_event_id`, tightly coupling buff/debuff lifecycle to the time system.

Each `WorldArea` maintains independent time with configurable `time_scale`:
```python
class WorldArea:
    area_time: WorldTime   # independent clock
    time_scale: float      # 1.0 = normal, 4.0 = 4x faster
```

### Shared GameContext
All systems communicate through a shared `GameContext` rather than direct references. This enables loose coupling—`CombatSystem` can trigger effects without importing `EffectSystem`:

```python
class GameContext:
    world: World
    combat_system: CombatSystem
    effect_system: EffectSystem
    trigger_system: TriggerSystem
    quest_system: QuestSystem
    # ...
```

### Composable Systems
- `CombatSystem` – Turn-based combat with weapon stats and auto-attack scheduling
- `EffectSystem` – Buffs, debuffs, DoTs with stat stacking and duration tracking
- `TriggerSystem` – Room-based reactive events (conditions → actions)
- `QuestSystem` – Quest lifecycle with dialogue trees and objective tracking
- `AuthSystem` – JWT auth with role-based permissions
- `StateTracker` – Dirty-entity tracking for persistence

### Serialized Command Processing
Single `WorldEngine` instance per process. Commands flow through one async queue, eliminating shared-state races inside the engine. The world state is always consistent.

### World/Engine Separation
Database stores persistent data (rooms, players, items). On startup, data loads into an in-memory `World`. The `WorldEngine` mutates this in-memory state. Persistence back to DB is periodic or event-driven via `StateTracker`.

### YAML Content Layer
World defined in data files—areas, rooms, NPCs, items, quests, triggers, dialogues. Extend the world without writing Python:
```yaml
id: room_1_1_1
name: "Heart of the Nexus"
room_type: ethereal
exits:
  north: room_1_2_1
```

### Behavior Composition
NPCs load behavior modules by name from YAML templates:
- `WanderingBehavior` – Random exploration within area bounds
- `CombatBehavior` – Target selection, threat response, disengage logic
- `FleeBehavior` – Retreat at health threshold
- `SocialBehavior` – Greetings, idle chatter

Custom behaviors are Python files dropped into `behaviors/`.

### Persistence
Dirty-entity tracking with periodic saves. Critical saves on death/quest completion. Ground item decay. Graceful shutdown flush.

### Authentication
JWT access tokens (1h) + refresh token rotation (7d). Argon2 hashing. Role hierarchy: Player → Moderator → Game Master → Admin. Security audit logging.

### Headless Protocol
```json
{"type": "command", "text": "attack goblin"}
{"type": "message", "text": "You swing at the Goblin Scout..."}
{"type": "stat_update", "payload": {"current_health": 85}}
```
Reference Flet client included.

## Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) – Backend and engine design
- [CONTRIBUTING.md](./CONTRIBUTING.md) – Development workflow
- [protocol.md](./protocol.md) – WebSocket message format
- [roadmap.md](./roadmap.md) – Feature roadmap
- [alembic.md](./alembic.md) – Database migrations

## Quick Start

```bash
cd 1126
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

cd backend
python -m alembic upgrade head
uvicorn app.main:app --reload

# Separate terminal
cd client
python client.py
```

## Status

| Phase | Description |
|-------|-------------|
| 0-7 | Complete (stats, time, items, combat, NPCs, triggers, quests, persistence, auth) |
| 8 | Planned: Admin tools |
| 9 | Planned: Classes & abilities |

## Stack

- Python 3.11+, FastAPI, Uvicorn
- SQLAlchemy (async) + SQLite
- python-jose, passlib/Argon2
- Flet (reference client)
- Alembic