import asyncio
from sqlalchemy import select
from app.db import engine, AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Player, Room
from app.engine.loader import load_world

async def check():
    async with AsyncSessionLocal() as s:
        # Get all players
        players = (await s.execute(select(Player))).scalars().all()
        print(f"Found {len(players)} players:")
        for p in players:
            print(f"  - {p.name}: room_id = '{p.current_room_id}'")
        
        # Get all rooms
        rooms = (await s.execute(select(Room))).scalars().all()
        print(f"\nFound {len(rooms)} rooms in DB")
        
        # Check if player rooms exist
        print("\nRoom match check:")
        for p in players:
            room = (await s.execute(select(Room).where(Room.id == p.current_room_id))).scalars().first()
            print(f"  - {p.name}: room '{p.current_room_id}' exists = {room is not None}")
        
        # Test the loader
        print("\n--- Testing load_world() ---")
        world = await load_world(s)
        print(f"World.rooms loaded: {len(world.rooms)}")
        print(f"World.players loaded: {len(world.players)}")
        
        # Check specific room
        room = world.rooms.get('room_1_1_1')
        print(f"room_1_1_1 in world.rooms: {room is not None}")
        if room:
            print(f"  Room name: {room.name}")
            print(f"  Room entities: {room.entities}")

asyncio.run(check())
