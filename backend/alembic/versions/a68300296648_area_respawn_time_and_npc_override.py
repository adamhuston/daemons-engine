"""area_respawn_time_and_npc_override

Revision ID: a68300296648
Revises: 7d4e8f2a3b1c
Create Date: 2025-11-28 16:13:12.140479

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a68300296648"
down_revision: str | Sequence[str] | None = "7d4e8f2a3b1c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add default_respawn_time to areas table
    op.add_column(
        "areas",
        sa.Column(
            "default_respawn_time", sa.Integer(), nullable=False, server_default="300"
        ),
    )

    # Make npc_instances.respawn_time nullable (for override behavior)
    # First, we need to create a new column, copy data, drop old, rename new
    # For SQLite compatibility, we'll use batch mode
    with op.batch_alter_table("npc_instances") as batch_op:
        # Add new nullable column
        batch_op.add_column(sa.Column("respawn_time_new", sa.Integer(), nullable=True))

    # Set all existing to NULL (they'll inherit from area)
    op.execute("UPDATE npc_instances SET respawn_time_new = NULL")

    with op.batch_alter_table("npc_instances") as batch_op:
        # Drop old column and rename new one
        batch_op.drop_column("respawn_time")
        batch_op.alter_column("respawn_time_new", new_column_name="respawn_time")


def downgrade() -> None:
    """Downgrade schema."""
    # Remove default_respawn_time from areas
    op.drop_column("areas", "default_respawn_time")

    # Restore respawn_time as non-nullable with default 300
    with op.batch_alter_table("npc_instances") as batch_op:
        batch_op.add_column(
            sa.Column(
                "respawn_time_new", sa.Integer(), nullable=False, server_default="300"
            )
        )

    # Copy values, defaulting NULL to 300
    op.execute(
        "UPDATE npc_instances SET respawn_time_new = COALESCE(respawn_time, 300)"
    )

    with op.batch_alter_table("npc_instances") as batch_op:
        batch_op.drop_column("respawn_time")
        batch_op.alter_column("respawn_time_new", new_column_name="respawn_time")
