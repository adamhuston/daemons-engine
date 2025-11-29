# backend/app/engine/systems/events.py
"""
EventDispatcher - Handles event creation and routing to players.

Provides:
- Event construction helpers (msg_to_player, msg_to_room, stat_update)
- Event routing to player queues based on scope
- Stat update emissions for UI synchronization

Extracted from WorldEngine for modularity.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Dict, Any, Set

if TYPE_CHECKING:
    from .context import GameContext
    from ..world import PlayerId, RoomId


# Type alias for events (message dicts sent to players)
Event = Dict[str, Any]


class EventDispatcher:
    """
    Manages event construction and routing to players.
    
    Features:
    - Creates typed events with proper scope (player, room, all)
    - Routes events to appropriate player queues
    - Handles exclusions and payloads
    - Provides stat update emissions for UI sync
    
    Usage:
        dispatcher = EventDispatcher(ctx)
        event = dispatcher.msg_to_player(player_id, "Hello!")
        await dispatcher.dispatch([event])
    """
    
    def __init__(self, ctx: "GameContext") -> None:
        self.ctx = ctx
    
    # ---------- Event Construction ----------
    
    def msg_to_player(
        self,
        player_id: "PlayerId",
        text: str,
        *,
        payload: dict | None = None,
    ) -> Event:
        """
        Create a per-player message event.
        
        Args:
            player_id: The player to send to
            text: The message text (supports markdown)
            payload: Optional additional data
        
        Returns:
            An event dict ready to dispatch
        """
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
        """
        Create a room-broadcast message event.
        
        Args:
            room_id: The room to broadcast to
            text: The message text (supports markdown)
            exclude: Set of player IDs to exclude from broadcast
            payload: Optional additional data
        
        Returns:
            An event dict ready to dispatch
        """
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
    
    def stat_update(
        self,
        player_id: "PlayerId",
        stats: dict,
    ) -> Event:
        """
        Create a stat_update event for UI synchronization.
        
        Args:
            player_id: The player to update
            stats: Dict of stat values (health, energy, AC, level, etc.)
        
        Returns:
            A stat_update event dict
        """
        ev: Event = {
            "type": "stat_update",
            "scope": "player",
            "player_id": player_id,
            "payload": stats,
        }
        return ev
    
    def emit_stat_update(self, player_id: "PlayerId") -> List[Event]:
        """
        Generate a stat update event from current player state.
        
        Args:
            player_id: The player to generate stats for
        
        Returns:
            List containing stat_update event (or empty if player not found)
        """
        if player_id not in self.ctx.world.players:
            return []
        
        player = self.ctx.world.players[player_id]
        
        # Calculate current effective stats
        effective_ac = player.get_effective_armor_class()
        
        payload = {
            "health": player.current_health,
            "max_health": player.max_health,
            "energy": player.current_energy,
            "max_energy": player.max_energy,
            "armor_class": effective_ac,
            "level": player.level,
            "experience": player.experience,
        }
        
        return [self.stat_update(player_id, payload)]
    
    # ---------- Event Dispatch ----------
    
    async def dispatch(self, events: List[Event]) -> None:
        """
        Route events to the appropriate player queues.
        
        Handles:
        - player-scoped messages (direct to one player)
        - room-scoped messages (to all players in a room)
        - all-scoped messages (broadcast to everyone)
        
        Args:
            events: List of event dicts to dispatch
        """
        for ev in events:
            print(f"EventDispatcher: routing event: {ev!r}")
            
            scope = ev.get("scope", "player")
            
            if scope == "player":
                target = ev.get("player_id")
                if not target:
                    continue
                q = self.ctx._listeners.get(target)
                if q is None:
                    continue
                
                # Strip engine-internal keys before sending, but keep player_id
                wire_event = {
                    k: v
                    for k, v in ev.items()
                    if k not in ("scope", "exclude")
                }
                await q.put(wire_event)
            
            elif scope == "room":
                room_id = ev.get("room_id")
                if not room_id:
                    continue
                room = self.ctx.world.rooms.get(room_id)
                if room is None:
                    continue
                
                exclude = set(ev.get("exclude", []))
                
                # Get player IDs from unified entity set
                player_ids = self._get_player_ids_in_room(room_id)
                
                for pid in player_ids:
                    if pid in exclude:
                        continue
                    q = self.ctx._listeners.get(pid)
                    if q is None:
                        continue
                    
                    wire_event = {
                        k: v
                        for k, v in ev.items()
                        if k not in ("scope", "exclude")
                    }
                    wire_event["player_id"] = pid
                    await q.put(wire_event)
            
            elif scope == "all":
                exclude = set(ev.get("exclude", []))
                for pid, q in self.ctx._listeners.items():
                    if pid in exclude:
                        continue
                    wire_event = {
                        k: v
                        for k, v in ev.items()
                        if k not in ("scope", "exclude")
                    }
                    wire_event["player_id"] = pid
                    await q.put(wire_event)
    
    def ability_cast(
        self,
        caster_id: "PlayerId",
        ability_id: str,
        ability_name: str,
        target_ids: List["PlayerId"] | None = None,
        room_id: "RoomId | None" = None,
    ) -> Event:
        """
        Create an ability_cast event when an ability is used.
        
        Args:
            caster_id: Player who cast the ability
            ability_id: The ability ID
            ability_name: Human-readable ability name
            target_ids: List of target player IDs affected
            room_id: Room where ability was cast (for room-scoped events)
        
        Returns:
            An ability_cast event dict
        """
        ev: Event = {
            "type": "ability_cast",
            "caster_id": caster_id,
            "ability_id": ability_id,
            "ability_name": ability_name,
        }
        if target_ids:
            ev["target_ids"] = target_ids
        if room_id:
            ev["room_id"] = room_id
        return ev
    
    def ability_error(
        self,
        player_id: "PlayerId",
        ability_id: str,
        ability_name: str,
        error_message: str,
    ) -> Event:
        """
        Create an ability_error event when ability use fails.
        
        Args:
            player_id: Player who attempted the ability
            ability_id: The ability ID
            ability_name: Human-readable ability name
            error_message: Why the ability failed
        
        Returns:
            An ability_error event dict
        """
        ev: Event = {
            "type": "ability_error",
            "scope": "player",
            "player_id": player_id,
            "ability_id": ability_id,
            "ability_name": ability_name,
            "error": error_message,
        }
        return ev
    
    def ability_cast_complete(
        self,
        caster_id: "PlayerId",
        ability_id: str,
        ability_name: str,
        success: bool,
        message: str,
        damage_dealt: int | None = None,
        targets_hit: int | None = None,
    ) -> Event:
        """
        Create an ability_cast_complete event when ability execution finishes.
        
        Args:
            caster_id: Player who cast the ability
            ability_id: The ability ID
            ability_name: Human-readable ability name
            success: Whether the ability succeeded
            message: Result message
            damage_dealt: Optional total damage dealt
            targets_hit: Optional number of targets hit
        
        Returns:
            An ability_cast_complete event dict
        """
        payload = {
            "success": success,
            "message": message,
        }
        if damage_dealt is not None:
            payload["damage_dealt"] = damage_dealt
        if targets_hit is not None:
            payload["targets_hit"] = targets_hit
        
        ev: Event = {
            "type": "ability_cast_complete",
            "scope": "player",
            "player_id": caster_id,
            "ability_id": ability_id,
            "ability_name": ability_name,
            "payload": payload,
        }
        return ev
    
    def cooldown_update(
        self,
        player_id: "PlayerId",
        ability_id: str,
        cooldown_remaining: float,
    ) -> Event:
        """
        Create a cooldown_update event when ability cooldown is applied.
        
        Args:
            player_id: Player who cast the ability
            ability_id: The ability ID
            cooldown_remaining: Seconds remaining on cooldown
        
        Returns:
            A cooldown_update event dict
        """
        ev: Event = {
            "type": "cooldown_update",
            "scope": "player",
            "player_id": player_id,
            "ability_id": ability_id,
            "cooldown_remaining": cooldown_remaining,
        }
        return ev
    
    def resource_update(
        self,
        player_id: "PlayerId",
        resources: Dict[str, Dict[str, Any]],
    ) -> Event:
        """
        Create a resource_update event when player resources change.
        
        Args:
            player_id: The player whose resources changed
            resources: Dict mapping resource_id -> {current, max, percent}
        
        Returns:
            A resource_update event dict
        """
        ev: Event = {
            "type": "resource_update",
            "scope": "player",
            "player_id": player_id,
            "payload": resources,
        }
        return ev
    
    def ability_learned(
        self,
        player_id: "PlayerId",
        ability_id: str,
        ability_name: str,
    ) -> Event:
        """
        Create an ability_learned event when player learns a new ability.
        
        Args:
            player_id: The player who learned the ability
            ability_id: The ability ID
            ability_name: Human-readable ability name
        
        Returns:
            An ability_learned event dict
        """
        ev: Event = {
            "type": "ability_learned",
            "scope": "player",
            "player_id": player_id,
            "ability_id": ability_id,
            "ability_name": ability_name,
        }
        return ev

    # ---------- Helpers ----------
    
    def _get_player_ids_in_room(self, room_id: "RoomId") -> Set["PlayerId"]:
        """Get all player IDs in a room from the unified entities set."""
        room = self.ctx.world.rooms.get(room_id)
        if not room:
            return set()
        return {eid for eid in room.entities if eid in self.ctx.world.players}
