"""Phase 17.2 - Weather System

Revision ID: q9r0s1t2u3v4
Revises: p8q9r0s1t2u3
Create Date: 2024-12-07

Adds weather system to areas:
- areas: weather_patterns (JSON), weather_immunity (bool)
- weather_states table for tracking current weather per area
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "q9r0s1t2u3v4"
down_revision = "p8q9r0s1t2u3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add weather system tables and fields."""
    
    # Create weather_states table for tracking current weather per area
    op.create_table(
        "weather_states",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("area_id", sa.String(), sa.ForeignKey("areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weather_type", sa.String(), nullable=False),  # clear, rain, storm, snow, fog, wind
        sa.Column("intensity", sa.String(), nullable=False, server_default="moderate"),  # light, moderate, heavy
        sa.Column("started_at", sa.Float(), nullable=False),  # Unix timestamp
        sa.Column("duration", sa.Integer(), nullable=False),  # Duration in seconds
        sa.Column("next_change_at", sa.Float(), nullable=True),  # When weather will transition
        sa.UniqueConstraint("area_id", name="uq_weather_states_area_id"),
    )
    
    # Add index on area_id for fast lookups
    op.create_index("ix_weather_states_area_id", "weather_states", ["area_id"])
    
    # Add weather fields to areas table
    with op.batch_alter_table("areas", schema=None) as batch_op:
        # Weather patterns - JSON dict with weather type probabilities
        # Format: {"clear": 0.4, "rain": 0.3, "storm": 0.1, "cloudy": 0.2}
        # If null, uses climate-based defaults
        batch_op.add_column(
            sa.Column(
                "weather_patterns",
                sa.JSON(),
                nullable=True
            )
        )
        # Weather immunity - if true, area has no weather (underground, indoor, etc.)
        batch_op.add_column(
            sa.Column(
                "weather_immunity",
                sa.Boolean(),
                nullable=False,
                server_default="0"  # SQLite uses 0/1 for booleans
            )
        )


def downgrade() -> None:
    """Remove weather system tables and fields."""
    
    # Remove weather fields from areas table
    with op.batch_alter_table("areas", schema=None) as batch_op:
        batch_op.drop_column("weather_immunity")
        batch_op.drop_column("weather_patterns")
    
    # Drop weather_states table
    op.drop_index("ix_weather_states_area_id", table_name="weather_states")
    op.drop_table("weather_states")
