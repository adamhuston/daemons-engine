"""
Clan System for Phase 10.2

Manages persistent player clans with:
- Leader and officer hierarchy
- Rank-based permissions
- Clan experience and leveling
- Database persistence
- Member contribution tracking

Design:
- O(1) clan lookups via clan_id_map
- O(n) member operations (typically small groups)
- Async DB loading and saving
- Rank-based permission enforcement
"""

import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession


RANK_LEADER = "leader"
RANK_OFFICER = "officer"
RANK_MEMBER = "member"
RANK_INITIATE = "initiate"

RANK_HIERARCHY = {
    RANK_LEADER: 4,
    RANK_OFFICER: 3,
    RANK_MEMBER: 2,
    RANK_INITIATE: 1,
}


@dataclass
class ClanMemberInfo:
    """In-memory representation of a clan member."""
    player_id: str
    rank: str
    joined_at: float
    contribution_points: int = 0


@dataclass
class ClanInfo:
    """In-memory representation of a clan."""
    clan_id: str
    name: str
    leader_id: str
    description: str = ""
    level: int = 1
    experience: int = 0
    created_at: float = None
    members: Dict[str, ClanMemberInfo] = None
    
    def __post_init__(self):
        if self.members is None:
            self.members = {}
        if self.created_at is None:
            self.created_at = time.time()
    
    def member_count(self) -> int:
        return len(self.members)
    
    def has_member(self, player_id: str) -> bool:
        return player_id in self.members
    
    def get_member(self, player_id: str) -> Optional[ClanMemberInfo]:
        return self.members.get(player_id)


class ClanSystem:
    """
    Manages all persistent player clans.
    
    Maintains two index structures:
    - clans: Dict[clan_id, ClanInfo] - All clans by ID
    - player_clan_map: Dict[player_id, clan_id] - Player → clan mapping
    
    Requires async DB session factory for persistence.
    """
    
    def __init__(self, db_session_factory: callable):
        self.clans: Dict[str, ClanInfo] = {}
        self.player_clan_map: Dict[str, str] = {}  # player_id -> clan_id
        self.db_session_factory = db_session_factory
    
    async def load_clans_from_db(self) -> int:
        """
        Load all clans from database into memory.
        
        Returns:
            Number of clans loaded
        """
        from app.models import Clan, ClanMember
        
        async with self.db_session_factory() as session:
            # Load all clans
            result = await session.execute(select(Clan))
            clan_rows = result.scalars().all()
            
            for clan_row in clan_rows:
                clan_info = ClanInfo(
                    clan_id=clan_row.id,
                    name=clan_row.name,
                    leader_id=clan_row.leader_id,
                    description=clan_row.description or "",
                    level=clan_row.level,
                    experience=clan_row.experience,
                    created_at=clan_row.created_at,
                )
                self.clans[clan_row.id] = clan_info
            
            # Load all clan members
            result = await session.execute(select(ClanMember))
            member_rows = result.scalars().all()
            
            for member_row in member_rows:
                clan_info = self.clans.get(member_row.clan_id)
                if clan_info:
                    member = ClanMemberInfo(
                        player_id=member_row.player_id,
                        rank=member_row.rank,
                        joined_at=member_row.joined_at,
                        contribution_points=member_row.contribution_points,
                    )
                    clan_info.members[member_row.player_id] = member
                    self.player_clan_map[member_row.player_id] = member_row.clan_id
        
        return len(self.clans)
    
    async def create_clan(self, name: str, leader_id: str, description: str = "") -> ClanInfo:
        """
        Create a new clan and persist to DB.
        
        Args:
            name: Clan name (must be unique)
            leader_id: UUID of clan founder/leader
            description: Optional clan description
            
        Returns:
            ClanInfo object
            
        Raises:
            ValueError: If name taken or leader already in a clan
        """
        from app.models import Clan, ClanMember
        
        if leader_id in self.player_clan_map:
            raise ValueError(f"Player {leader_id} is already in a clan")
        
        if any(c.name == name for c in self.clans.values()):
            raise ValueError(f"Clan name '{name}' already exists")
        
        clan_id = str(uuid.uuid4())
        created_at = time.time()
        
        # Create in-memory representation
        clan_info = ClanInfo(
            clan_id=clan_id,
            name=name,
            leader_id=leader_id,
            description=description,
            created_at=created_at,
        )
        
        # Add leader as member
        leader_member = ClanMemberInfo(
            player_id=leader_id,
            rank=RANK_LEADER,
            joined_at=created_at,
        )
        clan_info.members[leader_id] = leader_member
        self.clans[clan_id] = clan_info
        self.player_clan_map[leader_id] = clan_id
        
        # Persist to DB
        async with self.db_session_factory() as session:
            clan = Clan(
                id=clan_id,
                name=name,
                leader_id=leader_id,
                description=description,
                level=1,
                experience=0,
                created_at=created_at,
            )
            session.add(clan)
            
            member = ClanMember(
                id=str(uuid.uuid4()),
                clan_id=clan_id,
                player_id=leader_id,
                rank=RANK_LEADER,
                joined_at=created_at,
                contribution_points=0,
            )
            session.add(member)
            await session.commit()
        
        return clan_info
    
    async def invite_player(self, clan_id: str, player_id: str, rank: str = RANK_INITIATE) -> None:
        """
        Invite a player to a clan.
        
        Args:
            clan_id: Clan ID
            player_id: Player to invite
            rank: Starting rank (default: initiate)
            
        Raises:
            ValueError: If clan doesn't exist, player in another clan, etc.
        """
        from app.models import ClanMember
        
        if clan_id not in self.clans:
            raise ValueError(f"Clan {clan_id} does not exist")
        
        if player_id in self.player_clan_map:
            raise ValueError(f"Player {player_id} is already in a clan")
        
        clan_info = self.clans[clan_id]
        if clan_info.has_member(player_id):
            raise ValueError(f"Player {player_id} is already in this clan")
        
        # Create in-memory member
        joined_at = time.time()
        member = ClanMemberInfo(
            player_id=player_id,
            rank=rank,
            joined_at=joined_at,
        )
        clan_info.members[player_id] = member
        self.player_clan_map[player_id] = clan_id
        
        # Persist to DB
        async with self.db_session_factory() as session:
            clan_member = ClanMember(
                id=str(uuid.uuid4()),
                clan_id=clan_id,
                player_id=player_id,
                rank=rank,
                joined_at=joined_at,
                contribution_points=0,
            )
            session.add(clan_member)
            await session.commit()
    
    async def remove_player(self, player_id: str) -> Optional[str]:
        """
        Remove a player from their clan.
        
        If player is leader, clan is disbanded.
        
        Args:
            player_id: Player to remove
            
        Returns:
            clan_id if player was in a clan, None otherwise
        """
        from app.models import ClanMember
        
        if player_id not in self.player_clan_map:
            return None
        
        clan_id = self.player_clan_map.pop(player_id)
        clan_info = self.clans[clan_id]
        clan_info.members.pop(player_id, None)
        
        # If leader left, disband clan
        if player_id == clan_info.leader_id:
            return await self.disband_clan(clan_id)
        
        # Persist to DB
        async with self.db_session_factory() as session:
            await session.execute(
                delete(ClanMember).where(
                    (ClanMember.clan_id == clan_id) &
                    (ClanMember.player_id == player_id)
                )
            )
            await session.commit()
        
        return clan_id
    
    async def disband_clan(self, clan_id: str) -> Optional[str]:
        """
        Disband a clan and remove all members.
        
        Args:
            clan_id: Clan to disband
            
        Returns:
            clan_id if clan existed, None otherwise
        """
        from app.models import Clan
        
        if clan_id not in self.clans:
            return None
        
        clan_info = self.clans.pop(clan_id)
        
        # Remove all player mappings
        for player_id in list(clan_info.members.keys()):
            self.player_clan_map.pop(player_id, None)
        
        # Delete from DB
        async with self.db_session_factory() as session:
            await session.execute(
                delete(Clan).where(Clan.id == clan_id)
            )
            await session.commit()
        
        return clan_id
    
    async def promote_player(self, clan_id: str, player_id: str, new_rank: str) -> None:
        """
        Change a player's rank within clan.
        
        Args:
            clan_id: Clan ID
            player_id: Player to promote/demote
            new_rank: New rank (leader|officer|member|initiate)
            
        Raises:
            ValueError: If player not in clan, invalid rank, etc.
        """
        from app.models import ClanMember
        
        if new_rank not in RANK_HIERARCHY:
            raise ValueError(f"Invalid rank: {new_rank}")
        
        clan_info = self.clans.get(clan_id)
        if not clan_info:
            raise ValueError(f"Clan {clan_id} does not exist")
        
        member = clan_info.get_member(player_id)
        if not member:
            raise ValueError(f"Player {player_id} is not in this clan")
        
        # Can't demote leader unless reassigning leadership
        if member.rank == RANK_LEADER and new_rank != RANK_LEADER:
            raise ValueError("Cannot demote the clan leader")
        
        # Update in-memory
        member.rank = new_rank
        
        # Persist to DB
        async with self.db_session_factory() as session:
            await session.execute(
                update(ClanMember)
                .where(
                    (ClanMember.clan_id == clan_id) &
                    (ClanMember.player_id == player_id)
                )
                .values(rank=new_rank)
            )
            await session.commit()
    
    async def add_contribution(self, player_id: str, points: int) -> None:
        """
        Award contribution points to a player.
        
        Args:
            player_id: Player to award
            points: Points to add
        """
        from app.models import ClanMember
        
        if player_id not in self.player_clan_map:
            return
        
        clan_id = self.player_clan_map[player_id]
        clan_info = self.clans.get(clan_id)
        if not clan_info:
            return
        
        member = clan_info.get_member(player_id)
        if member:
            member.contribution_points += points
            
            # Persist to DB
            async with self.db_session_factory() as session:
                await session.execute(
                    update(ClanMember)
                    .where(
                        (ClanMember.clan_id == clan_id) &
                        (ClanMember.player_id == player_id)
                    )
                    .values(contribution_points=member.contribution_points)
                )
                await session.commit()
    
    def get_clan(self, clan_id: str) -> Optional[ClanInfo]:
        """Get a clan by ID."""
        return self.clans.get(clan_id)
    
    def get_player_clan(self, player_id: str) -> Optional[ClanInfo]:
        """Get the clan a player belongs to."""
        clan_id = self.player_clan_map.get(player_id)
        return self.clans.get(clan_id) if clan_id else None
    
    def get_clan_members(self, clan_id: str) -> Dict[str, ClanMemberInfo]:
        """Get all members in a clan."""
        clan = self.clans.get(clan_id)
        return clan.members.copy() if clan else {}
    
    def can_invite(self, clan_id: str, requester_id: str) -> bool:
        """Check if player can invite others to clan."""
        clan = self.clans.get(clan_id)
        if not clan:
            return False
        
        member = clan.get_member(requester_id)
        if not member:
            return False
        
        # Leader or Officer can invite
        return member.rank in (RANK_LEADER, RANK_OFFICER)
    
    def can_promote(self, clan_id: str, requester_id: str) -> bool:
        """Check if player can promote others in clan."""
        clan = self.clans.get(clan_id)
        if not clan:
            return False
        
        member = clan.get_member(requester_id)
        if not member:
            return False
        
        # Only Leader can promote
        return member.rank == RANK_LEADER
    
    def can_disband(self, clan_id: str, requester_id: str) -> bool:
        """Check if player can disband clan."""
        clan = self.clans.get(clan_id)
        if not clan:
            return False
        
        # Only leader can disband
        return clan.leader_id == requester_id
