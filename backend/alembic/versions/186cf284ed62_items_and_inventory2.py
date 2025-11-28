"""items_and_inventory2

Revision ID: 186cf284ed62
Revises: 4f2e8d3c1a5b
Create Date: 2025-11-28 01:20:14.678088

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '186cf284ed62'
down_revision: Union[str, Sequence[str], None] = '4f2e8d3c1a5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
