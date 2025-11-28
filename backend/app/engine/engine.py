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
            
            # Send initial room description
            look_events = self._look(player_id)
            await self._dispatch_events(look_events)
            
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
        Persist current WorldPlayer stats and inventory to the database.
        
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
        from ..models import Player as DBPlayer, PlayerInventory as DBPlayerInventory, ItemInstance as DBItemInstance
        
        async with self._db_session_factory() as session:
            # Update player stats in database
            player_stmt = (
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
            await session.execute(player_stmt)
            
            # Update player inventory metadata (Phase 3)
            if player.inventory_meta:
                inventory_stmt = (
                    update(DBPlayerInventory)
                    .where(DBPlayerInventory.player_id == player_id)
                    .values(
                        max_weight=player.inventory_meta.max_weight,
                        max_slots=player.inventory_meta.max_slots,
                        current_weight=player.inventory_meta.current_weight,
                        current_slots=player.inventory_meta.current_slots,
                    )
                )
                await session.execute(inventory_stmt)
            
            # Update all items owned by this player (Phase 3)
            for item_id in player.inventory_items:
                if item_id in self.world.items:
                    item = self.world.items[item_id]
                    item_stmt = (
                        update(DBItemInstance)
                        .where(DBItemInstance.id == item_id)
                        .values(
                            player_id=player_id,
                            room_id=None,
                            container_id=item.container_id,
                            quantity=item.quantity,
                            current_durability=item.current_durability,
                            equipped_slot=item.equipped_slot,
                            instance_data=item.instance_data,
                        )
                    )
                    await session.execute(item_stmt)
            
            await session.commit()
            print(f"[Persistence] Saved stats and inventory for player {player.name} (ID: {player_id})")
    
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
        if cmd in {"look", "l"} or cmd.startswith("look ") or cmd.startswith("l "):
            # Check if looking at specific item
            parts = raw.split(maxsplit=1)
            if len(parts) > 1:
                item_name = parts[1]
                return self._look_at_item(player_id, item_name)
            else:
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

        # Inventory system commands (Phase 3)
        if cmd in {"inventory", "inv", "i"}:
            return self._inventory(player_id)
        
        if cmd.startswith(("get ", "take ", "pickup ")) or cmd in {"get", "take", "pickup"}:
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                return [self._msg_to_player(player_id, "Get what?")]
            item_arg = parts[1].strip()
            
            # Check for "get <item> from <container>" syntax
            from_match = None
            for separator in [" from ", " out of ", " out "]:
                if separator in item_arg.lower():
                    idx = item_arg.lower().find(separator)
                    item_name = item_arg[:idx].strip()
                    container_name = item_arg[idx + len(separator):].strip()
                    return self._get_from_container(player_id, item_name, container_name)
            
            # Regular get from room
            return self._get(player_id, item_arg)
        
        if cmd.startswith(("put ", "place ", "store ")) or cmd in {"put", "place", "store"}:
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                return [self._msg_to_player(player_id, "Put what where? Usage: put <item> in <container>")]
            item_arg = parts[1].strip()
            
            # Parse "put <item> in <container>" syntax
            for separator in [" in ", " into ", " inside "]:
                if separator in item_arg.lower():
                    idx = item_arg.lower().find(separator)
                    item_name = item_arg[:idx].strip()
                    container_name = item_arg[idx + len(separator):].strip()
                    return self._put_in_container(player_id, item_name, container_name)
            
            return [self._msg_to_player(player_id, "Put what where? Usage: put <item> in <container>")]
        
        if cmd.startswith("drop"):
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                return [self._msg_to_player(player_id, "Drop what?")]
            item_name = parts[1].strip()
            return self._drop(player_id, item_name)
        
        if cmd.startswith(("equip ", "wear ", "wield ")) or cmd in {"equip", "wear", "wield"}:
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                return [self._msg_to_player(player_id, "Equip what?")]
            item_name = parts[1].strip()
            return self._equip(player_id, item_name)
        
        if cmd.startswith(("unequip ", "remove ")) or cmd in {"unequip", "remove"}:
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                return [self._msg_to_player(player_id, "Unequip what?")]
            item_name = parts[1].strip()
            return self._unequip(player_id, item_name)
        
        if cmd.startswith(("use ", "consume ", "drink ")) or cmd in {"use", "consume", "drink"}:
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                return [self._msg_to_player(player_id, "Use what?")]
            item_name = parts[1].strip()
            return self._use(player_id, item_name)
        
        if cmd.startswith("give ") or cmd == "give":
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                return [self._msg_to_player(player_id, "Give what to whom? Usage: give <item> <player>")]
            item_arg = parts[1].strip()
            
            # Parse "give <item> to <player>" or "give <item> <player>" syntax
            for separator in [" to "]:
                if separator in item_arg.lower():
                    idx = item_arg.lower().find(separator)
                    item_name = item_arg[:idx].strip()
                    target_name = item_arg[idx + len(separator):].strip()
                    return self._give(player_id, item_name, target_name)
            
            # Try splitting on last word as player name
            words = item_arg.rsplit(maxsplit=1)
            if len(words) == 2:
                item_name, target_name = words
                return self._give(player_id, item_name.strip(), target_name.strip())
            
            return [self._msg_to_player(player_id, "Give what to whom? Usage: give <item> <player>")]

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
    
    def _emit_stat_update(self, player_id: PlayerId) -> List[Event]:
        """Helper function to emit stat update for a player."""
        if player_id not in self.world.players:
            return []
        
        player = self.world.players[player_id]
        
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
        
        return [self._stat_update_to_player(player_id, payload)]

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
        
        # Show items in new room (Phase 3)
        if new_room.items:
            items_here = []
            for item_id in new_room.items:
                item = self.world.items[item_id]
                template = self.world.item_templates[item.template_id]
                quantity_str = f" x{item.quantity}" if item.quantity > 1 else ""
                items_here.append(f"  {template.name}{quantity_str}")
            
            description_lines.append("")
            description_lines.append("Items here:")
            description_lines.extend(items_here)
        
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

        # Show items in room (Phase 3)
        if room.items:
            items_here = []
            for item_id in room.items:
                item = world.items[item_id]
                template = world.item_templates[item.template_id]
                quantity_str = f" x{item.quantity}" if item.quantity > 1 else ""
                items_here.append(f"  {template.name}{quantity_str}")
            
            lines.append("")
            lines.append("Items here:")
            lines.extend(items_here)

        # List available exits
        if room.exits:
            exits = list(room.exits.keys())
            lines.append("")
            lines.append(f"Exits: {', '.join(exits)}")

        return [self._msg_to_player(player_id, "\n".join(lines))]

    def _look_at_item(self, player_id: PlayerId, item_name: str) -> List[Event]:
        """Examine an item in detail, showing description and container contents."""
        from .inventory import find_item_by_name, find_item_in_room
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        room = world.rooms[player.room_id]
        
        # First check player's inventory and equipped items
        found_item_id = find_item_by_name(world, player_id, item_name, "both")
        
        # If not found in inventory, check room
        if not found_item_id:
            found_item_id = find_item_in_room(world, room.id, item_name)
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't see '{item_name}' anywhere.")]
        
        item = world.items[found_item_id]
        template = world.item_templates[item.template_id]
        
        # Build detailed description
        lines = [f"**{template.name}**"]
        lines.append(template.description)
        
        # Add flavor text if available
        if template.flavor_text:
            lines.append("")
            lines.append(template.flavor_text)
        
        # Show item properties
        lines.append("")
        properties = []
        
        # Item type and rarity
        type_str = template.item_type.title()
        if template.item_subtype:
            type_str += f" ({template.item_subtype})"
        if template.rarity != "common":
            type_str += f" - {template.rarity.title()}"
        properties.append(f"Type: {type_str}")
        
        # Weight
        total_weight = template.weight * item.quantity
        if item.quantity > 1:
            properties.append(f"Weight: {total_weight:.1f} kg ({template.weight:.1f} kg each)")
        else:
            properties.append(f"Weight: {total_weight:.1f} kg")
        
        # Durability
        if template.has_durability and item.current_durability is not None:
            properties.append(f"Durability: {item.current_durability}/{template.max_durability}")
        
        # Equipment slot
        if template.equipment_slot:
            slot_name = template.equipment_slot.replace("_", " ").title()
            properties.append(f"Equipment Slot: {slot_name}")
        
        # Stat modifiers
        if template.stat_modifiers:
            stat_strs = []
            for stat, value in template.stat_modifiers.items():
                sign = "+" if value >= 0 else ""
                stat_display = stat.replace("_", " ").title()
                stat_strs.append(f"{sign}{value} {stat_display}")
            properties.append(f"Effects: {', '.join(stat_strs)}")
        
        # Value
        if template.value > 0:
            total_value = template.value * item.quantity
            if item.quantity > 1:
                properties.append(f"Value: {total_value} gold ({template.value} each)")
            else:
                properties.append(f"Value: {total_value} gold")
        
        # Stackable info
        if template.max_stack_size > 1:
            properties.append(f"Quantity: {item.quantity}/{template.max_stack_size}")
        elif item.quantity > 1:
            properties.append(f"Quantity: {item.quantity}")
        
        lines.extend(f"  {prop}" for prop in properties)
        
        # Show equipped status
        if item.is_equipped():
            lines.append("")
            lines.append("  [Currently Equipped]")
        
        # Container contents
        if template.is_container:
            lines.append("")
            container_items = []
            
            # Find all items in this container
            for other_item_id, other_item in world.items.items():
                if other_item.container_id == found_item_id:
                    other_template = world.item_templates[other_item.template_id]
                    quantity_str = f" x{other_item.quantity}" if other_item.quantity > 1 else ""
                    container_items.append(f"  {other_template.name}{quantity_str}")
            
            if container_items:
                lines.append(f"**Contents of {template.name}:**")
                lines.extend(container_items)
                
                # Show container capacity if available
                if template.container_capacity:
                    if template.container_type == "weight_based":
                        # Calculate current weight in container
                        container_weight = 0.0
                        for other_item_id, other_item in world.items.items():
                            if other_item.container_id == found_item_id:
                                other_template = world.item_templates[other_item.template_id]
                                container_weight += other_template.weight * other_item.quantity
                        lines.append(f"  Weight: {container_weight:.1f}/{template.container_capacity:.1f} kg")
                    else:
                        # Slot-based container
                        item_count = len(container_items)
                        lines.append(f"  Slots: {item_count}/{template.container_capacity}")
            else:
                lines.append(f"**{template.name} is empty.**")
        
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

    # ---------- Inventory system commands (Phase 3) ----------

    def _inventory(self, player_id: PlayerId) -> List[Event]:
        """Show player inventory."""
        from .inventory import calculate_inventory_weight
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        inventory = player.inventory_meta
        
        if not inventory:
            return [self._msg_to_player(player_id, "You have no inventory.")]
        
        if not player.inventory_items:
            return [self._msg_to_player(player_id, "Your inventory is empty.")]
        
        # Group items by template (for stacking display)
        items_display = []
        for item_id in player.inventory_items:
            item = world.items[item_id]
            template = world.item_templates[item.template_id]
            
            equipped_marker = " [equipped]" if item.is_equipped() else ""
            quantity_str = f" x{item.quantity}" if item.quantity > 1 else ""
            
            items_display.append(f"  {template.name}{quantity_str}{equipped_marker}")
        
        weight = calculate_inventory_weight(world, player_id)
        
        lines = [
            "=== Inventory ===",
            *items_display,
            "",
            f"Weight: {weight:.1f}/{inventory.max_weight:.1f} kg",
            f"Slots: {inventory.current_slots}/{inventory.max_slots}"
        ]
        
        return [self._msg_to_player(player_id, "\n".join(lines))]

    def _get(self, player_id: PlayerId, item_name: str) -> List[Event]:
        """Pick up item from room (one at a time for stacks)."""
        from .inventory import add_item_to_inventory, InventoryFullError, find_item_in_room
        import uuid
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        room = world.rooms[player.room_id]
        
        # Find item in room by name
        found_item_id = find_item_in_room(world, room.id, item_name)
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't see '{item_name}' here.")]
        
        item = world.items[found_item_id]
        template = world.item_templates[item.template_id]
        
        # Check quest item / no pickup flags
        if template.flags.get("no_pickup"):
            return [self._msg_to_player(player_id, f"You cannot pick up {template.name}.")]
        
        # Handle stacked items - only pick up one at a time
        if item.quantity > 1:
            # Reduce stack on ground
            item.quantity -= 1
            
            # Create a new item instance for the one we're picking up
            from .world import WorldItem
            new_item_id = str(uuid.uuid4())
            new_item = WorldItem(
                id=new_item_id,
                template_id=item.template_id,
                room_id=None,
                player_id=player_id,
                container_id=None,
                quantity=1,
                current_durability=item.current_durability,
                equipped_slot=None,
                instance_data=dict(item.instance_data)
            )
            world.items[new_item_id] = new_item
            
            # Try to add to inventory (will stack with existing if possible)
            try:
                add_item_to_inventory(world, player_id, new_item_id)
                
                return [
                    self._msg_to_player(player_id, f"You pick up {template.name}."),
                    self._msg_to_room(room.id, f"{player.name} picks up {template.name}.", exclude={player_id})
                ]
                
            except InventoryFullError as e:
                # Revert: add back to ground stack and remove new item
                item.quantity += 1
                del world.items[new_item_id]
                return [self._msg_to_player(player_id, str(e))]
        else:
            # Single item - just move it
            try:
                room.items.remove(found_item_id)
                add_item_to_inventory(world, player_id, found_item_id)
                
                return [
                    self._msg_to_player(player_id, f"You pick up {template.name}."),
                    self._msg_to_room(room.id, f"{player.name} picks up {template.name}.", exclude={player_id})
                ]
                
            except InventoryFullError as e:
                # Return item to room
                room.items.add(found_item_id)
                item.room_id = room.id
                return [self._msg_to_player(player_id, str(e))]

    def _get_from_container(self, player_id: PlayerId, item_name: str, container_name: str) -> List[Event]:
        """Get an item from a container."""
        from .inventory import find_item_by_name, add_item_to_inventory, InventoryFullError
        import uuid
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        
        # Find the container (in inventory or room)
        container_id = find_item_by_name(world, player_id, container_name, "both")
        
        if not container_id:
            # Check room for container
            from .inventory import find_item_in_room
            room = world.rooms[player.room_id]
            container_id = find_item_in_room(world, room.id, container_name)
        
        if not container_id:
            return [self._msg_to_player(player_id, f"You don't see '{container_name}' anywhere.")]
        
        container = world.items[container_id]
        container_template = world.item_templates[container.template_id]
        
        if not container_template.is_container:
            return [self._msg_to_player(player_id, f"{container_template.name} is not a container.")]
        
        # Find the item inside the container using keyword matching
        from .inventory import _matches_item_name
        item_name_lower = item_name.lower()
        found_item_id = None
        
        # Exact match first
        for other_id, other_item in world.items.items():
            if other_item.container_id == container_id:
                other_template = world.item_templates[other_item.template_id]
                if _matches_item_name(other_template, item_name_lower, exact=True):
                    found_item_id = other_id
                    break
        
        # Partial match if no exact match
        if not found_item_id:
            for other_id, other_item in world.items.items():
                if other_item.container_id == container_id:
                    other_template = world.item_templates[other_item.template_id]
                    if _matches_item_name(other_template, item_name_lower, exact=False):
                        found_item_id = other_id
                        break
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't see '{item_name}' in {container_template.name}.")]
        
        item = world.items[found_item_id]
        template = world.item_templates[item.template_id]
        
        # Handle stacks - take one at a time
        if item.quantity > 1:
            item.quantity -= 1
            
            from .world import WorldItem
            new_item_id = str(uuid.uuid4())
            new_item = WorldItem(
                id=new_item_id,
                template_id=item.template_id,
                room_id=None,
                player_id=player_id,
                container_id=None,
                quantity=1,
                current_durability=item.current_durability,
                equipped_slot=None,
                instance_data=dict(item.instance_data)
            )
            world.items[new_item_id] = new_item
            
            try:
                add_item_to_inventory(world, player_id, new_item_id)
                return [self._msg_to_player(player_id, f"You take {template.name} from {container_template.name}.")]
            except InventoryFullError as e:
                item.quantity += 1
                del world.items[new_item_id]
                return [self._msg_to_player(player_id, str(e))]
        else:
            # Single item - move it
            item.container_id = None
            try:
                add_item_to_inventory(world, player_id, found_item_id)
                return [self._msg_to_player(player_id, f"You take {template.name} from {container_template.name}.")]
            except InventoryFullError as e:
                item.container_id = container_id
                return [self._msg_to_player(player_id, str(e))]

    def _put_in_container(self, player_id: PlayerId, item_name: str, container_name: str) -> List[Event]:
        """Put an item into a container."""
        from .inventory import find_item_by_name, remove_item_from_inventory, InventoryError
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        
        # Find the item in inventory
        item_id = find_item_by_name(world, player_id, item_name, "inventory")
        
        if not item_id:
            return [self._msg_to_player(player_id, f"You don't have '{item_name}'.")]
        
        item = world.items[item_id]
        template = world.item_templates[item.template_id]
        
        # Can't put equipped items in containers
        if item.is_equipped():
            return [self._msg_to_player(player_id, f"Unequip {template.name} first.")]
        
        # Find the container (in inventory or room)
        container_id = find_item_by_name(world, player_id, container_name, "both")
        
        if not container_id:
            # Check room for container
            from .inventory import find_item_in_room
            room = world.rooms[player.room_id]
            container_id = find_item_in_room(world, room.id, container_name)
        
        if not container_id:
            return [self._msg_to_player(player_id, f"You don't see '{container_name}' anywhere.")]
        
        # Can't put item in itself
        if container_id == item_id:
            return [self._msg_to_player(player_id, "You can't put something inside itself.")]
        
        container = world.items[container_id]
        container_template = world.item_templates[container.template_id]
        
        if not container_template.is_container:
            return [self._msg_to_player(player_id, f"{container_template.name} is not a container.")]
        
        # Check container capacity
        if container_template.container_capacity:
            # Count current items in container
            current_count = 0
            current_weight = 0.0
            
            for other_id, other_item in world.items.items():
                if other_item.container_id == container_id:
                    current_count += 1
                    other_template = world.item_templates[other_item.template_id]
                    current_weight += other_template.weight * other_item.quantity
            
            if container_template.container_type == "weight_based":
                new_weight = current_weight + (template.weight * item.quantity)
                if new_weight > container_template.container_capacity:
                    return [self._msg_to_player(player_id, f"{container_template.name} is too full. ({current_weight:.1f}/{container_template.container_capacity:.1f} kg)")]
            else:
                # Slot-based
                if current_count >= container_template.container_capacity:
                    return [self._msg_to_player(player_id, f"{container_template.name} is full. ({current_count}/{container_template.container_capacity} slots)")]
        
        # Remove from inventory and put in container
        try:
            player.inventory_items.remove(item_id)
            item.player_id = None
            item.container_id = container_id
            
            # Update inventory metadata
            if player.inventory_meta:
                from .inventory import calculate_inventory_weight
                player.inventory_meta.current_weight = calculate_inventory_weight(world, player_id)
                player.inventory_meta.current_slots = len(player.inventory_items)
            
            return [self._msg_to_player(player_id, f"You put {template.name} in {container_template.name}.")]
            
        except KeyError:
            return [self._msg_to_player(player_id, f"Failed to put {template.name} in {container_template.name}.")]

    def _drop(self, player_id: PlayerId, item_name: str) -> List[Event]:
        """Drop item from inventory."""
        from .inventory import remove_item_from_inventory, InventoryError, find_item_by_name
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        room = world.rooms[player.room_id]
        
        # Find item in inventory
        found_item_id = find_item_by_name(world, player_id, item_name, "inventory")
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't have '{item_name}'.")]
        
        item = world.items[found_item_id]
        template = world.item_templates[item.template_id]
        
        # Check no-drop flag
        if template.flags.get("no_drop"):
            return [self._msg_to_player(player_id, f"You cannot drop {template.name}.")]
        
        try:
            remove_item_from_inventory(world, player_id, found_item_id)
            item.room_id = room.id
            room.items.add(found_item_id)
            
            # Broadcast to room
            return [
                self._msg_to_player(player_id, f"You drop {template.name}."),
                self._msg_to_room(room.id, f"{player.name} drops {template.name}.", exclude={player_id})
            ]
            
        except InventoryError as e:
            return [self._msg_to_player(player_id, str(e))]

    def _equip(self, player_id: PlayerId, item_name: str) -> List[Event]:
        """Equip item."""
        from .inventory import equip_item, InventoryError, find_item_by_name
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        
        # Find item in inventory
        found_item_id = find_item_by_name(world, player_id, item_name, "inventory")
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't have '{item_name}'.")]
        
        template = world.item_templates[world.items[found_item_id].template_id]
        
        try:
            previously_equipped = equip_item(world, player_id, found_item_id)
            
            messages = [f"You equip {template.name}."]
            
            if previously_equipped:
                prev_template = world.item_templates[world.items[previously_equipped].template_id]
                messages.append(f"You unequip {prev_template.name}.")
            
            # Emit stat update event (reuse existing pattern from effect system)
            events = [self._msg_to_player(player_id, "\n".join(messages))]
            events.extend(self._emit_stat_update(player_id))
            
            return events
            
        except InventoryError as e:
            return [self._msg_to_player(player_id, str(e))]

    def _unequip(self, player_id: PlayerId, item_name: str) -> List[Event]:
        """Unequip item."""
        from .inventory import unequip_item, InventoryError, find_item_by_name
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        
        # Find equipped item
        found_item_id = find_item_by_name(world, player_id, item_name, "equipped")
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't have '{item_name}' equipped.")]
        
        template = world.item_templates[world.items[found_item_id].template_id]
        
        try:
            unequip_item(world, player_id, found_item_id)
            
            # Emit stat update event
            events = [self._msg_to_player(player_id, f"You unequip {template.name}.")]
            events.extend(self._emit_stat_update(player_id))
            
            return events
            
        except InventoryError as e:
            return [self._msg_to_player(player_id, str(e))]

    def _use(self, player_id: PlayerId, item_name: str) -> List[Event]:
        """Use/consume item."""
        from .inventory import find_item_by_name, remove_item_from_inventory
        from .world import Effect
        import time
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        
        # Find item in inventory
        found_item_id = find_item_by_name(world, player_id, item_name, "inventory")
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't have '{item_name}'.")]
        
        item = world.items[found_item_id]
        template = world.item_templates[item.template_id]
        
        if not template.is_consumable:
            return [self._msg_to_player(player_id, f"You can't consume {template.name}.")]
        
        events = []
        
        # Apply consume effect
        if template.consume_effect:
            effect_data = template.consume_effect
            effect_id = f"consumable_{found_item_id}_{time.time()}"
            
            effect = Effect(
                effect_id=effect_id,
                name=effect_data.get("name", "Consumable Effect"),
                effect_type=effect_data.get("effect_type", "buff"),
                stat_modifiers=effect_data.get("stat_modifiers", {}),
                duration=effect_data.get("duration", 0.0),
                magnitude=effect_data.get("magnitude", 0),
            )
            
            # Apply instant healing if hot/magnitude specified
            if effect.magnitude > 0 and effect.effect_type == "hot":
                old_health = player.current_health
                player.current_health = min(
                    player.max_health,
                    player.current_health + effect.magnitude
                )
                healed = player.current_health - old_health
                if healed > 0:
                    events.append(self._msg_to_player(player_id, f"You heal for {healed} health."))
            
            # Apply ongoing effect if duration > 0 or stat modifiers
            if effect.stat_modifiers or effect.duration > 0:
                player.apply_effect(effect)
                # Schedule effect removal
                if effect.duration > 0:
                    self.schedule_event(
                        delay_seconds=effect.duration,
                        callback=lambda: self._remove_effect_callback(player_id, effect_id),
                        event_id=f"remove_{effect_id}"
                    )
        
        # Reduce quantity or remove item
        if item.quantity > 1:
            item.quantity -= 1
        else:
            remove_item_from_inventory(world, player_id, found_item_id)
            del world.items[found_item_id]
        
        events.insert(0, self._msg_to_player(player_id, f"You consume {template.name}."))
        events.extend(self._emit_stat_update(player_id))
        
        return events

    async def _remove_effect_callback(self, player_id: PlayerId, effect_id: str) -> None:
        """Callback to remove an effect and emit stat update."""
        if player_id in self.world.players:
            player = self.world.players[player_id]
            removed_effect = player.remove_effect(effect_id)
            
            if removed_effect:
                await self.emit_events(self._emit_stat_update(player_id))
                await self.emit_events([
                    self._msg_to_player(player_id, f"{removed_effect.name} wears off.")
                ])

    def _give(self, player_id: PlayerId, item_name: str, target_name: str) -> List[Event]:
        """Give an item from your inventory to another player."""
        from .inventory import find_item_by_name, add_item_to_inventory, InventoryFullError, calculate_inventory_weight
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        room = world.rooms[player.room_id]
        
        # Find the item in giver's inventory
        found_item_id = find_item_by_name(world, player_id, item_name, "inventory")
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't have '{item_name}'.")]
        
        item = world.items[found_item_id]
        template = world.item_templates[item.template_id]
        
        # Can't give equipped items
        if item.is_equipped():
            return [self._msg_to_player(player_id, f"Unequip {template.name} first.")]
        
        # Find target player in the same room
        target_id = None
        target_name_lower = target_name.lower()
        
        for other_id in room.players:
            if other_id == player_id:
                continue
            other_player = world.players[other_id]
            if other_player.name.lower() == target_name_lower or other_player.name.lower().startswith(target_name_lower):
                target_id = other_id
                break
        
        if not target_id:
            return [self._msg_to_player(player_id, f"You don't see '{target_name}' here.")]
        
        target = world.players[target_id]
        
        # Check if target is connected
        if not target.is_connected:
            return [self._msg_to_player(player_id, f"{target.name} is in stasis and cannot receive items.")]
        
        # Remove from giver's inventory
        player.inventory_items.remove(found_item_id)
        item.player_id = None
        
        # Update giver's inventory metadata
        if player.inventory_meta:
            player.inventory_meta.current_weight = calculate_inventory_weight(world, player_id)
            player.inventory_meta.current_slots = len(player.inventory_items)
        
        # Try to add to target's inventory
        try:
            add_item_to_inventory(world, target_id, found_item_id)
            
            return [
                self._msg_to_player(player_id, f"You give {template.name} to {target.name}."),
                self._msg_to_player(target_id, f"{player.name} gives you {template.name}."),
                self._msg_to_room(room.id, f"{player.name} gives {template.name} to {target.name}.", exclude={player_id, target_id})
            ]
            
        except InventoryFullError as e:
            # Revert: give item back to giver
            item.player_id = player_id
            player.inventory_items.add(found_item_id)
            if player.inventory_meta:
                player.inventory_meta.current_weight = calculate_inventory_weight(world, player_id)
                player.inventory_meta.current_slots = len(player.inventory_items)
            
            return [self._msg_to_player(player_id, f"{target.name}'s inventory is full.")]
