"""
Unit tests for SQLAlchemy database models.

Tests model creation, validation, relationships, and constraints.
"""

import time

import pytest
from sqlalchemy.exc import IntegrityError

from daemons.models import (
    AdminAction,
    Area,
    Clan,
    ClanMember,
    Faction,
    ItemInstance,
    ItemTemplate,
    NpcInstance,
    NpcTemplate,
    Player,
    PlayerInventory,
    Room,
    RoomType,
    SecurityEvent,
    UserAccount,
)

# ============================================================================
# Player Model Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_player_creation(db_session):
    """Test creating a basic player."""
    # Note: Room must exist for foreign key constraint
    room = Room(id="test_room_players", name="Test Room", description="A test room")
    db_session.add(room)
    await db_session.flush()

    player = Player(
        id="test_player_1",
        name="TestHero",
        current_room_id="test_room_players",
        character_class="warrior",
        level=1,
        experience=0,
        current_health=100,
        max_health=100,
        current_energy=50,
        max_energy=50,
    )

    db_session.add(player)
    await db_session.commit()
    await db_session.refresh(player)

    assert player.id == "test_player_1"
    assert player.name == "TestHero"
    assert player.level == 1
    assert player.current_health == 100


@pytest.mark.unit
@pytest.mark.asyncio
async def test_player_unique_player_id(db_session):
    """Test that player id must be unique."""
    room = Room(id="test_room_unique", name="Test Room", description="A test room")
    db_session.add(room)
    await db_session.flush()

    player1 = Player(
        id="duplicate_id",
        name="Player1",
        current_room_id="test_room_unique",
        character_class="warrior",
    )
    player2 = Player(
        id="duplicate_id",
        name="Player2",
        current_room_id="test_room_unique",
        character_class="mage",
    )

    db_session.add(player1)
    await db_session.commit()

    db_session.add(player2)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_player_nullable_fields(db_session):
    """Test that optional fields can be null."""
    room = Room(id="test_room_nullable", name="Test Room", description="A test room")
    db_session.add(room)
    await db_session.flush()

    player = Player(
        id="minimal_player",
        name="Minimal",
        current_room_id="test_room_nullable",
        character_class="adventurer",
    )

    db_session.add(player)
    await db_session.commit()
    await db_session.refresh(player)

    assert player.account_id is None


# ============================================================================
# Room Model Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_room_creation(db_session):
    """Test creating a basic room."""
    room = Room(
        id="test_room_1",
        name="Test Chamber",
        description="A simple test room",
        room_type="test",
    )

    db_session.add(room)
    await db_session.commit()
    await db_session.refresh(room)

    assert room.id == "test_room_1"
    assert room.name == "Test Chamber"
    assert room.room_type == "test"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_room_with_area(db_session):
    """Test room associated with an area."""
    area = Area(id="test_area", name="Test Area", description="A test area")

    room = Room(
        id="area_room_1",
        name="Room in Area",
        description="Part of test area",
        room_type="test",
        area_id="test_area",
    )

    db_session.add(area)
    db_session.add(room)
    await db_session.commit()
    await db_session.refresh(room)

    assert room.area_id == "test_area"


# ============================================================================
# RoomType Model Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_room_type_creation(db_session):
    """Test creating a room type."""
    room_type = RoomType(name="forest", emoji="🌲", description="A wooded area")

    db_session.add(room_type)
    await db_session.commit()
    await db_session.refresh(room_type)

    assert room_type.name == "forest"
    assert room_type.emoji == "🌲"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_room_type_unique_id(db_session):
    """Test that room_type name must be unique."""
    type1 = RoomType(name="urban", emoji="🏙️")
    type2 = RoomType(name="urban", emoji="🌆")

    db_session.add(type1)
    await db_session.commit()

    db_session.add(type2)
    with pytest.raises(IntegrityError):
        await db_session.commit()


# ============================================================================
# Item Model Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_item_template_creation(db_session):
    """Test creating an item template."""
    template = ItemTemplate(
        id="sword_001",
        name="Iron Sword",
        description="A sturdy iron sword",
        item_type="weapon",
        weight=5.0,
        value=100,
    )

    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    assert template.id == "sword_001"
    assert template.weight == 5.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_item_instance_creation(db_session):
    """Test creating an item instance from a template."""
    template = ItemTemplate(
        id="potion_001",
        name="Health Potion",
        description="Restores health",
        item_type="consumable",
        weight=0.5,
    )

    instance = ItemInstance(id="potion_inst_1", template_id="potion_001", quantity=3)

    db_session.add(template)
    db_session.add(instance)
    await db_session.commit()
    await db_session.refresh(instance)

    assert instance.template_id == "potion_001"
    assert instance.quantity == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_player_inventory_relationship(db_session):
    """Test player inventory relationship."""
    room = Room(id="inv_room", name="Inventory Test Room", description="Test")

    player = Player(
        id="inv_test_player",
        name="InvTest",
        current_room_id="inv_room",
        character_class="warrior",
    )

    inventory = PlayerInventory(
        player_id="inv_test_player", max_weight=100.0, max_slots=20
    )

    db_session.add(room)
    db_session.add(player)
    db_session.add(inventory)
    await db_session.commit()

    assert inventory.player_id == "inv_test_player"
    assert inventory.max_weight == 100.0


# ============================================================================
# NPC Model Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_npc_template_creation(db_session):
    """Test creating an NPC template."""
    template = NpcTemplate(
        id="goblin_001",
        name="Goblin Warrior",
        description="A hostile goblin",
        level=5,
        max_health=50,
    )

    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    assert template.id == "goblin_001"
    assert template.level == 5


@pytest.mark.unit
@pytest.mark.asyncio
async def test_npc_instance_creation(db_session):
    """Test creating an NPC instance."""
    room = Room(id="village_square", name="Village Square", description="Test")

    template = NpcTemplate(
        id="merchant_001",
        name="Village Merchant",
        description="Sells goods",
        level=1,
        max_health=100,
    )

    instance = NpcInstance(
        id="merchant_inst_1",
        template_id="merchant_001",
        room_id="village_square",
        spawn_room_id="village_square",
        current_health=100,
    )

    db_session.add(room)
    db_session.add(template)
    db_session.add(instance)
    await db_session.commit()
    await db_session.refresh(instance)

    assert instance.template_id == "merchant_001"
    assert instance.room_id == "village_square"


# ============================================================================
# Clan Model Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_clan_creation(db_session):
    """Test creating a clan."""
    room = Room(id="clan_room", name="Clan Room", description="Test")

    leader = Player(
        id="clan_leader",
        name="Leader",
        current_room_id="clan_room",
        character_class="warrior",
    )

    clan = Clan(
        id="test_clan",
        name="Test Guild",
        leader_id="clan_leader",
        description="A test guild",
        created_at=time.time(),
    )

    db_session.add(room)
    db_session.add(leader)
    db_session.add(clan)
    await db_session.commit()
    await db_session.refresh(clan)

    assert clan.name == "Test Guild"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_clan_member_relationship(db_session):
    """Test clan member relationship."""
    room = Room(id="clan_member_room", name="Member Room", description="Test")

    leader = Player(
        id="member_leader",
        name="MemberLeader",
        current_room_id="clan_member_room",
        character_class="warrior",
    )

    clan = Clan(
        id="clan_with_members",
        name="Member Test Clan",
        description="Testing members",
        leader_id="member_leader",
        created_at=time.time(),
    )

    player = Player(
        id="clan_member_1",
        name="Member1",
        current_room_id="clan_member_room",
        character_class="warrior",
    )

    member = ClanMember(
        id="member_entry_1",
        clan_id="clan_with_members",
        player_id="clan_member_1",
        rank="member",
        joined_at=time.time(),
    )

    db_session.add(room)
    db_session.add(leader)
    db_session.add(clan)
    db_session.add(player)
    db_session.add(member)
    await db_session.commit()

    assert member.clan_id == "clan_with_members"
    assert member.player_id == "clan_member_1"
    assert member.rank == "member"


# ============================================================================
# Faction Model Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_faction_creation(db_session):
    """Test creating a faction."""
    faction = Faction(
        id="test_faction",
        name="Test Faction",
        description="A test faction",
        created_at=time.time(),
    )

    db_session.add(faction)
    await db_session.commit()
    await db_session.refresh(faction)

    assert faction.name == "Test Faction"


# ============================================================================
# User Account Model Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_account_creation(db_session):
    """Test creating a user account."""
    user = UserAccount(
        id="user_001",
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.role == "player"  # Default value


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_unique_username(db_session):
    """Test that username must be unique."""
    user1 = UserAccount(
        id="user_dup_1",
        username="duplicate",
        email="user1@example.com",
        password_hash="hash1",
    )
    user2 = UserAccount(
        id="user_dup_2",
        username="duplicate",
        email="user2@example.com",
        password_hash="hash2",
    )

    db_session.add(user1)
    await db_session.commit()

    db_session.add(user2)
    with pytest.raises(IntegrityError):
        await db_session.commit()


# ============================================================================
# Security Event Model Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_security_event_creation(db_session):
    """Test creating a security event."""
    event = SecurityEvent(
        id="event_001",
        event_type="login_attempt",
        ip_address="192.168.1.1",
        timestamp=time.time(),
    )

    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    assert event.event_type == "login_attempt"
    assert event.timestamp is not None


# ============================================================================
# Admin Action Model Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_action_creation(db_session):
    """Test creating an admin action log."""
    action = AdminAction(
        id="action_001",
        admin_name="admin",
        action="player_ban",
        target_type="player",
        target_id="banned_player",
        details={"reason": "cheating"},
        timestamp=time.time(),
    )

    db_session.add(action)
    await db_session.commit()
    await db_session.refresh(action)

    assert action.action == "player_ban"
    assert action.details["reason"] == "cheating"
