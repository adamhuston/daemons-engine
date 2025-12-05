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
            click.echo(f"⚠️ Error: Directory '{name}' already exists and is not empty.")
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
            click.echo("🗺️  Copied world_data/ (all starter content)")
        else:
            click.echo("🗺️  Skipped world_data/ (already exists)")

        # Count copied files
        yaml_count = len(list(dest_world_data.rglob("*.yaml")))
        click.echo(f"📁    ({yaml_count} YAML files)")
    else:
        # Fallback: create empty directory structure
        click.echo("⚠️  Warning: Bundled world_data not found, creating empty structure")
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
    click.echo("😇  Created behaviors/")

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
    click.echo("🥧  Created main.py")

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
DATABASE_URL = os.getenv("DAEMONS_DATABASE_URL", "sqlite+aiosqlite:///./dungeon.db")

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
    click.echo("⚙️  Created config.py")

    # Note: We don't create a local alembic folder by default.
    # The 'daemons db upgrade' command will use the package's built-in migrations.
    # If users need custom migrations, they can run 'daemons db init-migrations' (future feature)
    # or manually create an alembic folder.

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
    click.echo("💁  Created .gitignore")

    click.echo("")
    click.echo(
        click.style("✅ Project initialized successfully!", fg="green", bold=True)
    )
    click.echo("")
    click.echo("Next steps:")
    if name != ".":
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
@click.option("--production", is_flag=True, help="Run in production mode (requires JWT_SECRET_KEY)")
def run(host: str, port: int, reload: bool, workers: int, production: bool):
    """Start the Daemons game server.

    Run this command from your project directory (where main.py is located).

    For production deployments, use --production flag which enforces
    secure JWT secret key configuration.
    """
    import os
    import secrets

    import uvicorn

    # Handle production mode
    if production:
        os.environ["DAEMONS_ENV"] = "production"
        click.echo(click.style("🔒 Production mode enabled", fg="yellow", bold=True))

        # Check if JWT_SECRET_KEY is already set
        existing_key = os.environ.get("JWT_SECRET_KEY")
        if not existing_key or existing_key == "dev-secret-key-change-in-production":
            click.echo("")
            click.echo(click.style("⚠️  JWT_SECRET_KEY not set!", fg="red", bold=True))
            click.echo("")
            click.echo("🔑 A secure secret key is required for production.")
            click.echo("🔑 This key is used to sign authentication tokens.")
            click.echo("")

            # Generate a suggested key
            suggested_key = secrets.token_hex(32)

            if click.confirm("🔑 Would you like to generate a new secret key?", default=True):
                click.echo("")
                click.echo("🔑 Generated secret key:")
                click.echo(click.style(f"  {suggested_key}", fg="green"))
                click.echo("")
                click.echo("🔑 To use this key, set the environment variable before running:")
                click.echo("")
                click.echo(click.style("  PowerShell:", fg="cyan"))
                click.echo(f'    $env:JWT_SECRET_KEY = "{suggested_key}"')
                click.echo("")
                click.echo(click.style("  Bash/Linux:", fg="cyan"))
                click.echo(f'    export JWT_SECRET_KEY="{suggested_key}"')
                click.echo("")
                click.echo(click.style("  Or add to your .env file:", fg="cyan"))
                click.echo(f'    JWT_SECRET_KEY={suggested_key}')
                click.echo("")

                if click.confirm("🔑 Set this key for the current session and continue?", default=True):
                    os.environ["JWT_SECRET_KEY"] = suggested_key
                    click.echo(click.style("🔐 Secret key set for this session", fg="green"))
                    click.echo("")
                else:
                    click.echo("")
                    click.echo("⚠️ Server startup cancelled. Set JWT_SECRET_KEY and try again.")
                    sys.exit(1)
            else:
                click.echo("")
                click.echo("🔑 Generate a key manually with:")
                click.echo('  python -c "import secrets; print(secrets.token_hex(32))"')
                click.echo("")
                click.echo("🔑 Then set it as an environment variable before running.")
                sys.exit(1)
        else:
            click.echo(click.style("🔐 JWT_SECRET_KEY is configured", fg="green"))

        # Warn about reload in production
        if reload:
            click.echo(click.style("⚠️  Warning: --reload is not recommended in production", fg="yellow"))

    # Check if we're in a project directory with a custom main.py
    if Path("main.py").exists():
        # Ensure current directory is in Python path for imports
        cwd = os.getcwd()
        if cwd not in sys.path:
            sys.path.insert(0, cwd)

        click.echo(f"⏳ Starting game server from {cwd}...")
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,
            log_level="info",
        )
    else:
        # Check if there's a project directory nearby (user might be in wrong dir)
        possible_dirs = [d for d in Path(".").iterdir() if d.is_dir() and (d / "main.py").exists()]
        if possible_dirs:
            click.echo(click.style("📂 No main.py found in current directory.", fg="yellow"))
            click.echo("")
            click.echo("📂 Found project directory nearby. Try:")
            for d in possible_dirs[:3]:  # Show up to 3
                click.echo(f"  cd {d.name} && daemons run")
            click.echo("")
            # Still run the engine directly as fallback

        # Run the engine directly using the installed package
        click.echo("⏳ Starting Daemons server (standalone mode)...")

        from daemons.main import app

        if reload:
            click.echo("Note: Hot reload is only supported when running from a project directory with main.py")

        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=False,  # Reload requires import string which has path issues
            workers=workers,
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
        click.echo("🗃️ Running migrations from local alembic.ini...")
        alembic_cfg = Config(str(alembic_ini))
    else:
        # Use the engine's built-in migrations
        click.echo("🗃️ Running engine migrations...")
        package_dir = Path(__file__).parent
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", str(package_dir / "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", "sqlite+aiosqlite:///./dungeon.db")

    try:
        command.upgrade(alembic_cfg, revision)
        click.echo(click.style("✅ Database upgraded successfully!", fg="green"))
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
        alembic_cfg.set_main_option("sqlalchemy.url", "sqlite+aiosqlite:///./dungeon.db")

    try:
        command.downgrade(alembic_cfg, revision)
        click.echo(click.style("✅ Database downgraded successfully!", fg="green"))
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
        alembic_cfg.set_main_option("sqlalchemy.url", "sqlite+aiosqlite:///./dungeon.db")

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
        alembic_cfg.set_main_option("sqlalchemy.url", "sqlite+aiosqlite:///./dungeon.db")

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
        click.echo(click.style("⚠️ Error: Flet is not installed.", fg="red"))
        click.echo("Install it with: pip install daemons-engine[client]")
        click.echo("Or: pip install flet")
        sys.exit(1)

    # Try to import and run the client
    try:
        from daemons.client import client as client_module

        click.echo(f"⏳ Launching client connecting to {host}:{port}...")
        client_module.run(host=host, port=port)
    except ImportError:
        click.echo(click.style("⚠️ Error: Client module not found.", fg="red"))
        click.echo("The client may not be installed with this package.")
        sys.exit(1)


@main.command()
@click.option("--world-data", "-w", default=None, help="Path to world_data folder to open")
def wright(world_data: str | None):
    """Launch the Daemonswright Content Studio.

    A visual content editor for creating and editing game content.
    Works offline with local YAML files, optionally connects to a
    running server for hot-reload and enhanced validation.

    Examples:
        daemons wright
        daemons wright -w ./my-game/world_data
    """
    import subprocess

    # Check if daemonswright is installed/available
    wright_dir = Path(__file__).parent.parent.parent / "daemonswright"

    if not wright_dir.exists():
        click.echo(click.style("⚠️ Error: Daemonswright not found.", fg="red"))
        click.echo("")
        click.echo("Daemonswright is the visual content editor for Daemons.")
        click.echo("It should be installed alongside the daemons-engine package.")
        click.echo("")
        click.echo("If you're developing locally, ensure the daemonswright/ directory exists.")
        sys.exit(1)

    # Check if npm dependencies are installed
    node_modules = wright_dir / "node_modules"
    if not node_modules.exists():
        click.echo(click.style("⚠️ Daemonswright dependencies not installed.", fg="yellow"))
        click.echo("Installing dependencies (this may take a moment)...")
        click.echo("")

        try:
            subprocess.run(
                ["npm", "install"],
                cwd=str(wright_dir),
                check=True,
                shell=True,
            )
            click.echo(click.style("✓ Dependencies installed!", fg="green"))
            click.echo("")
        except subprocess.CalledProcessError:
            click.echo(click.style("⚠️ Error: Failed to install dependencies.", fg="red"))
            click.echo("Try running 'npm install' manually in the daemonswright directory.")
            sys.exit(1)

    # Launch the electron app
    click.echo("🚀 Launching Daemonswright...")

    args = ["npm", "run", "electron:dev"]
    env = None

    if world_data:
        # Pass the world_data path as an environment variable
        import os
        env = os.environ.copy()
        env["DAEMONSWRIGHT_WORLD_DATA"] = str(Path(world_data).resolve())

    try:
        subprocess.run(
            args,
            cwd=str(wright_dir),
            env=env,
            shell=True,
        )
    except KeyboardInterrupt:
        click.echo("")
        click.echo("Daemonswright closed.")
    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"⚠️ Error launching Daemonswright: {e}", fg="red"))
        sys.exit(1)


if __name__ == "__main__":
    main()
