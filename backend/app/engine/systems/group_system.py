"""
Group System for Phase 10.1

Manages player groups (temporary teams) with automatic disbanding
after inactivity, group messaging, and member tracking.

Design:
- O(1) player → group lookup via player_to_group mapping
- Auto-disband after 30 minutes inactivity
- Per-group message broadcasting
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Set, Optional
from uuid import uuid4


@dataclass
class Group:
    """Represents a group of players."""
    
    group_id: str
    name: str
    leader_id: str
    members: Set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    
    INACTIVITY_TIMEOUT = 30 * 60  # 30 minutes
    
    def is_stale(self) -> bool:
        """Check if group has been inactive for too long."""
        return time.time() - self.last_activity > self.INACTIVITY_TIMEOUT
    
    def update_activity(self):
        """Refresh the last activity timestamp."""
        self.last_activity = time.time()
    
    def add_member(self, player_id: str) -> None:
        """Add a member to the group."""
        self.members.add(player_id)
        self.update_activity()
    
    def remove_member(self, player_id: str) -> None:
        """Remove a member from the group."""
        self.members.discard(player_id)
        self.update_activity()
    
    def has_member(self, player_id: str) -> bool:
        """Check if player is in group."""
        return player_id in self.members
    
    def member_count(self) -> int:
        """Return number of members in group."""
        return len(self.members)


class GroupSystem:
    """
    Manages all player groups.
    
    Maintains two index structures for fast lookups:
    - groups: Dict[group_id, Group] - All groups by ID
    - player_to_group: Dict[player_id, group_id] - Player → group mapping
    
    Auto-disband stale groups (30 min inactivity).
    """
    
    def __init__(self):
        self.groups: Dict[str, Group] = {}
        self.player_to_group: Dict[str, str] = {}  # player_id -> group_id
    
    def create_group(self, name: str, leader_id: str) -> Group:
        """
        Create a new group.
        
        Args:
            name: Group name
            leader_id: UUID of group leader
            
        Returns:
            Group object
            
        Raises:
            ValueError: If leader already in a group or name already exists
        """
        if leader_id in self.player_to_group:
            raise ValueError(f"Player {leader_id} is already in a group")
        
        if any(g.name == name for g in self.groups.values()):
            raise ValueError(f"Group name '{name}' already exists")
        
        group_id = str(uuid4())
        group = Group(group_id=group_id, name=name, leader_id=leader_id)
        group.add_member(leader_id)
        
        self.groups[group_id] = group
        self.player_to_group[leader_id] = group_id
        
        return group
    
    def invite_player(self, group_id: str, player_id: str) -> None:
        """
        Add a player to a group.
        
        Args:
            group_id: UUID of target group
            player_id: UUID of player to add
            
        Raises:
            ValueError: If group doesn't exist, player already in group, etc.
        """
        if group_id not in self.groups:
            raise ValueError(f"Group {group_id} does not exist")
        
        if player_id in self.player_to_group:
            raise ValueError(f"Player {player_id} is already in a group")
        
        group = self.groups[group_id]
        group.add_member(player_id)
        self.player_to_group[player_id] = group_id
    
    def remove_player(self, player_id: str) -> Optional[str]:
        """
        Remove a player from their group.
        
        Args:
            player_id: UUID of player to remove
            
        Returns:
            group_id if player was in a group, None otherwise
        """
        if player_id not in self.player_to_group:
            return None
        
        group_id = self.player_to_group.pop(player_id)
        group = self.groups[group_id]
        group.remove_member(player_id)
        
        # Auto-disband if leader leaves or group is empty
        if player_id == group.leader_id or group.member_count() == 0:
            return self.disband_group(group_id)
        
        return group_id
    
    def disband_group(self, group_id: str) -> Optional[str]:
        """
        Disband a group and remove all members.
        
        Args:
            group_id: UUID of group to disband
            
        Returns:
            group_id if group existed, None otherwise
        """
        if group_id not in self.groups:
            return None
        
        group = self.groups.pop(group_id)
        for player_id in list(group.members):
            self.player_to_group.pop(player_id, None)
        
        return group_id
    
    def get_group(self, group_id: str) -> Optional[Group]:
        """Get a group by ID."""
        return self.groups.get(group_id)
    
    def get_player_group(self, player_id: str) -> Optional[Group]:
        """Get the group a player belongs to."""
        group_id = self.player_to_group.get(player_id)
        return self.groups.get(group_id) if group_id else None
    
    def get_group_members(self, group_id: str) -> Set[str]:
        """Get all member IDs in a group."""
        group = self.groups.get(group_id)
        return group.members.copy() if group else set()
    
    def rename_group(self, group_id: str, new_name: str) -> None:
        """
        Rename a group.
        
        Args:
            group_id: UUID of group to rename
            new_name: New group name
            
        Raises:
            ValueError: If group doesn't exist or name already taken
        """
        if group_id not in self.groups:
            raise ValueError(f"Group {group_id} does not exist")
        
        if any(g.name == new_name for gid, g in self.groups.items() if gid != group_id):
            raise ValueError(f"Group name '{new_name}' already exists")
        
        self.groups[group_id].name = new_name
        self.groups[group_id].update_activity()
    
    def clean_stale_groups(self) -> list[str]:
        """
        Remove all stale groups (inactive for 30+ minutes).
        
        Returns:
            List of disbanded group IDs
        """
        stale_groups = [gid for gid, group in self.groups.items() if group.is_stale()]
        disbanded = []
        
        for group_id in stale_groups:
            if self.disband_group(group_id):
                disbanded.append(group_id)
        
        return disbanded
    
    def broadcast_group_message(self, group_id: str, message: str, sender_id: str) -> Set[str]:
        """
        Broadcast a message to all group members (except sender).
        
        Args:
            group_id: UUID of group
            message: Message text
            sender_id: UUID of sender (excluded from recipients)
            
        Returns:
            Set of player IDs who should receive the message
        """
        group = self.groups.get(group_id)
        if not group:
            return set()
        
        # Return all members except sender
        return group.members - {sender_id}
