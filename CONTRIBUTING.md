Thank you for your interest in contributing! This document explains how to set up a development environment, run the app and sample client, and how to contribute safely to the project.

Table of Contents
- Purpose
- Contribution workflow
- Dev quickstart
- Running the sample client
- Seeding and creating dev test players
- Database migrations (Alembic)
- Where to find important code
- Code style & guidelines
- Troubleshooting & contact

Purpose
-------
This file provides a quick onboarding guide and describes the expected steps for contributing code. It complements the `ARCHITECTURE.md`, `protocol.md`, and `alembic.md` documents.

Contribution Workflow
---------------------
We welcome contributions! Please follow these steps:

### 1. Fork and clone
1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/daemons-engine.git
   cd daemons-engine
   ```
3. Add the upstream remote:
   ```bash
   git remote add upstream https://github.com/adamhuston/daemons-engine.git
   ```

### 2. Create a feature branch
Always create a new branch for your work. Never commit directly to `main`.

```bash
git checkout main
git pull upstream main
git checkout -b feature/your-feature-name
```

Use descriptive branch names:
- `feature/add-inventory-system` — for new features
- `fix/combat-damage-calculation` — for bug fixes
- `docs/update-api-reference` — for documentation
- `refactor/engine-cleanup` — for refactoring

### 3. Make your changes
- Write clear, focused commits with descriptive messages.
- Follow the code style guidelines below.
- Add or update tests for your changes.
- Run the test suite to ensure nothing is broken:
  ```bash
  cd backend
  pytest
  ```

### 4. Keep your branch updated
Before submitting, sync with upstream:
```bash
git fetch upstream
git rebase upstream/main
```

Resolve any conflicts if they arise.

### 5. Submit a pull request
1. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
2. Open a pull request on GitHub against `adamhuston/daemons-engine:main`.
3. Fill out the PR template (if provided) with:
   - A clear description of what the PR does
   - Any related issue numbers (e.g., "Fixes #42")
   - Screenshots or examples if applicable

### 6. Code review process
- All PRs require at least one maintainer review before merging.
- Address review feedback by pushing additional commits to your branch.
- Once approved, a maintainer will merge your PR.
- Please be patient—reviews may take a few days.

### What makes a good PR?
- **Small and focused**: One feature or fix per PR is easier to review.
- **Well-tested**: Include tests that cover your changes.
- **Documented**: Update docs if you change behavior or add features.
- **Clean history**: Squash WIP commits before requesting review.

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
uvicorn daemons.main:app --reload --log-level info
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
- `backend/daemons/main.py` — app startup, seeding, HTTP endpoints, WebSocket entry.
- `backend/daemons/db.py` — SQLAlchemy DB engine and session.
- `backend/daemons/models.py` — DB models (Room, Player, UserAccount, etc.).
- `backend/daemons/engine/loader.py` — loading DB data into in-memory `World`.
- `backend/daemons/engine/world.py` — in-memory world model (WorldPlayer, WorldRoom, WorldEntity, World).
- `backend/daemons/engine/engine.py` — `WorldEngine` logic (game loop, queues, command handlers).
- `backend/daemons/engine/systems/` — modular game systems:
  - `combat.py` — real-time combat with auto-attack
  - `effects.py` — buffs, debuffs, DoT/HoT
  - `classes.py` — character classes and abilities
  - `weather.py` — dynamic weather system (Phase 17.2)
  - `temperature.py` — temperature calculations (Phase 17.1)
  - `biome.py` — biome/season system (Phase 17.3)
  - `flora.py` — plants and harvesting (Phase 17.4)
  - `fauna.py` — fauna behaviors and spawning (Phase 17.5)
  - `spawn_conditions.py` — conditional spawning (Phase 17.6)
  - `population.py` — ecosystem management (Phase 17.6)
- `backend/daemons/routes/admin.py` — admin REST API endpoints.
- `client/client.py` — sample Flet client showing how to connect and parse events.

Code Style & Guidelines
-----------------------
- **Python**: Follow PEP 8. Use type hints where practical.
- **Formatting**: We recommend using `black` for Python formatting.
- **Naming**: Use descriptive names; prefer clarity over brevity.
- **Comments**: Explain *why*, not *what*. Code should be self-documenting.
- **Tests**: Place tests in `backend/tests/`. Mirror the source structure.

Troubleshooting & contact
-------------------------
- If you see issues during startup, check the logs that Uvicorn prints for seeded IDs and engine initialization details.
- Problems with migrations are often due to missing autogenerate targets—see `alembic.md` for config details.
- For questions or guidance, open an issue or comment on PRs. For urgent issues, tag maintainers in the PR.
