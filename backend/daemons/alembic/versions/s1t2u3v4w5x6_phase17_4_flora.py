"""Phase 17.4: Flora System

Adds flora instances table for tracking harvestable plants and vegetation.

Revision ID: s1t2u3v4w5x6
Revises: r0s1t2u3v4w5
Create Date: 2024-01-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "s1t2u3v4w5x6"
down_revision: Union[str, None] = "r0s1t2u3v4w5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add flora instances table and room flora configuration."""
    # Create flora_instances table for runtime flora state
    op.create_table(
        "flora_instances",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("template_id", sa.String(64), nullable=False, index=True),
        sa.Column(
            "room_id",
            sa.String(255),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # State tracking
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_harvested_at", sa.DateTime(), nullable=True),
        sa.Column(
            "last_harvested_by",
            sa.String(255),
            sa.ForeignKey("players.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("harvest_count", sa.Integer(), nullable=False, server_default="0"),
        # Respawn tracking
        sa.Column("is_depleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("depleted_at", sa.DateTime(), nullable=True),
        # Spawn tracking
        sa.Column(
            "spawned_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("is_permanent", sa.Boolean(), nullable=False, server_default="0"),
        # Indexes
        sa.Index("ix_flora_room_template", "room_id", "template_id"),
    )

    # Add flora_config to rooms table for per-room flora settings
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "flora_config",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )

    # Add flora density and configuration to areas
    with op.batch_alter_table("areas", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "flora_density",
                sa.String(50),
                nullable=False,
                server_default="moderate",
            )
        )
        batch_op.add_column(
            sa.Column(
                "flora_spawn_pools",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )


def downgrade() -> None:
    """Remove flora system tables and columns."""
    # Remove area columns
    with op.batch_alter_table("areas", schema=None) as batch_op:
        batch_op.drop_column("flora_spawn_pools")
        batch_op.drop_column("flora_density")

    # Remove room columns
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.drop_column("flora_config")

    # Drop flora_instances table
    op.drop_table("flora_instances")
