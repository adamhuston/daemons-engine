"""Phase 6 persistence tables

Revision ID: e1f2a3b4c5d6
Revises: d9e5f8a7b2c3
Create Date: 2025-11-28

Phase 6: Persistence & Scaling
- player_effects: Active buffs/debuffs that survive disconnect
- room_state: Runtime room state (flags, dynamic exits)
- trigger_state: Fire counts for permanent triggers
- npc_state: Position/HP for persistent NPCs
- item_instances: Add dropped_at and decay_minutes columns
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d9e5f8a7b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === player_effects table ===
    # Stores active effects that should persist across disconnects
    op.create_table(
        "player_effects",
        sa.Column(
            "player_id", sa.String(), sa.ForeignKey("players.id"), nullable=False
        ),
        sa.Column("effect_id", sa.String(), nullable=False),
        sa.Column("effect_type", sa.String(), nullable=False),  # buff, debuff, dot, hot
        sa.Column("effect_data", sa.JSON(), nullable=True),  # Full effect serialization
        sa.Column("expires_at", sa.Float(), nullable=False),  # Unix timestamp
        sa.Column("created_at", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("player_id", "effect_id"),
    )

    # === room_state table ===
    # Stores runtime room state that should persist across restarts
    op.create_table(
        "room_state",
        sa.Column("room_id", sa.String(), sa.ForeignKey("rooms.id"), primary_key=True),
        sa.Column("room_flags", sa.JSON(), nullable=True, server_default="{}"),
        sa.Column("dynamic_exits", sa.JSON(), nullable=True, server_default="{}"),
        sa.Column("dynamic_description", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Float(), nullable=True),
    )

    # === trigger_state table ===
    # Stores fire counts for permanent triggers
    op.create_table(
        "trigger_state",
        sa.Column("trigger_id", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),  # 'room', 'area', or 'global'
        sa.Column("scope_id", sa.String(), nullable=False),  # room_id or area_id
        sa.Column("fire_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_fired_at", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("trigger_id", "scope", "scope_id"),
    )

    # === npc_state table ===
    # Stores runtime state for persistent NPCs (companions, unique bosses)
    op.create_table(
        "npc_state",
        sa.Column("instance_id", sa.String(), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(),
            sa.ForeignKey("npc_templates.id"),
            nullable=False,
        ),
        sa.Column(
            "current_room_id", sa.String(), sa.ForeignKey("rooms.id"), nullable=True
        ),
        sa.Column("current_hp", sa.Integer(), nullable=True),
        sa.Column("is_alive", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "owner_player_id", sa.String(), sa.ForeignKey("players.id"), nullable=True
        ),  # For companions
        sa.Column("instance_data", sa.JSON(), nullable=True),  # Additional state
        sa.Column("updated_at", sa.Float(), nullable=True),
    )

    # === Extend item_instances table ===
    # Add columns for ground item decay tracking
    op.add_column("item_instances", sa.Column("dropped_at", sa.Float(), nullable=True))
    op.add_column(
        "item_instances",
        sa.Column("decay_minutes", sa.Integer(), nullable=True, server_default="60"),
    )

    # === Extend npc_templates table ===
    # Add persist_state flag for NPCs that should survive restarts
    op.add_column(
        "npc_templates",
        sa.Column("persist_state", sa.Boolean(), nullable=True, server_default="0"),
    )


def downgrade() -> None:
    # Remove columns from existing tables
    op.drop_column("npc_templates", "persist_state")
    op.drop_column("item_instances", "decay_minutes")
    op.drop_column("item_instances", "dropped_at")

    # Drop new tables
    op.drop_table("npc_state")
    op.drop_table("trigger_state")
    op.drop_table("room_state")
    op.drop_table("player_effects")
