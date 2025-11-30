"""Phase 11: Light and vision system

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2025-11-29 16:05:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k3l4m5n6o7p8"
down_revision: Union[str, None] = "j2k3l4m5n6o7"  # Changed to point to Phase 10.3
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add lighting_override to rooms
    op.add_column("rooms", sa.Column("lighting_override", sa.String(50), nullable=True))

    # Add light source fields to item_templates
    op.add_column(
        "item_templates",
        sa.Column("provides_light", sa.Boolean(), server_default="0", nullable=False),
    )
    op.add_column(
        "item_templates",
        sa.Column("light_intensity", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "item_templates", sa.Column("light_duration", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    # Remove light source fields from item_templates
    op.drop_column("item_templates", "light_duration")
    op.drop_column("item_templates", "light_intensity")
    op.drop_column("item_templates", "provides_light")

    # Remove lighting_override from rooms
    op.drop_column("rooms", "lighting_override")
