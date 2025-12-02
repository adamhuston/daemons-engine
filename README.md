# Daemons Engine

A Python framework for building text-based multiplayer RPGs with real-time WebSocket communication.

>  **Pre-Release Beta**  API subject to change. Not recommended for production use.
>  **Latest Roadmap Release:**  Phase 16 - Cybersecurity upgrades, including input validation and production mode

---

## Quickstart

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Step 1: Create Project Directory

```bash
mkdir my-game
cd my-game
```

### Step 2: Create Virtual Environment

```powershell
# Windows
python -m venv .venv
.\.venv\Scripts\Activate
```

```bash
# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Daemons Engine

```bash
pip install daemons-engine
```

### Step 4: Initialize Your Game

```bash
daemons init <new_game>
```

This creates:
- `world_data/`  YAML content (rooms, NPCs, items)
- `config.py`  Server configuration
- `main.py`  Application entry point
- `alembic.ini`  Database migration config
- `alembic/`  Migration scripts

### Step 5: Set Up Database

```bash
cd <new_game>
daemons db upgrade
```

### Step 6: Run the Server
From `/<new_game>`...

```bash
# Development (auto-reload on code changes)
daemons run --reload

# Production (requires JWT secret key)
daemons run --production
```

The `--production` flag enables security hardening:
- Requires `JWT_SECRET_KEY` environment variable
- Enforces JWT issuer/audience validation
- Runs without auto-reload

If `JWT_SECRET_KEY` is not set, you'll be prompted to generate one.

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### Step 7: Connect a Client

**Option A: Reference Client**

```bash
pip install flet
daemons client
```

**Option B: Build Your Own**

Connect via WebSocket to `ws://127.0.0.1:8000/ws/game/auth`.

**Test Credentials:**
- Username: `testplayer1` / Password: `testpass1`
- Username: `testplayer2` / Password: `testpass2`

---

## Create Game Content

All content is defined in YAML files under `world_data/`.

### Example Room (`world_data/rooms/tavern.yaml`)

```yaml
id: tavern_main
name: "The Rusty Tankard"
description: |
  A cozy tavern with a crackling fireplace.
room_type: indoor
area_id: starter_town
exits:
  north: town_square
```

### Example NPC (`world_data/npcs/barkeeper.yaml`)

```yaml
id: npc_barkeeper
name: "Greta the Barkeeper"
description: "A stout woman with a warm smile."
level: 5
behaviors:
  - merchant
spawn_room: tavern_main
```

---

## Project Structure

```
my-game/
 world_data/              # Your game content
    rooms/               # Room definitions
    items/               # Items and equipment
    npcs/                # NPC templates
    quests/              # Quest definitions
    dialogues/           # NPC dialogue trees
 alembic/                 # Database migrations
 config.py                # Server configuration
 main.py                  # Application entry point
 dungeon.db               # SQLite database
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Initialize project | `daemons init` |
| Run migrations | `daemons db upgrade` |
| Start server (dev) | `daemons run --reload` |
| Start server (prod) | `daemons run --production` |
| Run client | `daemons client` |

| URL | Description |
|-----|-------------|
| http://127.0.0.1:8000/docs | Swagger API docs |
| http://127.0.0.1:8000/redoc | ReDoc API docs |

---

## Documentation

Coming soon

---

## License

MIT License  see [LICENSE](LICENSE) for details.
