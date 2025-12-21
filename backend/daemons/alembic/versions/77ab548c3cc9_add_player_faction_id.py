"""add_player_faction_id

Revision ID: 77ab548c3cc9
Revises: w6x7y8z9a0b1
Create Date: 2025-12-20 20:54:51.123373

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77ab548c3cc9'
down_revision: Union[str, Sequence[str], None] = 'w6x7y8z9a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add faction_id column to players table
    op.add_column('players', sa.Column('faction_id', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove faction_id column from players table
    op.drop_column('players', 'faction_id')
