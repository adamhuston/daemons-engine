"""merge yaml rooms and phase11 branches

Revision ID: ef8829faa761
Revises: c3d4e5f6a7b8, k3l4m5n6o7p8
Create Date: 2025-11-29 16:18:16.539818

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef8829faa761'
down_revision: Union[str, Sequence[str], None] = ('c3d4e5f6a7b8', 'k3l4m5n6o7p8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
