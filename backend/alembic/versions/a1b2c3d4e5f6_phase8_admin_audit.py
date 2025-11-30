"""Phase 8 admin audit and metrics tables

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2025-01-15

Phase 8: Admin & Content Tools
- admin_actions: Audit log for all privileged administrative actions
- server_metrics: Historical server performance metrics
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === admin_actions table ===
    # Audit log for all administrative actions
    op.create_table(
        "admin_actions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column(
            "admin_id", sa.String(), nullable=True
        ),  # Nullable for system actions
        sa.Column("admin_name", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["user_accounts.id"],
            name=op.f("fk_admin_actions_admin_id_user_accounts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_actions")),
    )

    # Create indexes for common query patterns
    op.create_index("ix_admin_actions_timestamp", "admin_actions", ["timestamp"])
    op.create_index("ix_admin_actions_action", "admin_actions", ["action"])
    op.create_index("ix_admin_actions_admin_id", "admin_actions", ["admin_id"])

    # === server_metrics table ===
    # Historical server performance metrics
    op.create_table(
        "server_metrics",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("metric_type", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_server_metrics")),
    )

    # Create indexes for time-series queries
    op.create_index("ix_server_metrics_timestamp", "server_metrics", ["timestamp"])
    op.create_index("ix_server_metrics_metric_type", "server_metrics", ["metric_type"])
    # Composite index for efficient metric queries by type and time range
    op.create_index(
        "ix_server_metrics_type_time", "server_metrics", ["metric_type", "timestamp"]
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index("ix_server_metrics_type_time", table_name="server_metrics")
    op.drop_index("ix_server_metrics_metric_type", table_name="server_metrics")
    op.drop_index("ix_server_metrics_timestamp", table_name="server_metrics")
    op.drop_table("server_metrics")

    op.drop_index("ix_admin_actions_admin_id", table_name="admin_actions")
    op.drop_index("ix_admin_actions_action", table_name="admin_actions")
    op.drop_index("ix_admin_actions_timestamp", table_name="admin_actions")
    op.drop_table("admin_actions")
