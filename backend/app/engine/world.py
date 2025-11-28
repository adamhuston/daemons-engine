# backend/app/engine/world.py
from dataclasses import dataclass, field
from typing import Dict, Set


# Simple type aliases for clarity
RoomId = str
PlayerId = str
Direction = str  # "north", "south", "east", "west", "up", "down"


@dataclass
class WorldPlayer:
    """Runtime representation of a player in the world."""
    id: PlayerId
    name: str
    room_id: RoomId
    inventory: list[str] = field(default_factory=list)
    # Movement effects - flavor text triggered by player movement
    on_move_effect: str | None = None  # e.g., "You glide gracefully"
    # Connection state - whether player is actively connected
    is_connected: bool = False


@dataclass
class WorldRoom:
    """Runtime representation of a room in the world."""
    id: RoomId
    name: str
    description: str
    exits: Dict[Direction, RoomId] = field(default_factory=dict)
    players: Set[PlayerId] = field(default_factory=set)
    # Movement effects - flavor text triggered when entering/leaving
    on_enter_effect: str | None = None  # e.g., "Mist swirls as you enter"
    on_exit_effect: str | None = None   # e.g., "Clouds part around you as you leave"


@dataclass
class World:
    """
    In-memory world state.

    This is the authoritative runtime graph used by WorldEngine.
    It is built from the database at startup and updated by game logic.
    """
    rooms: Dict[RoomId, WorldRoom]
    players: Dict[PlayerId, WorldPlayer]
