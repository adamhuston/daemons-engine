# backend/app/engine/loader.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Room, Player, Area
from .world import World, WorldRoom, WorldPlayer, WorldArea, WorldTime, RoomId, PlayerId, AreaId, DEFAULT_TIME_PHASES


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
            room_type=r.room_type,
            exits=exits,
            on_enter_effect=r.on_enter_effect,
            on_exit_effect=r.on_exit_effect,
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
            on_move_effect=p.data.get("on_move_effect"),
            character_class=p.character_class,
            level=p.level,
            experience=p.experience,
            strength=p.strength,
            dexterity=p.dexterity,
            intelligence=p.intelligence,
            vitality=p.vitality,
            max_health=p.max_health,
            current_health=p.current_health,
            armor_class=p.armor_class,
            max_energy=p.max_energy,
            current_energy=p.current_energy,
        )

    # ----- Place players into rooms -----
    for player in players.values():
        room = rooms.get(player.room_id)
        if room:
            room.players.add(player.id)

    # ----- Load areas from database -----
    area_result = await session.execute(select(Area))
    area_models = area_result.scalars().all()

    areas: dict[AreaId, WorldArea] = {}

    for a in area_models:
        # Create WorldTime for this area
        area_time = WorldTime(
            day=a.starting_day,
            hour=a.starting_hour,
            minute=a.starting_minute,
        )
        
        # Get time phases, fall back to defaults if not specified
        time_phases = a.time_phases if a.time_phases else DEFAULT_TIME_PHASES
        
        # Get entry points
        entry_points = set(a.entry_points) if a.entry_points else set()
        
        areas[a.id] = WorldArea(
            id=a.id,
            name=a.name,
            description=a.description,
            area_time=area_time,
            time_scale=a.time_scale,
            biome=a.biome,
            climate=a.climate,
            ambient_lighting=a.ambient_lighting,
            weather_profile=a.weather_profile,
            danger_level=a.danger_level,
            magic_intensity=a.magic_intensity,
            ambient_sound=a.ambient_sound,
            time_phases=time_phases,
            entry_points=entry_points,
        )

    # ----- Link rooms to areas -----
    for room in rooms.values():
        if room.area_id and room.area_id in areas:
            area = areas[room.area_id]
            area.room_ids.add(room.id)

    return World(rooms=rooms, players=players, areas=areas)
