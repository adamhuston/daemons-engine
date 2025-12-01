"""items_and_inventory2

Revision ID: 186cf284ed62
Revises: 4f2e8d3c1a5b
Create Date: 2025-11-28 01:20:14.678088

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "186cf284ed62"
down_revision: str | Sequence[str] | None = "4f2e8d3c1a5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
