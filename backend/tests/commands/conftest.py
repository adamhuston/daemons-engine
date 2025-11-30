"""Command test specific fixtures."""

import pytest

from app.engine.systems.context import GameContext


@pytest.fixture
def command_context(world_with_rooms, player_factory):
    """Create a GameContext with world and players for command testing."""
    world = world_with_rooms

    # Add some test players
    for i in range(3):
        player = player_factory(
            player_id=f"player_{i}", name=f"Player{i}", room_id="room_center"
        )
        world.players[player.id] = player

    # Create minimal context (no database needed for most command tests)
    context = GameContext(db_session=None, world=world)

    return context
