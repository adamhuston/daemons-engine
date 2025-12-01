"""Phase 9: Character Classes & Abilities System

Revision ID: g8h9i0j1k2l3
Revises: a1b2c3d4e5f6
Create Date: 2025-01-15

Phase 9a: Domain Models & Database

This migration documents the Phase 9 character system schema that is stored
in the existing Player.data JSON column. No new tables are created - all
character data (class, level, experience, resources, abilities) is stored
as JSON within the player record.

Player.data JSON Schema (Phase 9):
{
    # Existing fields (backward compatible)
    "character_class": "warrior",  # Old style, deprecated
    "level": 5,                    # Old style, deprecated

    # Phase 9 new fields
    "class_id": "warrior",         # Class template ID
    "experience": 1200,             # Class-specific XP
    "learned_abilities": [
        "slash",
        "power_attack",
        "rally"
    ],
    "ability_loadout": [
        {
            "slot_id": 0,
            "ability_id": "slash",
            "last_used_at": 1234567890.5,
            "learned_at": 1
        },
        {
            "slot_id": 1,
            "ability_id": "power_attack",
            "last_used_at": 1234567885.2,
            "learned_at": 5
        }
    ],
    "resource_pools": {
        "health": {
            "current": 100,
            "max": 120,
            "last_regen_tick": 1234567890.5
        },
        "rage": {
            "current": 50,
            "max": 100,
            "last_regen_tick": 1234567890.5
        }
    }
}

Migration Notes:
- No database schema changes (data stored as JSON)
- Backward compatible: existing players without "class_id" continue to work
- New players will have character_sheet created on class selection
- One-time migration function will convert old players to new schema
- ClassSystem runtime manager loads class/ability templates from YAML
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "g8h9i0j1k2l3"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    No database schema changes for Phase 9a.

    Character class data is stored in the existing Player.data JSON column.
    The schema is documented above in the docstring.

    A migration function (migrate_existing_players) will be called separately
    to initialize character sheets for existing players.
    """
    pass


def downgrade() -> None:
    """
    Downgrade: removes Phase 9 fields from Player.data JSON.

    This is a documentation-only migration, so downgrade is a no-op.
    If needed, a migration script would remove class_id, experience,
    learned_abilities, ability_loadout, and resource_pools from Player.data.
    """
    pass
