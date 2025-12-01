"""Quest progress and player flags

Revision ID: d9e5f8a7b2c3
Revises: a68300296648
Create Date: 2025-11-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9e5f8a7b2c3"
down_revision: str | None = "a68300296648"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add player_flags column to players table
    op.add_column(
        "players",
        sa.Column("player_flags", sa.JSON(), nullable=True, server_default="{}"),
    )

    # Add quest_progress column to players table (stores all quest progress as JSON)
    op.add_column(
        "players",
        sa.Column("quest_progress", sa.JSON(), nullable=True, server_default="{}"),
    )

    # Add completed_quests column to players table (stores set of completed quest IDs as JSON array)
    op.add_column(
        "players",
        sa.Column("completed_quests", sa.JSON(), nullable=True, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("players", "completed_quests")
    op.drop_column("players", "quest_progress")
    op.drop_column("players", "player_flags")
