"""Phase 17.1 - Temperature System

Revision ID: p8q9r0s1t2u3
Revises: o7p8q9r0s1t2
Create Date: 2024-12-07

Adds temperature system to areas and rooms:
- areas: base_temperature (default 70°F), temperature_variation (default 20)
- rooms: temperature_override (nullable, overrides area calculation)
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "p8q9r0s1t2u3"
down_revision = "o7p8q9r0s1t2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add temperature fields to areas and rooms tables."""
    
    # Add temperature fields to areas table
    with op.batch_alter_table("areas", schema=None) as batch_op:
        # Base temperature in Fahrenheit (-50 to 150 range typical)
        # Default 70°F = comfortable room temperature
        batch_op.add_column(
            sa.Column(
                "base_temperature",
                sa.Integer(),
                nullable=False,
                server_default="70"
            )
        )
        # Daily temperature variation (+/- this amount based on time of day)
        # Default 20 = temps vary from base-15 (night) to base+5 (afternoon)
        batch_op.add_column(
            sa.Column(
                "temperature_variation",
                sa.Integer(),
                nullable=False,
                server_default="20"
            )
        )
    
    # Add temperature override to rooms table
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        # Per-room override - if set, ignores area calculation entirely
        # Useful for: caves (constant temp), forges (hot), ice caves (freezing)
        batch_op.add_column(
            sa.Column(
                "temperature_override",
                sa.Integer(),
                nullable=True
            )
        )


def downgrade() -> None:
    """Remove temperature fields from areas and rooms tables."""
    
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.drop_column("temperature_override")
    
    with op.batch_alter_table("areas", schema=None) as batch_op:
        batch_op.drop_column("temperature_variation")
        batch_op.drop_column("base_temperature")
