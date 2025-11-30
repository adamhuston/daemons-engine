"""NPCs and AI Framework

Revision ID: 5a3f9b7e2d1c
Revises: 4f2e8d3c1a5b
Create Date: 2025-11-28 12:00:00.000000

"""

import uuid
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
import yaml
from sqlalchemy import MetaData, Table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5a3f9b7e2d1c"
down_revision: Union[str, Sequence[str], None] = "186cf284ed62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema and load NPC data from YAML files."""

    # Create npc_templates table
    op.create_table(
        "npc_templates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        # NPC categorization
        sa.Column("npc_type", sa.String(), nullable=False, server_default="hostile"),
        # Base stats
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_health", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("armor_class", sa.Integer(), nullable=False, server_default="10"),
        # Primary attributes
        sa.Column("strength", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("dexterity", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("intelligence", sa.Integer(), nullable=False, server_default="10"),
        # Combat properties (for Phase 4.5)
        sa.Column(
            "attack_damage_min", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column(
            "attack_damage_max", sa.Integer(), nullable=False, server_default="5"
        ),
        sa.Column("attack_speed", sa.Float(), nullable=False, server_default="3.0"),
        sa.Column(
            "experience_reward", sa.Integer(), nullable=False, server_default="10"
        ),
        # AI behavior flags (JSON)
        sa.Column("behavior", sa.JSON(), nullable=False, server_default="{}"),
        # Loot table (JSON array for Phase 4.5)
        sa.Column("loot_table", sa.JSON(), nullable=False, server_default="[]"),
        # Flavor
        sa.Column("idle_messages", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("keywords", sa.JSON(), nullable=False, server_default="[]"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_npc_templates")),
    )

    # Create npc_instances table
    op.create_table(
        "npc_instances",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("template_id", sa.String(), nullable=False),
        # Location
        sa.Column("room_id", sa.String(), nullable=False),
        sa.Column("spawn_room_id", sa.String(), nullable=False),
        # Instance state
        sa.Column("current_health", sa.Integer(), nullable=False),
        sa.Column("is_alive", sa.Integer(), nullable=False, server_default="1"),
        # Respawn tracking
        sa.Column("respawn_time", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("last_killed_at", sa.Float(), nullable=True),
        # Instance-specific overrides (JSON)
        sa.Column("instance_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["npc_templates.id"],
            name=op.f("fk_npc_instances_template_id_npc_templates"),
        ),
        sa.ForeignKeyConstraint(
            ["room_id"], ["rooms.id"], name=op.f("fk_npc_instances_room_id_rooms")
        ),
        sa.ForeignKeyConstraint(
            ["spawn_room_id"],
            ["rooms.id"],
            name=op.f("fk_npc_instances_spawn_room_id_rooms"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_npc_instances")),
    )

    # Load NPC templates from YAML files
    load_npcs_from_yaml()

    # Load NPC instances from YAML files
    load_npc_spawns_from_yaml()


def downgrade() -> None:
    """Downgrade schema - remove NPC tables."""
    op.drop_table("npc_instances")
    op.drop_table("npc_templates")


def load_npcs_from_yaml() -> None:
    """Load NPC templates from YAML files in world_data/npcs/."""
    print("Loading NPC templates from YAML files...")

    # Get database connection
    connection = op.get_bind()

    # Define the table for raw SQL operations
    metadata = MetaData()
    npc_templates = Table(
        "npc_templates",
        metadata,
        sa.Column("id", sa.String),
        sa.Column("name", sa.String),
        sa.Column("description", sa.Text),
        sa.Column("npc_type", sa.String),
        sa.Column("level", sa.Integer),
        sa.Column("max_health", sa.Integer),
        sa.Column("armor_class", sa.Integer),
        sa.Column("strength", sa.Integer),
        sa.Column("dexterity", sa.Integer),
        sa.Column("intelligence", sa.Integer),
        sa.Column("attack_damage_min", sa.Integer),
        sa.Column("attack_damage_max", sa.Integer),
        sa.Column("attack_speed", sa.Float),
        sa.Column("experience_reward", sa.Integer),
        sa.Column("behavior", sa.JSON),
        sa.Column("loot_table", sa.JSON),
        sa.Column("idle_messages", sa.JSON),
        sa.Column("keywords", sa.JSON),
    )

    # Look for YAML files in world_data/npcs
    base_dir = Path("world_data/npcs")
    yaml_files = []

    if base_dir.exists():
        yaml_files = list(base_dir.glob("*.yaml"))

    npcs_loaded = 0

    for yaml_path in yaml_files:
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                npc_data = yaml.safe_load(f)

            if not npc_data:
                continue

            print(f"Loading NPC template from {yaml_path.name}")

            # Insert NPC template
            connection.execute(
                npc_templates.insert().values(
                    id=npc_data["id"],
                    name=npc_data["name"],
                    description=npc_data.get("description", ""),
                    npc_type=npc_data.get("npc_type", "hostile"),
                    level=npc_data.get("level", 1),
                    max_health=npc_data.get("max_health", 50),
                    armor_class=npc_data.get("armor_class", 10),
                    strength=npc_data.get("strength", 10),
                    dexterity=npc_data.get("dexterity", 10),
                    intelligence=npc_data.get("intelligence", 10),
                    attack_damage_min=npc_data.get("attack_damage_min", 1),
                    attack_damage_max=npc_data.get("attack_damage_max", 5),
                    attack_speed=npc_data.get("attack_speed", 3.0),
                    experience_reward=npc_data.get("experience_reward", 10),
                    behavior=npc_data.get("behavior", {}),
                    loot_table=npc_data.get("loot_table", []),
                    idle_messages=npc_data.get("idle_messages", []),
                    keywords=npc_data.get("keywords", []),
                )
            )
            npcs_loaded += 1

        except Exception as e:
            print(f"Error loading NPC from {yaml_path.name}: {e}")

    print(f"Loaded {npcs_loaded} NPC templates.")


def load_npc_spawns_from_yaml() -> None:
    """Load NPC instances from YAML spawn files in world_data/npc_spawns/."""
    print("Loading NPC spawns from YAML files...")

    # Get database connection
    connection = op.get_bind()

    # Define the table for raw SQL operations
    metadata = MetaData()
    npc_instances = Table(
        "npc_instances",
        metadata,
        sa.Column("id", sa.String),
        sa.Column("template_id", sa.String),
        sa.Column("room_id", sa.String),
        sa.Column("spawn_room_id", sa.String),
        sa.Column("current_health", sa.Integer),
        sa.Column("is_alive", sa.Integer),
        sa.Column("respawn_time", sa.Integer),
        sa.Column("last_killed_at", sa.Float),
        sa.Column("instance_data", sa.JSON),
    )

    # We need to look up NPC templates to get max_health
    npc_templates = Table(
        "npc_templates",
        metadata,
        sa.Column("id", sa.String),
        sa.Column("max_health", sa.Integer),
    )

    # Look for YAML files in world_data/npc_spawns
    base_dir = Path("world_data/npc_spawns")
    yaml_files = []

    if base_dir.exists():
        yaml_files = list(base_dir.glob("*.yaml"))

    spawns_loaded = 0

    for yaml_path in yaml_files:
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                spawn_data = yaml.safe_load(f)

            if not spawn_data or "spawns" not in spawn_data:
                continue

            print(f"Loading NPC spawns from {yaml_path.name}")

            for spawn in spawn_data["spawns"]:
                template_id = spawn["template_id"]
                room_id = spawn["room_id"]

                # Look up template to get max_health
                result = connection.execute(
                    sa.select(npc_templates.c.max_health).where(
                        npc_templates.c.id == template_id
                    )
                ).fetchone()

                if not result:
                    print(
                        f"  Warning: NPC template {template_id} not found, skipping spawn"
                    )
                    continue

                max_health = result[0]

                # Generate unique instance ID
                instance_id = f"npc_{uuid.uuid4().hex[:12]}"

                # Insert NPC instance
                connection.execute(
                    npc_instances.insert().values(
                        id=instance_id,
                        template_id=template_id,
                        room_id=room_id,
                        spawn_room_id=room_id,  # Spawn room is where it starts
                        current_health=max_health,
                        is_alive=1,
                        respawn_time=spawn.get("respawn_time", 300),
                        last_killed_at=None,
                        instance_data=spawn.get("instance_data", {}),
                    )
                )
                spawns_loaded += 1
                print(f"  Spawned {template_id} in {room_id}")

        except Exception as e:
            print(f"Error loading spawns from {yaml_path.name}: {e}")

    print(f"Loaded {spawns_loaded} NPC instances.")
