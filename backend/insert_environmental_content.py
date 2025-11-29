"""Directly insert new areas and rooms."""
import asyncio
import aiosqlite


async def main():
    async with aiosqlite.connect('./dungeon.db') as db:
        # Insert Dark Caves Area
        await db.execute("""
            INSERT INTO areas (
                id, name, description, biome, danger_level, ambient_lighting,
                time_phases, entry_points
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'area_dark_caves',
            'The Dark Caves',
            'A twisting network of underground passages where light rarely penetrates. Strange echoes bounce off unseen walls, and the air carries a damp, mineral scent. Some chambers hold bioluminescent fungi that provide eerie illumination, while others are wrapped in absolute darkness.',
            'underground',
            3,
            'dim',
            '{}',  # time_phases JSON
            '["room_cave_entrance"]'  # entry_points JSON
        ))
        
        # Insert Sunlit Meadow Area
        await db.execute("""
            INSERT INTO areas (
                id, name, description, biome, danger_level, ambient_lighting,
                time_phases, entry_points
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'area_sunlit_meadow',
            'The Sunlit Meadow',
            'A peaceful expanse of wildflowers and tall grasses bathed in golden sunlight. Butterflies dance between blooms, and the air is filled with the gentle hum of bees. The meadow stretches in all directions, dotted with ancient oaks that provide patches of welcome shade. This is a safe haven, untouched by the darkness that plagues other lands.',
            'grassland',
            1,
            'bright',
            '{}',  # time_phases JSON
            '["room_meadow_center"]'  # entry_points JSON
        ))
        
        print("✓ Inserted areas")
        
        # Insert Cave Rooms
        cave_rooms = [
            ('room_cave_entrance', 'area_dark_caves', 'Cave Entrance', 
             'The mouth of the cave yawns before you, a dark threshold between the outside world and the depths below. Weak daylight filters in from behind, creating long shadows that stretch into the tunnel ahead. The rocky walls are damp with moisture, and a cool breeze whispers from the darkness.',
             '40'),
            ('room_cave_tunnel_1', 'area_dark_caves', 'Dark Tunnel',
             'The passage narrows here, forcing you to watch your footing on the uneven stone floor. Nearly all light has fled this place—only the faintest hint of illumination remains. The darkness presses close, almost tangible, and you can hear water dripping somewhere in the black void ahead.',
             '5'),
            ('room_cave_chamber', 'area_dark_caves', 'Bioluminescent Chamber',
             'The tunnel opens into a larger chamber where the walls glow with soft blue-green light. Bioluminescent fungi cover the stone surfaces in patches, creating an otherworldly atmosphere. Their gentle radiance reveals crystalline formations jutting from the ceiling, and you can see several passages branching off into the deeper darkness.',
             '65'),
            ('room_deep_cave', 'area_dark_caves', 'Deep Cave',
             'You have descended into the deepest part of the cave system. Here, darkness is absolute—a complete absence of light that swallows all. The air is still and cold, carrying no scent except ancient stone. Without a light source, you are utterly blind, able only to feel your way along the smooth, cold walls.',
             '0'),
        ]
        
        for room_id, area_id, name, description, lighting in cave_rooms:
            await db.execute("""
                INSERT INTO rooms (id, area_id, name, description, lighting_override)
                VALUES (?, ?, ?, ?, ?)
            """, (room_id, area_id, name, description, lighting))
        
        print(f"✓ Inserted {len(cave_rooms)} cave rooms")
        
        # Insert Meadow Rooms
        meadow_rooms = [
            ('room_meadow_center', 'area_sunlit_meadow', 'Sunlit Clearing',
             'You stand in the heart of the meadow where the sunlight seems most intense. Wildflowers of every color carpet the ground, and the sky above is a brilliant blue, unmarred by clouds. The light is so bright it almost hurts your eyes, revealing every detail of the landscape with crystalline clarity. Everything here seems more vivid, more alive.',
             '95'),
            ('room_meadow_north', 'area_sunlit_meadow', 'Shaded Grove',
             'Ancient oak trees cluster together here, their broad canopies filtering the sunlight into dappled patterns on the ground. The light is gentler here, still bright enough to see clearly but without the intense glare of the open meadow. Soft green moss covers the tree roots, and the air is cooler in the shade.',
             '70'),
            ('room_meadow_south', 'area_sunlit_meadow', 'Open Field',
             'An expansive field of swaying grasses stretches before you, unbroken by trees or large rocks. The sunlight pours down steadily, creating a warm and welcoming atmosphere. Small purple flowers dot the grasses, and you can hear crickets singing in the warmth. The lighting here feels natural and balanced.',
             None),
            ('room_meadow_east', 'area_sunlit_meadow', 'Eastern Rise',
             'The meadow slopes gently upward here, rising toward the east. From this elevated position, you can see across the entire meadow, and the morning sun strikes this spot with particular brilliance. The light seems to shimmer in the air, and colors appear more saturated than usual. It feels like standing in a painting of an idealized summer day.',
             '90'),
            ('room_meadow_west', 'area_sunlit_meadow', 'Flower Garden',
             'Wild roses, daisies, and lavender grow in profusion here, creating a natural garden of breathtaking beauty. The flowers seem to glow in the sunlight, their petals catching and reflecting the light. Bees move lazily from bloom to bloom, and the air is heavy with sweet fragrance. The lighting perfectly showcases the vibrant colors.',
             None),
        ]
        
        for room_id, area_id, name, description, lighting in meadow_rooms:
            await db.execute("""
                INSERT INTO rooms (id, area_id, name, description, lighting_override)
                VALUES (?, ?, ?, ?, ?)
            """, (room_id, area_id, name, description, lighting))
        
        print(f"✓ Inserted {len(meadow_rooms)} meadow rooms")
        
        await db.commit()
        
        print("\n" + "="*80)
        print("VERIFICATION:")
        print("="*80)
        
        # Verify areas
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, name, biome, ambient_lighting FROM areas ORDER BY id") as cursor:
            print("\nAreas:")
            async for row in cursor:
                print(f"  {row['id']:25s} | {row['name']:30s} | {row['biome'] or 'none':12s} | {row['ambient_lighting'] or 'none'}")
        
        # Verify cave rooms
        async with db.execute("""
            SELECT id, name, lighting_override 
            FROM rooms 
            WHERE area_id = 'area_dark_caves' 
            ORDER BY id
        """) as cursor:
            print("\nCave Rooms:")
            async for row in cursor:
                override = row['lighting_override'] or 'area default'
                print(f"  {row['id']:25s} | {row['name']:30s} | Light: {override}")
        
        # Verify meadow rooms
        async with db.execute("""
            SELECT id, name, lighting_override 
            FROM rooms 
            WHERE area_id = 'area_sunlit_meadow' 
            ORDER BY id
        """) as cursor:
            print("\nMeadow Rooms:")
            async for row in cursor:
                override = row['lighting_override'] or 'area default'
                print(f"  {row['id']:25s} | {row['name']:30s} | Light: {override}")
        
        print("\n✓ All environmental content successfully loaded!")


if __name__ == "__main__":
    asyncio.run(main())
