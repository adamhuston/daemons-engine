"""Add weapon combat stats to item_templates

Revision ID: 7d4e8f2a3b1c
Revises: 5a3f9b7e2d1c
Create Date: 2024-01-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d4e8f2a3b1c"
down_revision: Union[str, None] = "5a3f9b7e2d1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add weapon combat stats columns to item_templates
    op.add_column(
        "item_templates",
        sa.Column("damage_min", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "item_templates",
        sa.Column("damage_max", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "item_templates",
        sa.Column("attack_speed", sa.Float(), nullable=False, server_default="2.0"),
    )
    op.add_column(
        "item_templates",
        sa.Column(
            "damage_type", sa.String(), nullable=False, server_default="physical"
        ),
    )


def downgrade() -> None:
    op.drop_column("item_templates", "damage_type")
    op.drop_column("item_templates", "attack_speed")
    op.drop_column("item_templates", "damage_max")
    op.drop_column("item_templates", "damage_min")
