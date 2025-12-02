"""Areas

Revision ID: 921a4875c30b
Revises: bc07882b503f
Create Date: 2025-11-28 00:16:50.564656

"""

from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
import yaml
from alembic import op
from sqlalchemy import MetaData, Table

# revision identifiers, used by Alembic.
revision: str = "921a4875c30b"
down_revision: str | Sequence[str] | None = "bc07882b503f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema and load area data from YAML files."""

    # Create areas table
    op.create_table(
        "areas",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        # Time system
        sa.Column("time_scale", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("starting_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("starting_hour", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("starting_minute", sa.Integer(), nullable=False, server_default="0"),
        # Environmental properties
        sa.Column("biome", sa.String(), nullable=False, server_default="ethereal"),
        sa.Column("climate", sa.String(), nullable=False, server_default="mild"),
        sa.Column(
            "ambient_lighting", sa.String(), nullable=False, server_default="normal"
        ),
        sa.Column(
            "weather_profile", sa.String(), nullable=False, server_default="clear"
        ),
        # Gameplay properties
        sa.Column("danger_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("magic_intensity", sa.String(), nullable=False, server_default="low"),
        # Atmospheric details
        sa.Column("ambient_sound", sa.Text(), nullable=True),
        # JSON columns
        sa.Column("time_phases", sa.JSON(), nullable=True),
        sa.Column("entry_points", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_areas")),
    )

    # Add area_id foreign key to rooms table
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("area_id", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_rooms_area_id_areas"), "areas", ["area_id"], ["id"]
        )

    # Load area data from YAML files
    load_areas_from_yaml()

    # Load room data from YAML files
    load_rooms_from_yaml()


def downgrade() -> None:
    """Downgrade schema."""

    # Remove area_id from rooms
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("fk_rooms_area_id_areas"), type_="foreignkey")
        batch_op.drop_column("area_id")

    # Drop areas table
    op.drop_table("areas")


def load_areas_from_yaml():
    """Load area definitions from YAML files into the database."""

    # Find YAML files
    world_data_dir = Path(__file__).parent.parent.parent / "world_data" / "areas"

    if not world_data_dir.exists():
        print(
            f"No world_data/areas directory found at {world_data_dir}, skipping area import"
        )
        return

    yaml_files = list(world_data_dir.glob("*.yaml")) + list(
        world_data_dir.glob("*.yml")
    )
    # Filter out schema/documentation files (starting with _)
    yaml_files = [f for f in yaml_files if not f.name.startswith("_")]

    if not yaml_files:
        print("No YAML files found in world_data/areas/, skipping area import")
        return

    # Get connection and metadata
    connection = op.get_bind()
    metadata = MetaData()
    areas_table = Table("areas", metadata, autoload_with=connection)

    # Load each YAML file
    for yaml_file in yaml_files:
        print(f"Loading area from {yaml_file.name}")

        with open(yaml_file, encoding="utf-8") as f:
            area_data = yaml.safe_load(f)

        # Prepare data for insertion
        insert_data = {
            "id": area_data["id"],
            "name": area_data["name"],
            "description": area_data["description"],
            "time_scale": area_data.get("time_scale", 1.0),
            "starting_day": area_data.get("starting_day", 1),
            "starting_hour": area_data.get("starting_hour", 6),
            "starting_minute": area_data.get("starting_minute", 0),
            "biome": area_data.get("biome", "ethereal"),
            "climate": area_data.get("climate", "mild"),
            "ambient_lighting": area_data.get("ambient_lighting", "normal"),
            "weather_profile": area_data.get("weather_profile", "clear"),
            "danger_level": area_data.get("danger_level", 1),
            "magic_intensity": area_data.get("magic_intensity", "low"),
            "ambient_sound": area_data.get("ambient_sound"),
            "time_phases": area_data.get("time_phases", {}),
            "entry_points": area_data.get("entry_points", []),
        }

        # Insert into database
        connection.execute(areas_table.insert().values(**insert_data))

    print(f"Loaded {len(yaml_files)} area(s) from YAML files")


def load_rooms_from_yaml():
    """Load room definitions from YAML files into the database."""

    # Find YAML files in all subdirectories of world_data/rooms/
    world_data_dir = Path(__file__).parent.parent.parent / "world_data" / "rooms"

    if not world_data_dir.exists():
        print(
            f"No world_data/rooms directory found at {world_data_dir}, skipping room import"
        )
        return

    # Find all YAML files recursively
    yaml_files = list(world_data_dir.glob("**/*.yaml")) + list(
        world_data_dir.glob("**/*.yml")
    )
    # Filter out schema/documentation files (starting with _)
    yaml_files = [f for f in yaml_files if not f.name.startswith("_")]

    if not yaml_files:
        print("No YAML files found in world_data/rooms/, skipping room import")
        return

    # Get connection and metadata
    connection = op.get_bind()
    metadata = MetaData()
    rooms_table = Table("rooms", metadata, autoload_with=connection)

    # Load each YAML file
    for yaml_file in yaml_files:
        print(f"Loading room from {yaml_file.name}")

        with open(yaml_file, encoding="utf-8") as f:
            room_data = yaml.safe_load(f)

        # Prepare data for insertion
        # Convert exits dict to individual columns
        exits = room_data.get("exits", {})

        insert_data = {
            "id": room_data["id"],
            "name": room_data["name"],
            "description": room_data["description"],
            "room_type": room_data.get("room_type", "ethereal"),
            "area_id": room_data.get("area_id"),
            "north_id": exits.get("north"),
            "south_id": exits.get("south"),
            "east_id": exits.get("east"),
            "west_id": exits.get("west"),
            "up_id": exits.get("up"),
            "down_id": exits.get("down"),
            "on_enter_effect": room_data.get("on_enter_effect"),
            "on_exit_effect": room_data.get("on_exit_effect"),
        }

        # Insert into database
        connection.execute(rooms_table.insert().values(**insert_data))

    print(f"Loaded {len(yaml_files)} room(s) from YAML files")
