"""Script to update temporal rift lighting and load new areas."""
import asyncio
from sqlalchemy import select
from app.models import Area, Room
from app.db import AsyncSessionLocal


async def update_lighting():
    async with AsyncSessionLocal() as session:
        # Update temporal rift to use 'normal' instead of 'distorted'
        result = await session.execute(
            select(Area).where(Area.id == "area_temporal_rift")
        )
        temporal_rift = result.scalar_one_or_none()
        
        if temporal_rift:
            print(f"Updating Temporal Rift: {temporal_rift.ambient_lighting} -> normal")
            temporal_rift.ambient_lighting = "normal"
        
        # Check if our new areas exist
        result = await session.execute(
            select(Area).where(Area.id.in_(["area_dark_caves", "area_sunlit_meadow"]))
        )
        new_areas = result.scalars().all()
        
        if not new_areas:
            print("\nNew areas not found in database. They exist only as YAML files.")
            print("To load them, you would need to:")
            print("1. Create SQL migration/seed scripts")
            print("2. Or implement YAML area loading in the loader")
        else:
            print(f"\nFound {len(new_areas)} new areas already loaded")
        
        await session.commit()
        
        # Show all areas
        result = await session.execute(select(Area))
        all_areas = result.scalars().all()
        
        print(f"\n{'='*80}")
        print(f"All areas ({len(all_areas)}):")
        print(f"{'='*80}")
        for area in all_areas:
            print(f"  {area.id:25s} | {area.name:30s} | {area.biome or 'none':12s} | {area.ambient_lighting or 'none'}")


if __name__ == "__main__":
    asyncio.run(update_lighting())
