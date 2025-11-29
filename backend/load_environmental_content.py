"""Load environmental content SQL files into the database."""
import asyncio
import aiosqlite


async def load_sql_file(db_path: str, sql_file: str):
    """Execute SQL from file."""
    with open(sql_file, 'r') as f:
        sql_content = f.read()
    
    async with aiosqlite.connect(db_path) as db:
        # Split on semicolons and execute each statement
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        
        for statement in statements:
            if statement and not statement.startswith('--'):
                await db.execute(statement)
        
        await db.commit()
        print(f"✓ Loaded {sql_file}")


async def main():
    db_path = './dungeon.db'
    
    sql_files = [
        'world_data/areas/dark_caves_area.sql',
        'world_data/areas/sunlit_meadow_area.sql',
    ]
    
    print("Loading environmental content into database...\n")
    
    for sql_file in sql_files:
        await load_sql_file(db_path, sql_file)
    
    print("\n✓ All environmental content loaded successfully!")
    
    # Verify the data was loaded
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        
        print("\n" + "="*80)
        print("AREAS:")
        print("="*80)
        async with db.execute("SELECT id, name, biome, ambient_lighting FROM areas ORDER BY id") as cursor:
            async for row in cursor:
                print(f"  {row['id']:25s} | {row['name']:30s} | {row['biome'] or 'none':12s} | {row['ambient_lighting'] or 'none'}")
        
        print("\n" + "="*80)
        print("CAVE ROOMS:")
        print("="*80)
        async with db.execute("""
            SELECT id, name, lighting_override 
            FROM rooms 
            WHERE area_id = 'area_dark_caves' 
            ORDER BY id
        """) as cursor:
            async for row in cursor:
                override = row['lighting_override'] or 'area default'
                print(f"  {row['id']:25s} | {row['name']:30s} | Light: {override}")
        
        print("\n" + "="*80)
        print("MEADOW ROOMS:")
        print("="*80)
        async with db.execute("""
            SELECT id, name, lighting_override 
            FROM rooms 
            WHERE area_id = 'area_sunlit_meadow' 
            ORDER BY id
        """) as cursor:
            async for row in cursor:
                override = row['lighting_override'] or 'area default'
                print(f"  {row['id']:25s} | {row['name']:30s} | Light: {override}")


if __name__ == "__main__":
    asyncio.run(main())
