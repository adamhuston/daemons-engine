"""merge_heads

Revision ID: 845936599777
Revises: 2a6413d60daa, m5n6o7p8q9r0
Create Date: 2025-12-01 15:50:24.810539

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "845936599777"
down_revision: str | Sequence[str] | None = ("2a6413d60daa", "m5n6o7p8q9r0")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
