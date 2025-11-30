"""
Unit tests for World data structures.

Tests WorldPlayer, WorldNpc, WorldRoom, World, and related structures.
"""

import pytest

from app.engine.world import (EntityType, TargetableType, World, WorldArea,
                              WorldNpc, WorldPlayer, WorldRoom)

# ============================================================================
# WorldPlayer Tests
# ============================================================================


@pytest.mark.unit
def test_world_player_creation():
    """Test creating a WorldPlayer with all required fields."""
    player = WorldPlayer(
        id="player_1",
        entity_type=EntityType.PLAYER,
        name="TestHero",
        room_id="room_void",
        current_health=100,
        max_health=100,
        current_energy=50,
        max_energy=50,
    )

    assert player.id == "player_1"
    assert player.name == "TestHero"
    assert player.entity_type == EntityType.PLAYER
    assert player.current_health == 100
    assert player.current_energy == 50
    assert player.level == 1  # Default
    assert not player.is_connected  # Default


@pytest.mark.unit
def test_world_player_is_alive():
    """Test the is_alive property."""
    player = WorldPlayer(
        id="player_2",
        entity_type=EntityType.PLAYER,
        name="AlivePlayer",
        room_id="room_void",
        current_health=50,
        max_health=100,
    )

    assert player.is_alive() is True

    player.current_health = 0
    assert player.is_alive() is False


@pytest.mark.unit
def test_world_player_entity_type():
    """Test that WorldPlayer has correct entity_type."""
    player = WorldPlayer(
        id="player_3",
        entity_type=EntityType.PLAYER,
        name="TypeTest",
        room_id="room_void",
    )

    assert player.entity_type == EntityType.PLAYER
    assert player.get_targetable_type() == TargetableType.PLAYER


@pytest.mark.unit
def test_world_player_keywords():
    """Test player keywords for targeting."""
    player = WorldPlayer(
        id="player_4",
        entity_type=EntityType.PLAYER,
        name="Aragorn",
        room_id="room_void",
        keywords=["ranger", "strider", "dunadan"],
    )

    assert "ranger" in player.keywords
    assert "strider" in player.keywords
    assert len(player.keywords) == 3


# ============================================================================
# WorldRoom Tests
# ============================================================================


@pytest.mark.unit
def test_world_room_creation():
    """Test creating a WorldRoom."""
    room = WorldRoom(
        id="room_test_1",
        name="Test Chamber",
        description="A test room for unit tests",
        room_type="test",
    )

    assert room.id == "room_test_1"
    assert room.name == "Test Chamber"
    assert room.room_type == "test"
    assert len(room.entities) == 0
    assert len(room.items) == 0


@pytest.mark.unit
def test_world_room_exits():
    """Test room exits dictionary."""
    room = WorldRoom(
        id="room_exits",
        name="Exit Test Room",
        description="Testing exits",
        exits={"north": "room_north", "south": "room_south"},
    )

    assert room.exits["north"] == "room_north"
    assert room.exits["south"] == "room_south"
    assert "east" not in room.exits


@pytest.mark.unit
def test_world_room_players_and_npcs():
    """Test that room tracks entities (players and NPCs)."""
    room = WorldRoom(
        id="room_with_entities", name="Entity Room", description="Has entities"
    )

    room.entities.add("player_1")
    room.entities.add("npc_1")

    assert "player_1" in room.entities
    assert "npc_1" in room.entities
    assert len(room.entities) == 2


@pytest.mark.unit
def test_world_room_items():
    """Test room item tracking."""
    room = WorldRoom(
        id="room_items",
        name="Item Room",
        description="Has items",
        items={"sword_1", "shield_1"},
    )

    assert "sword_1" in room.items
    assert "shield_1" in room.items
    assert len(room.items) == 2


# ============================================================================
# WorldNpc Tests
# ============================================================================


@pytest.mark.unit
def test_world_npc_creation():
    """Test creating a WorldNpc."""
    npc = WorldNpc(
        id="npc_goblin_1",
        entity_type=EntityType.NPC,
        name="Goblin Warrior",
        room_id="room_cave",
        current_health=50,
        max_health=50,
        template_id="npc_goblin",
    )

    assert npc.id == "npc_goblin_1"
    assert npc.name == "Goblin Warrior"
    assert npc.entity_type == EntityType.NPC
    assert npc.current_health == 50


@pytest.mark.unit
def test_world_npc_entity_type():
    """Test that WorldNpc has correct entity_type."""
    npc = WorldNpc(
        id="npc_test",
        entity_type=EntityType.NPC,
        name="Test NPC",
        room_id="room_void",
        template_id="npc_template",
    )

    assert npc.entity_type == EntityType.NPC
    assert npc.get_targetable_type() == TargetableType.NPC


@pytest.mark.unit
def test_world_npc_behaviors():
    """Test NPC instance_data attribute."""
    npc = WorldNpc(
        id="npc_with_data",
        entity_type=EntityType.NPC,
        name="Wandering Merchant",
        room_id="room_market",
        template_id="npc_merchant",
        instance_data={"custom_flag": True, "merchant_type": "traveling"},
    )

    assert npc.instance_data["custom_flag"] is True
    assert npc.instance_data["merchant_type"] == "traveling"
    assert len(npc.instance_data) == 2


# ============================================================================
# WorldArea Tests
# ============================================================================


@pytest.mark.unit
def test_world_area_creation():
    """Test creating a WorldArea."""
    from app.engine.world import WorldTime

    area = WorldArea(
        id="area_forest",
        name="Darkwood Forest",
        description="A mysterious forest",
        area_time=WorldTime(),
        danger_level=5,
    )

    assert area.id == "area_forest"
    assert area.name == "Darkwood Forest"
    assert area.danger_level == 5


@pytest.mark.unit
def test_world_area_time_system():
    """Test area time system properties."""
    from app.engine.world import WorldTime

    area_time = WorldTime(day=1, hour=12, minute=0)
    area = WorldArea(
        id="area_time_test",
        name="Time Test Area",
        description="For testing time",
        area_time=area_time,
        time_scale=2.0,  # Double speed
    )

    assert area.time_scale == 2.0
    assert area.area_time.hour == 12
    assert area.area_time.minute == 0


# ============================================================================
# World Tests
# ============================================================================


@pytest.mark.unit
def test_world_creation():
    """Test creating a World instance."""
    world = World(rooms={}, players={})

    assert len(world.rooms) == 0
    assert len(world.players) == 0
    assert len(world.npcs) == 0
    assert len(world.areas) == 0


@pytest.mark.unit
def test_world_add_player():
    """Test adding a player to the world."""
    world = World(rooms={}, players={})

    player = WorldPlayer(
        id="p1", entity_type=EntityType.PLAYER, name="Hero", room_id="r1"
    )

    world.players["p1"] = player

    assert "p1" in world.players
    assert world.players["p1"].name == "Hero"


@pytest.mark.unit
def test_world_add_room():
    """Test adding a room to the world."""
    world = World(rooms={}, players={})

    room = WorldRoom(id="r1", name="Test Room", description="A test")

    world.rooms["r1"] = room

    assert "r1" in world.rooms
    assert world.rooms["r1"].name == "Test Room"


@pytest.mark.unit
def test_world_add_npc():
    """Test adding an NPC to the world."""
    world = World(rooms={}, players={})

    npc = WorldNpc(
        id="n1",
        entity_type=EntityType.NPC,
        name="Guard",
        room_id="r1",
        template_id="npc_guard",
    )

    world.npcs["n1"] = npc

    assert "n1" in world.npcs
    assert world.npcs["n1"].name == "Guard"


# ============================================================================
# Utility Function Tests
# ============================================================================


@pytest.mark.unit
def test_entity_id_comparison():
    """Test comparing entity IDs."""
    player1 = WorldPlayer(
        id="same_id", entity_type=EntityType.PLAYER, name="Player1", room_id="r1"
    )
    player2 = WorldPlayer(
        id="same_id", entity_type=EntityType.PLAYER, name="Player2", room_id="r2"
    )

    assert player1.id == player2.id
    assert player1 != player2  # Different objects


@pytest.mark.unit
def test_targetable_protocol_compliance():
    """Test that entities implement the Targetable protocol."""
    player = WorldPlayer(
        id="p1",
        entity_type=EntityType.PLAYER,
        name="Hero",
        room_id="r1",
        keywords=["hero", "warrior"],
    )

    # Check Targetable protocol attributes
    assert hasattr(player, "id")
    assert hasattr(player, "name")
    assert hasattr(player, "room_id")
    assert hasattr(player, "keywords")
    assert hasattr(player, "get_description")
    assert hasattr(player, "get_targetable_type")

    assert player.get_targetable_type() == TargetableType.PLAYER
