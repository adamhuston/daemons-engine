#!/usr/bin/env python
"""
Phase 9a Player Migration Script

Converts existing players from old character_class/level schema to new
CharacterSheet schema with class_id, experience, learned_abilities, etc.

Usage:
    python migrate_players_phase9.py

This script:
1. Connects to the database
2. Iterates over all Player records
3. For players without class_id, assigns default class ("adventurer")
4. Initializes resource pools based on class template
5. Creates ability loadout with starting abilities
6. Saves updated player record

Run this once after deploying Phase 9a code.
"""
import asyncio
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models import Player, engine as app_engine


async def migrate_player_to_phase9(session: AsyncSession, player_record: Player) -> bool:
    """
    Migrate a single player to Phase 9 schema.
    
    Returns:
        True if migrated, False if already migrated
    """
    data = player_record.data or {}
    
    # Check if already migrated
    if "class_id" in data:
        return False
    
    print(f"  Migrating player: {player_record.id} ({player_record.username})")
    
    # Get old class or assign default
    old_class = data.get("character_class", "adventurer")
    old_level = data.get("level", 1)
    
    # Initialize Phase 9 fields
    data["class_id"] = old_class
    data["level"] = old_level
    data["experience"] = 0
    data["learned_abilities"] = ["slash", "power_attack"]  # Start with basic abilities
    
    # Create ability loadout (2 slots at level 1)
    data["ability_loadout"] = [
        {
            "slot_id": 0,
            "ability_id": "slash",
            "last_used_at": 0.0,
            "learned_at": 1
        },
        {
            "slot_id": 1,
            "ability_id": None,
            "last_used_at": 0.0,
            "learned_at": 0
        }
    ]
    
    # Initialize resource pools (health, mana)
    # These will be refined based on class template once ClassSystem is available
    current_time = time.time()
    data["resource_pools"] = {
        "health": {
            "current": 100,
            "max": 100,
            "last_regen_tick": current_time
        },
        "mana": {
            "current": 50,
            "max": 50,
            "last_regen_tick": current_time
        }
    }
    
    # Update player record
    player_record.data = data
    await session.commit()
    
    return True


async def main():
    """Main migration function."""
    print("=" * 70)
    print("Phase 9a Player Migration")
    print("=" * 70)
    
    # Create async engine
    db_engine = create_async_engine(
        "sqlite+aiosqlite:///dungeon.db",
        echo=False
    )
    
    try:
        async with AsyncSession(db_engine) as session:
            # Get all players
            result = await session.execute(select(Player))
            players = result.scalars().all()
            
            print(f"\nFound {len(players)} players in database")
            print("Checking for players needing migration...\n")
            
            migrated_count = 0
            skipped_count = 0
            
            for player in players:
                try:
                    was_migrated = await migrate_player_to_phase9(session, player)
                    if was_migrated:
                        migrated_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    print(f"  ERROR migrating {player.id}: {str(e)}")
            
            print("\n" + "=" * 70)
            print(f"Migration complete!")
            print(f"  Migrated: {migrated_count}")
            print(f"  Already done: {skipped_count}")
            print("=" * 70)
    
    finally:
        await db_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
