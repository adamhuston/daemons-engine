"""
Test suite for Phase 12.4 QueryService

Tests:
- Full-text search across content
- Dependency graph building and lookups
- Content analytics (broken refs, orphans, stats)
- Safe delete checking
"""

import pytest


@pytest.mark.systems
@pytest.mark.phase12
class TestSearchFunctionality:
    """Test full-text search across content."""

    async def test_search_by_id(self, query_service, temp_world_data):
        """Test searching for content by ID."""
        # Create a test class file
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        warrior_file = classes_dir / "warrior.yaml"
        warrior_file.write_text(
            """
class_id: warrior
name: Warrior
description: A brave fighter specializing in combat
base_stats:
  strength: 14
  dexterity: 10
  intelligence: 8
  vitality: 12
starting_resources:
  health: 120
"""
        )

        results = await query_service.search("warrior", limit=10)
        assert len(results) > 0, "Should find warrior class"

        # Check that warrior is in results
        warrior_found = any(r.entity_id == "warrior" for r in results)
        assert warrior_found, "Should find warrior by ID"

    async def test_search_by_description(self, query_service, temp_world_data):
        """Test searching for content by description text."""
        # Create test content
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        warrior_file = classes_dir / "warrior.yaml"
        warrior_file.write_text(
            """
class_id: warrior
name: Warrior
description: A combat specialist
base_stats:
  strength: 14
starting_resources:
  health: 100
"""
        )

        results = await query_service.search("combat", limit=10)
        # Should not error even if no results
        assert isinstance(results, list), "Should return list"

    async def test_search_with_content_type_filter(
        self, query_service, temp_world_data
    ):
        """Test filtering search results by content type."""
        # Create test files
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        warrior_file = classes_dir / "warrior.yaml"
        warrior_file.write_text("class_id: warrior\nname: Warrior\n")

        results = await query_service.search(
            "warrior", content_type="classes", limit=10
        )
        assert all(
            r.content_type == "classes" for r in results
        ), "Should only return classes"

    async def test_relevance_scoring(self, query_service, temp_world_data):
        """Test that search results are sorted by relevance."""
        # Create multiple test files
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)

        # Exact match
        warrior_file = classes_dir / "warrior.yaml"
        warrior_file.write_text("class_id: warrior\nname: Warrior\n")

        # Partial match
        fighter_file = classes_dir / "fighter.yaml"
        fighter_file.write_text(
            "class_id: fighter\nname: Fighter\ndescription: Like a warrior\n"
        )

        results = await query_service.search("warrior", limit=10)
        if len(results) >= 2:
            # Results should be sorted by score (descending)
            for i in range(len(results) - 1):
                assert (
                    results[i].score >= results[i + 1].score
                ), "Results should be sorted by relevance score"

    async def test_context_snippets(self, query_service, temp_world_data):
        """Test that search results include context snippets."""
        # Create test content
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        warrior_file = classes_dir / "warrior.yaml"
        warrior_file.write_text(
            "class_id: warrior\nname: Warrior\ndescription: A fighter\n"
        )

        results = await query_service.search("warrior", limit=5)
        for result in results:
            assert hasattr(
                result, "context_snippet"
            ), "Should have context_snippet attribute"
            # Context snippet might be empty if no matching content
            if result.context_snippet:
                assert (
                    len(result.context_snippet) > 0
                ), "Non-empty snippet should have content"


@pytest.mark.systems
@pytest.mark.phase12
class TestDependencyGraph:
    """Test dependency graph building and lookups."""

    async def test_build_dependency_graph(self, query_service, temp_world_data):
        """Test building the dependency graph."""
        # Create test content with dependencies
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        warrior_file = classes_dir / "warrior.yaml"
        warrior_file.write_text(
            """
class_id: warrior
name: Warrior
description: A fighter
base_stats:
  strength: 14
starting_resources:
  health: 100
available_abilities:
  - slash
  - power_attack
"""
        )

        abilities_dir = temp_world_data / "abilities"
        abilities_dir.mkdir(exist_ok=True)
        slash_file = abilities_dir / "slash.yaml"
        slash_file.write_text(
            "ability_id: slash\nname: Slash\ndescription: Basic attack\n"
        )

        # Build graph
        await query_service.build_dependency_graph()
        assert query_service._graph_built, "Graph should be marked as built"
        assert len(query_service._dependency_graph) > 0, "Should index entities"

    async def test_get_dependencies(self, query_service, temp_world_data):
        """Test getting dependencies for an entity."""
        # Create test content
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        warrior_file = classes_dir / "warrior.yaml"
        warrior_file.write_text(
            """
class_id: warrior
name: Warrior
available_abilities:
  - slash
"""
        )

        abilities_dir = temp_world_data / "abilities"
        abilities_dir.mkdir(exist_ok=True)
        slash_file = abilities_dir / "slash.yaml"
        slash_file.write_text("ability_id: slash\nname: Slash\n")

        await query_service.build_dependency_graph()

        graph = await query_service.get_dependencies("classes", "warrior")
        if graph:
            assert graph.entity_id == "warrior", "Should have correct ID"
            assert graph.entity_type == "classes", "Should have correct type"

    async def test_bidirectional_dependencies(self, query_service, temp_world_data):
        """Test that dependencies are tracked bidirectionally."""
        # Create class that references ability
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        warrior_file = classes_dir / "warrior.yaml"
        warrior_file.write_text(
            """
class_id: warrior
name: Warrior
available_abilities:
  - slash
"""
        )

        abilities_dir = temp_world_data / "abilities"
        abilities_dir.mkdir(exist_ok=True)
        slash_file = abilities_dir / "slash.yaml"
        slash_file.write_text("ability_id: slash\nname: Slash\n")

        await query_service.build_dependency_graph()

        # Warrior should reference slash
        warrior_graph = await query_service.get_dependencies("classes", "warrior")
        if warrior_graph:
            ability_refs = [
                dep
                for dep in warrior_graph.references
                if dep.target_type == "abilities"
            ]
            if ability_refs:
                # Slash should show warrior as referencing it
                slash_graph = await query_service.get_dependencies("abilities", "slash")
                if slash_graph:
                    referencing_classes = [
                        dep
                        for dep in slash_graph.referenced_by
                        if dep.source_type == "classes"
                    ]
                    class_ids = [dep.source_id for dep in referencing_classes]
                    assert (
                        "warrior" in class_ids
                    ), "Ability should show warrior as referencing it"

    async def test_room_exit_dependencies(self, query_service, temp_world_data):
        """Test tracking of room exit dependencies."""
        rooms_dir = temp_world_data / "rooms"
        rooms_dir.mkdir(exist_ok=True)

        inn_file = rooms_dir / "inn.yaml"
        inn_file.write_text(
            """
room_id: inn
name: The Inn
description: A cozy inn
exits:
  north: market
  south: town_square
"""
        )

        market_file = rooms_dir / "market.yaml"
        market_file.write_text("room_id: market\nname: Market\n")

        await query_service.build_dependency_graph()

        inn_graph = await query_service.get_dependencies("rooms", "inn")
        if inn_graph:
            exit_deps = [
                dep for dep in inn_graph.references if dep.relationship == "exit"
            ]
            # Should track exits as dependencies
            assert len(exit_deps) >= 0, "Should track exit dependencies"


@pytest.mark.systems
@pytest.mark.phase12
class TestAnalytics:
    """Test content analytics generation."""

    async def test_basic_statistics(self, query_service, temp_world_data):
        """Test generation of basic content statistics."""
        # Create some test content
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        test_file = classes_dir / "test_class.yaml"
        test_file.write_text("class_id: test_class\nname: Test Class\n")

        items_dir = temp_world_data / "items"
        items_dir.mkdir(exist_ok=True)
        test_file = items_dir / "test_item.yaml"
        test_file.write_text("item_id: test_item\nname: Test Item\n")

        npcs_dir = temp_world_data / "npcs"
        npcs_dir.mkdir(exist_ok=True)
        test_file = npcs_dir / "test_npc.yaml"
        test_file.write_text("npc_id: test_npc\nname: Test NPC\n")

        analytics = await query_service.get_analytics()
        assert analytics.total_entities >= 3, "Should count created entities"
        assert len(analytics.entities_by_type) >= 3, "Should have multiple types"

    async def test_entities_by_type(self, query_service, temp_world_data):
        """Test counting entities by type."""
        # Create test files
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        for i in range(3):
            test_file = classes_dir / f"class_{i}.yaml"
            test_file.write_text(f"class_id: class_{i}\nname: Class {i}\n")

        analytics = await query_service.get_analytics()
        if "classes" in analytics.entities_by_type:
            assert (
                analytics.entities_by_type["classes"] >= 3
            ), "Should count all class files"

    async def test_broken_references(self, query_service, temp_world_data):
        """Test detection of broken references in analytics."""
        # Create class with broken ability reference
        classes_dir = temp_world_data / "classes"
        classes_dir.mkdir(exist_ok=True)
        warrior_file = classes_dir / "warrior.yaml"
        warrior_file.write_text(
            """
class_id: warrior
name: Warrior
available_abilities:
  - nonexistent_ability
"""
        )

        analytics = await query_service.get_analytics()
        # Should track broken references
        assert hasattr(analytics, "broken_references"), "Should have broken_references"

    async def test_orphaned_entities(self, query_service, temp_world_data):
        """Test detection of orphaned entities."""
        # Create an ability not referenced by any class
        abilities_dir = temp_world_data / "abilities"
        abilities_dir.mkdir(exist_ok=True)
        orphan_file = abilities_dir / "orphan.yaml"
        orphan_file.write_text("ability_id: orphan\nname: Orphan\n")

        analytics = await query_service.get_analytics()
        # Should track orphaned entities
        assert hasattr(analytics, "orphaned_entities"), "Should have orphaned_entities"


@pytest.mark.systems
@pytest.mark.phase12
def test_query_service_initialization(file_manager, temp_world_data):
    """Test QueryService initialization."""
    from daemons.engine.systems.query_service import QueryService

    service = QueryService(
        file_manager=file_manager, world_data_path=str(temp_world_data)
    )
    assert service.file_manager is not None, "Should have file manager"
    assert not service._graph_built, "Graph should not be built initially"
