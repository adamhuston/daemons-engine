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

from typing import TYPE_CHECKING, Any, Dict, List, Set

if TYPE_CHECKING:
    from ..world import PlayerId, RoomId
    from .context import GameContext


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
        - group-scoped messages (to all members in a group)
        - tell-scoped messages (to sender and recipient only)
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
                    k: v for k, v in ev.items() if k not in ("scope", "exclude")
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

                    # Skip sleeping players for room messages (they don't hear/see)
                    player = self.ctx.world.players.get(pid)
                    if player and player.is_sleeping:
                        continue

                    q = self.ctx._listeners.get(pid)
                    if q is None:
                        continue

                    wire_event = {
                        k: v for k, v in ev.items() if k not in ("scope", "exclude")
                    }
                    wire_event["player_id"] = pid
                    await q.put(wire_event)

            elif scope == "group":
                group_id = ev.get("group_id")
                if not group_id or not self.ctx.group_system:
                    continue

                group = self.ctx.group_system.get_group(group_id)
                if not group:
                    continue

                # Send to all group members
                for pid in group.members:
                    q = self.ctx._listeners.get(pid)
                    if q is None:
                        continue

                    wire_event = {
                        k: v for k, v in ev.items() if k not in ("scope", "exclude")
                    }
                    wire_event["player_id"] = pid
                    await q.put(wire_event)

            elif scope == "tell":
                sender_id = ev.get("sender_id")
                recipient_id = ev.get("recipient_id")

                if not sender_id or not recipient_id:
                    continue

                # Send to sender
                q = self.ctx._listeners.get(sender_id)
                if q is not None:
                    wire_event = {
                        k: v for k, v in ev.items() if k not in ("scope", "exclude")
                    }
                    wire_event["player_id"] = sender_id
                    await q.put(wire_event)

                # Send to recipient
                q = self.ctx._listeners.get(recipient_id)
                if q is not None:
                    wire_event = {
                        k: v for k, v in ev.items() if k not in ("scope", "exclude")
                    }
                    wire_event["player_id"] = recipient_id
                    await q.put(wire_event)

            elif scope == "clan":
                clan_id = ev.get("clan_id")
                if not clan_id or not self.ctx.clan_system:
                    continue

                clan = self.ctx.clan_system.clans.get(clan_id)
                if not clan:
                    continue

                # Send to all clan members
                for pid in clan.members:
                    q = self.ctx._listeners.get(pid)
                    if q is None:
                        continue

                    wire_event = {
                        k: v for k, v in ev.items() if k not in ("scope", "exclude")
                    }
                    wire_event["player_id"] = pid
                    await q.put(wire_event)

            elif scope == "faction":
                faction_id = ev.get("faction_id")
                if not faction_id or not self.ctx.faction_system:
                    continue

                # Get all players in faction
                standing_dict = self.ctx.faction_system.player_standings
                faction_members = {
                    pid
                    for (pid, fid), standing in standing_dict.items()
                    if fid == faction_id and standing.joined_at is not None
                }

                # Send to all faction members who are online
                for pid in faction_members:
                    q = self.ctx._listeners.get(pid)
                    if q is None:
                        continue

                    wire_event = {
                        k: v for k, v in ev.items() if k not in ("scope", "exclude")
                    }
                    wire_event["player_id"] = pid
                    await q.put(wire_event)

            elif scope == "all":
                exclude = set(ev.get("exclude", []))
                for pid, q in self.ctx._listeners.items():
                    if pid in exclude:
                        continue
                    wire_event = {
                        k: v for k, v in ev.items() if k not in ("scope", "exclude")
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

    # ---------- Social Events ----------

    def group_message(
        self,
        group_id: str,
        sender_id: "PlayerId",
        sender_name: str,
        text: str,
    ) -> Event:
        """
        Create a group message event.

        Args:
            group_id: The group ID
            sender_id: The sender's player ID
            sender_name: The sender's player name
            text: The message text

        Returns:
            A group_message event dict
        """
        ev: Event = {
            "type": "group_message",
            "scope": "group",
            "group_id": group_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "text": text,
        }
        return ev

    def tell_message(
        self,
        sender_id: "PlayerId",
        sender_name: str,
        recipient_id: "PlayerId",
        text: str,
    ) -> Event:
        """
        Create a tell/private message event.

        Args:
            sender_id: The sender's player ID
            sender_name: The sender's player name
            recipient_id: The recipient's player ID
            text: The message text

        Returns:
            A tell_message event dict (routed to sender and recipient only)
        """
        ev: Event = {
            "type": "tell_message",
            "scope": "tell",
            "sender_id": sender_id,
            "sender_name": sender_name,
            "recipient_id": recipient_id,
            "text": text,
        }
        return ev

    def follow_event(
        self,
        follower_id: "PlayerId",
        follower_name: str,
        followed_id: "PlayerId",
        action: str,  # "started_following" or "stopped_following"
    ) -> Event:
        """
        Create a follow event.

        Args:
            follower_id: The player starting/stopping to follow
            follower_name: The follower's player name
            followed_id: The player being followed
            action: "started_following" or "stopped_following"

        Returns:
            A follow_event dict
        """
        ev: Event = {
            "type": "follow_event",
            "scope": "player",
            "follower_id": follower_id,
            "follower_name": follower_name,
            "followed_id": followed_id,
            "action": action,
        }
        return ev

    def clan_message(
        self,
        clan_id: int,
        sender_id: "PlayerId",
        sender_name: str,
        text: str,
    ) -> Event:
        """
        Create a clan message event.

        Args:
            clan_id: The clan ID
            sender_id: The sender's player ID
            sender_name: The sender's player name
            text: The message text

        Returns:
            A clan_message event dict
        """
        ev: Event = {
            "type": "clan_message",
            "scope": "clan",
            "clan_id": clan_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "text": text,
        }
        return ev

    def faction_message(
        self,
        faction_id: str,
        sender_id: "PlayerId",
        sender_name: str,
        text: str,
    ) -> Event:
        """
        Create a faction message event.

        Args:
            faction_id: The faction ID
            sender_id: The sender's player ID
            sender_name: The sender's player name
            text: The message text

        Returns:
            A faction_message event dict
        """
        ev: Event = {
            "type": "faction_message",
            "scope": "faction",
            "faction_id": faction_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "text": text,
        }
        return ev

    # ---------- Helpers ----------

    def _get_player_ids_in_room(self, room_id: "RoomId") -> Set["PlayerId"]:
        """Get all player IDs in a room from the unified entities set."""
        room = self.ctx.world.rooms.get(room_id)
        if not room:
            return set()
        return {eid for eid in room.entities if eid in self.ctx.world.players}
