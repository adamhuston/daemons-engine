# Daemons Engine Documentation

> **A modern MUD engine** — Headless game engine for real-time, text-based multiplayer worlds.

---

## 📚 Table of Contents

### Getting Started
| Document | Description |
|----------|-------------|
| [LONGFORM_README.md](./LONGFORM_README.md) | Project overview, architecture highlights, and quick start guide |
| [OPERATIONS.md](./OPERATIONS.md) | Server management, CLI commands, and troubleshooting |

### Architecture & Design
| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | High-level system design, stack overview, and core concepts |
| [protocol.md](./protocol.md) | WebSocket API documentation (client ↔ server messages) |
| [ROADMAP.md](./ROADMAP.md) | Development phases, completed features, and future plans |

### Content Creation
| Document | Description |
|----------|-------------|
| [SCHEMAS_FOR_CONTENT_CREATORS.md](./SCHEMAS_FOR_CONTENT_CREATORS.md) | Guide to YAML schemas for creating game content |
| [YAML_IMPLEMENTATION.md](./YAML_IMPLEMENTATION.md) | How the YAML content system works |
| [flora_and_fauna.md](./flora_and_fauna.md) | Reference lists for world flora and fauna |
| [fauna_behaviors.md](./fauna_behaviors.md) | Fauna NPC behavior configuration guide |

### Abilities & Mechanics
| Document | Description |
|----------|-------------|
| [utility_abilities.md](./utility_abilities.md) | Non-combat ability system (light, unlock, teleport, etc.) |
| [utility_abilities_summary.md](./utility_abilities_summary.md) | Quick reference for utility abilities |
| [utility_abilities_examples.md](./utility_abilities_examples.md) | Example ability configurations |

### Developer Reference
| Document | Description |
|----------|-------------|
| [SCHEMAS_FOR_DEVS.md](./SCHEMAS_FOR_DEVS.md) | Database schema reference (SQLAlchemy tables, columns, constraints) |
| [alembic.md](./alembic.md) | Database migration guide using Alembic |
| [TEST_ARCHITECTURE.md](./TEST_ARCHITECTURE.md) | Test infrastructure, fixtures, and coverage guidelines |

### Quality Assurance
| Document | Description |
|----------|-------------|
| [qa_todos.md](./qa_todos.md) | Manual QA testing checklist |

### Build Documentation (Phase Design Docs)
| Document | Description |
|----------|-------------|
| [build_docs/](./build_docs/) | Detailed design documents for each development phase |

See [build_docs/build_docs_README.md](./build_docs/build_docs_README.md) for the full list of phase documentation.

---

## 🔤 Index of Key Terms

### A
- **Abilities** — Character powers with cooldowns and resource costs. See [utility_abilities.md](./utility_abilities.md), [ROADMAP.md](./ROADMAP.md#phase-9---classes--abilities)
- **AbilityExecutor** — Runtime system for validating and executing abilities. See [TEST_ARCHITECTURE.md](./TEST_ARCHITECTURE.md)
- **Account Lockout** — Security feature preventing brute-force attacks. See [ROADMAP.md](./ROADMAP.md#phase-162---account-lockout)
- **Admin API** — HTTP endpoints for server management. See [OPERATIONS.md](./OPERATIONS.md), [protocol.md](./protocol.md)
- **Alembic** — Database migration tool. See [alembic.md](./alembic.md)
- **Areas** — Geographic regions containing rooms with shared properties. See [SCHEMAS_FOR_CONTENT_CREATORS.md](./SCHEMAS_FOR_CONTENT_CREATORS.md)
- **AuthSystem** — JWT-based authentication system. See [ROADMAP.md](./ROADMAP.md#phase-7---accounts-auth-and-security)

### B
- **Behaviors** — NPC AI scripts (wandering, aggressive, merchant, etc.). See [fauna_behaviors.md](./fauna_behaviors.md), [ARCHITECTURE.md](./ARCHITECTURE.md)
- **BehaviorResult** — Output from behavior execution (movement, attacks, messages). See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Biomes** — Environmental types affecting spawns and weather. See [fauna_behaviors.md](./fauna_behaviors.md)
- **Bulk Operations** — Import/export multiple content files. See [ROADMAP.md](./ROADMAP.md#phase-125---bulk-operations-api)

### C
- **Character Sheet** — Player/NPC class, level, abilities, and resources. See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Classes** — Character archetypes (Warrior, Mage, Rogue). See [ROADMAP.md](./ROADMAP.md#phase-9---classes--abilities)
- **ClassSystem** — Runtime manager for class/ability templates. See [ROADMAP.md](./ROADMAP.md#phase-9c---classsystem-runtime-manager)
- **Clans** — Persistent player guilds with ranks. See [ROADMAP.md](./ROADMAP.md#phase-102-persistent-clans)
- **CMS API** — REST API for Daemonswright content management. See [ROADMAP.md](./ROADMAP.md#phase-12---cms-api-integration)
- **Combat** — Real-time attack system with swing timers. See [ROADMAP.md](./ROADMAP.md#phase-4---npcs--combat-system)
- **Commands** — Player input processed by CommandRouter. See [protocol.md](./protocol.md)
- **Cooldowns** — Per-ability and global cooldown (GCD) tracking. See [utility_abilities.md](./utility_abilities.md)

### D
- **Daemons** — The engine name. See [LONGFORM_README.md](./LONGFORM_README.md)
- **Daemonswright** — Visual CMS for Daemons worlds (planned). See [LONGFORM_README.md](./LONGFORM_README.md)
- **Dialogue System** — NPC conversation trees. See [ROADMAP.md](./ROADMAP.md#npc-dialogue-system)
- **Dynamic Exits** — Runtime-created room connections. See [ROADMAP.md](./ROADMAP.md#phase-53---dynamic-world-state)

### E
- **Effects** — Buffs, debuffs, DoTs, HoTs applied to entities. See [ROADMAP.md](./ROADMAP.md#phase-2b--effect-system)
- **Entities** — Base class for players, NPCs, items. See [LONGFORM_README.md](./LONGFORM_README.md)
- **EventDispatcher** — Routes game events to clients. See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Exits** — Room connections (north, south, up, down, etc.). See [protocol.md](./protocol.md)

### F
- **Factions** — World organizations with reputation standings. See [ROADMAP.md](./ROADMAP.md#phase-103-factions-with-reputation)
- **FastAPI** — Python web framework for HTTP/WebSocket. See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Fauna** — Wildlife NPCs with ecological behaviors. See [fauna_behaviors.md](./fauna_behaviors.md)
- **Flora** — Harvestable plants. See [flora_and_fauna.md](./flora_and_fauna.md)
- **Follow System** — Auto-follow another player. See [ROADMAP.md](./ROADMAP.md#phase-101-groups-tells-follow)

### G
- **GameContext** — Dependency injection container for systems. See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **GCD (Global Cooldown)** — Shared cooldown between abilities. See [utility_abilities.md](./utility_abilities.md)
- **Groups** — Ephemeral parties for coordinated play. See [ROADMAP.md](./ROADMAP.md#phase-101-groups-tells-follow)

### H
- **Heartbeat** — WebSocket ping/pong for connection health. See [ROADMAP.md](./ROADMAP.md#phase-164---websocket-security)
- **Hot-Reload** — Update content without server restart. See [ROADMAP.md](./ROADMAP.md#content-hot-reload-system)

### I
- **Input Sanitization** — Protection against Unicode exploits. See [ROADMAP.md](./ROADMAP.md#phase-165---input-sanitization)
- **Inventory** — Player item storage with weight/slots. See [ROADMAP.md](./ROADMAP.md#phase-3---items--inventory)
- **Items** — Equipment, consumables, containers. See [SCHEMAS_FOR_CONTENT_CREATORS.md](./SCHEMAS_FOR_CONTENT_CREATORS.md)

### J
- **JWT** — JSON Web Tokens for authentication. See [ROADMAP.md](./ROADMAP.md#phase-7---accounts-auth-and-security)

### L
- **Legacy Endpoint** — Deprecated `/ws/game?player_id=` connection. See [protocol.md](./protocol.md)
- **Lighting System** — Dynamic room illumination. See [ROADMAP.md](./ROADMAP.md#phase-11---light-and-vision-system)
- **Loader** — YAML content loading into World. See [YAML_IMPLEMENTATION.md](./YAML_IMPLEMENTATION.md)

### M
- **Migrations** — Database schema updates via Alembic. See [alembic.md](./alembic.md)

### N
- **NPCs** — Non-player characters with behaviors and combat. See [ROADMAP.md](./ROADMAP.md#phase-4---npcs--combat-system)

### O
- **Origin Validation** — WebSocket security check. See [ROADMAP.md](./ROADMAP.md#phase-164---websocket-security)

### P
- **Persistence** — Saving world state across restarts. See [ROADMAP.md](./ROADMAP.md#phase-6---persistence--scaling)
- **Permissions** — Role-based access control. See [ROADMAP.md](./ROADMAP.md#phase-7---accounts-auth-and-security)
- **Protocol** — Client-server message format. See [protocol.md](./protocol.md)
- **PyPI** — Python package index distribution. See [pypi.md](./pypi.md)

### Q
- **Quests** — Structured objectives with rewards. See [ROADMAP.md](./ROADMAP.md#phase-x---quest-system-and-narrative-progression)
- **Quest Chains** — Linked quest series. See [ROADMAP.md](./ROADMAP.md#advanced-quest-features-phase-x4)

### R
- **Rate Limiting** — Prevent API abuse. See [ROADMAP.md](./ROADMAP.md#phase-161---rate-limiting)
- **Refresh Tokens** — JWT session management. See [ROADMAP.md](./ROADMAP.md#phase-7---accounts-auth-and-security)
- **ResourcePool** — Mana, rage, energy tracking. See [ROADMAP.md](./ROADMAP.md#phase-9a---domain-models--database)
- **Rooms** — Individual locations in the world. See [SCHEMAS_FOR_CONTENT_CREATORS.md](./SCHEMAS_FOR_CONTENT_CREATORS.md)

### S
- **Schemas** — YAML structure definitions for content. See [SCHEMAS_FOR_CONTENT_CREATORS.md](./SCHEMAS_FOR_CONTENT_CREATORS.md)
- **Scry** — Cross-platform game client (planned). See [LONGFORM_README.md](./LONGFORM_README.md)
- **SecurityEvent** — Audit log for auth events. See [SCHEMAS_FOR_DEVS.md](./SCHEMAS_FOR_DEVS.md)
- **SQLAlchemy** — Python ORM for database access. See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **StateTracker** — Dirty entity tracking for persistence. See [ROADMAP.md](./ROADMAP.md#phase-6---persistence--scaling)
- **Stats** — Entity attributes (str, dex, int, vit, con, wis, cha). See [ROADMAP.md](./ROADMAP.md#phase-1--player-stats-and-progression)

### T
- **Targetable** — Protocol for unified command targeting. See [LONGFORM_README.md](./LONGFORM_README.md)
- **Tell** — Private player-to-player messaging. See [ROADMAP.md](./ROADMAP.md#phase-101-groups-tells-follow)
- **Temperature System** — Environmental temperature affecting gameplay. See [ROADMAP.md](./ROADMAP.md#phase-171---temperature-system)
- **TimeEventManager** — Priority-queue event scheduling. See [ROADMAP.md](./ROADMAP.md#phase-2a--core-time-system)
- **Triggers** — Event-driven room reactions. See [ROADMAP.md](./ROADMAP.md#phase-5---world-structure-triggers-and-scripting)

### U
- **UserRole** — Permission levels (PLAYER, MODERATOR, GAME_MASTER, ADMIN). See [ROADMAP.md](./ROADMAP.md#phase-7---accounts-auth-and-security)
- **Utility Abilities** — Non-combat abilities (light, unlock, teleport). See [utility_abilities.md](./utility_abilities.md)
- **Uvicorn** — ASGI server for FastAPI. See [ARCHITECTURE.md](./ARCHITECTURE.md)

### V
- **Validation Service** — Real-time YAML validation with line/column errors. See [ROADMAP.md](./ROADMAP.md#phase-123---enhanced-validation-api)
- **Visibility Levels** — NONE, MINIMAL, PARTIAL, NORMAL, ENHANCED. See [ROADMAP.md](./ROADMAP.md#phase-11---light-and-vision-system)

### W
- **Weather System** — Dynamic weather affecting gameplay. See [ROADMAP.md](./ROADMAP.md#phase-172---weather-system)
- **WebSocket** — Real-time client-server communication. See [protocol.md](./protocol.md)
- **WorldArea** — Runtime representation of areas. See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **WorldEngine** — Core game state manager. See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **WorldEntity** — Base class for all game entities. See [LONGFORM_README.md](./LONGFORM_README.md)
- **WorldItem** — Runtime representation of items. See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **WorldNPC** — Runtime representation of NPCs. See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **WorldPlayer** — Runtime representation of players. See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **WorldRoom** — Runtime representation of rooms. See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **WorldTime** — In-game time tracking. See [ROADMAP.md](./ROADMAP.md#phase-2c--world-time-system)

### Y
- **YAML** — Content definition format. See [YAML_IMPLEMENTATION.md](./YAML_IMPLEMENTATION.md)
- **Yell** — Extended-range broadcast chat. See [ROADMAP.md](./ROADMAP.md#phase-101-groups-tells-follow)

---

## 📁 Directory Structure

```
docs/
├── index.md                      # This file - Table of contents and index
├── LONGFORM_README.md            # Project overview
├── ARCHITECTURE.md               # System design
├── ROADMAP.md                    # Development phases
├── protocol.md                   # WebSocket API
├── OPERATIONS.md                 # Server management
│
├── SCHEMAS_FOR_CONTENT_CREATORS.md  # Content creation guide
├── SCHEMAS_FOR_DEVS.md              # Database schema reference
├── YAML_IMPLEMENTATION.md           # YAML system details
│
├── utility_abilities.md          # Utility ability system
├── utility_abilities_summary.md  # Utility ability quick ref
├── utility_abilities_examples.md # Utility ability examples
├── flora_and_fauna.md            # World flora/fauna lists
├── fauna_behaviors.md            # Fauna behavior config
│
├── alembic.md                    # Migration guide
├── TEST_ARCHITECTURE.md          # Testing infrastructure
├── cicd.md                       # CI/CD setup
├── pypi.md                       # Package publishing
├── deployment_cheatsheet.md      # Deploy quick reference
├── qa_todos.md                   # QA checklist
│
└── build_docs/                   # Phase design documents
    ├── phase2_time_NOTES.md
    ├── phase5_triggers.md
    ├── phase6_persistence.md
    ├── phase7_auth.md
    ├── phase8_admin.MD
    ├── phase9_classes_design.md
    ├── phase9_classes_implementation.md
    ├── phase10_socials*.md
    ├── phase11_lighting_design.md
    ├── phase13_abilities_testing_plan.md
    ├── phase14_entity_abilities_*.md
    ├── phase17_environment_implementation.md
    ├── phaseX_quests.md
    └── ... (additional design docs)
```

---

## 🔗 Quick Links

- **Start here**: [LONGFORM_README.md](./LONGFORM_README.md)
- **Run the server**: [OPERATIONS.md](./OPERATIONS.md)
- **Create content**: [SCHEMAS_FOR_CONTENT_CREATORS.md](./SCHEMAS_FOR_CONTENT_CREATORS.md)
- **Build a client**: [protocol.md](./protocol.md)
- **Contribute**: [TEST_ARCHITECTURE.md](./TEST_ARCHITECTURE.md)
