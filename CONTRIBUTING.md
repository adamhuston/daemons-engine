Thank you for your interest in contributing! This document explains how to set up a development environment, run the app and sample client, and how to contribute safely to the project.

Table of Contents
- Purpose
- Dev quickstart
- Running the sample client
- Seeding and creating dev test players
- Database migrations (Alembic)
- Where to find important code
- Troubleshooting & contact

Purpose
-------
This file provides a quick onboarding guide and describes the expected steps for contributing code. It complements the `ARCHITECTURE.md`, `protocol.md`, and `alembic.md` documents.

Dev Quickstart
--------------
Run the server locally (PowerShell):

```powershell
# Install dependencies (requirements.txt is in the root)
py -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt

# Apply database migrations
cd backend
alembic upgrade head

# Start the server
uvicorn app.main:app --reload --log-level info
```

Notes:
- The app seeds a small world on first run (27 rooms and 2 test players). Check the app logs to see the seeded player IDs and sample room IDs.
- `alembic upgrade head` applies migrations. If you change models, follow the Alembic workflow documented in `alembic.md`.

Running the sample client
-------------------------
The repository contains a Flet-based test client at `client/client.py`. 

First, install Flet (if not already installed):

```powershell
pip install flet
```

Then run the client:

```powershell
cd client
py client.py
```

Use this to connect as a test player and exercise the protocol.

Seeding and creating dev players
--------------------------------
- The server automatically seeds players on first run (see `backend/app/main.py -> seed_world`). To list players:

```powershell
curl http://127.0.0.1:8000/players
```

- To manually add or change seeded data, either use the SQLAlchemy session or create a migration + seed script. When adding persistent changes, prefer migrations.

Database migrations (Alembic)
----------------------------
- Follow `alembic.md` for how to add migrations. The critical steps:
	1. Update your models in `app/models.py`.
	2. Create a migration: `cd backend` + `alembic revision --autogenerate -m "Description"`.
	3. Review/adjust the migration file if necessary (especially for renames/datamigration).
	4. Apply locally: `alembic upgrade head`.
	5. Add the generated migration to your PR.


Where to find important code
---------------------------
- `backend/app/main.py` — app startup, seeding, HTTP endpoints, WebSocket entry.
- `backend/app/db.py` — SQLAlchemy DB engine and session.
- `backend/app/models.py` — DB models (Room, Player, etc.).
- `backend/app/engine/loader.py` — loading DB data into in-memory `World`.
- `backend/app/engine/world.py` — in-memory world model (WorldPlayer, WorldRoom, World).
- `backend/app/engine/engine.py` — `WorldEngine` logic (game loop, queues, command handlers).
- `client/client.py` — sample Flet client showing how to connect and parse events.

Troubleshooting & contact
-------------------------
- If you see issues during startup, check the logs that Uvicorn prints for seeded IDs and engine initialization details.
- Problems with migrations are often due to missing autogenerate targets—see `alembic.md` for config details.
- For questions or guidance, open an issue or comment on PRs. For urgent issues, tag maintainers in the PR.

