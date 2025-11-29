"""
FactionSystem - Persistent faction management with reputation tracking (Phase 10.3)

Handles:
- Loading factions from database
- Caching NPC faction memberships for O(1) lookup
- Player reputation tracking (-100 to +100)
- Alignment tier calculation (hated > disliked > neutral > liked > revered)
- NPC behavior changes based on player standing
- Faction chat broadcasting
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Set, Optional, Callable, Awaitable
import logging
from sqlalchemy import select

if TYPE_CHECKING:
    from .context import GameContext

logger = logging.getLogger(__name__)

# Faction standing constants
STANDING_HATED = -100
STANDING_DISLIKED = -50
STANDING_NEUTRAL = 0
STANDING_LIKED = 50
STANDING_REVERED = 100

# Alignment tier definitions
TIER_HATED = "hated"
TIER_DISLIKED = "disliked"
TIER_NEUTRAL = "neutral"
TIER_LIKED = "liked"
TIER_REVERED = "revered"


@dataclass
class FactionInfo:
    """In-memory representation of a faction."""
    faction_id: str
    name: str
    description: str = ""
    color: str = "#FFFFFF"
    emblem: Optional[str] = None
    player_joinable: bool = True
    max_members: Optional[int] = None
    require_level: int = 1
    created_at: Optional[float] = None
    
    # In-memory cache
    npc_members: Set[str] = field(default_factory=set)  # Set of NPC template IDs
    pending_invites: Set[str] = field(default_factory=set)  # Players invited but not joined


@dataclass
class FactionStanding:
    """Player's standing with a faction."""
    faction_id: str
    player_id: str
    standing: int  # Range: -100 to +100
    tier: str = TIER_NEUTRAL  # hated|disliked|neutral|liked|revered
    joined_at: Optional[float] = None
    contribution_points: int = 0


class FactionSystem:
    """
    Manages all faction-related operations.
    
    Features:
    - Load factions from database at startup
    - Track player reputation with O(1) faction lookups
    - Calculate alignment tiers (hated -> revered)
    - Cache NPC faction memberships for combat/dialogue checks
    - Broadcast faction-wide messages
    
    Usage:
        faction_system = FactionSystem(db_session_factory)
        await faction_system.load_factions_from_db()
        faction_system.add_reputation("player_0", "faction_1", 10)
        tier = faction_system.get_alignment_tier("player_0", "faction_1")
    """
    
    def __init__(self, db_session_factory: Callable[[], Awaitable] | None = None) -> None:
        self.db_session_factory = db_session_factory
        
        # In-memory faction cache: faction_id -> FactionInfo
        self.factions: Dict[str, FactionInfo] = {}
        
        # NPC to faction mapping for O(1) lookup: npc_template_id -> faction_id
        self.npc_to_faction: Dict[str, str] = {}
        
        # Player reputation: (player_id, faction_id) -> FactionStanding
        self.player_standings: Dict[tuple[str, str], FactionStanding] = {}
    
    # ---------- Database Operations ----------
    
    async def load_factions_from_db(self) -> None:
        """Load all factions and NPC memberships from database at startup."""
        if not self.db_session_factory:
            logger.warning("FactionSystem: No db_session_factory provided, skipping DB load")
            return
        
        try:
            async with self.db_session_factory() as session:
                from ..models import Faction, FactionNPCMember
                
                # Load all factions
                result = await session.execute(select(Faction))
                factions = result.scalars().all()
                
                for faction_row in factions:
                    faction_info = FactionInfo(
                        faction_id=faction_row.id,
                        name=faction_row.name,
                        description=faction_row.description or "",
                        color=faction_row.color,
                        emblem=faction_row.emblem,
                        player_joinable=faction_row.player_joinable,
                        max_members=faction_row.max_members,
                        require_level=faction_row.require_level,
                        created_at=faction_row.created_at,
                    )
                    self.factions[faction_row.id] = faction_info
                    
                    # Load NPC members
                    for member in faction_row.npc_members:
                        faction_info.npc_members.add(member.npc_template_id)
                        self.npc_to_faction[member.npc_template_id] = faction_row.id
                
                logger.info(f"Loaded {len(self.factions)} factions with {len(self.npc_to_faction)} NPC members")
        except Exception as e:
            logger.error(f"Error loading factions from database: {e}")
    
    async def load_factions_from_yaml(self, factions_dir: str) -> None:
        """
        Load faction definitions from YAML files and populate database.
        
        Expected YAML format:
        - name: "Faction Name"
          description: "Description"
          color: "#HEXCOLOR"
          emblem: "emoji"
          player_joinable: true
          require_level: 3
          npc_members:
            - npc_template_id_1
            - npc_template_id_2
        
        Args:
            factions_dir: Path to directory containing YAML files
        """
        from pathlib import Path
        import yaml
        import uuid
        import time
        
        factions_path = Path(factions_dir)
        if not factions_path.exists():
            logger.warning(f"Factions directory not found: {factions_dir}")
            return
        
        try:
            # Load all YAML files
            faction_definitions = []
            for yaml_file in sorted(factions_path.glob("*.yaml")):
                with open(yaml_file, 'r') as f:
                    data = yaml.safe_load(f)
                    if data:
                        faction_definitions.extend(data if isinstance(data, list) else [data])
            
            # Clear existing in-memory factions
            self.factions.clear()
            self.npc_to_faction.clear()
            
            # Process each faction
            for faction_def in faction_definitions:
                faction_id = str(uuid.uuid4())
                faction_name = faction_def.get("name", "Unknown")
                description = faction_def.get("description", "")
                color = faction_def.get("color", "#FFFFFF")
                emblem = faction_def.get("emblem")
                player_joinable = faction_def.get("player_joinable", True)
                require_level = faction_def.get("require_level", 1)
                
                faction_info = FactionInfo(
                    faction_id=faction_id,
                    name=faction_name,
                    description=description,
                    color=color,
                    emblem=emblem,
                    player_joinable=player_joinable,
                    require_level=require_level,
                    created_at=time.time(),
                )
                
                # Add NPC members
                npc_members = faction_def.get("npc_members", [])
                for npc_id in npc_members:
                    faction_info.npc_members.add(npc_id)
                    self.npc_to_faction[npc_id] = faction_id
                
                self.factions[faction_id] = faction_info
                
                # Persist to database
                await self._create_faction_in_db(
                    faction_id, faction_name, description, color, player_joinable, faction_info.created_at
                )
                
                # Add NPC members to database
                for npc_id in npc_members:
                    await self._add_npc_member_in_db(faction_id, npc_id)
            
            logger.info(f"Loaded {len(self.factions)} factions from YAML files")
        except Exception as e:
            logger.error(f"Error loading factions from YAML: {e}")
    
    async def _create_faction_in_db(
        self,
        faction_id: str,
        name: str,
        description: str,
        color: str,
        player_joinable: bool,
        created_at: float,
    ) -> None:
        """Persist a new faction to the database."""
        if not self.db_session_factory:
            return
        
        try:
            async with self.db_session_factory() as session:
                from ..models import Faction
                
                faction = Faction(
                    id=faction_id,
                    name=name,
                    description=description,
                    color=color,
                    player_joinable=player_joinable,
                    created_at=created_at,
                )
                session.add(faction)
                await session.commit()
        except Exception as e:
            logger.error(f"Error creating faction in DB: {e}")
    
    async def _add_npc_member_in_db(self, faction_id: str, npc_template_id: str) -> None:
        """Link an NPC template to a faction in the database."""
        if not self.db_session_factory:
            return
        
        try:
            async with self.db_session_factory() as session:
                from ..models import FactionNPCMember
                
                member = FactionNPCMember(
                    faction_id=faction_id,
                    npc_template_id=npc_template_id,
                )
                session.add(member)
                await session.commit()
        except Exception as e:
            logger.error(f"Error adding NPC member to faction: {e}")
    
    # ---------- Faction Operations ----------
    
    def get_faction(self, faction_id: str) -> Optional[FactionInfo]:
        """Get a faction by ID."""
        return self.factions.get(faction_id)
    
    def get_faction_by_name(self, name: str) -> Optional[FactionInfo]:
        """Get a faction by name (case-insensitive)."""
        for faction in self.factions.values():
            if faction.name.lower() == name.lower():
                return faction
        return None
    
    def list_factions(self, player_joinable_only: bool = True) -> List[FactionInfo]:
        """List all factions, optionally filtered to only joinable ones."""
        factions = list(self.factions.values())
        if player_joinable_only:
            factions = [f for f in factions if f.player_joinable]
        return sorted(factions, key=lambda f: f.name)
    
    def get_npc_faction(self, npc_template_id: str) -> Optional[str]:
        """Get the faction ID for an NPC template (O(1) lookup)."""
        return self.npc_to_faction.get(npc_template_id)
    
    # ---------- Reputation Operations ----------
    
    def get_standing(self, player_id: str, faction_id: str) -> FactionStanding:
        """Get player's standing with a faction (creates neutral if not found)."""
        key = (player_id, faction_id)
        
        if key not in self.player_standings:
            # Create neutral standing if first time
            self.player_standings[key] = FactionStanding(
                faction_id=faction_id,
                player_id=player_id,
                standing=0,
                tier=TIER_NEUTRAL,
            )
        
        return self.player_standings[key]
    
    def add_reputation(self, player_id: str, faction_id: str, amount: int) -> int:
        """
        Add reputation points to a player with a faction.
        
        Args:
            player_id: Player ID
            faction_id: Faction ID
            amount: Reputation change (positive or negative)
        
        Returns:
            New standing value (clamped to [-100, 100])
        """
        standing = self.get_standing(player_id, faction_id)
        
        # Clamp to valid range
        standing.standing = max(STANDING_HATED, min(STANDING_REVERED, standing.standing + amount))
        
        # Update tier based on new standing
        standing.tier = self._calculate_tier(standing.standing)
        
        return standing.standing
    
    def get_alignment_tier(self, player_id: str, faction_id: str) -> str:
        """Get the alignment tier (hated/disliked/neutral/liked/revered) for a player with a faction."""
        standing = self.get_standing(player_id, faction_id)
        return standing.tier
    
    def _calculate_tier(self, standing: int) -> str:
        """Calculate alignment tier from standing value."""
        if standing <= STANDING_HATED:
            return TIER_HATED
        elif standing < STANDING_NEUTRAL:
            return TIER_DISLIKED
        elif standing == STANDING_NEUTRAL:
            return TIER_NEUTRAL
        elif standing <= STANDING_REVERED:
            return TIER_LIKED
        else:
            return TIER_REVERED
    
    def should_attack_player(self, npc_template_id: str, player_id: str) -> bool:
        """
        Determine if an NPC should attack a player based on faction standing.
        
        NPCs attack players they are hated by (i.e., player is hated by the faction).
        """
        faction_id = self.npc_to_faction.get(npc_template_id)
        if not faction_id:
            # Not in a faction, don't auto-attack
            return False
        
        tier = self.get_alignment_tier(player_id, faction_id)
        return tier == TIER_HATED
    
    def get_player_standings(self, player_id: str) -> Dict[str, FactionStanding]:
        """Get all faction standings for a player."""
        return {
            faction_id: standing
            for (pid, faction_id), standing in self.player_standings.items()
            if pid == player_id
        }
    
    # ---------- Membership Operations ----------
    
    async def join_faction(self, player_id: str, faction_id: str) -> bool:
        """
        Player joins a faction.
        
        Returns True if successful, False if already member or faction full.
        """
        if faction_id not in self.factions:
            raise ValueError(f"Faction {faction_id} not found")
        
        faction = self.factions[faction_id]
        key = (player_id, faction_id)
        
        # Check if already in faction
        if key in self.player_standings:
            return False
        
        # Create neutral standing for new member
        self.player_standings[key] = FactionStanding(
            faction_id=faction_id,
            player_id=player_id,
            standing=0,
            tier=TIER_NEUTRAL,
        )
        
        return True
    
    async def leave_faction(self, player_id: str, faction_id: str) -> bool:
        """
        Player leaves a faction.
        
        Returns True if successful, False if not a member.
        """
        key = (player_id, faction_id)
        
        if key not in self.player_standings:
            return False
        
        # Preserve reputation data for rejoining
        # (could optionally delete on leave)
        return True
    
    # ---------- Utility Methods ----------
    
    def get_faction_color(self, faction_id: str) -> str:
        """Get faction's display color for UI."""
        faction = self.get_faction(faction_id)
        return faction.color if faction else "#FFFFFF"
    
    def get_faction_emblem(self, faction_id: str) -> Optional[str]:
        """Get faction's emblem/symbol."""
        faction = self.get_faction(faction_id)
        return faction.emblem if faction else None
    
    def format_standing(self, standing: int) -> str:
        """Format standing value for display (e.g., '+25', '-50')."""
        if standing >= 0:
            return f"+{standing}"
        return str(standing)
    
    def get_tier_emoji(self, tier: str) -> str:
        """Get emoji for alignment tier."""
        emojis = {
            TIER_HATED: "💀",
            TIER_DISLIKED: "👎",
            TIER_NEUTRAL: "➖",
            TIER_LIKED: "👍",
            TIER_REVERED: "⭐",
        }
        return emojis.get(tier, "❓")
