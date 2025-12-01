"""phase14_item_abilities

Revision ID: m5n6o7p8q9r0
Revises: l4m5n6o7p8q9
Create Date: 2025-12-01 12:00:00.000000

Adds ability system and combat stats support to ItemTemplate.

This migration extends ItemTemplate to support:
- Ability system (class_id, default_abilities, ability_loadout) for magic items
- Combat stats (max_health, base_armor_class, resistances) for destructible items

All fields are optional/nullable to maintain backward compatibility.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m5n6o7p8q9r0"
down_revision: str | None = "l4m5n6o7p8q9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ability and combat stat fields to item_templates table."""

    # Phase 14+: Ability system support (magic items with spells)
    op.add_column(
        "item_templates",
        sa.Column(
            "class_id",
            sa.String(),
            nullable=True,
            comment='Character class for items with abilities (e.g., "staff_wielder")',
        ),
    )

    op.add_column(
        "item_templates",
        sa.Column(
            "default_abilities",
            sa.JSON(),
            nullable=False,
            server_default="[]",
            comment="List of ability IDs this item grants",
        ),
    )

    op.add_column(
        "item_templates",
        sa.Column(
            "ability_loadout",
            sa.JSON(),
            nullable=False,
            server_default="[]",
            comment="Pre-equipped abilities for this item",
        ),
    )

    # Phase 14+: Combat stats (destructible items like doors, barrels)
    op.add_column(
        "item_templates",
        sa.Column(
            "max_health",
            sa.Integer(),
            nullable=True,
            comment="HP for destructible items (None = indestructible)",
        ),
    )

    op.add_column(
        "item_templates",
        sa.Column(
            "base_armor_class",
            sa.Integer(),
            nullable=False,
            server_default="10",
            comment="AC for destructible items",
        ),
    )

    op.add_column(
        "item_templates",
        sa.Column(
            "resistances",
            sa.JSON(),
            nullable=False,
            server_default="{}",
            comment='Damage resistances (e.g., {"fire": -50, "physical": 20})',
        ),
    )


def downgrade() -> None:
    """Remove ability and combat stat fields from item_templates table."""

    # Remove combat stat fields
    op.drop_column("item_templates", "resistances")
    op.drop_column("item_templates", "base_armor_class")
    op.drop_column("item_templates", "max_health")

    # Remove ability system fields
    op.drop_column("item_templates", "ability_loadout")
    op.drop_column("item_templates", "default_abilities")
    op.drop_column("item_templates", "class_id")
