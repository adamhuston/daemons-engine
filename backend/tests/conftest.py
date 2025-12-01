"""
Global pytest configuration and shared fixtures.

Provides common test infrastructure for all test suites including:
- Database session management
- Mock world setup
- Player/room factories
- AsyncIO event loop configuration
- Test data cleanup
"""

import asyncio
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import daemons.models  # noqa: F401, E402
from daemons.engine.world import World, WorldPlayer, WorldRoom  # noqa: E402
from daemons.models import Base  # noqa: E402

# ============================================================================
# Session Configuration
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def test_engine(event_loop):
    """Create in-memory SQLite database engine for testing."""
    # Use check_same_thread=False to allow sharing across async contexts
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Use StaticPool to share single connection
        echo=False,
    )

    # Create tables synchronously in the session-scoped engine
    async def create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    event_loop.run_until_complete(create_tables())

    yield engine

    # Cleanup
    event_loop.run_until_complete(engine.dispose())


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create fresh database session for each test."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


# ============================================================================
# World Fixtures
# ============================================================================


@pytest.fixture
def mock_world() -> World:
    """Create empty World instance."""
    return World(rooms={}, players={})


@pytest.fixture
def world_with_rooms(mock_world: World) -> World:
    """Create World with basic room structure (5 rooms in cross pattern)."""
    # Center room
    center = WorldRoom(
        id="room_center",
        name="Center Room",
        description="The center of the test world",
        room_type="test",
    )
    mock_world.rooms["room_center"] = center

    # Create 4 cardinal direction rooms
    directions = ["north", "south", "east", "west"]
    opposites = {"north": "south", "south": "north", "east": "west", "west": "east"}

    for direction in directions:
        room = WorldRoom(
            id=f"room_{direction}",
            name=f"{direction.capitalize()} Room",
            description=f"A room to the {direction}",
            room_type="test",
        )
        mock_world.rooms[room.id] = room

        # Link to center
        center.exits[direction] = room.id
        room.exits[opposites[direction]] = "room_center"

    return mock_world


@pytest.fixture
def player_factory():
    """Factory for creating test WorldPlayer instances."""

    def _create_player(
        player_id: str = "test_player",
        name: str = "TestPlayer",
        room_id: str = "room_center",
        level: int = 1,
        character_class: str = "adventurer",
    ) -> WorldPlayer:
        return WorldPlayer(
            id=player_id,
            name=name,
            room_id=room_id,
            character_class=character_class,
            level=level,
            hp=100,
            max_hp=100,
            mp=50,
            max_mp=50,
            strength=10,
            dexterity=10,
            intelligence=10,
            vitality=10,
            constitution=10,
            wisdom=10,
            charisma=10,
        )

    return _create_player


# ============================================================================
# Temporary File System Fixtures
# ============================================================================


@pytest.fixture
def temp_world_data(tmp_path: Path) -> Path:
    """Create temporary world_data directory structure."""
    world_data = tmp_path / "world_data"

    # Create standard content directories
    content_types = [
        "rooms",
        "items",
        "npcs",
        "classes",
        "abilities",
        "quests",
        "quest_chains",
        "dialogues",
        "factions",
        "areas",
        "triggers",
    ]

    for content_type in content_types:
        content_dir = world_data / content_type
        content_dir.mkdir(parents=True)

        # Create minimal schema file
        schema_file = content_dir / "_schema.yaml"
        schema_file.write_text(
            f"""# Schema for {content_type}
required_fields:
  - {content_type[:-1]}_id
  - name
  - description
"""
        )

    return world_data


# ============================================================================
# Utility Fixtures
# ============================================================================


@pytest.fixture
def capture_events():
    """Capture events emitted during test execution."""
    events = []

    def _capture(event_type: str, **kwargs):
        events.append({"type": event_type, **kwargs})

    return events, _capture


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    # Clear any singleton state here
    yield
    # Cleanup after test
