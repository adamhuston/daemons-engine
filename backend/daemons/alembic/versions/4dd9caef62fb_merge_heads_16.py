"""merge_heads_16

Revision ID: 4dd9caef62fb
Revises: 845936599777, n6o7p8q9r0s1
Create Date: 2025-12-02 14:10:02.089209

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '4dd9caef62fb'
down_revision: str | Sequence[str] | None = ('845936599777', 'n6o7p8q9r0s1')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
