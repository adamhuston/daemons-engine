# backend/app/engine/loader.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Room, Player
from .world import World, WorldRoom, WorldPlayer, RoomId, PlayerId


async def load_world(session: AsyncSession) -> World:
    """
    Build the in-memory World from the database.

    Called once at startup (in main.py), but can be reused for reloads/tests.
    """
    # ----- Load rooms -----
    room_result = await session.execute(select(Room))
    room_models = room_result.scalars().all()

    rooms: dict[RoomId, WorldRoom] = {}

    for r in room_models:
        exits: dict[str, str] = {}
        for d in ("north", "south", "east", "west", "up", "down"):
            dest_id = getattr(r, f"{d}_id")
            if dest_id:
                exits[d] = dest_id

        rooms[r.id] = WorldRoom(
            id=r.id,
            name=r.name,
            description=r.description,
            exits=exits,
        )

    # ----- Load players -----
    player_result = await session.execute(select(Player))
    player_models = player_result.scalars().all()

    players: dict[PlayerId, WorldPlayer] = {}

    for p in player_models:
        players[p.id] = WorldPlayer(
            id=p.id,
            name=p.name,
            room_id=p.current_room_id,
        )

    # ----- Place players into rooms -----
    for player in players.values():
        room = rooms.get(player.room_id)
        if room:
            room.players.add(player.id)

    return World(rooms=rooms, players=players)
