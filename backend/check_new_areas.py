"""Check if new areas were inserted."""
import asyncio
import aiosqlite


async def main():
    async with aiosqlite.connect('./dungeon.db') as db:
        db.row_factory = aiosqlite.Row
        
        # Check for new areas
        async with db.execute("""
            SELECT * FROM areas 
            WHERE id IN ('area_dark_caves', 'area_sunlit_meadow')
        """) as cursor:
            rows = await cursor.fetchall()
            print(f"Found {len(rows)} new areas")
            for row in rows:
                print(dict(row))
        
        # Check all areas
        print("\nAll areas:")
        async with db.execute("SELECT id, name FROM areas") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                print(f"  {row['id']}: {row['name']}")


if __name__ == "__main__":
    asyncio.run(main())
