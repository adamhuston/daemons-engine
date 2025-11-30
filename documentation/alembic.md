# Database Migrations with Alembic

This document describes how to manage database schema changes using Alembic for the dungeon crawler project.

## Why Alembic?

Without migrations, schema changes require deleting the database and losing all player data. Alembic allows you to evolve the database schema while preserving existing data.

**Without Alembic:**
```bash
# Change models.py
# Delete dungeon.db
# Restart server
# ❌ All player data lost
```

**With Alembic:**
```bash
# Change models.py
alembic revision --autogenerate -m "Add player stats"
alembic upgrade head
# ✅ Schema updated, data preserved
```

## Initial Setup

### 1. Install Alembic

```bash
pip install alembic
```

Add to `requirements.txt`:
```
alembic==1.13.1
```

### 2. Initialize Alembic

```bash
cd backend
alembic init alembic
```

This creates:
```
backend/
  alembic/           # Migration scripts directory
    versions/        # Individual migration files
    env.py          # Alembic environment config
  alembic.ini       # Alembic configuration
```

### 3. Configure Alembic

Edit `backend/alembic.ini`:

```ini
# Change this line:
sqlalchemy.url = sqlite:///./dungeon.db
```

Edit `backend/alembic/env.py`:

```python
# Add at the top:
import sys
from pathlib import Path

# Add backend/app to path so we can import models
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Base

# Update this line (around line 21):
target_metadata = Base.metadata
```

### 4. Create Initial Migration

Capture the current schema as a baseline:

```bash
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

## Development Workflow

### Making Schema Changes

1. **Modify models in `app/models.py`**

```python
# Example: Add level to Player
class Player(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    current_room_id: Mapped[str] = mapped_column(String, ForeignKey("rooms.id"))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    level: Mapped[int] = mapped_column(Integer, default=1)  # NEW!
```

2. **Generate migration**

```bash
cd backend
alembic revision --autogenerate -m "Add player level"
```

This creates a file like `alembic/versions/abc123_add_player_level.py`

3. **Review the migration**

Open the generated file and verify it looks correct:

```python
def upgrade() -> None:
    op.add_column('players', sa.Column('level', sa.Integer(), nullable=True))
    # Alembic auto-detects the change!

def downgrade() -> None:
    op.drop_column('players', 'level')
```

4. **Apply the migration**

```bash
alembic upgrade head
```

5. **Test your changes**

```bash
uvicorn app.main:app --reload
```

The app now uses the new schema without losing data!

## Production Deployment

### Standard Deployment Process

```bash
# 1. Stop the running application (optional but safer)
# Ctrl+C in uvicorn terminal

# 2. Pull latest code
git pull

# 3. Apply any pending migrations
cd backend
alembic upgrade head

# 4. Restart the application
uvicorn app.main:app --reload --log-level info
```

### Zero-Downtime Deployment (Advanced)

For production with users online:

1. Ensure migrations are backward-compatible
2. Apply migrations while app is running
3. Deploy new code
4. Old code works with new schema until restart

## Common Commands

### Check Migration Status

```bash
# Show current migration version
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic heads
```

### Apply Migrations

```bash
# Upgrade to latest
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Upgrade to specific revision
alembic upgrade abc123
```

### Rollback Migrations

```bash
# Downgrade one version
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade abc123

# Downgrade all (⚠️ dangerous!)
alembic downgrade base
```

### Create Migrations

```bash
# Auto-generate from model changes (recommended)
alembic revision --autogenerate -m "Description"

# Create empty migration (for manual edits)
alembic revision -m "Custom migration"
```

## Common Patterns

### Adding a New Column with Default

```python
# models.py
level: Mapped[int] = mapped_column(Integer, default=1)

# Auto-generated migration handles this!
# Existing rows get level=1
```

### Adding a New Table

```python
# models.py - add new model class
class Item(Base):
    __tablename__ = "items"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)

# Generate migration - it creates the table
alembic revision --autogenerate -m "Add items table"
```

### Renaming a Column

Alembic can't auto-detect renames. Create manual migration:

```python
def upgrade() -> None:
    op.alter_column('players', 'old_name', new_column_name='new_name')

def downgrade() -> None:
    op.alter_column('players', 'new_name', new_column_name='old_name')
```

### Data Migration

For complex changes that need to transform data:

```python
from alembic import op
from sqlalchemy import orm
from app.models import Player

def upgrade() -> None:
    # Add column
    op.add_column('players', sa.Column('health', sa.Integer(), nullable=True))

    # Migrate data
    bind = op.get_bind()
    session = orm.Session(bind=bind)

    # Set health=100 for all existing players
    session.execute(
        Player.__table__.update().values(health=100)
    )
    session.commit()

def downgrade() -> None:
    op.drop_column('players', 'health')
```

## Troubleshooting

### "Can't locate revision identified by 'abc123'"

The migration file is missing. Check:
- Is the file in `alembic/versions/`?
- Did you commit it to git?

### "Target database is not up to date"

Your database is behind. Run:
```bash
alembic upgrade head
```

### "Multiple heads detected"

You have conflicting migrations (rare). Resolve by:
```bash
alembic merge heads -m "Merge migrations"
alembic upgrade head
```

### Migration fails mid-way

SQLite doesn't support transactions for DDL. If a migration fails:
1. Fix the migration file
2. Manually restore from backup, or
3. Manually fix the database state to match what the migration expected

## Best Practices

1. **Always review auto-generated migrations** - Alembic is smart but not perfect
2. **Test migrations locally first** - Don't discover issues in production
3. **Commit migrations with code** - They should be versioned together
4. **Never edit applied migrations** - Create a new one instead
5. **Backup before production migrations** - Especially for complex changes
6. **Use descriptive migration messages** - "Add player stats" not "update models"
7. **Keep migrations small** - One logical change per migration

## SQLite Limitations

SQLite has limited ALTER TABLE support:
- ❌ Can't drop columns (workaround: create new table, copy data, rename)
- ❌ Can't rename tables easily
- ❌ Can't modify column types directly
- ✅ Can add columns
- ✅ Can create/drop tables
- ✅ Can create/drop indexes

For complex schema changes, you may need to write custom migrations that:
1. Create new table with correct schema
2. Copy data from old table
3. Drop old table
4. Rename new table

## Further Reading

- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Auto-generating Migrations](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [SQLite ALTER TABLE Limitations](https://www.sqlite.org/lang_altertable.html)
