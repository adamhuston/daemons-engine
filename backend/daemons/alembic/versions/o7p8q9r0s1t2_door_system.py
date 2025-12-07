"""Add door_states column to room_state table for door system

Revision ID: o7p8q9r0s1t2
Revises: 4dd9caef62fb
Create Date: 2024-12-06

Adds support for:
- door_states: JSON column storing door open/closed/locked states per exit direction
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "o7p8q9r0s1t2"
down_revision = "4dd9caef62fb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add door_states column to room_state table."""
    with op.batch_alter_table("room_state", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("door_states", sa.JSON(), nullable=True, server_default="{}")
        )


def downgrade() -> None:
    """Remove door_states column from room_state table."""
    with op.batch_alter_table("room_state", schema=None) as batch_op:
        batch_op.drop_column("door_states")
