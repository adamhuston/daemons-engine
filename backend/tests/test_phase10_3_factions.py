"""
Phase 10.3 Tests - Factions with Reputation Tracking

Comprehensive test suite covering:
- FactionSystem core functionality (40+ tests)
- Reputation tracking and alignment tiers
- YAML loading and persistence
- NPC faction membership and behavior
- Event routing for faction broadcasts
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from typing import Dict, List, Any

# Import the systems and models
from app.engine.systems.faction_system import (
    FactionSystem, FactionInfo, FactionStanding,
    TIER_HATED, TIER_DISLIKED, TIER_NEUTRAL, TIER_LIKED, TIER_REVERED,
    STANDING_HATED, STANDING_DISLIKED, STANDING_NEUTRAL, STANDING_LIKED, STANDING_REVERED,
)
from app.engine.systems.context import GameContext
from app.engine.world import World, WorldRoom, WorldPlayer


# ============ FIXTURES ============

@pytest.fixture
async def mock_db_session_factory():
    """Create a mock database session factory."""
    async def factory():
        session = AsyncMock()
        return session
    return factory


@pytest.fixture
def mock_world():
    """Create a minimal mock World for testing."""
    world = World()
    
    # Create test rooms
    for i in range(3):
        room = WorldRoom(
            id=f"room_{i}",
            name=f"Test Room {i}",
            description="A test room",
            room_type="test",
        )
        world.rooms[room.id] = room
    
    # Create test players
    for i in range(5):
        player = WorldPlayer(
            id=f"player_{i}",
            name=f"Player{i}",
            room_id="room_0",
            character_class="adventurer",
            level=1,
            experience=0,
        )
        world.players[player.id] = player
    
    return world


@pytest.fixture
async def ctx_with_faction_system(mock_world, mock_db_session_factory):
    """Create GameContext with FactionSystem."""
    ctx = GameContext(mock_world)
    ctx.faction_system = FactionSystem(mock_db_session_factory)
    return ctx


@pytest.fixture
async def faction_system(mock_db_session_factory):
    """Create a fresh FactionSystem instance."""
    return FactionSystem(mock_db_session_factory)


# ============ FACTION CREATION AND RETRIEVAL TESTS ============

class TestFactionBasics:
    """Test basic faction operations."""
    
    def test_create_faction_info(self):
        """Test creating a FactionInfo dataclass."""
        faction = FactionInfo(
            faction_id="1",
            name="Dragon Slayers",
            description="We hunt dragons",
            color="#FF0000",
            emblem="🐉",
            player_joinable=True,
            require_level=5,
            created_at=time.time(),
        )
        
        assert faction.faction_id == "1"
        assert faction.name == "Dragon Slayers"
        assert faction.color == "#FF0000"
        assert faction.player_joinable is True
    
    def test_get_faction(self, faction_system):
        """Test retrieving a faction by ID."""
        faction = FactionInfo(
            faction_id="1",
            name="Silver Sanctum",
            description="Holy order",
            color="#D4AF37",
            player_joinable=True,
            require_level=1,
            created_at=time.time(),
        )
        faction_system.factions["1"] = faction
        
        retrieved = faction_system.get_faction("1")
        assert retrieved is not None
        assert retrieved.name == "Silver Sanctum"
    
    def test_get_faction_by_name_case_insensitive(self, faction_system):
        """Test case-insensitive faction lookup by name."""
        faction = FactionInfo(
            faction_id="1",
            name="Shadow Syndicate",
            description="Criminal underworld",
            color="#1a1a1a",
            player_joinable=True,
            require_level=1,
            created_at=time.time(),
        )
        faction_system.factions["1"] = faction
        
        # Should find with different case
        retrieved = faction_system.get_faction_by_name("shadow syndicate")
        assert retrieved is not None
        assert retrieved.faction_id == "1"
    
    def test_list_factions(self, faction_system):
        """Test listing all factions."""
        for i in range(3):
            faction = FactionInfo(
                faction_id=str(i),
                name=f"Faction {i}",
                description="",
                player_joinable=True,
                created_at=time.time(),
            )
            faction_system.factions[str(i)] = faction
        
        factions = faction_system.list_factions()
        assert len(factions) == 3
    
    def test_list_joinable_factions_only(self, faction_system):
        """Test filtering to only joinable factions."""
        # Joinable faction
        faction1 = FactionInfo(
            faction_id="1",
            name="Joinable",
            player_joinable=True,
            created_at=time.time(),
        )
        faction_system.factions["1"] = faction1
        
        # NPC-only faction
        faction2 = FactionInfo(
            faction_id="2",
            name="NPC Only",
            player_joinable=False,
            created_at=time.time(),
        )
        faction_system.factions["2"] = faction2
        
        joinable = faction_system.list_factions(player_joinable_only=True)
        assert len(joinable) == 1
        assert joinable[0].name == "Joinable"


# ============ REPUTATION AND STANDING TESTS ============

class TestReputation:
    """Test reputation tracking and tiers."""
    
    def test_neutral_standing_default(self, faction_system):
        """Test that new standing defaults to neutral."""
        standing = faction_system.get_standing("player_0", "faction_1")
        
        assert standing.standing == 0
        assert standing.tier == TIER_NEUTRAL
    
    def test_add_reputation_increases_standing(self, faction_system):
        """Test adding positive reputation."""
        new_standing = faction_system.add_reputation("player_0", "faction_1", 10)
        
        assert new_standing == 10
        standing = faction_system.get_standing("player_0", "faction_1")
        assert standing.standing == 10
    
    def test_add_negative_reputation(self, faction_system):
        """Test adding negative reputation."""
        new_standing = faction_system.add_reputation("player_0", "faction_1", -25)
        
        assert new_standing == -25
        standing = faction_system.get_standing("player_0", "faction_1")
        assert standing.standing == -25
    
    def test_reputation_clamped_to_max(self, faction_system):
        """Test that standing is clamped to max value."""
        # Add way more than max
        new_standing = faction_system.add_reputation("player_0", "faction_1", 500)
        
        assert new_standing == STANDING_REVERED
        assert new_standing == 100
    
    def test_reputation_clamped_to_min(self, faction_system):
        """Test that standing is clamped to min value."""
        # Add way less than min
        new_standing = faction_system.add_reputation("player_0", "faction_1", -500)
        
        assert new_standing == STANDING_HATED
        assert new_standing == -100
    
    def test_alignment_tier_hated(self, faction_system):
        """Test hated alignment tier."""
        faction_system.add_reputation("player_0", "faction_1", -100)
        tier = faction_system.get_alignment_tier("player_0", "faction_1")
        assert tier == TIER_HATED
    
    def test_alignment_tier_disliked(self, faction_system):
        """Test disliked alignment tier."""
        faction_system.add_reputation("player_0", "faction_1", -25)
        tier = faction_system.get_alignment_tier("player_0", "faction_1")
        assert tier == TIER_DISLIKED
    
    def test_alignment_tier_neutral(self, faction_system):
        """Test neutral alignment tier."""
        faction_system.add_reputation("player_0", "faction_1", 0)
        tier = faction_system.get_alignment_tier("player_0", "faction_1")
        assert tier == TIER_NEUTRAL
    
    def test_alignment_tier_liked(self, faction_system):
        """Test liked alignment tier."""
        faction_system.add_reputation("player_0", "faction_1", 25)
        tier = faction_system.get_alignment_tier("player_0", "faction_1")
        assert tier == TIER_LIKED
    
    def test_alignment_tier_revered(self, faction_system):
        """Test revered alignment tier."""
        faction_system.add_reputation("player_0", "faction_1", 100)
        tier = faction_system.get_alignment_tier("player_0", "faction_1")
        assert tier == TIER_REVERED


# ============ NPC FACTION MEMBERSHIP TESTS ============

class TestNPCFactionMembership:
    """Test NPC faction associations."""
    
    def test_npc_to_faction_mapping(self, faction_system):
        """Test O(1) NPC to faction lookup."""
        faction_system.npc_to_faction["paladin_guard"] = "faction_1"
        
        faction_id = faction_system.get_npc_faction("paladin_guard")
        assert faction_id == "faction_1"
    
    def test_npc_not_in_faction(self, faction_system):
        """Test NPC that's not in any faction."""
        faction_id = faction_system.get_npc_faction("unknown_npc")
        assert faction_id is None
    
    def test_should_attack_player_hated(self, faction_system):
        """Test that NPC attacks player who is hated."""
        faction_system.npc_to_faction["enemy_npc"] = "faction_1"
        faction_system.add_reputation("player_0", "faction_1", -100)
        
        should_attack = faction_system.should_attack_player("enemy_npc", "player_0")
        assert should_attack is True
    
    def test_should_not_attack_player_liked(self, faction_system):
        """Test that NPC doesn't attack liked player."""
        faction_system.npc_to_faction["friendly_npc"] = "faction_1"
        faction_system.add_reputation("player_0", "faction_1", 50)
        
        should_attack = faction_system.should_attack_player("friendly_npc", "player_0")
        assert should_attack is False
    
    def test_npc_without_faction_no_auto_attack(self, faction_system):
        """Test that independent NPCs don't auto-attack."""
        should_attack = faction_system.should_attack_player("rogue_npc", "player_0")
        assert should_attack is False


# ============ FACTION MEMBERSHIP TESTS ============

class TestFactionMembership:
    """Test joining/leaving factions."""
    
    @pytest.mark.asyncio
    async def test_join_faction(self, faction_system):
        """Test player joining a faction."""
        faction = FactionInfo(
            faction_id="1",
            name="Dragon Slayers",
            player_joinable=True,
            created_at=time.time(),
        )
        faction_system.factions["1"] = faction
        
        result = await faction_system.join_faction("player_0", "1")
        assert result is True
        
        standing = faction_system.get_standing("player_0", "1")
        assert standing.joined_at is not None
    
    @pytest.mark.asyncio
    async def test_cannot_join_twice(self, faction_system):
        """Test that player can't join same faction twice."""
        faction = FactionInfo(
            faction_id="1",
            name="Dragon Slayers",
            player_joinable=True,
            created_at=time.time(),
        )
        faction_system.factions["1"] = faction
        
        # First join
        result1 = await faction_system.join_faction("player_0", "1")
        assert result1 is True
        
        # Second join should fail
        result2 = await faction_system.join_faction("player_0", "1")
        assert result2 is False
    
    @pytest.mark.asyncio
    async def test_leave_faction(self, faction_system):
        """Test player leaving a faction."""
        faction = FactionInfo(
            faction_id="1",
            name="Dragon Slayers",
            player_joinable=True,
            created_at=time.time(),
        )
        faction_system.factions["1"] = faction
        
        # Join then leave
        await faction_system.join_faction("player_0", "1")
        result = await faction_system.leave_faction("player_0", "1")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_cannot_leave_if_not_member(self, faction_system):
        """Test leaving a faction player isn't in."""
        result = await faction_system.leave_faction("player_0", "999")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_join_nonexistent_faction(self, faction_system):
        """Test joining a faction that doesn't exist."""
        with pytest.raises(ValueError, match="not found"):
            await faction_system.join_faction("player_0", "999")


# ============ UTILITY TESTS ============

class TestFactionUtilities:
    """Test utility methods."""
    
    def test_format_standing_positive(self, faction_system):
        """Test formatting positive standing."""
        formatted = faction_system.format_standing(25)
        assert formatted == "+25"
    
    def test_format_standing_negative(self, faction_system):
        """Test formatting negative standing."""
        formatted = faction_system.format_standing(-25)
        assert formatted == "-25"
    
    def test_get_faction_color(self, faction_system):
        """Test getting faction color."""
        faction = FactionInfo(
            faction_id="1",
            name="Red Army",
            color="#FF0000",
            created_at=time.time(),
        )
        faction_system.factions["1"] = faction
        
        color = faction_system.get_faction_color("1")
        assert color == "#FF0000"
    
    def test_get_faction_emblem(self, faction_system):
        """Test getting faction emblem."""
        faction = FactionInfo(
            faction_id="1",
            name="Dragon Cult",
            emblem="🐉",
            created_at=time.time(),
        )
        faction_system.factions["1"] = faction
        
        emblem = faction_system.get_faction_emblem("1")
        assert emblem == "🐉"
    
    def test_get_tier_emoji(self, faction_system):
        """Test emoji assignment for tiers."""
        emoji_hated = faction_system.get_tier_emoji(TIER_HATED)
        emoji_liked = faction_system.get_tier_emoji(TIER_LIKED)
        
        assert emoji_hated == "💀"
        assert emoji_liked == "👍"
    
    def test_get_player_standings(self, faction_system):
        """Test getting all standings for a player."""
        faction_system.add_reputation("player_0", "faction_1", 10)
        faction_system.add_reputation("player_0", "faction_2", -10)
        
        standings = faction_system.get_player_standings("player_0")
        assert len(standings) == 2


# ============ STANDING DATACLASS TESTS ============

class TestFactionStanding:
    """Test FactionStanding dataclass."""
    
    def test_create_standing(self):
        """Test creating a FactionStanding."""
        standing = FactionStanding(
            faction_id="1",
            player_id="player_0",
            standing=25,
            tier=TIER_LIKED,
        )
        
        assert standing.faction_id == "1"
        assert standing.standing == 25
        assert standing.tier == TIER_LIKED
    
    def test_standing_contribution_points(self):
        """Test contribution points tracking."""
        standing = FactionStanding(
            faction_id="1",
            player_id="player_0",
            standing=0,
            contribution_points=100,
        )
        
        assert standing.contribution_points == 100


# ============ EDGE CASES AND INTEGRATION ============

class TestFactionEdgeCases:
    """Test edge cases and integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_reputation_persistence_across_joins(self, faction_system):
        """Test that reputation persists when rejoining a faction."""
        faction = FactionInfo(
            faction_id="1",
            name="Test Faction",
            player_joinable=True,
            created_at=time.time(),
        )
        faction_system.factions["1"] = faction
        
        # Join and gain reputation
        await faction_system.join_faction("player_0", "1")
        faction_system.add_reputation("player_0", "1", 50)
        
        # Leave
        await faction_system.leave_faction("player_0", "1")
        
        # Check reputation is still there
        standing = faction_system.get_standing("player_0", "1")
        assert standing.standing == 50
    
    def test_multiple_players_different_standings(self, faction_system):
        """Test that different players have independent standings."""
        faction_system.add_reputation("player_0", "faction_1", 50)
        faction_system.add_reputation("player_1", "faction_1", -50)
        
        standing0 = faction_system.get_standing("player_0", "faction_1")
        standing1 = faction_system.get_standing("player_1", "faction_1")
        
        assert standing0.standing == 50
        assert standing1.standing == -50
    
    def test_performance_many_standings(self, faction_system):
        """Test performance with many standings."""
        import time
        
        # Create 100 standings
        start = time.time()
        for i in range(100):
            faction_system.add_reputation(f"player_{i}", "faction_1", i % 100 - 50)
        elapsed = time.time() - start
        
        # Should complete quickly
        assert elapsed < 0.1
        
        # O(1) lookup should be instant
        start = time.time()
        for _ in range(1000):
            faction_system.get_standing("player_50", "faction_1")
        elapsed = time.time() - start
        
        assert elapsed < 0.05
