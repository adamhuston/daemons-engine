"""Phase 16.2: Account lockout columns

Revision ID: n6o7p8q9r0s1
Revises: m5n6o7p8q9r0_phase14_item_abilities
Create Date: 2024-01-15 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "n6o7p8q9r0s1"
down_revision: str = "m5n6o7p8q9r0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add account lockout columns to user_accounts table."""
    # Add failed_login_attempts column with default 0
    op.add_column(
        "user_accounts",
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    # Add locked_until column (nullable timestamp)
    op.add_column(
        "user_accounts",
        sa.Column("locked_until", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Remove account lockout columns from user_accounts table."""
    op.drop_column("user_accounts", "locked_until")
    op.drop_column("user_accounts", "failed_login_attempts")
