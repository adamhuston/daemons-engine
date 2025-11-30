"""Phase 10.3: Add Faction system (factions and faction_npc_members tables)

Revision ID: j2k3l4m5n6o7
Revises: i1j2k3l4m5n6
Create Date: 2025-11-29 12:15:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "j2k3l4m5n6o7"
down_revision = "i1j2k3l4m5n6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create factions table
    op.create_table(
        "factions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(), nullable=False, server_default="#FFFFFF"),
        sa.Column("emblem", sa.String(), nullable=True),
        sa.Column("player_joinable", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("max_members", sa.Integer(), nullable=True),
        sa.Column("require_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_factions_name"),
    )
    op.create_index("ix_factions_name", "factions", ["name"], unique=True)
    op.create_index("ix_factions_player_joinable", "factions", ["player_joinable"])

    # Create faction_npc_members table (links NPCs to factions)
    op.create_table(
        "faction_npc_members",
        sa.Column("faction_id", sa.String(), nullable=False),
        sa.Column("npc_template_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("faction_id", "npc_template_id"),
        sa.ForeignKeyConstraint(
            ["faction_id"],
            ["factions.id"],
            ondelete="CASCADE",
            name="fk_faction_npc_members_faction_id",
        ),
    )
    op.create_index(
        "ix_faction_npc_members_faction_id", "faction_npc_members", ["faction_id"]
    )
    op.create_index(
        "ix_faction_npc_members_npc_template_id",
        "faction_npc_members",
        ["npc_template_id"],
    )


def downgrade() -> None:
    # Drop faction_npc_members table
    op.drop_index("ix_faction_npc_members_npc_template_id", "faction_npc_members")
    op.drop_index("ix_faction_npc_members_faction_id", "faction_npc_members")
    op.drop_table("faction_npc_members")

    # Drop factions table
    op.drop_index("ix_factions_player_joinable", "factions")
    op.drop_index("ix_factions_name", "factions")
    op.drop_table("factions")
