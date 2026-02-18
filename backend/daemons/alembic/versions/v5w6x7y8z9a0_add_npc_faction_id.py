"""Add faction_id to npc_templates for NPC warfare

Revision ID: v5w6x7y8z9a0
Revises: u3v4w5x6y7z8
Create Date: 2025-12-20 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "v5w6x7y8z9a0"
down_revision = "u3v4w5x6y7z8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add faction_id column to npc_templates
    op.add_column(
        "npc_templates", sa.Column("faction_id", sa.String(), nullable=True)
    )


def downgrade() -> None:
    # Remove faction_id column from npc_templates
    op.drop_column("npc_templates", "faction_id")
