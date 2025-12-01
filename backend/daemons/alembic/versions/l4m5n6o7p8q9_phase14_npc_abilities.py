"""phase14_npc_abilities

Revision ID: l4m5n6o7p8q9
Revises: k3l4m5n6o7p8
Create Date: 2025-12-01

Phase 14.1: Add character class and ability fields to NPC templates
- Enables NPCs to have classes (warrior, mage, rogue, etc.)
- NPCs can spawn with pre-learned abilities
- NPCs can have pre-equipped ability loadouts

Changes:
- Add class_id column to npc_templates (nullable, backward compatible)
- Add default_abilities JSON column to npc_templates
- Add ability_loadout JSON column to npc_templates
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "l4m5n6o7p8q9"
down_revision = "k3l4m5n6o7p8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add character class and ability fields to npc_templates."""
    # Add class_id column (nullable for backward compatibility)
    op.add_column("npc_templates", sa.Column("class_id", sa.String(), nullable=True))

    # Add default_abilities JSON column (abilities NPC spawns with)
    op.add_column(
        "npc_templates",
        sa.Column("default_abilities", sa.JSON(), nullable=False, server_default="[]"),
    )

    # Add ability_loadout JSON column (pre-equipped abilities)
    op.add_column(
        "npc_templates",
        sa.Column("ability_loadout", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    """Remove character class and ability fields from npc_templates."""
    op.drop_column("npc_templates", "ability_loadout")
    op.drop_column("npc_templates", "default_abilities")
    op.drop_column("npc_templates", "class_id")
