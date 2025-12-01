"""
Schema Registry System for Phase 12.1

Provides a central registry for all YAML schema definitions (_schema.yaml files)
used by the Daemonswright CMS for dynamic type generation and validation.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class SchemaInfo:
    """Metadata for a single schema file."""

    content_type: str  # e.g., "classes", "items", "rooms"
    file_path: str  # Absolute path to _schema.yaml
    content: str  # Raw YAML content
    checksum: str  # SHA256 hash
    last_modified: datetime  # File modification time
    size_bytes: int  # File size


@dataclass
class SchemaVersion:
    """Version metadata for the schema registry."""

    version: str = "1.0.0"  # Schema version
    engine_version: str = "0.12.1"  # Game engine version
    last_modified: datetime = field(
        default_factory=datetime.now
    )  # Most recent schema update
    schema_count: int = 0  # Total number of schemas


class SchemaRegistry:
    """
    Central registry for all YAML schema definitions.

    Loads and caches _schema.yaml files from world_data/ subdirectories,
    providing API access for the CMS to fetch schema definitions dynamically.
    """

    def __init__(self, world_data_path: str):
        """
        Initialize the schema registry.

        Args:
            world_data_path: Absolute path to the world_data directory
        """
        self.world_data_path = Path(world_data_path)
        self.schemas: dict[str, SchemaInfo] = {}
        self.version = SchemaVersion()

    def load_all_schemas(self) -> None:
        """
        Load all _schema.yaml files from world_data subdirectories.

        Scans the world_data directory for _schema.yaml files and caches them.
        Updates the version metadata with the most recent modification time.
        """
        self.schemas.clear()
        latest_modified = datetime.fromtimestamp(0)

        # Scan all subdirectories for _schema.yaml files
        for schema_path in self.world_data_path.rglob("_schema.yaml"):
            content_type = schema_path.parent.name

            # Handle nested directories (e.g., items/weapons/_schema.yaml)
            # We want the top-level type (items), not subdirectory (weapons)
            relative_to_world_data = schema_path.relative_to(self.world_data_path)
            if len(relative_to_world_data.parts) > 2:
                # This is a subdirectory schema, use parent directory name
                content_type = relative_to_world_data.parts[0]

            schema_info = self._load_schema_file(str(schema_path), content_type)

            if schema_info:
                # Use a unique key that includes subdirectory if present
                if len(relative_to_world_data.parts) > 2:
                    # e.g., "items/weapons" for items/weapons/_schema.yaml
                    key = "/".join(relative_to_world_data.parts[:-1])
                else:
                    # e.g., "classes" for classes/_schema.yaml
                    key = content_type

                self.schemas[key] = schema_info

                if schema_info.last_modified > latest_modified:
                    latest_modified = schema_info.last_modified

        # Update version metadata
        self.version.last_modified = latest_modified
        self.version.schema_count = len(self.schemas)

    def _load_schema_file(self, file_path: str, content_type: str) -> SchemaInfo | None:
        """
        Load a single schema file and compute metadata.

        Args:
            file_path: Absolute path to the schema file
            content_type: Content type identifier (e.g., "classes", "items")

        Returns:
            SchemaInfo object or None if loading failed
        """
        try:
            path = Path(file_path)

            # Read file content
            with open(path, encoding="utf-8") as f:
                content = f.read()

            # Compute checksum
            checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()

            # Get file metadata
            stat = path.stat()
            last_modified = datetime.fromtimestamp(stat.st_mtime)
            size_bytes = stat.st_size

            return SchemaInfo(
                content_type=content_type,
                file_path=str(path),
                content=content,
                checksum=checksum,
                last_modified=last_modified,
                size_bytes=size_bytes,
            )
        except Exception as e:
            print(f"Error loading schema {file_path}: {e}")
            return None

    def get_schema(self, content_type: str) -> SchemaInfo | None:
        """
        Get a specific schema by content type.

        Args:
            content_type: Content type identifier (e.g., "classes", "items")

        Returns:
            SchemaInfo object or None if not found
        """
        return self.schemas.get(content_type)

    def get_all_schemas(
        self, content_type_filter: str | None = None
    ) -> list[SchemaInfo]:
        """
        Get all schemas, optionally filtered by content type.

        Args:
            content_type_filter: Optional filter by content type

        Returns:
            List of SchemaInfo objects
        """
        if content_type_filter:
            # Return matching schemas (supports both exact match and prefix match)
            return [
                schema
                for key, schema in self.schemas.items()
                if schema.content_type == content_type_filter
                or key.startswith(content_type_filter + "/")
            ]
        return list(self.schemas.values())

    def get_version(self) -> SchemaVersion:
        """
        Get the current schema version metadata.

        Returns:
            SchemaVersion object
        """
        return self.version

    def reload_schemas(self) -> int:
        """
        Reload all schemas from disk.

        Returns:
            Number of schemas loaded
        """
        self.load_all_schemas()
        return len(self.schemas)

    def get_schema_list(self) -> list[str]:
        """
        Get a list of all available schema content types.

        Returns:
            List of content type identifiers
        """
        return list(self.schemas.keys())
