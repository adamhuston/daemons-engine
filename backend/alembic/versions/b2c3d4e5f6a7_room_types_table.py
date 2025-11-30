"""Add room_types table and room_type_emoji column

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-11-28

Adds dynamic room type emoji system:
- room_types: Table to store room types with their emojis
- rooms.room_type_emoji: Optional per-room emoji override
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default room types to seed
DEFAULT_ROOM_TYPES = {
    "forest": "🌲",
    "urban": "🏙️",
    "rural": "🏘️",
    "underground": "🕳️",
    "underwater": "🌊",
    "lake": "🏞️",
    "ocean": "🌊",
    "river": "🏞️",
    "marsh": "🌾",
    "grassland": "🌾",
    "desert": "🏜️",
    "sky": "☁️",
    "ethereal": "✨",
    "forsaken": "💀",
}


def upgrade() -> None:
    # === room_types table ===
    # Check if table already exists (SQLite doesn't have IF NOT EXISTS for create_table via op)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='room_types'"
        )
    )
    if result.fetchone() is None:
        op.create_table(
            "room_types",
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("emoji", sa.String(), nullable=False, server_default="❓"),
            sa.Column("description", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("name", name=op.f("pk_room_types")),
        )

        # Seed default room types
        room_types_table = sa.table(
            "room_types",
            sa.column("name", sa.String),
            sa.column("emoji", sa.String),
            sa.column("description", sa.String),
        )

        op.bulk_insert(
            room_types_table,
            [
                {"name": name, "emoji": emoji, "description": None}
                for name, emoji in DEFAULT_ROOM_TYPES.items()
            ],
        )

    # === Add room_type_emoji column to rooms ===
    # Check if column already exists
    result = conn.execute(sa.text("PRAGMA table_info(rooms)"))
    columns = [row[1] for row in result.fetchall()]
    if "room_type_emoji" not in columns:
        op.add_column("rooms", sa.Column("room_type_emoji", sa.String(), nullable=True))


def downgrade() -> None:
    # Remove room_type_emoji column from rooms
    op.drop_column("rooms", "room_type_emoji")

    # Drop room_types table
    op.drop_table("room_types")
