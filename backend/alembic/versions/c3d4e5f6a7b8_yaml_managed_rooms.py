"""Add yaml_managed column to rooms

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-11-29

Adds yaml_managed boolean column to rooms table.
When true (default), room is managed by YAML content system.
When false, room was created/modified via API and will be skipped during YAML reload.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add yaml_managed column with default True
    # Existing rooms are considered YAML-managed
    op.add_column('rooms', sa.Column('yaml_managed', sa.Boolean(), nullable=False, server_default='1'))


def downgrade() -> None:
    op.drop_column('rooms', 'yaml_managed')
