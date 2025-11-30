"""
File Manager System for Phase 12.2

Provides secure async file operations for YAML content files in world_data directory.
Enables CMS to list, download, and upload content files with proper security checks.
"""

import asyncio
import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiofiles
import aiofiles.os
import yaml


@dataclass
class FileInfo:
    """Metadata for a single YAML file."""

    file_path: str  # Relative path from world_data root
    absolute_path: str  # Absolute file system path
    content_type: str  # Content category (e.g., "classes", "items", "rooms")
    size_bytes: int  # File size
    last_modified: datetime  # File modification timestamp
    checksum: Optional[str] = None  # SHA256 hash (only computed on demand)


@dataclass
class FileContent:
    """File content with metadata."""

    file_path: str  # Relative path from world_data root
    content: str  # Raw file content
    checksum: str  # SHA256 hash
    last_modified: datetime  # File modification timestamp
    size_bytes: int  # File size


class FileManager:
    """
    Manages YAML file operations for the CMS.

    Provides secure file listing, reading, and writing with:
    - Path traversal attack prevention
    - Atomic write operations
    - Checksum validation
    - Content type categorization
    """

    # Allowed content types (subdirectories of world_data)
    CONTENT_TYPES = {
        "abilities",
        "areas",
        "classes",
        "dialogues",
        "factions",
        "item_instances",
        "items",
        "npc_spawns",
        "npcs",
        "quest_chains",
        "quests",
        "rooms",
        "triggers",
    }

    # File extensions to scan
    YAML_EXTENSIONS = {".yaml", ".yml"}

    def __init__(self, world_data_path: str):
        """
        Initialize the file manager.

        Args:
            world_data_path: Absolute path to the world_data directory
        """
        self.world_data_path = Path(world_data_path).resolve()

        if not self.world_data_path.exists():
            raise ValueError(f"world_data directory not found: {world_data_path}")

        if not self.world_data_path.is_dir():
            raise ValueError(f"world_data path is not a directory: {world_data_path}")

    def _is_safe_path(self, file_path: str) -> bool:
        """
        Validate that a file path is safe (no path traversal).

        Args:
            file_path: Relative file path to validate

        Returns:
            True if path is safe, False otherwise
        """
        try:
            # Resolve the full path
            full_path = (self.world_data_path / file_path).resolve()

            # Check if it's within world_data directory
            return full_path.is_relative_to(self.world_data_path)
        except (ValueError, OSError):
            return False

    def _get_content_type(self, file_path: str) -> str:
        """
        Determine content type from file path.

        Args:
            file_path: Relative file path

        Returns:
            Content type string (e.g., "classes", "items")
        """
        parts = Path(file_path).parts
        if len(parts) > 0 and parts[0] in self.CONTENT_TYPES:
            return parts[0]
        return "unknown"

    async def list_files(
        self,
        content_type_filter: Optional[str] = None,
        include_schema_files: bool = False,
    ) -> List[FileInfo]:
        """
        List all YAML files in world_data directory.

        Args:
            content_type_filter: Optional filter by content type
            include_schema_files: Whether to include _schema.yaml files

        Returns:
            List of FileInfo objects
        """
        files = []

        # Scan directory recursively (synchronous Path operations are fine for metadata)
        for file_path in self.world_data_path.rglob("*"):
            # Skip directories
            if file_path.is_dir():
                continue

            # Check file extension
            if file_path.suffix.lower() not in self.YAML_EXTENSIONS:
                continue

            # Skip schema files unless requested
            if not include_schema_files and file_path.name == "_schema.yaml":
                continue

            # Get relative path
            try:
                rel_path = file_path.relative_to(self.world_data_path)
            except ValueError:
                continue  # Skip files outside world_data

            # Determine content type
            content_type = self._get_content_type(str(rel_path))

            # Apply filter
            if content_type_filter and content_type != content_type_filter:
                continue

            # Get file metadata
            stat = file_path.stat()

            files.append(
                FileInfo(
                    file_path=str(rel_path).replace("\\", "/"),  # Use forward slashes
                    absolute_path=str(file_path),
                    content_type=content_type,
                    size_bytes=stat.st_size,
                    last_modified=datetime.fromtimestamp(stat.st_mtime),
                )
            )

        return files

    async def read_file(self, file_path: str) -> FileContent:
        """
        Read a YAML file and return its content with metadata.

        Args:
            file_path: Relative path from world_data root

        Returns:
            FileContent object

        Raises:
            ValueError: If path is invalid or unsafe
            FileNotFoundError: If file doesn't exist
        """
        # Validate path safety
        if not self._is_safe_path(file_path):
            raise ValueError(f"Invalid or unsafe file path: {file_path}")

        full_path = self.world_data_path / file_path

        # Check if file exists
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not full_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        # Read file content asynchronously
        async with aiofiles.open(full_path, "r", encoding="utf-8") as f:
            content = await f.read()

        # Compute checksum in thread pool (CPU-bound operation)
        checksum = await asyncio.to_thread(
            lambda: hashlib.sha256(content.encode("utf-8")).hexdigest()
        )

        # Get file metadata
        stat = full_path.stat()

        return FileContent(
            file_path=file_path.replace("\\", "/"),
            content=content,
            checksum=checksum,
            last_modified=datetime.fromtimestamp(stat.st_mtime),
            size_bytes=stat.st_size,
        )

    async def write_file(
        self, file_path: str, content: str, validate_only: bool = False
    ) -> Tuple[bool, Optional[str], List[str]]:
        """
        Write content to a YAML file using atomic operations.

        Args:
            file_path: Relative path from world_data root
            content: Raw YAML content to write
            validate_only: If True, validate but don't write

        Returns:
            Tuple of (success, checksum, errors)
            - success: True if operation succeeded
            - checksum: SHA256 hash of content (or None if validate_only)
            - errors: List of error messages
        """
        errors = []

        # Validate path safety
        if not self._is_safe_path(file_path):
            errors.append(f"Invalid or unsafe file path: {file_path}")
            return False, None, errors

        # Validate YAML syntax (CPU-bound, run in thread pool)
        try:
            await asyncio.to_thread(yaml.safe_load, content)
        except yaml.YAMLError as e:
            errors.append(f"Invalid YAML syntax: {str(e)}")
            return False, None, errors

        # Compute checksum in thread pool (CPU-bound operation)
        checksum = await asyncio.to_thread(
            lambda: hashlib.sha256(content.encode("utf-8")).hexdigest()
        )

        # If validate_only, stop here
        if validate_only:
            return True, None, []

        full_path = self.world_data_path / file_path

        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file, then rename
        try:
            # Create temp file in same directory (for atomic rename)
            # Use tempfile.NamedTemporaryFile synchronously, then write async
            temp_fd, temp_path = tempfile.mkstemp(
                dir=full_path.parent, suffix=".tmp", text=True
            )

            try:
                # Write content asynchronously
                async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                    await f.write(content)

                # Close the file descriptor
                os.close(temp_fd)

                # Atomic rename (overwrites existing file)
                await aiofiles.os.replace(temp_path, str(full_path))

                return True, checksum, []

            except Exception as e:
                # Clean up temp file
                try:
                    os.close(temp_fd)
                    await aiofiles.os.unlink(temp_path)
                except Exception:
                    pass
                raise e

        except Exception as e:
            errors.append(f"Failed to write file: {str(e)}")
            return False, None, errors

    async def delete_file(self, file_path: str) -> Tuple[bool, List[str]]:
        """
        Delete a YAML file.

        Args:
            file_path: Relative path from world_data root

        Returns:
            Tuple of (success, errors)
        """
        errors = []

        # Validate path safety
        if not self._is_safe_path(file_path):
            errors.append(f"Invalid or unsafe file path: {file_path}")
            return False, errors

        full_path = self.world_data_path / file_path

        # Check if file exists
        if not full_path.exists():
            errors.append(f"File not found: {file_path}")
            return False, errors

        if not full_path.is_file():
            errors.append(f"Path is not a file: {file_path}")
            return False, errors

        # Prevent deletion of schema files
        if full_path.name == "_schema.yaml":
            errors.append("Cannot delete schema files")
            return False, errors

        try:
            await aiofiles.os.unlink(full_path)
            return True, []
        except Exception as e:
            errors.append(f"Failed to delete file: {str(e)}")
            return False, errors

    async def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about YAML files in world_data.

        Returns:
            Dictionary with file counts per content type
        """
        stats = {content_type: 0 for content_type in self.CONTENT_TYPES}
        stats["total"] = 0
        stats["unknown"] = 0

        files = await self.list_files(include_schema_files=False)

        for file_info in files:
            stats["total"] += 1
            if file_info.content_type in self.CONTENT_TYPES:
                stats[file_info.content_type] += 1
            else:
                stats["unknown"] += 1

        return stats
