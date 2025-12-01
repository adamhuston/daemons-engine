"""
Query Service System for Phase 12.4

Provides content querying capabilities for CMS:
- Full-text search across YAML files
- Dependency graph tracking (what references what)
- Content statistics and analytics
- Orphaned content detection
- Broken reference reporting
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SearchResult:
    """A single search result with context."""

    content_type: str  # Content category (e.g., "classes", "items")
    file_path: str  # Relative path from world_data root
    entity_id: str  # Primary ID of the entity
    entity_name: str  # Display name
    match_field: str  # Field that matched (e.g., "name", "description")
    match_value: str  # The matching text
    context_snippet: str  # Surrounding text for preview
    score: float = 1.0  # Relevance score (higher = better match)


@dataclass
class Dependency:
    """A single dependency relationship."""

    source_type: str  # Content type of source entity
    source_id: str  # ID of source entity
    target_type: str  # Content type of target entity
    target_id: str  # ID of target entity
    relationship: str  # Type of relationship (e.g., "exit", "ability", "spawns")
    field_path: str  # Field where dependency exists


@dataclass
class DependencyGraph:
    """Bidirectional dependency information for an entity."""

    entity_type: str
    entity_id: str
    entity_name: str | None = None

    # What this entity references (outgoing dependencies)
    references: list[Dependency] = field(default_factory=list)

    # What references this entity (incoming dependencies)
    referenced_by: list[Dependency] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to API-friendly dict."""
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "references": [
                {
                    "target_type": dep.target_type,
                    "target_id": dep.target_id,
                    "relationship": dep.relationship,
                    "field_path": dep.field_path,
                }
                for dep in self.references
            ],
            "referenced_by": [
                {
                    "source_type": dep.source_type,
                    "source_id": dep.source_id,
                    "relationship": dep.relationship,
                    "field_path": dep.field_path,
                }
                for dep in self.referenced_by
            ],
            "reference_count": len(self.references),
            "referenced_by_count": len(self.referenced_by),
            "is_orphaned": len(self.referenced_by) == 0,
        }


@dataclass
class ContentAnalytics:
    """Advanced content statistics and health metrics."""

    total_entities: int = 0
    entities_by_type: dict[str, int] = field(default_factory=dict)

    # Reference health
    broken_references: list[Dependency] = field(default_factory=list)
    orphaned_entities: list[tuple[str, str]] = field(default_factory=list)  # (type, id)

    # Content metrics
    average_references_per_entity: float = 0.0
    most_referenced_entities: list[tuple[str, str, int]] = field(
        default_factory=list
    )  # (type, id, count)

    def to_dict(self) -> dict[str, Any]:
        """Convert to API-friendly dict."""
        return {
            "total_entities": self.total_entities,
            "entities_by_type": self.entities_by_type,
            "broken_reference_count": len(self.broken_references),
            "broken_references": [
                {
                    "source_type": dep.source_type,
                    "source_id": dep.source_id,
                    "target_type": dep.target_type,
                    "target_id": dep.target_id,
                    "relationship": dep.relationship,
                    "field_path": dep.field_path,
                }
                for dep in self.broken_references
            ],
            "orphaned_entity_count": len(self.orphaned_entities),
            "orphaned_entities": [
                {"type": entity_type, "id": entity_id}
                for entity_type, entity_id in self.orphaned_entities
            ],
            "average_references_per_entity": self.average_references_per_entity,
            "most_referenced_entities": [
                {"type": entity_type, "id": entity_id, "reference_count": count}
                for entity_type, entity_id, count in self.most_referenced_entities
            ],
        }


class QueryService:
    """
    Content querying and analytics service for CMS.

    Provides:
    1. Full-text search across YAML content
    2. Dependency graph tracking
    3. Content statistics and health metrics
    4. Orphaned content detection
    5. Broken reference reporting
    """

    def __init__(
        self, world_data_path: str, file_manager=None, validation_service=None
    ):
        """
        Initialize the query service.

        Args:
            world_data_path: Path to world_data directory
            file_manager: Optional FileManager instance
            validation_service: Optional ValidationService instance
        """
        self.world_data_path = Path(world_data_path)
        self.file_manager = file_manager
        self.validation_service = validation_service

        # Dependency tracking
        self._dependency_graph: dict[tuple[str, str], DependencyGraph] = {}
        self._reverse_index: dict[tuple[str, str], set[tuple[str, str]]] = {}
        self._graph_built = False

    async def search(
        self, query: str, content_type: str | None = None, limit: int = 50
    ) -> list[SearchResult]:
        """
        Full-text search across YAML content.

        Args:
            query: Search query string
            content_type: Optional filter by content type
            limit: Maximum results to return

        Returns:
            List of SearchResult objects ordered by relevance
        """
        if not self.file_manager:
            return []

        results = []
        query_lower = query.lower()

        # Get all files or filtered by type
        files = await self.file_manager.list_files(content_type_filter=content_type)

        for file_info in files:
            try:
                # Read file content
                file_content = await self.file_manager.read_file(file_info.file_path)
                data = yaml.safe_load(file_content.content)

                if data is None:
                    continue

                # Determine primary ID field based on content type
                id_field = self._get_id_field(file_info.content_type)
                entity_id = data.get(id_field, "unknown")
                entity_name = data.get("name", entity_id)

                # Search in various fields
                searchable_fields = {
                    "id": entity_id,
                    "name": data.get("name", ""),
                    "description": data.get("description", ""),
                }

                # Add type-specific fields
                if file_info.content_type == "rooms":
                    searchable_fields["flavor_text"] = data.get("flavor_text", "")
                elif file_info.content_type == "quests":
                    searchable_fields["objectives"] = str(data.get("objectives", ""))

                # Check each field for matches
                for field_name, field_value in searchable_fields.items():
                    if query_lower in str(field_value).lower():
                        # Calculate score (exact match = higher, id match = highest)
                        score = 1.0
                        if (
                            field_name == "id"
                            and query_lower == str(field_value).lower()
                        ):
                            score = 10.0
                        elif query_lower == str(field_value).lower():
                            score = 5.0
                        elif str(field_value).lower().startswith(query_lower):
                            score = 3.0

                        # Extract context snippet
                        context = self._extract_context(str(field_value), query_lower)

                        results.append(
                            SearchResult(
                                content_type=file_info.content_type,
                                file_path=file_info.file_path,
                                entity_id=entity_id,
                                entity_name=entity_name,
                                match_field=field_name,
                                match_value=str(field_value)[
                                    :200
                                ],  # Truncate long values
                                context_snippet=context,
                                score=score,
                            )
                        )

            except Exception:
                # Skip files that fail to parse
                continue

        # Sort by score (descending) and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def _get_id_field(self, content_type: str) -> str:
        """Get the primary ID field name for a content type."""
        id_fields = {
            "classes": "class_id",
            "items": "item_id",
            "rooms": "room_id",
            "npcs": "npc_id",
            "abilities": "ability_id",
            "quests": "quest_id",
            "areas": "area_id",
            "dialogues": "dialogue_id",
            "factions": "faction_id",
            "triggers": "trigger_id",
            "quest_chains": "quest_chain_id",
            "npc_spawns": "spawn_id",
            "item_instances": "instance_id",
        }
        return id_fields.get(content_type, "id")

    def _extract_context(self, text: str, query: str, context_chars: int = 100) -> str:
        """Extract context snippet around the query match."""
        text_lower = text.lower()
        query_lower = query.lower()

        match_index = text_lower.find(query_lower)
        if match_index == -1:
            return text[:context_chars] + ("..." if len(text) > context_chars else "")

        # Extract context around match
        start = max(0, match_index - context_chars // 2)
        end = min(len(text), match_index + len(query) + context_chars // 2)

        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        return snippet

    async def build_dependency_graph(self):
        """
        Build the complete dependency graph by analyzing all content files.

        This indexes all relationships between entities for fast dependency lookups.
        """
        if not self.file_manager:
            return

        self._dependency_graph.clear()
        self._reverse_index.clear()

        # Get all files
        files = await self.file_manager.list_files()

        # Pass 1: Index all entities
        for file_info in files:
            try:
                file_content = await self.file_manager.read_file(file_info.file_path)
                data = yaml.safe_load(file_content.content)

                if data is None:
                    continue

                id_field = self._get_id_field(file_info.content_type)
                entity_id = data.get(id_field)

                if entity_id:
                    key = (file_info.content_type, entity_id)
                    self._dependency_graph[key] = DependencyGraph(
                        entity_type=file_info.content_type,
                        entity_id=entity_id,
                        entity_name=data.get("name", entity_id),
                    )

            except Exception:
                continue

        # Pass 2: Build dependency relationships
        for file_info in files:
            try:
                file_content = await self.file_manager.read_file(file_info.file_path)
                data = yaml.safe_load(file_content.content)

                if data is None:
                    continue

                id_field = self._get_id_field(file_info.content_type)
                entity_id = data.get(id_field)

                if not entity_id:
                    continue

                source_key = (file_info.content_type, entity_id)

                # Extract dependencies based on content type
                deps = self._extract_dependencies(
                    file_info.content_type, entity_id, data
                )

                for dep in deps:
                    # Add to source's outgoing dependencies
                    if source_key in self._dependency_graph:
                        self._dependency_graph[source_key].references.append(dep)

                    # Add to target's incoming dependencies
                    target_key = (dep.target_type, dep.target_id)
                    if target_key in self._dependency_graph:
                        self._dependency_graph[target_key].referenced_by.append(dep)

                    # Build reverse index
                    if target_key not in self._reverse_index:
                        self._reverse_index[target_key] = set()
                    self._reverse_index[target_key].add(source_key)

            except Exception:
                continue

        self._graph_built = True

    def _extract_dependencies(
        self, content_type: str, entity_id: str, data: dict[str, Any]
    ) -> list[Dependency]:
        """Extract all dependencies from an entity's data."""
        deps = []

        if content_type == "rooms":
            # Room exits
            if "exits" in data and isinstance(data["exits"], dict):
                for direction, room_id in data["exits"].items():
                    deps.append(
                        Dependency(
                            source_type=content_type,
                            source_id=entity_id,
                            target_type="rooms",
                            target_id=room_id,
                            relationship="exit",
                            field_path=f"exits.{direction}",
                        )
                    )

            # Area reference
            if "area_id" in data and data["area_id"]:
                deps.append(
                    Dependency(
                        source_type=content_type,
                        source_id=entity_id,
                        target_type="areas",
                        target_id=data["area_id"],
                        relationship="belongs_to_area",
                        field_path="area_id",
                    )
                )

        elif content_type == "classes":
            # Ability references
            if "available_abilities" in data and isinstance(
                data["available_abilities"], list
            ):
                for ability_id in data["available_abilities"]:
                    deps.append(
                        Dependency(
                            source_type=content_type,
                            source_id=entity_id,
                            target_type="abilities",
                            target_id=ability_id,
                            relationship="has_ability",
                            field_path="available_abilities",
                        )
                    )

        elif content_type == "npcs":
            # Faction reference
            if "faction_id" in data and data["faction_id"]:
                deps.append(
                    Dependency(
                        source_type=content_type,
                        source_id=entity_id,
                        target_type="factions",
                        target_id=data["faction_id"],
                        relationship="belongs_to_faction",
                        field_path="faction_id",
                    )
                )

            # Dialogue reference
            if "dialogue_id" in data and data["dialogue_id"]:
                deps.append(
                    Dependency(
                        source_type=content_type,
                        source_id=entity_id,
                        target_type="dialogues",
                        target_id=data["dialogue_id"],
                        relationship="has_dialogue",
                        field_path="dialogue_id",
                    )
                )

        elif content_type == "npc_spawns":
            # NPC template reference
            if "npc_id" in data and data["npc_id"]:
                deps.append(
                    Dependency(
                        source_type=content_type,
                        source_id=entity_id,
                        target_type="npcs",
                        target_id=data["npc_id"],
                        relationship="spawns_npc",
                        field_path="npc_id",
                    )
                )

            # Room reference
            if "room_id" in data and data["room_id"]:
                deps.append(
                    Dependency(
                        source_type=content_type,
                        source_id=entity_id,
                        target_type="rooms",
                        target_id=data["room_id"],
                        relationship="spawns_in_room",
                        field_path="room_id",
                    )
                )

        elif content_type == "quest_chains":
            # Quest references
            if "quests" in data and isinstance(data["quests"], list):
                for quest_id in data["quests"]:
                    deps.append(
                        Dependency(
                            source_type=content_type,
                            source_id=entity_id,
                            target_type="quests",
                            target_id=quest_id,
                            relationship="contains_quest",
                            field_path="quests",
                        )
                    )

        return deps

    async def get_dependencies(
        self, entity_type: str, entity_id: str
    ) -> DependencyGraph | None:
        """
        Get dependency information for a specific entity.

        Args:
            entity_type: Content type (e.g., "rooms", "items")
            entity_id: Entity identifier

        Returns:
            DependencyGraph if entity exists, None otherwise
        """
        if not self._graph_built:
            await self.build_dependency_graph()

        key = (entity_type, entity_id)
        return self._dependency_graph.get(key)

    async def get_analytics(self) -> ContentAnalytics:
        """
        Generate comprehensive content analytics.

        Returns:
            ContentAnalytics with health metrics and statistics
        """
        if not self._graph_built:
            await self.build_dependency_graph()

        analytics = ContentAnalytics()

        # Count entities by type
        for (entity_type, entity_id), graph in self._dependency_graph.items():
            analytics.total_entities += 1
            analytics.entities_by_type[entity_type] = (
                analytics.entities_by_type.get(entity_type, 0) + 1
            )

        # Find broken references and orphaned entities
        reference_counts: dict[tuple[str, str], int] = {}

        for (entity_type, entity_id), graph in self._dependency_graph.items():
            # Check for broken references
            for dep in graph.references:
                target_key = (dep.target_type, dep.target_id)
                if target_key not in self._dependency_graph:
                    analytics.broken_references.append(dep)

            # Track reference counts
            incoming_count = len(graph.referenced_by)
            reference_counts[(entity_type, entity_id)] = incoming_count

            # Detect orphaned entities (nothing references them)
            # Exclude certain types that are naturally orphaned
            if incoming_count == 0 and entity_type not in [
                "areas",
                "factions",
                "quest_chains",
            ]:
                analytics.orphaned_entities.append((entity_type, entity_id))

        # Calculate average references
        if analytics.total_entities > 0:
            total_refs = sum(reference_counts.values())
            analytics.average_references_per_entity = (
                total_refs / analytics.total_entities
            )

        # Find most referenced entities
        sorted_refs = sorted(reference_counts.items(), key=lambda x: x[1], reverse=True)
        analytics.most_referenced_entities = [
            (entity_type, entity_id, count)
            for (entity_type, entity_id), count in sorted_refs[:10]
            if count > 0
        ]

        return analytics

    def find_safe_to_delete(
        self, entity_type: str, entity_id: str
    ) -> tuple[bool, list[str]]:
        """
        Check if an entity can be safely deleted.

        Args:
            entity_type: Content type
            entity_id: Entity identifier

        Returns:
            Tuple of (is_safe, blocking_references)
            is_safe is False if other entities depend on this one
        """
        graph = self.get_dependencies(entity_type, entity_id)

        if not graph:
            return True, []

        if len(graph.referenced_by) == 0:
            return True, []

        # Build list of blocking references
        blocking_refs = []
        for dep in graph.referenced_by:
            blocking_refs.append(
                f"{dep.source_type}:{dep.source_id} ({dep.relationship} via {dep.field_path})"
            )

        return False, blocking_refs
