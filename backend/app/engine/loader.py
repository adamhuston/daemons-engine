# backend/app/engine/loader.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Room, Player
from .world import World, WorldRoom, WorldPlayer, WorldArea, RoomId, PlayerId, AreaId


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

    # ----- Create sample areas (hardcoded for now, will be DB-driven later) -----
    areas: dict[AreaId, WorldArea] = {}
    
    # Example: Ethereal Nexus area (normal time)
    ethereal_nexus = WorldArea(
        id="area_ethereal_nexus",
        name="The Ethereal Nexus",
        biome="ethereal",
        time_scale=4,  # 4x time
        time_phases={
            "dawn": "Prismatic light filters through the mist as ethereal dawn breaks across the nexus.",
            "morning": "The ethereal mists glow with soft, radiant light.",
            "afternoon": "Shimmering energy pulses through the air, bathing everything in otherworldly luminescence.",
            "dusk": "The mists darken to deep purples and blues as the nexus transitions to twilight.",
            "evening": "Ghostly stars begin to emerge in the ethereal void above.",
            "night": "The nexus glows with bioluminescent energy, casting an eerie but beautiful light."
        },
        climate="ethereal",
        ambient_lighting="magical",
        weather_profile="clear",
        description="A mystical convergence point where realities blur and time flows strangely.",
        ambient_sound="Soft whispers and distant chimes echo through the mist."
    )
    areas[ethereal_nexus.id] = ethereal_nexus
    
    # Example: Temporal Rift area (accelerated time for testing)
    temporal_rift = WorldArea(
        id="area_temporal_rift",
        name="The Temporal Rift",
        biome="ethereal",
        time_scale=2.0,  # Time passes twice as fast!
        time_phases={
            "dawn": "Time fractures as dawn breaks, hours flowing like minutes through the rift.",
            "morning": "The morning sun races across the sky at an unnatural pace.",
            "afternoon": "Shadows shift and dance as time accelerates through the rift.",
            "dusk": "Sunset arrives in a blur of color, time rushing forward.",
            "evening": "Stars streak across the sky as evening passes in moments.",
            "night": "The night cycles rapidly, moonlight flickering like a strobe."
        },
        climate="ethereal",
        ambient_lighting="distorted",
        weather_profile="temporal_storm",
        description="A tear in the fabric of time where hours pass like minutes.",
        ambient_sound="The ticking of a thousand unsynchronized clocks fills the air."
    )
    areas[temporal_rift.id] = temporal_rift
    
    # Assign rooms to areas
    for room in rooms.values():
        if room.room_type == "ethereal":
            room.area_id = ethereal_nexus.id
            ethereal_nexus.room_ids.add(room.id)
        elif room.room_type == "forsaken":
            # Assign forsaken rooms to temporal rift for testing
            room.area_id = temporal_rift.id
            temporal_rift.room_ids.add(room.id)
    
    # Set entry points
    ethereal_rooms = [r for r in rooms.values() if r.area_id == ethereal_nexus.id]
    if ethereal_rooms:
        ethereal_nexus.entry_points.add(ethereal_rooms[0].id)
    
    rift_rooms = [r for r in rooms.values() if r.area_id == temporal_rift.id]
    if rift_rooms:
        temporal_rift.entry_points.add(rift_rooms[0].id)

    return World(rooms=rooms, players=players, areas=areas)
