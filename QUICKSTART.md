# Daemons Engine — Quickstart Guide

Build your own real-time MUD/RPG game using the Daemons engine.

---

## Prerequisites

- **Python 3.11+** — [Download](https://www.python.org/downloads/)
- **A terminal** — PowerShell (Windows), Terminal (macOS), or bash (Linux)

---

## 1. Create Your Game Project

```bash
mkdir my-game
cd my-game
```

---

## 2. Create a Virtual Environment

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

> **Tip:** You should see `(.venv)` in your terminal prompt when activated.

---

## 3. Install the Daemons Engine

```bash
pip install daemons-engine
```

This installs the engine and all its dependencies (FastAPI, SQLAlchemy, Alembic, etc.).

### Verify Installation

```bash
python -c "import daemons; print(daemons.__version__)"
```

---

## 4. Initialize Your Game

Create the initial project structure:

```bash
daemons init
```

This scaffolds:

```
my-game/
├── world_data/          # Your game content (YAML files)
│   ├── areas/
│   ├── rooms/
│   ├── items/
│   ├── npcs/
│   └── quests/
├── behaviors/           # Custom NPC behaviors (Python)
├── alembic/             # Database migrations
├── alembic.ini          # Alembic configuration
├── config.py            # Game configuration
└── main.py              # Entry point
```

---

## 5. Database Setup with Alembic

Initialize your game's database:

```bash
daemons db upgrade
```

Or use Alembic directly:

```bash
alembic upgrade head
```

This creates `game.db` with all tables and seeds the starter world.

### Common Alembic Commands

```bash
# Check current migration status
alembic current

# View migration history
alembic history

# Upgrade to latest
alembic upgrade head

# Downgrade one revision
alembic downgrade -1

# Create a new migration (after model changes)
alembic revision --autogenerate -m "description of changes"
```

---

## 6. Run the Server

```bash
daemons run
```

Or use uvicorn directly:

```bash
uvicorn main:app --reload --log-level info
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Application startup complete.
```

### Server Options

```bash
# Different port
daemons run --port 8080

# Bind to all interfaces (for LAN access)
daemons run --host 0.0.0.0

# Production mode (no reload, multiple workers)
uvicorn main:app --workers 4
```

### API Documentation

With the server running, visit:
- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

---

## 7. Connect a Client

### Option A: Use the Reference Client

Install and run the Flet-based debug client:

```bash
pip install flet
daemons client
```

### Option B: Build Your Own

Connect via WebSocket to `ws://127.0.0.1:8000/ws/game/auth`. See [protocol.md](https://github.com/adamhuston/1126/blob/main/documentation/protocol.md) for message formats.

### Test Credentials

The server seeds two test accounts on first run:
- Username: `testplayer1` / Password: `testpass1`
- Username: `testplayer2` / Password: `testpass2`

---

## 8. Create Game Content

All content is defined in YAML files under `world_data/`.

### Example: Create a Room

`world_data/rooms/tavern.yaml`:

```yaml
id: tavern_main
name: "The Rusty Tankard"
description: |
  A cozy tavern with a crackling fireplace. The smell of
  roasted meat and ale fills the air.
room_type: indoor
area_id: starter_town
exits:
  north: town_square
  up: tavern_rooms
```

### Example: Create an NPC

`world_data/npcs/barkeeper.yaml`:

```yaml
id: npc_barkeeper
name: "Greta the Barkeeper"
description: "A stout woman with a warm smile and keen eyes."
level: 5
behaviors:
  - merchant
  - friendly
dialogue_id: barkeeper_dialogue
spawn_room: tavern_main
```

### Hot Reload

Content changes are picked up automatically when using `--reload`, or trigger manually:

```bash
# In-game (as admin)
reload items
reload npcs
reload rooms
```

---

## 9. Project Structure

```
my-game/
├── world_data/              # Your game content
│   ├── areas/               # World areas
│   ├── rooms/               # Room definitions
│   ├── items/               # Items and equipment
│   │   ├── weapons/
│   │   ├── armor/
│   │   └── consumables/
│   ├── npcs/                # NPC templates
│   ├── quests/              # Quest definitions
│   ├── dialogues/           # NPC dialogue trees
│   └── triggers/            # Room/area triggers
├── behaviors/               # Custom Python behaviors
├── alembic/                 # Database migrations
├── alembic.ini
├── config.py                # Server configuration
├── main.py                  # Application entry point
└── game.db                  # SQLite database
```

---

## 10. Quick Reference

### Essential Commands

| Task | Command |
|------|---------|
| Install engine | `pip install daemons-engine` |
| Initialize project | `daemons init` |
| Run migrations | `daemons db upgrade` |
| Start server | `daemons run` |
| Start server (dev) | `daemons run --reload` |
| Run client | `daemons client` |

### Useful URLs (Server Running)

| URL | Description |
|-----|-------------|
| http://127.0.0.1:8000/docs | Swagger API docs |
| http://127.0.0.1:8000/redoc | ReDoc API docs |
| ws://127.0.0.1:8000/ws/game/auth | WebSocket game endpoint |

---

## Troubleshooting

### "Module not found" errors

Make sure your virtual environment is activated:

```powershell
# Windows
.\.venv\Scripts\Activate

# macOS/Linux
source .venv/bin/activate
```

Then reinstall:

```bash
pip install daemons-engine
```

### Database errors

Reset the database:

```bash
rm game.db          # or del game.db on Windows
daemons db upgrade
```

### Port already in use

Use a different port:

```bash
daemons run --port 8080
```

### Client can't connect

1. Ensure the server is running
2. Check `config.py` for the correct host/port
3. Verify firewall isn't blocking localhost connections

---

## Next Steps

- **Browse example content:** [world_data examples](https://github.com/adamhuston/1126/tree/main/backend/world_data)
- **Read the architecture:** [ARCHITECTURE.md](https://github.com/adamhuston/1126/blob/main/documentation/ARCHITECTURE.md)
- **Understand the protocol:** [protocol.md](https://github.com/adamhuston/1126/blob/main/documentation/protocol.md)
- **See the roadmap:** [roadmap.md](https://github.com/adamhuston/1126/blob/main/documentation/roadmap.md)

---

## Engine Development

If you want to contribute to the Daemons engine itself:

### Clone the Repository

```bash
git clone https://github.com/adamhuston/1126.git daemons-engine
cd daemons-engine
```

### Create Virtual Environment

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

### Install Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# Development dependencies
pip install pytest pytest-asyncio pytest-cov pytest-timeout pytest-xdist
pip install pre-commit ruff black isort mypy safety

# Or use the setup script
python setup_dev.py
```

### Run the Backend

```bash
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

### Run Tests

```bash
cd backend

# All tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# By category
pytest -m unit          # Unit tests
pytest -m systems       # System tests
pytest -m integration   # Integration tests
pytest -m abilities     # Ability tests
pytest -m api           # API tests
```

### Code Quality

```bash
# Install pre-commit hooks
pre-commit install

# Run all linters
pre-commit run --all-files

# Individual tools
ruff check backend/ --fix
black backend/
isort backend/
mypy backend/daemons/
```

### Run the Reference Client

```bash
daemons client
```

See [CONTRIBUTING.md](https://github.com/adamhuston/1126/blob/main/CONTRIBUTING.md) for the full development workflow.

---

Happy building! 🎮
