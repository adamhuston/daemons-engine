"""
Daemons CLI - Command line interface for the Daemons game engine.

Usage:
    daemons init          Initialize a new game project
    daemons run           Start the game server
    daemons db upgrade    Run database migrations
    daemons client        Launch the reference client
"""

import sys
from pathlib import Path

import click

from daemons import __version__


@click.group()
@click.version_option(version=__version__, prog_name="daemons")
def main():
    """Daemons - A modern MUD engine."""
    pass


@main.command()
@click.argument("name", default="my-game")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing files")
def init(name: str, force: bool):
    """Initialize a new game project with starter content.

    NAME is the project directory name (default: my-game).
    Use "." to initialize in the current directory.

    Examples:
        daemons init my-rpg
        daemons init .
        daemons init --force existing-project
    """
    import shutil

    project_dir = Path.cwd() / name if name != "." else Path.cwd()

    if project_dir.exists() and any(project_dir.iterdir()) and not force:
        if name != ".":
            click.echo(f"Error: Directory '{name}' already exists and is not empty.")
            click.echo("Use --force to overwrite, or choose a different name.")
            sys.exit(1)

    click.echo(f"Initializing Daemons project in {project_dir}...")

    # Find the bundled world_data directory from the installed package
    package_world_data = Path(__file__).parent / "world_data"

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Copy all world_data content from the package
    dest_world_data = project_dir / "world_data"
    if package_world_data.exists():
        if dest_world_data.exists() and force:
            shutil.rmtree(dest_world_data)
        if not dest_world_data.exists():
            shutil.copytree(package_world_data, dest_world_data)
            click.echo("  Copied world_data/ (all starter content)")
        else:
            click.echo("  Skipped world_data/ (already exists)")

        # Count copied files
        yaml_count = len(list(dest_world_data.rglob("*.yaml")))
        click.echo(f"    ({yaml_count} YAML files)")
    else:
        # Fallback: create empty directory structure
        click.echo("  Warning: Bundled world_data not found, creating empty structure")
        directories = [
            "world_data/areas",
            "world_data/rooms",
            "world_data/items/weapons",
            "world_data/items/armor",
            "world_data/items/consumables",
            "world_data/npcs",
            "world_data/npc_spawns",
            "world_data/quests",
            "world_data/quest_chains",
            "world_data/dialogues",
            "world_data/triggers",
            "world_data/classes",
            "world_data/abilities",
            "world_data/factions",
        ]
        for dir_path in directories:
            (project_dir / dir_path).mkdir(parents=True, exist_ok=True)

    # Create behaviors directory
    (project_dir / "behaviors").mkdir(parents=True, exist_ok=True)
    click.echo("  Created behaviors/")

    # Create main.py
    main_py = '''"""
Game server entry point.

Run with: uvicorn main:app --reload
Or use: daemons run
"""

from daemons.main import app

# Re-export the FastAPI app for uvicorn
__all__ = ["app"]
'''
    (project_dir / "main.py").write_text(main_py)
    click.echo("  Created main.py")

    # Create config.py
    config_py = '''"""
Game configuration.

Customize these settings for your game.
"""

import os

# Server settings
HOST = os.getenv("DAEMONS_HOST", "127.0.0.1")
PORT = int(os.getenv("DAEMONS_PORT", "8000"))

# Database settings
DATABASE_URL = os.getenv("DAEMONS_DATABASE_URL", "sqlite+aiosqlite:///./game.db")

# JWT settings (generate your own secret for production!)
JWT_SECRET = os.getenv("DAEMONS_JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Game settings
GAME_NAME = "My Daemons Game"
STARTING_ROOM = "room_1_1_1"
MAX_PLAYERS = 100

# Content directories
WORLD_DATA_DIR = "world_data"
BEHAVIORS_DIR = "behaviors"
'''
    (project_dir / "config.py").write_text(config_py)
    click.echo("  Created config.py")

    # Create alembic.ini
    alembic_ini = """# Alembic configuration for Daemons game

[alembic]
script_location = %(here)s/alembic
prepend_sys_path = .
sqlalchemy.url = sqlite+aiosqlite:///./game.db

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""
    (project_dir / "alembic.ini").write_text(alembic_ini)
    click.echo("  Created alembic.ini")

    # Create alembic env.py
    alembic_dir = project_dir / "alembic"
    alembic_dir.mkdir(exist_ok=True)
    (alembic_dir / "versions").mkdir(exist_ok=True)

    alembic_env = '''"""Alembic migration environment."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from daemons.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = configuration.get(
        "sqlalchemy.url", ""
    ).replace("sqlite://", "sqlite+aiosqlite://")

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''
    (alembic_dir / "env.py").write_text(alembic_env)
    click.echo("  Created alembic/env.py")

    # Create script.py.mako
    script_mako = '''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''
    (alembic_dir / "script.py.mako").write_text(script_mako)
    click.echo("  Created alembic/script.py.mako")

    # Create .gitignore
    gitignore = """# Daemons game project
*.db
*.pyc
__pycache__/
.venv/
venv/
.env
*.log
htmlcov/
.coverage
.pytest_cache/
"""
    (project_dir / ".gitignore").write_text(gitignore)
    click.echo("  Created .gitignore")

    click.echo("")
    click.echo(
        click.style("✓ Project initialized successfully!", fg="green", bold=True)
    )
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  cd {name}")
    click.echo("  daemons db upgrade    # Initialize the database")
    click.echo("  daemons run           # Start the server")
    click.echo("")
    click.echo("Documentation: https://github.com/adamhuston/1126")


@main.command()
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to")
@click.option("--port", "-p", default=8000, type=int, help="Port to bind to")
@click.option("--reload", "-r", is_flag=True, help="Enable auto-reload for development")
@click.option("--workers", "-w", default=1, type=int, help="Number of worker processes")
def run(host: str, port: int, reload: bool, workers: int):
    """Start the Daemons game server."""
    import uvicorn

    # Check if we're in a project directory
    if not Path("main.py").exists():
        # Try to run the engine directly
        click.echo("Starting Daemons server...")
        uvicorn.run(
            "daemons.main:app",
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,
            log_level="info",
        )
    else:
        click.echo("Starting game server...")
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,
            log_level="info",
        )


@main.group()
def db():
    """Database management commands."""
    pass


@db.command()
@click.option("--revision", "-r", default="head", help="Revision to upgrade to")
def upgrade(revision: str):
    """Run database migrations to upgrade the schema."""
    from alembic import command
    from alembic.config import Config

    # Look for alembic.ini in current directory or use package default
    alembic_ini = Path("alembic.ini")

    if alembic_ini.exists():
        click.echo("Running migrations from local alembic.ini...")
        alembic_cfg = Config(str(alembic_ini))
    else:
        # Use the engine's built-in migrations
        click.echo("Running engine migrations...")
        package_dir = Path(__file__).parent
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", str(package_dir / "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", "sqlite+aiosqlite:///./game.db")

    try:
        command.upgrade(alembic_cfg, revision)
        click.echo(click.style("✓ Database upgraded successfully!", fg="green"))
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"))
        sys.exit(1)


@db.command()
@click.option("--revision", "-r", default="-1", help="Revision to downgrade to")
def downgrade(revision: str):
    """Downgrade the database schema."""
    from alembic import command
    from alembic.config import Config

    alembic_ini = Path("alembic.ini")

    if alembic_ini.exists():
        alembic_cfg = Config(str(alembic_ini))
    else:
        package_dir = Path(__file__).parent
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", str(package_dir / "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", "sqlite+aiosqlite:///./game.db")

    try:
        command.downgrade(alembic_cfg, revision)
        click.echo(click.style("✓ Database downgraded successfully!", fg="green"))
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"))
        sys.exit(1)


@db.command()
def current():
    """Show current database revision."""
    from alembic import command
    from alembic.config import Config

    alembic_ini = Path("alembic.ini")

    if alembic_ini.exists():
        alembic_cfg = Config(str(alembic_ini))
    else:
        package_dir = Path(__file__).parent
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", str(package_dir / "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", "sqlite+aiosqlite:///./game.db")

    command.current(alembic_cfg)


@db.command()
def history():
    """Show migration history."""
    from alembic import command
    from alembic.config import Config

    alembic_ini = Path("alembic.ini")

    if alembic_ini.exists():
        alembic_cfg = Config(str(alembic_ini))
    else:
        package_dir = Path(__file__).parent
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", str(package_dir / "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", "sqlite+aiosqlite:///./game.db")

    command.history(alembic_cfg)


@main.command()
@click.option("--host", "-h", default="127.0.0.1", help="Server host to connect to")
@click.option("--port", "-p", default=8000, type=int, help="Server port to connect to")
def client(host: str, port: int):
    """Launch the reference Flet client for testing."""
    try:
        import importlib.util

        if importlib.util.find_spec("flet") is None:
            raise ImportError("flet not found")
    except ImportError:
        click.echo(click.style("Error: Flet is not installed.", fg="red"))
        click.echo("Install it with: pip install daemons-engine[client]")
        click.echo("Or: pip install flet")
        sys.exit(1)

    # Try to import and run the client
    try:
        from daemons.client import client as client_module

        click.echo(f"Launching client connecting to {host}:{port}...")
        client_module.run(host=host, port=port)
    except ImportError:
        click.echo(click.style("Error: Client module not found.", fg="red"))
        click.echo("The client may not be installed with this package.")
        sys.exit(1)


if __name__ == "__main__":
    main()
