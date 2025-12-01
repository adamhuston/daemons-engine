"""Phase 7 authentication tables

Revision ID: f7a8b9c0d1e2
Revises: e1f2a3b4c5d6
Create Date: 2025-11-28

Phase 7: Accounts, Authentication, Security
- user_accounts: Core account table with username, password hash, role
- refresh_tokens: JWT refresh token storage for session management
- security_events: Audit log for security-relevant events
- players: Add account_id foreign key to link characters to accounts
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # === user_accounts table ===
    # Core authentication table storing user credentials and role
    op.create_table(
        "user_accounts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role", sa.String(length=32), nullable=False, server_default="player"
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("active_character_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_accounts")),
        sa.UniqueConstraint("username", name=op.f("uq_user_accounts_username")),
        sa.UniqueConstraint("email", name=op.f("uq_user_accounts_email")),
    )

    # === refresh_tokens table ===
    # Stores refresh tokens for session management with rotation
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("device_info", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["user_accounts.id"],
            name=op.f("fk_refresh_tokens_account_id_user_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])
    op.create_index("ix_refresh_tokens_account_id", "refresh_tokens", ["account_id"])

    # === security_events table ===
    # Audit log for security-relevant events (login, logout, failures, etc.)
    op.create_table(
        "security_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column(
            "account_id", sa.String(), nullable=True
        ),  # Nullable for failed login attempts
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),  # IPv6 max length
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["user_accounts.id"],
            name=op.f("fk_security_events_account_id_user_accounts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_events")),
    )
    op.create_index("ix_security_events_account_id", "security_events", ["account_id"])
    op.create_index("ix_security_events_event_type", "security_events", ["event_type"])
    op.create_index("ix_security_events_timestamp", "security_events", ["timestamp"])

    # === Add account_id to players table ===
    # Link characters to accounts (nullable initially for migration)
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.add_column(sa.Column("account_id", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_players_account_id_user_accounts",
            "user_accounts",
            ["account_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_players_account_id", ["account_id"])

    # === Add FK for active_character_id in user_accounts ===
    # Note: SQLite doesn't support ALTER TABLE ADD CONSTRAINT for FKs
    # We'll handle this relationship at the application level


def downgrade() -> None:
    # Remove account_id from players
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.drop_index("ix_players_account_id")
        batch_op.drop_constraint(
            "fk_players_account_id_user_accounts", type_="foreignkey"
        )
        batch_op.drop_column("account_id")

    # Drop security_events
    op.drop_index("ix_security_events_timestamp", table_name="security_events")
    op.drop_index("ix_security_events_event_type", table_name="security_events")
    op.drop_index("ix_security_events_account_id", table_name="security_events")
    op.drop_table("security_events")

    # Drop refresh_tokens
    op.drop_index("ix_refresh_tokens_account_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    # Drop user_accounts
    op.drop_table("user_accounts")
