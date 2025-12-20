"""Add fauna columns to npc_templates table

Adds is_fauna boolean flag and fauna_data JSON to npc_templates for fauna system.

Revision ID: u3v4w5x6y7z8
Revises: t2u3v4w5x6y7
Create Date: 2024-12-19 00:00:01.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "u3v4w5x6y7z8"
down_revision: Union[str, None] = "t2u3v4w5x6y7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add fauna columns to npc_templates table."""
    with op.batch_alter_table("npc_templates", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_fauna",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "fauna_data",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )


def downgrade() -> None:
    """Remove fauna columns from npc_templates table."""
    with op.batch_alter_table("npc_templates", schema=None) as batch_op:
        batch_op.drop_column("fauna_data")
        batch_op.drop_column("is_fauna")
