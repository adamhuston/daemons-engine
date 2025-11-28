# backend/app/engine/systems/context.py
"""
GameContext - Shared context object for all game systems.

Provides:
- Access to World state
- Cross-system references
- Shared utilities (event dispatch, logging)

This avoids circular imports and provides a clean dependency injection pattern.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any, Callable, Awaitable, List
import asyncio

if TYPE_CHECKING:
    from ..world import World, PlayerId, RoomId


# Type alias for events (message dicts sent to players)
Event = Dict[str, Any]


class GameContext:
    """
    Shared context object passed to all game systems.
    
    Provides:
    - Access to the World state
    - Event dispatch helpers
    - Player listener management
    - Cross-system references (added as systems are initialized)
    
    Usage:
        ctx = GameContext(world)
        time_manager = TimeEventManager(ctx)
        ctx.time_manager = time_manager  # Register for cross-system access
    """
    
    def __init__(self, world: "World") -> None:
        self.world = world
        
        # Player event listeners (player_id -> queue of outgoing events)
        self._listeners: Dict["PlayerId", asyncio.Queue[Event]] = {}
        
        # System references (set by WorldEngine during initialization)
        self.time_manager: Any = None  # TimeEventManager
        self.combat_system: Any = None  # CombatSystem (future)
        self.effect_system: Any = None  # EffectSystem (future)
        self.event_dispatcher: Any = None  # EventDispatcher (future)
    
    # ---------- Event Dispatch Helpers ----------
    
    def msg_to_player(
        self,
        player_id: "PlayerId",
        text: str,
        *,
        payload: dict | None = None,
    ) -> Event:
        """Create a per-player message event."""
        ev: Event = {
            "type": "message",
            "scope": "player",
            "player_id": player_id,
            "text": text,
        }
        if payload:
            ev["payload"] = payload
        return ev
    
    def msg_to_room(
        self,
        room_id: "RoomId",
        text: str,
        *,
        exclude: set["PlayerId"] | None = None,
        payload: dict | None = None,
    ) -> Event:
        """Create a room-broadcast message event."""
        ev: Event = {
            "type": "message",
            "scope": "room",
            "room_id": room_id,
            "text": text,
        }
        if exclude:
            ev["exclude"] = list(exclude)
        if payload:
            ev["payload"] = payload
        return ev
    
    async def dispatch_events(self, events: List[Event]) -> None:
        """
        Route events to the appropriate player queues.
        
        Handles:
        - player-scoped messages (direct to one player)
        - room-scoped messages (to all players in a room)
        - all-scoped messages (broadcast to everyone)
        """
        for ev in events:
            scope = ev.get("scope", "player")
            
            if scope == "player":
                player_id = ev.get("player_id")
                if player_id and player_id in self._listeners:
                    await self._listeners[player_id].put(ev)
            
            elif scope == "room":
                room_id = ev.get("room_id")
                exclude = set(ev.get("exclude", []))
                room = self.world.rooms.get(room_id)
                if room:
                    for entity_id in room.entities:
                        if entity_id in self.world.players and entity_id not in exclude:
                            if entity_id in self._listeners:
                                await self._listeners[entity_id].put(ev)
            
            elif scope == "all":
                exclude = set(ev.get("exclude", []))
                for player_id, q in self._listeners.items():
                    if player_id not in exclude:
                        await q.put(ev)
    
    # ---------- Player Listener Management ----------
    
    def register_listener(self, player_id: "PlayerId") -> asyncio.Queue[Event]:
        """Register a player's event queue. Returns the queue for WebSocket to read from."""
        q: asyncio.Queue[Event] = asyncio.Queue()
        self._listeners[player_id] = q
        return q
    
    def unregister_listener(self, player_id: "PlayerId") -> None:
        """Remove a player's event queue."""
        self._listeners.pop(player_id, None)
    
    def has_listener(self, player_id: "PlayerId") -> bool:
        """Check if a player has an active listener."""
        return player_id in self._listeners
    
    def get_listener(self, player_id: "PlayerId") -> asyncio.Queue[Event] | None:
        """Get a player's event queue, or None if not registered."""
        return self._listeners.get(player_id)
