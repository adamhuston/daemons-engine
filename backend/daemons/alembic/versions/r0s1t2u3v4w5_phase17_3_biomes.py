"""Phase 17.3: Biome Coherence and Seasons System

Adds biome and season tracking to areas for environmental coherence.

Revision ID: r0s1t2u3v4w5
Revises: q9r0s1t2u3v4
Create Date: 2024-01-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "r0s1t2u3v4w5"
down_revision: Union[str, None] = "q9r0s1t2u3v4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add biome coherence and seasons fields."""
    # Add season tracking fields to areas
    with op.batch_alter_table("areas", schema=None) as batch_op:
        # Season configuration
        batch_op.add_column(
            sa.Column(
                "current_season",
                sa.String(50),
                nullable=False,
                server_default="summer",
            )
        )
        batch_op.add_column(
            sa.Column(
                "season_day",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
        batch_op.add_column(
            sa.Column(
                "days_per_season",
                sa.Integer(),
                nullable=False,
                server_default="30",
            )
        )
        batch_op.add_column(
            sa.Column(
                "season_locked",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )
        # Biome coherence data (JSON for extensibility)
        batch_op.add_column(
            sa.Column(
                "biome_data",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )
        # Flora/fauna compatibility tags (for future phases)
        batch_op.add_column(
            sa.Column(
                "flora_tags",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )
        batch_op.add_column(
            sa.Column(
                "fauna_tags",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )


def downgrade() -> None:
    """Remove biome coherence and seasons fields."""
    with op.batch_alter_table("areas", schema=None) as batch_op:
        batch_op.drop_column("fauna_tags")
        batch_op.drop_column("flora_tags")
        batch_op.drop_column("biome_data")
        batch_op.drop_column("season_locked")
        batch_op.drop_column("days_per_season")
        batch_op.drop_column("season_day")
        batch_op.drop_column("current_season")
