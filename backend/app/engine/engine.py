# backend/app/engine/engine.py
import asyncio
from typing import Dict, List, Any

from .world import World, Direction, PlayerId, RoomId


Event = dict[str, Any]


class WorldEngine:
    """
    Core game engine.

    - Holds a reference to the in-memory World.
    - Consumes commands from players via an asyncio.Queue.
    - Produces events destined for players via per-player queues.
    - Supports per-player messages and room broadcasts.
    """

    def __init__(self, world: World) -> None:
        self.world = world

        # Queue of (player_id, command_text)
        self._command_queue: asyncio.Queue[tuple[PlayerId, str]] = asyncio.Queue()

        # player_id -> queue of outgoing events (dicts)
        self._listeners: Dict[PlayerId, asyncio.Queue[Event]] = {}

    # ---------- Player connection management ----------

    async def register_player(self, player_id: PlayerId) -> asyncio.Queue[Event]:
        """
        Called when a player opens a WebSocket connection.

        Returns a queue; the WebSocket sender task will read events from this queue.
        """
        q: asyncio.Queue[Event] = asyncio.Queue()
        self._listeners[player_id] = q
        
        # Check if player is coming out of stasis
        if player_id in self.world.players:
            player = self.world.players[player_id]
            was_in_stasis = not player.is_connected
            player.is_connected = True
            
            # Broadcast awakening message if coming out of stasis
            if was_in_stasis:
                room = self.world.rooms.get(player.room_id)
                if room and len(room.players) > 1:
                    awaken_msg = (
                        f"The prismatic light around {player.name} shatters like glass. "
                        f"They gasp and return to awareness, freed from stasis."
                    )
                    event = self._msg_to_room(
                        room.id,
                        awaken_msg,
                        exclude={player_id}
                    )
                    await self._dispatch_events([event])
        
        return q

    def unregister_player(self, player_id: PlayerId) -> None:
        """
        Called when a player's WebSocket disconnects.
        """
        self._listeners.pop(player_id, None)
    
    async def player_disconnect(self, player_id: PlayerId) -> None:
        """
        Handle a player disconnect by putting them in stasis and broadcasting a message.
        Should be called before unregister_player.
        """
        if player_id in self.world.players:
            player = self.world.players[player_id]
            player.is_connected = False  # Put in stasis
            
            room = self.world.rooms.get(player.room_id)
            
            if room and len(room.players) > 1:
                # Create stasis event for others in the room
                stasis_msg = (
                    f"A bright flash of light engulfs {player.name}. "
                    f"Their form flickers and freezes, suddenly suspended in a prismatic stasis."
                )
                event = self._msg_to_room(
                    room.id,
                    stasis_msg,
                    exclude={player_id}
                )
                await self._dispatch_events([event])

    # ---------- Command submission / main loop ----------

    async def submit_command(self, player_id: PlayerId, command: str) -> None:
        """
        Called by the WebSocket receiver when a command comes in from the client.
        """
        await self._command_queue.put((player_id, command))

    async def game_loop(self) -> None:
        """
        Main engine loop.

        Simple version: process commands one-by-one, no global tick yet.
        You can later extend this to also run NPC AI / timed events.
        """
        while True:
            player_id, command = await self._command_queue.get()
            print(f"WorldEngine: got command from {player_id}: {command!r}")
            events = self.handle_command(player_id, command)
            print(f"WorldEngine: generated: {events!r}")
            await self._dispatch_events(events)

    # ---------- Command handling ----------

    def handle_command(self, player_id: PlayerId, command: str) -> List[Event]:
        """
        Parse a raw command string and return logical events.
        """
        raw = command.strip()
        if not raw:
            return []

        cmd = raw.lower()

        # Movement
        if cmd in {
            "n",
            "s",
            "e",
            "w",
            "u",
            "d",
            "north",
            "south",
            "east",
            "west",
            "up",
            "down",
        }:
            dir_map = {
                "n": "north",
                "s": "south",
                "e": "east",
                "w": "west",
                "u": "up",
                "d": "down",
            }
            direction: Direction = dir_map.get(cmd, cmd)
            return self._move_player(player_id, direction)

        # Look
        if cmd in {"look", "l"}:
            return self._look(player_id)

        # Say (room broadcast)
        if cmd.startswith("say"):
            # Preserve original casing for message text
            if len(raw) <= 3:
                return [self._msg_to_player(player_id, "Say what?")]
            # everything after "say "
            text = raw[4:].strip()
            if not text:
                return [self._msg_to_player(player_id, "Say what?")]
            return self._say(player_id, text)

        # Default
        return [
            self._msg_to_player(
                player_id,
                "You mutter something unintelligible. (Unknown command)",
            )
        ]

    # ---------- Helper: event constructors ----------

    def _msg_to_player(
        self,
        player_id: PlayerId,
        text: str,
        *,
        payload: dict | None = None,
    ) -> Event:
        """
        Create a per-player message event.
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

    def _msg_to_room(
        self,
        room_id: RoomId,
        text: str,
        *,
        exclude: set[PlayerId] | None = None,
        payload: dict | None = None,
    ) -> Event:
        """
        Create a room-broadcast message event.
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

    # ---------- Concrete command handlers ----------

    def _move_player(self, player_id: PlayerId, direction: Direction) -> List[Event]:
        events: List[Event] = []
        world = self.world

        if player_id not in world.players:
            return [
                self._msg_to_player(
                    player_id,
                    "You feel incorporeal. (Player not found in world)",
                )
            ]

        player = world.players[player_id]
        current_room = world.rooms.get(player.room_id)

        if current_room is None:
            return [
                self._msg_to_player(
                    player_id,
                    "You are lost in the void. (Room not found)",
                )
            ]

        if direction not in current_room.exits:
            return [
                self._msg_to_player(player_id, "You can't go that way."),
            ]

        new_room_id = current_room.exits[direction]
        new_room = world.rooms.get(new_room_id)
        if new_room is None:
            return [
                self._msg_to_player(
                    player_id,
                    "The way blurs and collapses. (Destination room missing)",
                )
            ]

        old_room_id = current_room.id

        # Update occupancy
        current_room.players.discard(player_id)
        new_room.players.add(player_id)
        player.room_id = new_room_id

        # Build movement message with effects
        description_lines = [f"You move {direction}."]
        
        # Trigger exit effect from old room
        if current_room.on_exit_effect:
            description_lines.append(current_room.on_exit_effect)
        
        # Trigger player movement effect
        if player.on_move_effect:
            description_lines.append(player.on_move_effect)
        
        # Show new room
        description_lines.extend([
            "",
            new_room.name,
            new_room.description
        ])
        
        # Trigger enter effect for new room
        if new_room.on_enter_effect:
            description_lines.append("")
            description_lines.append(new_room.on_enter_effect)
        
        # Add exits to the room description
        if new_room.exits:
            exits = list(new_room.exits.keys())
            description_lines.append("")
            description_lines.append(f"Exits: {', '.join(exits)}")
        
        # List other players in the new room
        others = [
            world.players[pid].name
            for pid in new_room.players
            if pid != player_id and world.players[pid].is_connected
        ]
        stasis_players = [
            world.players[pid].name
            for pid in new_room.players
            if pid != player_id and not world.players[pid].is_connected
        ]
        
        if others:
            description_lines.append("")
            description_lines.append("Others here:")
            for name in others:
                description_lines.append(f" - {name}")
        
        if stasis_players:
            description_lines.append("")
            for name in stasis_players:
                description_lines.append(f"(In Stasis) The form of {name} is here, flickering in the prismatic state of stasis.")
        
        events.append(
            self._msg_to_player(
                player_id,
                "\n".join(description_lines),
            )
        )

        # Broadcast to players still in the old room (they see you leave)
        # current_room.players now contains only *other* players
        if current_room.players:
            events.append(
                self._msg_to_room(
                    old_room_id,
                    f"{player.name} leaves.",
                )
            )

        # Broadcast to players in the new room (they see you enter)
        # new_room.players includes the moving player -> exclude them
        if len(new_room.players) > 1:
            events.append(
                self._msg_to_room(
                    new_room_id,
                    f"{player.name} enters.",
                    exclude={player_id},
                )
            )

        return events

    def _look(self, player_id: PlayerId) -> List[Event]:
        world = self.world

        if player_id not in world.players:
            return [
                self._msg_to_player(
                    player_id,
                    "You have no form here. (Player not found)",
                )
            ]

        player = world.players[player_id]
        room = world.rooms.get(player.room_id)

        if room is None:
            return [
                self._msg_to_player(
                    player_id,
                    "There is only darkness. (Room not found)",
                )
            ]

        lines: list[str] = [room.name, room.description]

        # List available exits
        if room.exits:
            exits = list(room.exits.keys())
            lines.append("")
            lines.append(f"Exits: {', '.join(exits)}")

        # List other players in the same room
        others = [
            world.players[pid].name
            for pid in room.players
            if pid != player_id and world.players[pid].is_connected
        ]
        stasis_players = [
            world.players[pid].name
            for pid in room.players
            if pid != player_id and not world.players[pid].is_connected
        ]
        
        if others:
            lines.append("")
            lines.append("Others here:")
            for name in others:
                lines.append(f" - {name}")
        
        if stasis_players:
            lines.append("")
            for name in stasis_players:
                lines.append(f"(In Stasis) The form of {name} is here, flickering in the prismatic state of stasis.")

        return [self._msg_to_player(player_id, "\n".join(lines))]

    def _say(self, player_id: PlayerId, text: str) -> List[Event]:
        """
        Player speaks; everyone in the same room hears it.
        """
        world = self.world

        if player_id not in world.players:
            return [
                self._msg_to_player(
                    player_id,
                    "No one hears you. (Player not found)",
                )
            ]

        player = world.players[player_id]
        room = world.rooms.get(player.room_id)

        if room is None:
            return [
                self._msg_to_player(
                    player_id,
                    "Your words vanish into nothing. (Room not found)",
                )
            ]

        events: List[Event] = []

        # Feedback to speaker
        events.append(self._msg_to_player(player_id, f'You say: "{text}"'))

        # Broadcast to everyone else in the room
        if room.players:
            events.append(
                self._msg_to_room(
                    room.id,
                    f'{player.name} says: "{text}"',
                    exclude={player_id},
                )
            )

        return events

    # ---------- Event dispatch ----------

    async def _dispatch_events(self, events: List[Event]) -> None:
        for ev in events:
            print(f"WorldEngine: dispatching event: {ev!r}")

            scope = ev.get("scope", "player")

            if scope == "player":
                target = ev.get("player_id")
                if not target:
                    continue
                q = self._listeners.get(target)
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
                room = self.world.rooms.get(room_id)
                if room is None:
                    continue

                exclude = set(ev.get("exclude", []))

                for pid in room.players:
                    if pid in exclude:
                        continue
                    q = self._listeners.get(pid)
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
                for pid, q in self._listeners.items():
                    if pid in exclude:
                        continue
                    wire_event = {
                        k: v
                        for k, v in ev.items()
                        if k not in ("scope", "exclude")
                    }
                    wire_event["player_id"] = pid
                    await q.put(wire_event)
