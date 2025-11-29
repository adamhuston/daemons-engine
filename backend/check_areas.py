"""Quick script to check areas in the database."""
import asyncio
from sqlalchemy import select
from app.models import Area
from app.db import AsyncSessionLocal


async def check_areas():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Area))
        areas = result.scalars().all()
        
        print(f"\nFound {len(areas)} areas:\n")
        for area in areas:
            print(f"ID: {str(area.id):3s} | Name: {area.name:30s} | Biome: {area.biome or 'None':15s} | Ambient: {area.ambient_lighting or 'None'}")


if __name__ == "__main__":
    asyncio.run(check_areas())
