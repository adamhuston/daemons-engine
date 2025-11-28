# backend/app/engine/engine.py
import asyncio
import heapq
import time
import uuid
from typing import Dict, List, Any, Callable, Awaitable

from .world import World, WorldRoom, Direction, PlayerId, RoomId, AreaId, get_room_emoji, TimeEvent, Effect


Event = dict[str, Any]


class WorldEngine:
    """
    Core game engine.

    - Holds a reference to the in-memory World.
    - Consumes commands from players via an asyncio.Queue.
    - Produces events destined for players via per-player queues.
    - Supports per-player messages and room broadcasts.
    - Persists player stats to database on disconnect (and optionally periodically).
    """

    def __init__(
        self,
        world: World,
        db_session_factory: Callable[[], Awaitable[Any]] | None = None
    ) -> None:
        self.world = world
        self._db_session_factory = db_session_factory

        # Queue of (player_id, command_text)
        self._command_queue: asyncio.Queue[tuple[PlayerId, str]] = asyncio.Queue()

        # player_id -> queue of outgoing events (dicts)
        self._listeners: Dict[PlayerId, asyncio.Queue[Event]] = {}
        
        # Command history (for ! repeat command)
        self._last_commands: Dict[PlayerId, str] = {}
        
        # Time event system (Phase 2)
        self._time_events: List[TimeEvent] = []  # Min-heap priority queue
        self._time_loop_task: asyncio.Task | None = None
        self._event_ids: Dict[str, TimeEvent] = {}  # For cancellation lookup

    # ---------- Time event system (Phase 2) ----------

    async def start_time_system(self) -> None:
        """
        Start the time event processing loop.
        Should be called once during engine startup.
        """
        if self._time_loop_task is not None:
            print("[TimeSystem] Already running")
            return
        
        self._time_loop_task = asyncio.create_task(self._time_loop())
        print("[TimeSystem] Started")
        
        # Schedule world time advancement (every 30 seconds = 1 game hour)
        self._schedule_time_advancement()
    
    def _schedule_time_advancement(self) -> None:
        """
        Schedule recurring time advancement event.
        Advances time in each area independently based on area-specific time_scale.
        """
        from .world import game_hours_to_real_seconds
        
        async def advance_world_time():
            """Callback to advance time in all areas and reschedule."""
            # Advance each area's time independently
            for area in self.world.areas.values():
                area.area_time.advance(
                    real_seconds_elapsed=30.0,  # 30 seconds have elapsed
                    time_scale=area.time_scale  # Use area-specific time scale
                )
                
                time_str = area.area_time.format_full(area.time_scale)
                scale_note = f" (scale: {area.time_scale:.1f}x)" if area.time_scale != 1.0 else ""
                print(f"[WorldTime] {area.name}: {time_str}{scale_note}")
            
            # Also advance global world time (for areas without specific areas)
            self.world.world_time.advance(
                real_seconds_elapsed=30.0,
                time_scale=1.0  # Global time runs at normal speed
            )
            
            # Reschedule for next hour
            self._schedule_time_advancement()
        
        # Schedule 30 seconds from now
        interval = game_hours_to_real_seconds(1.0)  # 30 seconds
        self.schedule_event(
            delay_seconds=interval,
            callback=advance_world_time,
            event_id="world_time_tick"
        )
    
    async def stop_time_system(self) -> None:
        """
        Stop the time event processing loop.
        Should be called during engine shutdown.
        """
        if self._time_loop_task is None:
            return
        
        self._time_loop_task.cancel()
        try:
            await self._time_loop_task
        except asyncio.CancelledError:
            pass
        
        self._time_loop_task = None
        print("[TimeSystem] Stopped")
    
    async def _time_loop(self) -> None:
        """
        Core time event processing loop.
        
        Continuously checks for due events and executes them.
        Sleeps dynamically based on next event time to minimize CPU usage.
        """
        print("[TimeSystem] Loop started")
        
        while True:
            now = time.time()
            
            # Execute all due events
            while self._time_events and self._time_events[0].execute_at <= now:
                event = heapq.heappop(self._time_events)
                
                # Remove from ID lookup
                self._event_ids.pop(event.event_id, None)
                
                try:
                    await event.callback()
                    print(f"[TimeSystem] Executed event {event.event_id}")
                except Exception as e:
                    print(f"[TimeSystem] Error executing event {event.event_id}: {e}")
                
                # Reschedule if recurring
                if event.recurring and event.interval > 0:
                    event.execute_at = now + event.interval
                    heapq.heappush(self._time_events, event)
                    self._event_ids[event.event_id] = event
                    print(f"[TimeSystem] Rescheduled recurring event {event.event_id} for {event.interval}s")
            
            # Calculate sleep duration until next event
            if self._time_events:
                next_event_time = self._time_events[0].execute_at
                sleep_duration = min(1.0, max(0.01, next_event_time - time.time()))
            else:
                # No events scheduled, check every second
                sleep_duration = 1.0
            
            await asyncio.sleep(sleep_duration)
    
    def schedule_event(
        self,
        delay_seconds: float,
        callback: Callable[[], Awaitable[None]],
        event_id: str | None = None,
        recurring: bool = False,
    ) -> str:
        """
        Schedule a time event to execute after a delay.
        
        Args:
            delay_seconds: How long to wait before executing
            callback: Async function to call when event fires
            event_id: Optional unique ID (auto-generated if None)
            recurring: If True, reschedule with same delay after execution
        
        Returns:
            The event_id (for cancellation)
        """
        if event_id is None:
            event_id = str(uuid.uuid4())
        
        execute_at = time.time() + delay_seconds
        event = TimeEvent(
            execute_at=execute_at,
            callback=callback,
            event_id=event_id,
            recurring=recurring,
            interval=delay_seconds if recurring else 0.0,
        )
        
        heapq.heappush(self._time_events, event)
        self._event_ids[event_id] = event
        
        print(f"[TimeSystem] Scheduled event {event_id} for {delay_seconds}s (recurring={recurring})")
        return event_id
    
    def cancel_event(self, event_id: str) -> bool:
        """
        Cancel a scheduled time event.
        
        Args:
            event_id: The ID of the event to cancel
        
        Returns:
            True if event was found and cancelled, False otherwise
        """
        event = self._event_ids.pop(event_id, None)
        if event is None:
            return False
        
        # Mark as non-recurring so it won't reschedule
        event.recurring = False
        
        # We can't efficiently remove from heap, but it will be skipped
        # when popped since it's no longer in _event_ids
        print(f"[TimeSystem] Cancelled event {event_id}")
        return True

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
            
            # Send initial stat update event to populate client UI
            stat_event = self._stat_update_to_player(player_id, {
                "current_health": player.current_health,
                "max_health": player.max_health,
            })
            await self._dispatch_events([stat_event])
            
            # Broadcast awakening message if coming out of stasis
            if was_in_stasis:
                room = self.world.rooms.get(player.room_id)
                
                # Message to the player themselves
                awakening_self_msg = (
                    "The prismatic stasis shatters around you like glass. "
                    "You gasp as awareness floods back into your form."
                )
                self_event = self._msg_to_player(player_id, awakening_self_msg)
                await self._dispatch_events([self_event])
                
                # Broadcast to others in the room
                if room and len(room.players) > 1:
                    awaken_msg = (
                        f"The prismatic light around {player.name} shatters like glass. "
                        f"They gasp and return to awareness, freed from stasis."
                    )
                    room_event = self._msg_to_room(
                        room.id,
                        awaken_msg,
                        exclude={player_id}
                    )
                    await self._dispatch_events([room_event])
        
        return q

    def unregister_player(self, player_id: PlayerId) -> None:
        """
        Called when a player's WebSocket disconnects.
        """
        self._listeners.pop(player_id, None)
    
    async def save_player_stats(self, player_id: PlayerId) -> None:
        """
        Persist current WorldPlayer stats to the database.
        
        This is called on disconnect, and can also be called periodically
        (once tick system is implemented in Phase 2) or on key events.
        """
        if self._db_session_factory is None:
            return  # No DB session factory configured
        
        player = self.world.players.get(player_id)
        if not player:
            return  # Player not found in world
        
        # Import here to avoid circular dependency
        from sqlalchemy import select, update
        from ..models import Player as DBPlayer
        
        async with self._db_session_factory() as session:
            # Update player stats in database
            stmt = (
                update(DBPlayer)
                .where(DBPlayer.id == player_id)
                .values(
                    current_health=player.current_health,
                    current_energy=player.current_energy,
                    level=player.level,
                    experience=player.experience,
                    current_room_id=player.room_id,
                )
            )
            await session.execute(stmt)
            await session.commit()
            print(f"[Persistence] Saved stats for player {player.name} (ID: {player_id})")
    
    async def player_disconnect(self, player_id: PlayerId) -> None:
        """
        Handle a player disconnect by putting them in stasis and broadcasting a message.
        Should be called before unregister_player.
        """
        # Save player stats to database before disconnect
        await self.save_player_stats(player_id)
        
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

        # Handle repeat command "!"
        if raw == "!":
            last_cmd = self._last_commands.get(player_id)
            if not last_cmd:
                return [self._msg_to_player(player_id, "No previous command to repeat.")]
            # Don't store "!" itself, use the previous command
            raw = last_cmd
        else:
            # Store command for future repeat (but not "!")
            self._last_commands[player_id] = raw

        # Replace "self" keyword with player's own name
        player = self.world.players.get(player_id)
        if player:
            # Use word boundaries to avoid replacing "self" in words like "yourself" or "selfish"
            import re
            raw = re.sub(r'\bself\b', player.name, raw, flags=re.IGNORECASE)

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

        # Stats
        if cmd in {"stats", "sheet", "status"}:
            return self._show_stats(player_id)

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

        # Emotes
        if cmd in {"smile", "nod", "laugh", "cringe", "smirk", "frown", "wink", "lookaround"}:
            return self._emote(player_id, cmd)

        # Admin/debug commands for stat manipulation
        if cmd.startswith("heal"):
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                return [self._msg_to_player(player_id, "Heal who? Usage: heal <player_name>")]
            target_name = parts[1].strip()
            return self._heal(player_id, target_name)
        
        if cmd.startswith("hurt"):
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                return [self._msg_to_player(player_id, "Hurt who? Usage: hurt <player_name>")]
            target_name = parts[1].strip()
            return self._hurt(player_id, target_name)
        
        # Time system test command
        if cmd.startswith("testtimer"):
            parts = raw.split(maxsplit=1)
            delay = 5.0  # default 5 seconds
            if len(parts) >= 2:
                try:
                    delay = float(parts[1])
                except ValueError:
                    return [self._msg_to_player(player_id, "Invalid delay. Usage: testtimer [seconds]")]
            return self._test_timer(player_id, delay)
        
        # Effect system commands (Phase 2b)
        if cmd.startswith("bless"):
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                return [self._msg_to_player(player_id, "Bless who? Usage: bless <player_name>")]
            target_name = parts[1].strip()
            return self._bless(player_id, target_name)
        
        if cmd.startswith("poison"):
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                return [self._msg_to_player(player_id, "Poison who? Usage: poison <player_name>")]
            target_name = parts[1].strip()
            return self._poison(player_id, target_name)
        
        if cmd in {"effects", "status"}:
            return self._show_effects(player_id)
        
        if cmd == "time":
            return self._time(player_id)

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

    def _stat_update_to_player(
        self,
        player_id: PlayerId,
        stats: dict,
    ) -> Event:
        """
        Create a stat_update event for a player.
        """
        ev: Event = {
            "type": "stat_update",
            "scope": "player",
            "player_id": player_id,
            "payload": stats,
        }
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

    def _format_room_occupants(
        self,
        room: WorldRoom,
        exclude_player_id: PlayerId,
    ) -> list[str]:
        """
        Format the list of other players in a room (both connected and in stasis).
        Returns a list of formatted strings to append to room description.
        """
        lines: list[str] = []
        world = self.world
        
        # List connected players
        others = [
            world.players[pid].name
            for pid in room.players
            if pid != exclude_player_id and world.players[pid].is_connected
        ]
        
        # List players in stasis
        stasis_players = [
            world.players[pid].name
            for pid in room.players
            if pid != exclude_player_id and not world.players[pid].is_connected
        ]
        
        if others:
            lines.append("")
            for name in others:
                lines.append(f"{name} is here.")
        
        if stasis_players:
            lines.append("")
            for name in stasis_players:
                lines.append(f"(Stasis) The flickering form of {name} is here, suspended in prismatic stasis.")
        
        return lines

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
        room_emoji = get_room_emoji(new_room.room_type)
        description_lines.extend([
            "",
            f"**{room_emoji} {new_room.name}**",
            new_room.description
        ])
        
        # Trigger enter effect for new room
        if new_room.on_enter_effect:
            description_lines.append("")
            description_lines.append(new_room.on_enter_effect)
        
        # List other players in the new room
        description_lines.extend(self._format_room_occupants(new_room, player_id))
        
        # Add exits to the room description
        if new_room.exits:
            exits = list(new_room.exits.keys())
            description_lines.append("")
            description_lines.append(f"Exits: {', '.join(exits)}")
        
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

        room_emoji = get_room_emoji(room.room_type)
        lines: list[str] = [f"**{room_emoji} {room.name}**", room.description]

        # List other players in the same room
        lines.extend(self._format_room_occupants(room, player_id))

        # List available exits
        if room.exits:
            exits = list(room.exits.keys())
            lines.append("")
            lines.append(f"Exits: {', '.join(exits)}")

        return [self._msg_to_player(player_id, "\n".join(lines))]

    def _show_stats(self, player_id: PlayerId) -> List[Event]:
        """
        Display player's current stats.
        """
        world = self.world

        if player_id not in world.players:
            return [
                self._msg_to_player(
                    player_id,
                    "You have no form. (Player not found)",
                )
            ]

        player = world.players[player_id]

        # Calculate effective armor class (with buffs)
        effective_ac = player.get_effective_armor_class()
        ac_display = f"Armor Class: {effective_ac}"
        if effective_ac != player.armor_class:
            ac_display += f" ({player.armor_class} base)"

        lines: list[str] = [
            f"═══ Character Sheet: {player.name} ═══",
            "",
            f"Class: {player.character_class.title()}",
            f"Level: {player.level}",
            f"Experience: {player.experience} XP",
            "",
            "═══ Base Attributes ═══",
            f"Strength:     {player.strength}",
            f"Dexterity:    {player.dexterity}",
            f"Intelligence: {player.intelligence}",
            f"Vitality:     {player.vitality}",
            "",
            "═══ Combat Stats ═══",
            f"Health: {player.current_health}/{player.max_health}",
            f"Energy: {player.current_energy}/{player.max_energy}",
            ac_display,
        ]
        
        # Show active effects count if any
        if player.active_effects:
            lines.append("")
            lines.append(f"Active Effects: {len(player.active_effects)} (use 'effects' to view)")

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

    def _emote(self, player_id: PlayerId, emote: str) -> List[Event]:
        """
        Player performs an emote; everyone in the same room sees the third-person version.
        """
        world = self.world

        if player_id not in world.players:
            return [
                self._msg_to_player(
                    player_id,
                    "No one perceives you. (Player not found)",
                )
            ]

        player = world.players[player_id]
        room = world.rooms.get(player.room_id)

        if room is None:
            return [
                self._msg_to_player(
                    player_id,
                    "Your gesture fades into the void. (Room not found)",
                )
            ]

        # Define first-person and third-person messages for each emote
        emote_map = {
            "smile": ("😊 You smile.", f"😊 {player.name} smiles."),
            "nod": ("🙂‍↕️ You nod.", f"🙂‍↕️ {player.name} nods."),
            "laugh": ("😄 You laugh.", f"😄 {player.name} laughs."),
            "cringe": ("😖 You cringe.", f"😖 {player.name} cringes."),
            "smirk": ("😏 You smirk.", f"😏 {player.name} smirks."),
            "frown": ("🙁 You frown.", f"🙁 {player.name} frowns."),
            "wink": ("😉 You wink.", f"😉 {player.name} winks."),
            "lookaround": ("👀 You look around.", f"👀 {player.name} looks around."),
        }

        first_person, third_person = emote_map.get(emote, ("You do something.", f"{player.name} does something."))

        events: List[Event] = []

        # Feedback to the player
        events.append(self._msg_to_player(player_id, first_person))

        # Broadcast to everyone else in the room
        if len(room.players) > 1:
            events.append(
                self._msg_to_room(
                    room.id,
                    third_person,
                    exclude={player_id},
                )
            )

        return events

    def _heal(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """
        Heal a player by name (admin/debug command).
        """
        world = self.world
        events: List[Event] = []

        # Find target player by name
        target_player = None
        target_id = None
        for pid, p in world.players.items():
            if p.name.lower() == target_name.lower():
                target_player = p
                target_id = pid
                break
        
        if not target_player:
            return [self._msg_to_player(player_id, f"Player '{target_name}' not found.")]
        
        # Heal for 20 HP (or up to max)
        heal_amount = 20
        old_health = target_player.current_health
        target_player.current_health = min(target_player.current_health + heal_amount, target_player.max_health)
        actual_heal = target_player.current_health - old_health
        
        # Send stat_update to target
        events.append(self._stat_update_to_player(
            target_id,
            {
                "current_health": target_player.current_health,
                "max_health": target_player.max_health,
            }
        ))
        
        # Send message to target
        events.append(self._msg_to_player(
            target_id,
            f"*A warm glow surrounds you.* You are healed for {actual_heal} HP."
        ))
        
        # Send confirmation to healer
        if player_id != target_id:
            events.append(self._msg_to_player(
                player_id,
                f"You heal {target_player.name} for {actual_heal} HP."
            ))
        
        # Broadcast to others in the room
        player = world.players.get(player_id)
        room = world.rooms.get(target_player.room_id) if target_player else None
        if room and len(room.players) > 1:
            healer_name = player.name if player else "Someone"
            if player_id == target_id:
                room_msg = f"*A warm glow surrounds {target_player.name}.*"
            else:
                room_msg = f"*{healer_name} channels healing energy into {target_player.name}.*"
            events.append(self._msg_to_room(
                room.id,
                room_msg,
                exclude={player_id, target_id}
            ))
        
        return events

    def _hurt(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """
        Hurt a player by name (admin/debug command).
        """
        world = self.world
        events: List[Event] = []

        # Find target player by name
        target_player = None
        target_id = None
        for pid, p in world.players.items():
            if p.name.lower() == target_name.lower():
                target_player = p
                target_id = pid
                break
        
        if not target_player:
            return [self._msg_to_player(player_id, f"Player '{target_name}' not found.")]
        
        # Damage for 15 HP (but not below 1)
        damage_amount = 15
        old_health = target_player.current_health
        target_player.current_health = max(target_player.current_health - damage_amount, 1)
        actual_damage = old_health - target_player.current_health
        
        # Send stat_update to target
        events.append(self._stat_update_to_player(
            target_id,
            {
                "current_health": target_player.current_health,
                "max_health": target_player.max_health,
            }
        ))
        
        # Send message to target
        events.append(self._msg_to_player(
            target_id,
            f"*A dark force strikes you!* You take {actual_damage} damage."
        ))
        
        # Send confirmation to attacker
        if player_id != target_id:
            events.append(self._msg_to_player(
                player_id,
                f"You hurt {target_player.name} for {actual_damage} damage."
            ))
        
        # Broadcast to others in the room
        player = world.players.get(player_id)
        room = world.rooms.get(target_player.room_id) if target_player else None
        if room and len(room.players) > 1:
            attacker_name = player.name if player else "Someone"
            if player_id == target_id:
                room_msg = f"*Dark energy lashes at {target_player.name}!*"
            else:
                room_msg = f"*{attacker_name} strikes {target_player.name} with dark energy!*"
            events.append(self._msg_to_room(
                room.id,
                room_msg,
                exclude={player_id, target_id}
            ))
        
        return events

    def _test_timer(self, player_id: PlayerId, delay: float) -> List[Event]:
        """
        Test command to demonstrate time event system.
        Schedules a message to be sent after a delay.
        """
        world = self.world
        player = world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "Player not found.")]
        
        # Get player's area for time scale info
        room = world.rooms.get(player.room_id)
        area = None
        time_scale = 1.0
        area_name = "global time"
        
        if room and room.area_id and room.area_id in world.areas:
            area = world.areas[room.area_id]
            time_scale = area.time_scale
            area_name = area.name
        
        # Calculate in-game time that will pass
        from .world import real_seconds_to_game_minutes
        game_minutes = real_seconds_to_game_minutes(delay) * time_scale
        
        # Create callback that will send a message when timer fires
        async def timer_callback():
            event = self._msg_to_player(
                player_id,
                f"⏰ Timer expired! {delay} seconds have passed."
            )
            await self._dispatch_events([event])
        
        # Schedule the event
        event_id = self.schedule_event(delay, timer_callback)
        
        # Build response message
        scale_note = f" at {time_scale:.1f}x timescale" if time_scale != 1.0 else ""
        message = f"⏱️ Timer set for {delay} seconds ({game_minutes:.1f} in-game minutes in {area_name}{scale_note})"
        
        return [self._msg_to_player(player_id, message)]

    def _bless(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """
        Apply a temporary armor class buff to a player (Phase 2b example).
        """
        world = self.world
        events: List[Event] = []

        # Find target player by name
        target_player = None
        target_id = None
        for pid, p in world.players.items():
            if p.name.lower() == target_name.lower():
                target_player = p
                target_id = pid
                break
        
        if not target_player:
            return [self._msg_to_player(player_id, f"Player '{target_name}' not found.")]
        
        # Create blessing effect
        effect_id = str(uuid.uuid4())
        effect = Effect(
            effect_id=effect_id,
            name="Blessed",
            effect_type="buff",
            stat_modifiers={"armor_class": 5},
            duration=30.0,  # 30 seconds
        )
        
        # Apply effect to player
        target_player.apply_effect(effect)
        
        # Schedule effect expiration
        async def expiration_callback():
            removed_effect = target_player.remove_effect(effect_id)
            if removed_effect:
                # Send expiration message
                expire_event = self._msg_to_player(
                    target_id,
                    "✨ The divine blessing fades away."
                )
                await self._dispatch_events([expire_event])
                
                # Send stat update with recalculated AC
                stat_event = self._stat_update_to_player(
                    target_id,
                    {"armor_class": target_player.get_effective_armor_class()}
                )
                await self._dispatch_events([stat_event])
        
        expiration_event_id = self.schedule_event(effect.duration, expiration_callback)
        effect.expiration_event_id = expiration_event_id
        
        # Send stat update with new AC
        events.append(self._stat_update_to_player(
            target_id,
            {"armor_class": target_player.get_effective_armor_class()}
        ))
        
        # Send message to target
        events.append(self._msg_to_player(
            target_id,
            "✨ *Divine light surrounds you!* You feel blessed. (+5 Armor Class for 30 seconds)"
        ))
        
        # Send confirmation to caster
        if player_id != target_id:
            events.append(self._msg_to_player(
                player_id,
                f"You bless {target_player.name} with divine protection."
            ))
        
        # Broadcast to others in the room
        player = world.players.get(player_id)
        room = world.rooms.get(target_player.room_id) if target_player else None
        if room and len(room.players) > 1:
            caster_name = player.name if player else "Someone"
            if player_id == target_id:
                room_msg = f"✨ *Divine light surrounds {target_player.name}!*"
            else:
                room_msg = f"✨ *{caster_name} blesses {target_player.name} with divine light!*"
            events.append(self._msg_to_room(
                room.id,
                room_msg,
                exclude={player_id, target_id}
            ))
        
        return events

    def _poison(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """
        Apply a damage over time (DoT) poison effect to a player (Phase 2b example).
        """
        world = self.world
        events: List[Event] = []

        # Find target player by name
        target_player = None
        target_id = None
        for pid, p in world.players.items():
            if p.name.lower() == target_name.lower():
                target_player = p
                target_id = pid
                break
        
        if not target_player:
            return [self._msg_to_player(player_id, f"Player '{target_name}' not found.")]
        
        # Create poison effect
        effect_id = str(uuid.uuid4())
        effect = Effect(
            effect_id=effect_id,
            name="Poisoned",
            effect_type="dot",
            duration=15.0,  # 15 seconds total
            interval=3.0,   # Damage every 3 seconds
            magnitude=5,    # 5 damage per tick
        )
        
        # Apply effect to player
        target_player.apply_effect(effect)
        
        # Periodic damage callback
        async def poison_tick():
            # Check if effect still active
            if effect_id not in target_player.active_effects:
                return
            
            # Apply damage
            old_health = target_player.current_health
            target_player.current_health = max(target_player.current_health - effect.magnitude, 1)
            actual_damage = old_health - target_player.current_health
            
            # Send damage message
            damage_event = self._msg_to_player(
                target_id,
                f"🤢 *The poison burns through your veins!* You take {actual_damage} poison damage."
            )
            await self._dispatch_events([damage_event])
            
            # Send stat update
            stat_event = self._stat_update_to_player(
                target_id,
                {
                    "current_health": target_player.current_health,
                    "max_health": target_player.max_health,
                }
            )
            await self._dispatch_events([stat_event])
        
        # Schedule periodic damage (recurring)
        periodic_event_id = self.schedule_event(
            effect.interval,
            poison_tick,
            recurring=True
        )
        effect.periodic_event_id = periodic_event_id
        
        # Schedule effect expiration
        async def expiration_callback():
            # Cancel periodic damage
            if effect.periodic_event_id:
                self.cancel_event(effect.periodic_event_id)
            
            # Remove effect
            removed_effect = target_player.remove_effect(effect_id)
            if removed_effect:
                # Send expiration message
                expire_event = self._msg_to_player(
                    target_id,
                    "🧪 The poison has run its course."
                )
                await self._dispatch_events([expire_event])
        
        expiration_event_id = self.schedule_event(effect.duration, expiration_callback)
        effect.expiration_event_id = expiration_event_id
        
        # Send message to target
        events.append(self._msg_to_player(
            target_id,
            "🤢 *Vile toxins course through your body!* You are poisoned. (5 damage every 3 seconds for 15 seconds)"
        ))
        
        # Send confirmation to poisoner
        if player_id != target_id:
            events.append(self._msg_to_player(
                player_id,
                f"You poison {target_player.name} with toxic energy."
            ))
        
        # Broadcast to others in the room
        player = world.players.get(player_id)
        room = world.rooms.get(target_player.room_id) if target_player else None
        if room and len(room.players) > 1:
            poisoner_name = player.name if player else "Someone"
            if player_id == target_id:
                room_msg = f"🤢 *Vile toxins course through {target_player.name}!*"
            else:
                room_msg = f"🤢 *{poisoner_name} poisons {target_player.name} with toxic energy!*"
            events.append(self._msg_to_room(
                room.id,
                room_msg,
                exclude={player_id, target_id}
            ))
        
        return events

    def _time(self, player_id: PlayerId) -> List[Event]:
        """
        Display the current time for the player's area.
        Usage: time
        """
        world = self.world
        
        # Get player's current area to use area-specific time and flavor text
        player = world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "Player not found.")]
        
        room = world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "Room not found.")]
        
        # Use area-specific time if in an area, otherwise global time
        if room.area_id and room.area_id in world.areas:
            area = world.areas[room.area_id]
            time_info = area.area_time.format_full(area.time_scale)
            phase = area.area_time.get_time_of_day(area.time_scale)
            flavor_text = area.time_phases.get(phase, "")
            
            # Build message with area context
            message_parts = [time_info]
            if area.name:
                message_parts.append(f"*{area.name}*")
            if flavor_text:
                message_parts.append("")
                message_parts.append(flavor_text)
            
            # Add ambient sound if present
            if area.ambient_sound:
                message_parts.append("")
                message_parts.append(f"*{area.ambient_sound}*")
            
            # Note if time flows differently here
            if area.time_scale != 1.0:
                message_parts.append("")
                if area.time_scale > 1.0:
                    message_parts.append(f"⚡ *Time flows {area.time_scale:.1f}x faster here.*")
                else:
                    message_parts.append(f"🐌 *Time flows {area.time_scale:.1f}x slower here.*")
            
            message = "\n".join(message_parts)
        else:
            # Use global world time for rooms not in an area
            time_info = world.world_time.format_full()
            phase = world.world_time.get_time_of_day()
            from .world import DEFAULT_TIME_PHASES
            flavor_text = DEFAULT_TIME_PHASES.get(phase, "")
            message = f"{time_info}\n\n{flavor_text}"
        
        return [self._msg_to_player(player_id, message)]

    def _show_effects(self, player_id: PlayerId) -> List[Event]:
        """
        Display active effects on the player.
        """
        world = self.world

        if player_id not in world.players:
            return [
                self._msg_to_player(
                    player_id,
                    "You have no form. (Player not found)",
                )
            ]

        player = world.players[player_id]

        if not player.active_effects:
            return [self._msg_to_player(player_id, "You have no active effects.")]

        lines: list[str] = [
            "═══ Active Effects ═══",
            ""
        ]

        for effect in player.active_effects.values():
            remaining = effect.get_remaining_duration()
            lines.append(f"**{effect.name}** ({effect.effect_type})")
            lines.append(f"  Duration: {remaining:.1f}s remaining")
            
            if effect.stat_modifiers:
                mods = ", ".join([f"{stat} {value:+d}" for stat, value in effect.stat_modifiers.items()])
                lines.append(f"  Modifiers: {mods}")
            
            if effect.magnitude != 0:
                lines.append(f"  Periodic: {effect.magnitude:+d} HP every {effect.interval:.1f}s")
            
            lines.append("")

        return [self._msg_to_player(player_id, "\n".join(lines))]

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
