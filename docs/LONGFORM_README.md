# Daemons

**A modern MUD engine.**

[![Tests](https://github.com/adamhuston/1126/workflows/Tests/badge.svg)](https://github.com/adamhuston/1126/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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
- `CombatSystem` – Real-time combat with weapon stats and auto-attack scheduling
- `EffectSystem` – Buffs, debuffs, DoTs with stat stacking and duration tracking
- `TriggerSystem` – Room/area-based reactive events (conditions → actions)
- `QuestSystem` – Quest lifecycle with dialogue trees, chains, and objective tracking
- `AuthSystem` – JWT auth with role-based permissions and audit logging
- `StateTracker` – Dirty-entity tracking for persistence
- `ClassSystem` – Character classes with unique abilities and resource pools
- `GroupSystem` – Party formation, leadership, and coordinated actions
- `ClanSystem` – Persistent player organizations with ranks and permissions
- `FactionSystem` – NPC factions with reputation and alignment tracking
- `LightingSystem` – Dynamic light sources and visibility-based gameplay
- `TemperatureSystem` – Environmental temperature with biome/weather/time modifiers
- `WeatherSystem` – Dynamic weather with climate-based Markov transitions
- `BiomeSystem` – Biome definitions with seasonal cycles and spawn modifiers
- `FloraSystem` – Plants, trees, and harvestable resources
- `FaunaSystem` – Wildlife behaviors, pack spawning, migration, predator-prey
- `SpawnConditionEvaluator` – Condition-based entity spawning
- `PopulationManager` – Ecological dynamics and population control

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

- [QUICKSTART.md](./QUICKSTART.md) – **Full setup guide** (venv, deps, server, client, linting, tests)
- [ARCHITECTURE.md](./documentation/ARCHITECTURE.md) – Backend and engine design
- [CONTRIBUTING.md](./CONTRIBUTING.md) – Development workflow
- [OPERATIONS.md](./documentation/OPERATIONS.md) – Server management and troubleshooting
- [protocol.md](./documentation/protocol.md) – WebSocket message format
- [roadmap.md](./documentation/roadmap.md) – Detailed feature roadmap (Phases 0-17 in progress)
- [alembic.md](./documentation/alembic.md) – Database migrations
- [TEST_ARCHITECTURE.md](./documentation/TEST_ARCHITECTURE.md) – Testing strategy
- [COVERAGE_CI_CD.md](./documentation/COVERAGE_CI_CD.md) – CI/CD setup

**Phase Completion Documentation:**
- Phase 0-7: Core systems (stats, time, items, combat, NPCs, triggers, quests, persistence, auth)
- Phase 8: Admin tools with hot-reload and audit logging
- Phase 9: Classes & abilities with 24 core behaviors
- Phase 10: Social features (groups, clans, factions with reputation)
- Phase 11: Lighting system with visibility-based gameplay
- Phase 12: CMS API (schema registry, validation, bulk operations)
- Phase 16: Cybersecurity (rate limiting, JWT hardening, input sanitization)
- Phase 17: Environmental systems (weather, temperature, biomes, flora, fauna)

## Quick Start

### Development Setup

```bash
cd 1126

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Run development setup script
python setup_dev.py  # or setup_dev.ps1 on Windows

# This installs:
# - Project dependencies
# - Development tools (pytest, ruff, black, etc.)
# - Pre-commit hooks
```

### Running the Server

```bash
cd backend

# Run database migrations
python -m alembic upgrade head

# Start the server
uvicorn daemons.main:app --reload
```

### Running Tests

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test categories
pytest -m unit          # Unit tests (models, stats, world data structures)
pytest -m systems       # Systems tests (time manager, persistence)
pytest -m integration   # Integration tests (combat flows, quest flows)
pytest -m abilities     # Ability system tests
pytest -m api           # API endpoint tests

# Open coverage report
start htmlcov/index.html  # Windows
open htmlcov/index.html   # Mac
```

**Test Coverage:**
- **334 passing tests** covering core functionality
- **57 placeholder tests** for future features (combat, quests, persistence)
- Unit tests: Database models, world entities, stat calculations
- Systems tests: Time event scheduling, behavior loading
- Test infrastructure: Session-scoped fixtures, async SQLite, test markers

### Running the Client

```bash
# Separate terminal
cd client
python client.py
```

## Status

**Current Phase: Environmental Systems (Phase 17)**

| Phase | Description | Status |
|-------|-------------|--------|
| 0-7 | Core systems: stats, time, items, combat, NPCs, triggers, quests, persistence, auth | ✅ Complete |
| 8 | Admin tools & content management | ✅ Complete |
| 9 | Character classes & abilities system | ✅ Complete |
| 10 | Social features: groups, clans, factions | ✅ Complete |
| 11 | Light and vision system | ✅ Complete |
| 12 | CMS API integration (schema, validation, bulk ops) | ✅ Complete |
| 16 | Cybersecurity audit: rate limiting, JWT hardening, input sanitization | ✅ Complete |
| 17.1-17.6 | Environmental systems: weather, temperature, biomes, flora, fauna, ecosystems | ✅ Complete |
| 17.7-17.8 | Roads/paths system, final integration | 📝 In Progress |
| Testing | Comprehensive test suite, CI/CD pipeline, coverage reporting | ✅ Complete |

**Feature Highlights:**
- 400+ passing tests across unit, systems, and integration test suites
- 17+ game systems with hot-reload support for content and behaviors
- YAML-based content layer with 80+ files across 15+ content types
- RESTful CMS API for schema registry, file management, validation, and bulk operations
- Real-time combat, quest chains, faction reputation, and dynamic lighting
- Dynamic weather, temperature, and seasonal systems
- Flora/fauna ecosystems with condition-based spawning
- Cybersecurity hardening (rate limiting, input sanitization, JWT security)
- Automated CI/CD via GitHub Actions (Python 3.11-3.13 matrix)
- Pre-commit hooks for code quality (ruff, black, isort)

## Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Database**: SQLAlchemy (async) + SQLite with Alembic migrations
- **Authentication**: python-jose (JWT), passlib/Argon2
- **Security**: slowapi rate limiting, input sanitization, WebSocket security
- **Game Systems**: 17+ composable systems (combat, quests, abilities, factions, lighting, weather, flora, fauna, etc.)
- **Content**: YAML-based with hot-reload support (80+ files, 15+ content types)
- **Testing**: pytest with asyncio support (400+ passing tests)
- **Client**: Flet reference implementation
- **CI/CD**: GitHub Actions with Python 3.11-3.13 matrix testing

## Key Features

**Game Mechanics:**
- Real-time combat with weapon stats, critical hits, and auto-attacks
- Character classes with unique abilities and resource pools (mana, rage, energy)
- Quest chains with dialogue trees and multi-stage objectives
- Faction reputation system with alignment tracking
- Dynamic lighting with visibility-based gameplay
- Effect system for buffs, debuffs, DoTs, and HoTs
- Trigger system for room/area events and scripted interactions
- Dynamic weather with climate-based patterns (rain, storms, fog, snow)
- Temperature system with environmental hazards (freezing, scorching)
- Biome and seasonal cycles with gameplay effects
- Flora harvesting with respawn mechanics
- Fauna ecosystems with predator-prey dynamics and migration

**Social Features:**
- Group/party system with leadership and coordinated actions
- Persistent clans with ranks and permissions
- Tell/whisper system for private messaging
- Follow system for coordinated movement

**Content Management:**
- YAML-based content layer (no code changes needed)
- Hot-reload for items, NPCs, rooms, quests, and abilities
- RESTful CMS API with validation and bulk operations
- Schema registry for type-safe content editing
- Dependency tracking and reference validation

**Admin Tools:**
- Role-based permissions (Player → Moderator → GM → Admin)
- In-game admin commands (teleport, spawn, give, heal, etc.)
- HTTP API for world inspection and manipulation
- Audit logging for all admin actions
- Server status monitoring and metrics

**Developer Experience:**
- Comprehensive test suite with 400+ passing tests
- CI/CD pipeline with automated testing
- Pre-commit hooks for code quality
- Structured logging with performance metrics
- Type hints throughout codebase
- Input sanitization and security hardening
