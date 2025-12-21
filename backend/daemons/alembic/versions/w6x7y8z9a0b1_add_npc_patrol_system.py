"""add_npc_patrol_system

Revision ID: w6x7y8z9a0b1
Revises: v5w6x7y8z9a0
Create Date: 2024-12-20 00:00:00.000000

Add patrol system fields to npc_instances table:
- patrol_route: JSON array of room IDs for patrol waypoints
- patrol_index: Current position in patrol route
- patrol_mode: How NPC moves through route (loop/bounce/once)
- home_room_id: Spawn point for respawn and patrol return

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'w6x7y8z9a0b1'
down_revision: Union[str, None] = 'v5w6x7y8z9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add patrol system fields to npc_instances
    op.add_column('npc_instances', sa.Column('patrol_route', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('npc_instances', sa.Column('patrol_index', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('npc_instances', sa.Column('patrol_mode', sa.String(), nullable=False, server_default="'loop'"))
    op.add_column('npc_instances', sa.Column('home_room_id', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove patrol system fields from npc_instances
    op.drop_column('npc_instances', 'home_room_id')
    op.drop_column('npc_instances', 'patrol_mode')
    op.drop_column('npc_instances', 'patrol_index')
    op.drop_column('npc_instances', 'patrol_route')
