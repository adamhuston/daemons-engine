"""Phase 10.2: Add Clan system (clans and clan_members tables)

Revision ID: i1j2k3l4m5n6
Revises: h1i2j3k4l5m6
Create Date: 2025-11-29 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "i1j2k3l4m5n6"
down_revision = "h1i2j3k4l5m6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create clans table
    op.create_table(
        "clans",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("leader_id", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("experience", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["leader_id"], ["players.id"], name="fk_clans_leader_id"
        ),
        sa.UniqueConstraint("name", name="uq_clans_name"),
    )
    op.create_index("ix_clans_name", "clans", ["name"], unique=True)
    op.create_index("ix_clans_leader_id", "clans", ["leader_id"])

    # Create clan_members table
    op.create_table(
        "clan_members",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("clan_id", sa.String(), nullable=False),
        sa.Column("player_id", sa.String(), nullable=False),
        sa.Column(
            "rank", sa.String(), nullable=False
        ),  # leader|officer|member|initiate
        sa.Column("joined_at", sa.Float(), nullable=False),
        sa.Column(
            "contribution_points", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["clan_id"],
            ["clans.id"],
            ondelete="CASCADE",
            name="fk_clan_members_clan_id",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.id"], name="fk_clan_members_player_id"
        ),
        sa.UniqueConstraint("clan_id", "player_id", name="uq_clan_members_clan_player"),
    )
    op.create_index("ix_clan_members_clan_id", "clan_members", ["clan_id"])
    op.create_index("ix_clan_members_player_id", "clan_members", ["player_id"])
    op.create_index("ix_clan_members_rank", "clan_members", ["rank"])


def downgrade() -> None:
    # Drop clan_members table
    op.drop_index("ix_clan_members_rank", "clan_members")
    op.drop_index("ix_clan_members_player_id", "clan_members")
    op.drop_index("ix_clan_members_clan_id", "clan_members")
    op.drop_table("clan_members")

    # Drop clans table
    op.drop_index("ix_clans_leader_id", "clans")
    op.drop_index("ix_clans_name", "clans")
    op.drop_table("clans")
