"""Add no_flora column to rooms table

Adds no_flora boolean flag to rooms table to prevent flora spawning in specific rooms.

Revision ID: t2u3v4w5x6y7
Revises: s1t2u3v4w5x6
Create Date: 2024-12-19 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "t2u3v4w5x6y7"
down_revision: Union[str, None] = "s1t2u3v4w5x6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add no_flora column to rooms table."""
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "no_flora",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    """Remove no_flora column from rooms table."""
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.drop_column("no_flora")
