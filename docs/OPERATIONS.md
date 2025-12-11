# Daemons Engine Operations Guide

This document covers server management, troubleshooting, and engine development.

---

## Default Admin Account

On first run, the server seeds a default admin account:

| Field    | Value   |
|----------|---------|
| Username | `admin` |
| Password | `admin` |

**⚠️ SECURITY WARNING**: Change the default password immediately in production!

Characters created under this account automatically have full admin permissions, including:
- All game master abilities (teleport, spawn, modify stats)
- User management (ban, unban, role assignment)
- Server commands (reload, maintenance mode)
- Full API access

---

## Server Options

```bash
# Different port
daemons run --port 8080

# Bind to all interfaces (for LAN access)
daemons run --host 0.0.0.0

# Development mode with auto-reload
daemons run --reload

# Production mode (requires JWT_SECRET_KEY)
daemons run --production
```

---

## Database Management

### Alembic Commands

```bash
# Apply all migrations
daemons db upgrade

# Downgrade one step
daemons db downgrade

# Show current revision
daemons db current

# View migration history
daemons db history
```

### Reset Database

```powershell
# Windows
Remove-Item dungeon.db
daemons db upgrade
```

```bash
# macOS/Linux
rm dungeon.db
daemons db upgrade
```

---

## Troubleshooting

### "Module not found" errors

Make sure your virtual environment is activated:

```powershell
# Windows
.\.venv\Scripts\Activate
```

```bash
# macOS/Linux
source .venv/bin/activate
```

Then reinstall:

```bash
pip install daemons-engine
```

### Database errors

Reset the database (see above).

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

## Content Hot Reload

**Note:** The `--reload` flag on uvicorn only hot-reloads Python code changes. YAML content changes require the `reload` command.

The reload system:
- **Updates** existing entities with changes from YAML files
- **Creates** new entities from YAML files that don't exist yet (adds to database + memory)
- Preserves player positions and entity states during reload

### In-Game Admin Commands

```bash
# Reload templates (definitions)
reload items       # Item templates
reload npcs        # NPC templates
reload rooms       # Room definitions
reload areas       # Area definitions

# Reload instances (placed in world)
reload instances   # Item instances (pre-placed items, flora)
reload spawns      # NPC spawns (fauna, placed NPCs)

# Reload everything
reload all         # All templates + all instances
```

### API Endpoints

```bash
# Reload all content
curl -X POST http://localhost:8000/api/admin/content/reload \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"content_type": "all"}'

# Reload specific content type
curl -X POST http://localhost:8000/api/admin/content/reload \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"content_type": "rooms"}'

# Reload schemas
curl -X POST http://localhost:8000/api/admin/schemas/reload \
  -H "Authorization: Bearer <admin_token>"

# Reload classes/abilities/behaviors
curl -X POST http://localhost:8000/api/admin/classes/reload \
  -H "Authorization: Bearer <admin_token>"
```

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
# Use the setup script (recommended)
python setup_dev.py
```

Or install manually:

```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov pytest-timeout pytest-xdist
pip install pre-commit ruff black isort mypy safety
```

### Run the Backend

```bash
cd backend
alembic upgrade head
daemons run
```

Alternative (without CLI):
```bash
cd backend
alembic upgrade head
uvicorn daemons.main:app --reload
```

### Run Tests

```bash
cd backend

# All tests
pytest

# With coverage
pytest --cov=daemons --cov-report=html

# By category
pytest -m unit          # Unit tests
pytest -m systems       # System tests
pytest -m integration   # Integration tests
pytest -m abilities     # Ability system tests
pytest -m api           # API endpoint tests
pytest -m social        # Group/Clan/Faction tests
pytest -m flora         # Flora system tests
pytest -m fauna         # Fauna system tests
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

---

## Environment Variables

### Security (Phase 16)

```bash
# Required for production mode
JWT_SECRET_KEY="your-256-bit-secret-key"
DAEMONS_ENV="production"

# Optional JWT customization
JWT_ISSUER="daemons-engine"
JWT_AUDIENCE="daemons-client"

# WebSocket security
WS_ALLOWED_ORIGINS="http://localhost:*,https://yourdomain.com"
WS_MAX_CONNECTIONS_PER_IP=10
WS_MAX_CONNECTIONS_PER_ACCOUNT=3
WS_MAX_MESSAGE_SIZE=65536

# Legacy auth deprecation phase (WARN, THROTTLE, or DISABLED)
WS_LEGACY_DEPRECATION_PHASE="WARN"
WS_LEGACY_AUTH_ENABLED=true
```

---

## Further Reading

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [protocol.md](protocol.md) - WebSocket protocol
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Database schema
- [roadmap.md](roadmap.md) - Development roadmap
