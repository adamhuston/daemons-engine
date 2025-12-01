"""Items and Inventory

Revision ID: 4f2e8d3c1a5b
Revises: 921a4875c30b
Create Date: 2025-11-28 02:30:00.000000

"""

import uuid
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
import yaml
from alembic import op
from sqlalchemy import MetaData, Table

# revision identifiers, used by Alembic.
revision: str = "4f2e8d3c1a5b"
down_revision: str | Sequence[str] | None = "921a4875c30b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema and load item data from YAML files."""

    # Create item_templates table
    op.create_table(
        "item_templates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        # Item categorization
        sa.Column("item_type", sa.String(), nullable=False),
        sa.Column("item_subtype", sa.String(), nullable=True),
        # Equipment properties
        sa.Column("equipment_slot", sa.String(), nullable=True),
        # Stat modifiers (JSON)
        sa.Column("stat_modifiers", sa.JSON(), nullable=False, server_default="{}"),
        # Physical properties
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("max_stack_size", sa.Integer(), nullable=False, server_default="1"),
        # Durability system
        sa.Column("has_durability", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_durability", sa.Integer(), nullable=True),
        # Container properties
        sa.Column("is_container", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("container_capacity", sa.Integer(), nullable=True),
        sa.Column("container_type", sa.String(), nullable=True),
        # Consumable properties
        sa.Column("is_consumable", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consume_effect", sa.JSON(), nullable=True),
        # Flavor and metadata
        sa.Column("flavor_text", sa.Text(), nullable=True),
        sa.Column("rarity", sa.String(), nullable=False, server_default="common"),
        sa.Column("value", sa.Integer(), nullable=False, server_default="0"),
        # Special flags (JSON)
        sa.Column("flags", sa.JSON(), nullable=False, server_default="{}"),
        # Keywords for searching (JSON array)
        sa.Column("keywords", sa.JSON(), nullable=False, server_default="[]"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_item_templates")),
    )

    # Create item_instances table
    op.create_table(
        "item_instances",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("template_id", sa.String(), nullable=False),
        # Location (one of these must be set)
        sa.Column("room_id", sa.String(), nullable=True),
        sa.Column("player_id", sa.String(), nullable=True),
        sa.Column("container_id", sa.String(), nullable=True),
        # Instance state
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_durability", sa.Integer(), nullable=True),
        # Equipped state
        sa.Column("equipped_slot", sa.String(), nullable=True),
        # Custom instance data (JSON)
        sa.Column("instance_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["item_templates.id"],
            name=op.f("fk_item_instances_template_id_item_templates"),
        ),
        sa.ForeignKeyConstraint(
            ["room_id"], ["rooms.id"], name=op.f("fk_item_instances_room_id_rooms")
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            name=op.f("fk_item_instances_player_id_players"),
        ),
        sa.ForeignKeyConstraint(
            ["container_id"],
            ["item_instances.id"],
            name=op.f("fk_item_instances_container_id_item_instances"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_item_instances")),
    )

    # Create player_inventories table
    op.create_table(
        "player_inventories",
        sa.Column("player_id", sa.String(), nullable=False),
        # Capacity limits
        sa.Column("max_weight", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("max_slots", sa.Integer(), nullable=False, server_default="20"),
        # Current usage (denormalized)
        sa.Column("current_weight", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("current_slots", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            name=op.f("fk_player_inventories_player_id_players"),
        ),
        sa.PrimaryKeyConstraint("player_id", name=op.f("pk_player_inventories")),
    )

    # Load item templates from YAML files
    load_items_from_yaml()

    # Load item instances from YAML files
    load_item_instances_from_yaml()

    # Create player inventories for existing players
    create_player_inventories()


def downgrade() -> None:
    """Downgrade schema - remove item tables."""
    op.drop_table("player_inventories")
    op.drop_table("item_instances")
    op.drop_table("item_templates")


def load_items_from_yaml() -> None:
    """Load item templates from YAML files in world_data/items/."""
    print("Loading item templates from YAML files...")

    # Get database connection
    connection = op.get_bind()

    # Define the table for raw SQL operations
    metadata = MetaData()
    item_templates = Table(
        "item_templates",
        metadata,
        sa.Column("id", sa.String),
        sa.Column("name", sa.String),
        sa.Column("description", sa.Text),
        sa.Column("item_type", sa.String),
        sa.Column("item_subtype", sa.String),
        sa.Column("equipment_slot", sa.String),
        sa.Column("stat_modifiers", sa.JSON),
        sa.Column("weight", sa.Float),
        sa.Column("max_stack_size", sa.Integer),
        sa.Column("has_durability", sa.Integer),
        sa.Column("max_durability", sa.Integer),
        sa.Column("is_container", sa.Integer),
        sa.Column("container_capacity", sa.Integer),
        sa.Column("container_type", sa.String),
        sa.Column("is_consumable", sa.Integer),
        sa.Column("consume_effect", sa.JSON),
        sa.Column("flavor_text", sa.Text),
        sa.Column("rarity", sa.String),
        sa.Column("value", sa.Integer),
        sa.Column("flags", sa.JSON),
        sa.Column("keywords", sa.JSON),
    )

    # Look for YAML files in world_data/items subdirectories
    base_dir = Path("world_data/items")
    yaml_files = []

    if base_dir.exists():
        for subdir in base_dir.iterdir():
            if subdir.is_dir():
                yaml_files.extend(subdir.glob("*.yaml"))

    items_loaded = 0

    for yaml_path in yaml_files:
        try:
            with open(yaml_path, encoding="utf-8") as f:
                item_data = yaml.safe_load(f)

            if not item_data:
                continue

            print(f"Loading item template from {yaml_path.name}")

            # Convert boolean fields for SQLite
            has_durability = 1 if item_data.get("has_durability", False) else 0
            is_container = 1 if item_data.get("is_container", False) else 0
            is_consumable = 1 if item_data.get("is_consumable", False) else 0

            # Insert item template
            connection.execute(
                item_templates.insert().values(
                    id=item_data["id"],
                    name=item_data["name"],
                    description=item_data["description"],
                    item_type=item_data["item_type"],
                    item_subtype=item_data.get("item_subtype"),
                    equipment_slot=item_data.get("equipment_slot"),
                    stat_modifiers=item_data.get("stat_modifiers", {}),
                    weight=item_data.get("weight", 1.0),
                    max_stack_size=item_data.get("max_stack_size", 1),
                    has_durability=has_durability,
                    max_durability=item_data.get("max_durability"),
                    is_container=is_container,
                    container_capacity=item_data.get("container_capacity"),
                    container_type=item_data.get("container_type"),
                    is_consumable=is_consumable,
                    consume_effect=item_data.get("consume_effect"),
                    flavor_text=item_data.get("flavor_text"),
                    rarity=item_data.get("rarity", "common"),
                    value=item_data.get("value", 0),
                    flags=item_data.get("flags", {}),
                    keywords=item_data.get("keywords", []),
                )
            )
            items_loaded += 1

        except Exception as e:
            print(f"Error loading item from {yaml_path}: {e}")

    print(f"Loaded {items_loaded} item template(s) from YAML files")


def load_item_instances_from_yaml() -> None:
    """Load item instances from YAML files in world_data/item_instances/."""
    print("Loading item instances from YAML files...")

    # Get database connection
    connection = op.get_bind()

    # Define the table for raw SQL operations
    metadata = MetaData()
    item_instances = Table(
        "item_instances",
        metadata,
        sa.Column("id", sa.String),
        sa.Column("template_id", sa.String),
        sa.Column("room_id", sa.String),
        sa.Column("player_id", sa.String),
        sa.Column("container_id", sa.String),
        sa.Column("quantity", sa.Integer),
        sa.Column("current_durability", sa.Integer),
        sa.Column("equipped_slot", sa.String),
        sa.Column("instance_data", sa.JSON),
    )

    # Look for YAML files in world_data/item_instances
    base_dir = Path("world_data/item_instances")
    yaml_files = []

    if base_dir.exists():
        # Get all YAML files in subdirectories
        for yaml_path in base_dir.rglob("*.yaml"):
            yaml_files.append(yaml_path)

    instances_loaded = 0

    for yaml_path in yaml_files:
        try:
            with open(yaml_path, encoding="utf-8") as f:
                instance_data = yaml.safe_load(f)

            if not instance_data:
                continue

            print(f"Loading item instances from {yaml_path.name}")

            # Handle different instance file formats
            items_list = []
            room_id = None

            if "items" in instance_data:
                items_list = instance_data["items"]
                room_id = instance_data.get("room_id")  # For room-specific spawns
            else:
                # Single item format
                items_list = [instance_data]

            for item in items_list:
                # Generate UUID for instance
                instance_id = str(uuid.uuid4())

                # Insert item instance
                connection.execute(
                    item_instances.insert().values(
                        id=instance_id,
                        template_id=item["template_id"],
                        room_id=room_id,
                        player_id=None,  # Will be assigned when given to players
                        container_id=None,
                        quantity=item.get("quantity", 1),
                        current_durability=item.get("current_durability"),
                        equipped_slot=None,
                        instance_data={},
                    )
                )
                instances_loaded += 1

        except Exception as e:
            print(f"Error loading item instances from {yaml_path}: {e}")

    print(f"Loaded {instances_loaded} item instance(s) from YAML files")


def create_player_inventories() -> None:
    """Create inventory records for existing players."""
    print("Creating inventory records for existing players...")

    # Get database connection
    connection = op.get_bind()

    # Get existing players
    players_result = connection.execute(sa.text("SELECT id FROM players"))
    players = players_result.fetchall()

    if not players:
        print("No existing players found")
        return

    # Define the table for raw SQL operations
    metadata = MetaData()
    player_inventories = Table(
        "player_inventories",
        metadata,
        sa.Column("player_id", sa.String),
        sa.Column("max_weight", sa.Float),
        sa.Column("max_slots", sa.Integer),
        sa.Column("current_weight", sa.Float),
        sa.Column("current_slots", sa.Integer),
    )

    inventories_created = 0

    for player in players:
        connection.execute(
            player_inventories.insert().values(
                player_id=player[0],
                max_weight=100.0,
                max_slots=20,
                current_weight=0.0,
                current_slots=0,
            )
        )
        inventories_created += 1

    print(f"Created {inventories_created} player inventory record(s)")
