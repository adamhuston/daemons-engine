# backend/app/engine/engine.py
import asyncio
import heapq
import time
import uuid
from typing import Dict, List, Any, Callable, Awaitable

from .world import (
    World, WorldRoom, Direction, PlayerId, RoomId, AreaId, get_room_emoji, 
    TimeEvent, Effect, EntityType, EntityId, WorldEntity, WorldPlayer, WorldNpc,
    Targetable, TargetableType, WorldItem, ItemId,
    CombatPhase, CombatState, CombatResult, WeaponStats,
    get_xp_for_next_level, LEVEL_UP_STAT_GAINS
)
from .behaviors import (
    BehaviorContext, BehaviorResult, get_behavior_instances
)
from .systems import GameContext, TimeEventManager


Event = dict[str, Any]


class WorldEngine:
    """
    Core game engine.

    - Holds a reference to the in-memory World.
    - Consumes commands from players via an asyncio.Queue.
    - Produces events destined for players via per-player queues.
    - Supports per-player messages and room broadcasts.
    - Persists player stats to database on disconnect (and optionally periodically).
    
    Uses modular systems for specific domains:
    - GameContext: Shared state and cross-system communication
    - TimeEventManager: Scheduled events and timers
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

        # Command history (for ! repeat command)
        self._last_commands: Dict[PlayerId, str] = {}
        
        # Initialize game context and systems
        self.ctx = GameContext(world)
        self.time_manager = TimeEventManager(self.ctx)
        self.ctx.time_manager = self.time_manager
        
        # Backward compatibility: reference listeners from context
        self._listeners = self.ctx._listeners

    # ---------- Time event system (delegates to TimeEventManager) ----------

    async def start_time_system(self) -> None:
        """
        Start the time event processing loop.
        Should be called once during engine startup.
        """
        await self.time_manager.start()
        
        # Schedule world time advancement (every 30 seconds = 1 game hour)
        self._schedule_time_advancement()
        
        # Schedule NPC housekeeping tick (respawns, etc.) - every 30 seconds
        self._schedule_npc_housekeeping_tick()
        
        # Initialize per-NPC behavior timers
        self._init_npc_behaviors()
    
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
    
    def _schedule_npc_housekeeping_tick(self) -> None:
        """
        Schedule recurring NPC housekeeping tick (every 30 seconds).
        Handles: respawn checks, cleanup, area-wide NPC events.
        Individual NPC behaviors (idle, wander) use per-NPC timers.
        """
        async def npc_housekeeping_tick():
            """Process housekeeping for all NPCs."""
            current_time = time.time()
            
            # Check for NPC respawns
            for npc_id, npc in list(self.world.npcs.items()):
                if npc.is_alive():
                    continue
                
                # Check if respawn time has elapsed
                if npc.last_killed_at and current_time - npc.last_killed_at >= npc.respawn_time:
                    # Respawn the NPC
                    template = self.world.npc_templates.get(npc.template_id)
                    if template:
                        npc.current_health = template.max_health
                        npc.last_killed_at = None
                        npc.room_id = npc.spawn_room_id
                        npc.target_id = None
                        
                        # Add back to room
                        spawn_room = self.world.rooms.get(npc.spawn_room_id)
                        if spawn_room:
                            spawn_room.entities.add(npc_id)
                            
                            # Announce respawn
                            npc_name = npc.instance_data.get("name_override", npc.name)
                            await self._dispatch_events([
                                self._msg_to_room(
                                    spawn_room.id,
                                    f"{npc_name} appears.",
                                )
                            ])
                            
                            # Start behavior timers for respawned NPC
                            self._schedule_npc_idle(npc_id)
                            self._schedule_npc_wander(npc_id)
            
            # Reschedule housekeeping
            self._schedule_npc_housekeeping_tick()
        
        # Housekeeping every 30 seconds
        self.schedule_event(
            delay_seconds=30.0,
            callback=npc_housekeeping_tick,
            event_id="npc_housekeeping_tick"
        )
    
    def _init_npc_behaviors(self) -> None:
        """
        Initialize per-NPC behavior timers for all living NPCs.
        Called once on engine startup after world is loaded.
        """
        for npc_id, npc in self.world.npcs.items():
            if npc.is_alive():
                self._schedule_npc_idle(npc_id)
                self._schedule_npc_wander(npc_id)
    
    def _schedule_npc_idle(self, npc_id: str) -> None:
        """
        Schedule the next idle behavior check for a specific NPC.
        Uses behavior scripts to determine idle messages.
        """
        import random
        
        npc = self.world.npcs.get(npc_id)
        if not npc or not npc.is_alive():
            return
        
        template = self.world.npc_templates.get(npc.template_id)
        if not template:
            return
        
        # Get idle timing from resolved behavior config
        config = template.resolved_behavior
        if not config.get("idle_enabled", True):
            return
        
        async def npc_idle_callback():
            """Run idle behavior hooks, then reschedule."""
            npc = self.world.npcs.get(npc_id)
            if not npc or not npc.is_alive():
                return
            
            # Run the on_idle_tick hook for all behaviors
            await self._run_behavior_hook(npc_id, "on_idle_tick")
            
            # Reschedule next idle check
            self._schedule_npc_idle(npc_id)
        
        # Cancel any existing idle timer for this NPC
        if npc.idle_event_id:
            self.cancel_event(npc.idle_event_id)
        
        # Get timing from config (with defaults)
        min_delay = config.get("idle_interval_min", 15.0)
        max_delay = config.get("idle_interval_max", 45.0)
        delay = random.uniform(min_delay, max_delay)
        
        event_id = f"npc_idle_{npc_id}_{time.time()}"
        npc.idle_event_id = event_id
        
        self.schedule_event(
            delay_seconds=delay,
            callback=npc_idle_callback,
            event_id=event_id
        )
    
    def _schedule_npc_wander(self, npc_id: str) -> None:
        """
        Schedule the next wander behavior check for a specific NPC.
        Uses behavior scripts to determine movement.
        """
        import random
        
        npc = self.world.npcs.get(npc_id)
        if not npc or not npc.is_alive():
            return
        
        template = self.world.npc_templates.get(npc.template_id)
        if not template:
            return
        
        # Get wander timing from resolved behavior config
        config = template.resolved_behavior
        wander_enabled = config.get("wander_enabled", False)
        
        if not wander_enabled:
            print(f"[NPC] {npc.name} wander NOT enabled (config={config})")
            return
        
        print(f"[NPC] Scheduling wander for {npc.name} (behaviors={template.behaviors})")
        
        async def npc_wander_callback():
            """Run wander behavior hooks, then reschedule."""
            npc = self.world.npcs.get(npc_id)
            if not npc or not npc.is_alive():
                return
            
            # Run the on_wander_tick hook for all behaviors
            result = await self._run_behavior_hook(npc_id, "on_wander_tick")
            if result and result.handled:
                print(f"[NPC] {npc.name} wander tick handled: move_to={result.move_to}")
            
            # Reschedule next wander check
            self._schedule_npc_wander(npc_id)
        
        # Cancel any existing wander timer for this NPC
        if npc.wander_event_id:
            self.cancel_event(npc.wander_event_id)
        
        # Get timing from config (with defaults)
        min_delay = config.get("wander_interval_min", 30.0)
        max_delay = config.get("wander_interval_max", 90.0)
        delay = random.uniform(min_delay, max_delay)
        
        event_id = f"npc_wander_{npc_id}_{time.time()}"
        npc.wander_event_id = event_id
        
        self.schedule_event(
            delay_seconds=delay,
            callback=npc_wander_callback,
            event_id=event_id
        )
    
    def _cancel_npc_timers(self, npc_id: str) -> None:
        """
        Cancel all behavior timers for an NPC (called on death/despawn).
        """
        npc = self.world.npcs.get(npc_id)
        if not npc:
            return
        
        if npc.idle_event_id:
            self.cancel_event(npc.idle_event_id)
            npc.idle_event_id = None
        
        if npc.wander_event_id:
            self.cancel_event(npc.wander_event_id)
            npc.wander_event_id = None
    
    def _get_npc_behavior_context(self, npc_id: str) -> BehaviorContext | None:
        """
        Create a BehaviorContext for the given NPC.
        Returns None if NPC doesn't exist or is dead.
        """
        npc = self.world.npcs.get(npc_id)
        if not npc or not npc.is_alive():
            return None
        
        template = self.world.npc_templates.get(npc.template_id)
        if not template:
            return None
        
        return BehaviorContext(
            npc=npc,
            world=self.world,
            template=template,
            config=template.resolved_behavior,
            broadcast=lambda room_id, msg: None  # We handle messages via BehaviorResult
        )
    
    async def _run_behavior_hook(
        self, 
        npc_id: str, 
        hook_name: str, 
        *args, 
        **kwargs
    ) -> BehaviorResult | None:
        """
        Run a specific behavior hook for an NPC.
        
        Executes all behaviors in priority order. Stops if a behavior returns
        handled=True (for most hooks).
        
        Returns the first result with handled=True, or the last result.
        """
        npc = self.world.npcs.get(npc_id)
        if not npc or not npc.is_alive():
            return None
        
        template = self.world.npc_templates.get(npc.template_id)
        if not template:
            return None
        
        ctx = self._get_npc_behavior_context(npc_id)
        if not ctx:
            return None
        
        # Get behavior instances for this NPC
        behaviors = get_behavior_instances(template.behaviors)
        print(f"[Behavior] Running {hook_name} for {npc.name} with {len(behaviors)} behaviors: {[b.name for b in behaviors]}")
        
        last_result: BehaviorResult | None = None
        for behavior in behaviors:
            hook = getattr(behavior, hook_name, None)
            if hook is None:
                continue
            
            try:
                result = await hook(ctx, *args, **kwargs)
                if result and result.handled:
                    # Process the result
                    await self._process_behavior_result(npc_id, result)
                    return result
                last_result = result
            except Exception as e:
                print(f"[Behavior] Error in {behavior.name}.{hook_name}: {e}")
        
        return last_result
    
    async def _process_behavior_result(self, npc_id: str, result: BehaviorResult) -> None:
        """
        Process a BehaviorResult - handle movement, messages, attacks, etc.
        """
        npc = self.world.npcs.get(npc_id)
        if not npc:
            return
        
        events: list[Event] = []
        
        # Handle messages
        if result.message:
            events.append(self._msg_to_room(npc.room_id, result.message))
        
        # Handle movement
        if result.move_to:
            old_room = self.world.rooms.get(npc.room_id)
            new_room = self.world.rooms.get(result.move_to)
            
            if old_room and new_room:
                # Update room tracking
                old_room.entities.discard(npc_id)
                npc.room_id = result.move_to
                new_room.entities.add(npc_id)
                
                # Announce arrival if we have a direction
                if result.move_direction:
                    opposite = {
                        "north": "south", "south": "north",
                        "east": "west", "west": "east",
                        "up": "down", "down": "up"
                    }
                    from_dir = opposite.get(result.move_direction, "somewhere")
                    events.append(self._msg_to_room(
                        result.move_to, 
                        f"{npc.name} arrives from the {from_dir}."
                    ))
        
        # Dispatch all events
        if events:
            await self._dispatch_events(events)
    
    async def stop_time_system(self) -> None:
        """Stop the time event processing loop. Delegates to TimeEventManager."""
        await self.time_manager.stop()
    
    def schedule_event(
        self,
        delay_seconds: float,
        callback: Callable[[], Awaitable[None]],
        event_id: str | None = None,
        recurring: bool = False,
    ) -> str:
        """Schedule a time event. Delegates to TimeEventManager."""
        return self.time_manager.schedule(delay_seconds, callback, event_id, recurring)
    
    def cancel_event(self, event_id: str) -> bool:
        """Cancel a scheduled time event. Delegates to TimeEventManager."""
        return self.time_manager.cancel(event_id)

    # ---------- Unified Entity System Helpers ----------

    def _get_players_in_room(self, room_id: RoomId) -> List[WorldPlayer]:
        """Get all players in a room (from unified entities set)."""
        room = self.world.rooms.get(room_id)
        if not room:
            return []
        
        players = []
        for entity_id in room.entities:
            if entity_id in self.world.players:
                players.append(self.world.players[entity_id])
        return players
    
    def _get_npcs_in_room(self, room_id: RoomId) -> List[WorldNpc]:
        """Get all NPCs in a room (from unified entities set)."""
        room = self.world.rooms.get(room_id)
        if not room:
            return []
        
        npcs = []
        for entity_id in room.entities:
            if entity_id in self.world.npcs:
                npcs.append(self.world.npcs[entity_id])
        return npcs
    
    def _get_player_ids_in_room(self, room_id: RoomId) -> set[PlayerId]:
        """Get IDs of all players in a room."""
        room = self.world.rooms.get(room_id)
        if not room:
            return set()
        return {eid for eid in room.entities if eid in self.world.players}
    
    def _find_entity_in_room(
        self, 
        room_id: RoomId, 
        search_term: str,
        include_players: bool = True,
        include_npcs: bool = True,
    ) -> tuple[EntityId | None, EntityType | None]:
        """
        Find an entity in a room by name or keyword.
        
        Returns:
            Tuple of (entity_id, entity_type) or (None, None) if not found.
        """
        room = self.world.rooms.get(room_id)
        if not room:
            return None, None
        
        search_lower = search_term.lower()
        
        for entity_id in room.entities:
            # Check players
            if include_players and entity_id in self.world.players:
                player = self.world.players[entity_id]
                if player.name.lower() == search_lower or search_lower in player.name.lower():
                    return entity_id, EntityType.PLAYER
            
            # Check NPCs
            if include_npcs and entity_id in self.world.npcs:
                npc = self.world.npcs[entity_id]
                template = self.world.npc_templates.get(npc.template_id)
                if not template or not npc.is_alive():
                    continue
                
                # Check instance name override
                npc_name = npc.instance_data.get("name_override", npc.name)
                
                # Exact or partial match on name
                if npc_name.lower() == search_lower or search_lower in npc_name.lower():
                    return entity_id, EntityType.NPC
                
                # Keyword match
                for keyword in template.keywords:
                    if search_lower == keyword.lower() or search_lower in keyword.lower():
                        return entity_id, EntityType.NPC
        
        return None, None
    
    def _find_targetable_in_room(
        self, 
        room_id: RoomId, 
        search_term: str,
        include_players: bool = True,
        include_npcs: bool = True,
        include_items: bool = True,
    ) -> tuple[Targetable | None, TargetableType | None]:
        """
        Find any targetable object in a room by name or keyword.
        
        Searches through entities (players, NPCs) and items in priority order.
        This provides a unified targeting interface for commands.
        
        Args:
            room_id: The room to search in
            search_term: Name or keyword to search for
            include_players: Whether to search players
            include_npcs: Whether to search NPCs
            include_items: Whether to search items
        
        Returns:
            Tuple of (targetable_object, targetable_type) or (None, None) if not found.
        """
        room = self.world.rooms.get(room_id)
        if not room:
            return None, None
        
        search_lower = search_term.lower()
        
        # Search entities first (players and NPCs)
        for entity_id in room.entities:
            # Check players
            if include_players and entity_id in self.world.players:
                player = self.world.players[entity_id]
                if player.matches_keyword(search_term):
                    return player, TargetableType.PLAYER
            
            # Check NPCs
            if include_npcs and entity_id in self.world.npcs:
                npc = self.world.npcs[entity_id]
                if not npc.is_alive():
                    continue
                if npc.matches_keyword(search_term):
                    return npc, TargetableType.NPC
        
        # Search items in the room
        if include_items:
            for item_id in room.items:
                item = self.world.items.get(item_id)
                if item and item.matches_keyword(search_term):
                    return item, TargetableType.ITEM
        
        return None, None
    
    def _find_item_in_room(
        self, 
        room_id: RoomId, 
        search_term: str,
    ) -> WorldItem | None:
        """
        Find an item in a room by name or keyword.
        
        Args:
            room_id: The room to search in
            search_term: Name or keyword to search for
        
        Returns:
            The matching WorldItem or None if not found.
        """
        room = self.world.rooms.get(room_id)
        if not room:
            return None
        
        for item_id in room.items:
            item = self.world.items.get(item_id)
            if item and item.matches_keyword(search_term):
                return item
        
        return None
    
    def _find_item_in_inventory(
        self, 
        player_id: PlayerId, 
        search_term: str,
    ) -> WorldItem | None:
        """
        Find an item in a player's inventory by name or keyword.
        
        Args:
            player_id: The player whose inventory to search
            search_term: Name or keyword to search for
        
        Returns:
            The matching WorldItem or None if not found.
        """
        player = self.world.players.get(player_id)
        if not player:
            return None
        
        for item_id in player.inventory_items:
            item = self.world.items.get(item_id)
            if item and item.matches_keyword(search_term):
                return item
        
        return None

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
                room_player_ids = self._get_player_ids_in_room(room.id) if room else set()
                if room and len(room_player_ids) > 1:
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
            room_player_ids = self._get_player_ids_in_room(room.id) if room else set()
            
            if room and len(room_player_ids) > 1:
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
            # Check if looking at specific thing
            parts = raw.split(maxsplit=1)
            if len(parts) > 1:
                target_name = parts[1]
                return self._look_at_target(player_id, target_name)
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

        # ===== Combat Commands =====
        if cmd.startswith(("attack ", "kill ", "fight ", "hit ")) or cmd in {"attack", "kill", "fight", "hit"}:
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                return [self._msg_to_player(player_id, "Attack whom?")]
            target_name = parts[1].strip()
            return self._attack(player_id, target_name)
        
        if cmd in {"stop", "disengage", "flee"}:
            return self._stop_combat(player_id, flee=(cmd == "flee"))
        
        if cmd == "combat" or cmd == "cs":
            return self._show_combat_status(player_id)

        # Default
        return [
            self._msg_to_player(
                player_id,
                "You mutter something unintelligible. (Unknown command)",
            )
        ]

    # ---------- Helper: event constructors ----------

    def _get_equipped_weapon_name(self, entity_id: EntityId) -> str:
        """Get the name of the equipped weapon for an entity, or 'fists' if unarmed."""
        entity = self.world.players.get(entity_id) or self.world.npcs.get(entity_id)
        if not entity:
            return "fists"
        
        if "weapon" in entity.equipped_items:
            weapon_template_id = entity.equipped_items["weapon"]
            weapon_template = self.world.item_templates.get(weapon_template_id)
            if weapon_template:
                return weapon_template.name
        
        return "fists"

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

    def _format_room_entities(
        self,
        room: WorldRoom,
        exclude_player_id: PlayerId,
    ) -> list[str]:
        """
        Format the list of all entities in a room (players and NPCs).
        Returns a list of formatted strings to append to room description.
        """
        lines: list[str] = []
        world = self.world
        
        # Get all entities from the room
        players_connected = []
        players_stasis = []
        npcs_by_type: dict[str, list[str]] = {
            "hostile": [],
            "neutral": [],
            "friendly": [],
            "merchant": [],
        }
        
        for entity_id in room.entities:
            # Check if it's a player
            if entity_id in world.players:
                player = world.players[entity_id]
                if entity_id == exclude_player_id:
                    continue
                if player.is_connected:
                    players_connected.append(player.name)
                else:
                    players_stasis.append(player.name)
            
            # Check if it's an NPC
            elif entity_id in world.npcs:
                npc = world.npcs[entity_id]
                if not npc.is_alive():
                    continue
                template = world.npc_templates.get(npc.template_id)
                if not template:
                    continue
                npc_name = npc.instance_data.get("name_override", npc.name)
                npc_type = template.npc_type
                if npc_type in npcs_by_type:
                    npcs_by_type[npc_type].append(npc_name)
        
        # Format connected players
        if players_connected:
            lines.append("")
            for name in players_connected:
                lines.append(f"{name} is here.")
        
        # Format players in stasis
        if players_stasis:
            lines.append("")
            for name in players_stasis:
                lines.append(f"(Stasis) The flickering form of {name} is here, suspended in prismatic stasis.")
        
        # Format NPCs (no disposition indicator in room listing)
        any_npcs = any(npcs for npcs in npcs_by_type.values())
        if any_npcs:
            lines.append("")
            for npc_type, npc_names in npcs_by_type.items():
                for name in npc_names:
                    lines.append(f"{name} is here.")
        
        return lines
    
    # Keep old name as alias for compatibility during refactoring
    def _format_room_occupants(
        self,
        room: WorldRoom,
        exclude_player_id: PlayerId,
    ) -> list[str]:
        """Deprecated: Use _format_room_entities instead."""
        return self._format_room_entities(room, exclude_player_id)

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

        # Cancel combat if player is in combat (you can't fight and run)
        if player.combat.is_in_combat():
            if player.combat.swing_event_id:
                self.cancel_event(player.combat.swing_event_id)
            player.combat.clear_combat()
            events.append(
                self._msg_to_player(player_id, "You disengage from combat.")
            )

        # Update occupancy (unified entity tracking)
        current_room.entities.discard(player_id)
        new_room.entities.add(player_id)
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
        old_room_players = self._get_player_ids_in_room(old_room_id)
        if old_room_players:
            events.append(
                self._msg_to_room(
                    old_room_id,
                    f"{player.name} leaves.",
                )
            )

        # Broadcast to players in the new room (they see you enter)
        new_room_players = self._get_player_ids_in_room(new_room_id)
        if len(new_room_players) > 1:  # More than just the moving player
            events.append(
                self._msg_to_room(
                    new_room_id,
                    f"{player.name} enters.",
                    exclude={player_id},
                )
            )

        # Trigger on_player_enter for NPCs in the new room (aggressive NPCs attack)
        asyncio.create_task(self._trigger_npc_player_enter(new_room_id, player_id))

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

        # List all entities (players and NPCs) in the same room
        lines.extend(self._format_room_entities(room, player_id))

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

    def _find_npc_in_room(self, room_id: RoomId, search_term: str) -> str | None:
        """
        Find an NPC in a room by name or keyword.
        Returns the NPC ID if found, None otherwise.
        
        Note: This is a convenience wrapper around _find_entity_in_room.
        """
        entity_id, entity_type = self._find_entity_in_room(
            room_id, search_term, 
            include_players=False, 
            include_npcs=True
        )
        return entity_id if entity_type == EntityType.NPC else None

    def _look_at_target(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """
        Examine any targetable object (player, NPC, or item) using unified targeting.
        
        Uses the Targetable protocol to find and describe targets uniformly.
        """
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        room = world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "You are nowhere. (Room not found)")]
        
        # Use unified targeting to find the target
        target, target_type = self._find_targetable_in_room(
            room.id, target_name,
            include_players=True,
            include_npcs=True,
            include_items=True
        )
        
        # Also check player's inventory for items
        if not target:
            inv_item = self._find_item_in_inventory(player_id, target_name)
            if inv_item:
                target = inv_item
                target_type = TargetableType.ITEM
        
        if not target:
            return [self._msg_to_player(player_id, f"You don't see '{target_name}' here.")]
        
        # Dispatch to appropriate detailed look method based on type
        if target_type == TargetableType.PLAYER:
            return self._look_at_player(player_id, target)
        elif target_type == TargetableType.NPC:
            return self._look_at_npc_detail(player_id, target)
        elif target_type == TargetableType.ITEM:
            return self._look_at_item_detail(player_id, target)
        
        return [self._msg_to_player(player_id, f"You don't see '{target_name}' here.")]
    
    def _look_at_player(self, player_id: PlayerId, target: WorldPlayer) -> List[Event]:
        """Examine another player in detail."""
        lines = [f"**{target.name}**"]
        lines.append(f"A level {target.level} {target.character_class}.")
        
        # Show health status (descriptive, not exact numbers)
        health_percent = (target.current_health / target.max_health) * 100
        if health_percent >= 100:
            health_status = "appears uninjured"
        elif health_percent >= 75:
            health_status = "has minor injuries"
        elif health_percent >= 50:
            health_status = "is moderately wounded"
        elif health_percent >= 25:
            health_status = "is heavily wounded"
        else:
            health_status = "is near death"
        
        lines.append(f"Condition: {target.name} {health_status}.")
        
        # Show connection status
        if not target.is_connected:
            lines.append("")
            lines.append("*They appear to be in a trance-like stasis.*")
        
        return [self._msg_to_player(player_id, "\n".join(lines))]
    
    def _look_at_npc_detail(self, player_id: PlayerId, npc: WorldNpc) -> List[Event]:
        """Examine an NPC in detail (internal implementation)."""
        world = self.world
        template = world.npc_templates.get(npc.template_id)
        
        if not template:
            return [self._msg_to_player(player_id, f"You see {npc.name}, but something seems off...")]
        
        # Use instance name override if available
        display_name = npc.instance_data.get("name_override", template.name)
        
        # Build detailed description
        lines = [f"**{display_name}**"]
        lines.append(template.description)
        
        # Show type indicator
        lines.append("")
        type_indicators = {
            "hostile": "🔴 Hostile",
            "neutral": "🟡 Neutral",
            "friendly": "🟢 Friendly",
            "merchant": "🛒 Merchant",
        }
        type_str = type_indicators.get(template.npc_type, template.npc_type.title())
        lines.append(f"Disposition: {type_str}")
        
        # Show level
        lines.append(f"Level: {template.level}")
        
        # Show health status (descriptive, not exact numbers)
        health_percent = (npc.current_health / template.max_health) * 100
        if health_percent >= 100:
            health_status = "appears uninjured"
        elif health_percent >= 75:
            health_status = "has minor injuries"
        elif health_percent >= 50:
            health_status = "is moderately wounded"
        elif health_percent >= 25:
            health_status = "is heavily wounded"
        else:
            health_status = "is near death"
        
        lines.append(f"Condition: {display_name} {health_status}.")
        
        # Show instance-specific data like guard messages
        if "guard_message" in npc.instance_data:
            lines.append("")
            lines.append(npc.instance_data["guard_message"])
        
        return [self._msg_to_player(player_id, "\n".join(lines))]
    
    def _look_at_item_detail(self, player_id: PlayerId, item: WorldItem) -> List[Event]:
        """Examine an item in detail (internal implementation)."""
        world = self.world
        template = world.item_templates.get(item.template_id)
        
        if not template:
            return [self._msg_to_player(player_id, f"You see {item.name}, but something seems off...")]
        
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
                if other_item.container_id == item.id:
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
                            if other_item.container_id == item.id:
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

    def _look_at_npc(self, player_id: PlayerId, npc_name: str) -> List[Event] | None:
        """
        Examine an NPC in detail.
        Returns None if no NPC found (so caller can try looking at items).
        """
        world = self.world
        
        if player_id not in world.players:
            return None
        
        player = world.players[player_id]
        room = world.rooms.get(player.room_id)
        if not room:
            return None
        
        # Find NPC in current room
        npc_id = self._find_npc_in_room(room.id, npc_name)
        if not npc_id:
            return None  # No NPC found, let caller try items
        
        npc = world.npcs[npc_id]
        template = world.npc_templates[npc.template_id]
        
        # Use instance name override if available
        display_name = npc.instance_data.get("name_override", template.name)
        
        # Build detailed description
        lines = [f"**{display_name}**"]
        lines.append(template.description)
        
        # Show type indicator
        lines.append("")
        type_indicators = {
            "hostile": "🔴 Hostile",
            "neutral": "🟡 Neutral",
            "friendly": "🟢 Friendly",
            "merchant": "🛒 Merchant",
        }
        type_str = type_indicators.get(template.npc_type, template.npc_type.title())
        lines.append(f"Disposition: {type_str}")
        
        # Show level
        lines.append(f"Level: {template.level}")
        
        # Show health status (descriptive, not exact numbers)
        health_percent = (npc.current_health / template.max_health) * 100
        if health_percent >= 100:
            health_status = "appears uninjured"
        elif health_percent >= 75:
            health_status = "has minor injuries"
        elif health_percent >= 50:
            health_status = "is moderately wounded"
        elif health_percent >= 25:
            health_status = "is heavily wounded"
        else:
            health_status = "is near death"
        
        lines.append(f"Condition: {display_name} {health_status}.")
        
        # Show instance-specific data like guard messages
        if "guard_message" in npc.instance_data:
            lines.append("")
            lines.append(npc.instance_data["guard_message"])
        
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
        room_player_ids = self._get_player_ids_in_room(room.id)
        if room_player_ids:
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
        room_player_ids = self._get_player_ids_in_room(room.id)
        if len(room_player_ids) > 1:
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
        Heal an entity by name (admin/debug command).
        Uses Targetable protocol for unified player/NPC targeting.
        """
        world = self.world
        events: List[Event] = []
        
        player = world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        room = world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "You are nowhere. (Room not found)")]

        # Use unified targeting to find target entity
        target, target_type = self._find_targetable_in_room(
            room.id, target_name,
            include_players=True,
            include_npcs=True,
            include_items=False
        )
        
        if not target or target_type == TargetableType.ITEM:
            return [self._msg_to_player(player_id, f"'{target_name}' not found.")]
        
        # Get entity reference
        entity: WorldEntity
        if target_type == TargetableType.PLAYER:
            entity = world.players[target.id]
        else:
            entity = world.npcs[target.id]
        
        # Heal for 20 HP (or up to max)
        heal_amount = 20
        old_health = entity.current_health
        entity.current_health = min(entity.current_health + heal_amount, entity.max_health)
        actual_heal = entity.current_health - old_health
        
        # Send stat_update to target (only for players)
        if target_type == TargetableType.PLAYER:
            events.append(self._stat_update_to_player(
                target.id,
                {
                    "current_health": entity.current_health,
                    "max_health": entity.max_health,
                }
            ))
            
            # Send message to target player
            events.append(self._msg_to_player(
                target.id,
                f"*A warm glow surrounds you.* You are healed for {actual_heal} HP."
            ))
        
        # Send confirmation to healer
        if target_type == TargetableType.PLAYER and player_id != target.id:
            events.append(self._msg_to_player(
                player_id,
                f"You heal {entity.name} for {actual_heal} HP."
            ))
        elif target_type == TargetableType.NPC:
            events.append(self._msg_to_player(
                player_id,
                f"You heal {entity.name} for {actual_heal} HP."
            ))
        
        # Broadcast to others in the room
        room_player_ids = self._get_player_ids_in_room(room.id)
        if len(room_player_ids) > 1:
            healer_name = player.name
            exclude_set = {player_id}
            if target_type == TargetableType.PLAYER:
                exclude_set.add(target.id)
            
            if target_type == TargetableType.PLAYER and player_id == target.id:
                room_msg = f"*A warm glow surrounds {entity.name}.*"
            else:
                room_msg = f"*{healer_name} channels healing energy into {entity.name}.*"
            events.append(self._msg_to_room(room.id, room_msg, exclude=exclude_set))
        
        return events

    def _hurt(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """
        Hurt an entity by name (admin/debug command).
        Uses Targetable protocol for unified player/NPC targeting.
        """
        world = self.world
        events: List[Event] = []
        
        player = world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        room = world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "You are nowhere. (Room not found)")]

        # Use unified targeting to find target entity
        target, target_type = self._find_targetable_in_room(
            room.id, target_name,
            include_players=True,
            include_npcs=True,
            include_items=False
        )
        
        if not target or target_type == TargetableType.ITEM:
            return [self._msg_to_player(player_id, f"'{target_name}' not found.")]
        
        # Get entity reference
        entity: WorldEntity
        if target_type == TargetableType.PLAYER:
            entity = world.players[target.id]
        else:
            entity = world.npcs[target.id]
        
        # Damage for 15 HP (but not below 1)
        damage_amount = 15
        old_health = entity.current_health
        entity.current_health = max(entity.current_health - damage_amount, 1)
        actual_damage = old_health - entity.current_health
        
        # Send stat_update to target (only for players)
        if target_type == TargetableType.PLAYER:
            events.append(self._stat_update_to_player(
                target.id,
                {
                    "current_health": entity.current_health,
                    "max_health": entity.max_health,
                }
            ))
            
            # Send message to target player
            events.append(self._msg_to_player(
                target.id,
                f"*A dark force strikes you!* You take {actual_damage} damage."
            ))
        
        # Send confirmation to attacker
        if target_type == TargetableType.PLAYER and player_id != target.id:
            events.append(self._msg_to_player(
                player_id,
                f"You hurt {entity.name} for {actual_damage} damage."
            ))
        elif target_type == TargetableType.NPC:
            events.append(self._msg_to_player(
                player_id,
                f"You hurt {entity.name} for {actual_damage} damage."
            ))
        
        # Broadcast to others in the room
        room_player_ids = self._get_player_ids_in_room(room.id)
        if len(room_player_ids) > 1:
            attacker_name = player.name
            exclude_set = {player_id}
            if target_type == TargetableType.PLAYER:
                exclude_set.add(target.id)
            
            if target_type == TargetableType.PLAYER and player_id == target.id:
                room_msg = f"*Dark energy lashes at {entity.name}!*"
            else:
                room_msg = f"*{attacker_name} strikes {entity.name} with dark energy!*"
            events.append(self._msg_to_room(room.id, room_msg, exclude=exclude_set))
        
        return events

    # =========================================================================
    # Real-Time Combat System
    # =========================================================================
    
    def _attack(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """
        Initiate an attack against a target.
        Starts the swing timer based on weapon speed.
        """
        import random
        
        world = self.world
        events: List[Event] = []
        
        player = world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        if not player.is_alive():
            return [self._msg_to_player(player_id, "You can't attack while dead.")]
        
        room = world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "You are nowhere.")]
        
        # Check if already in combat with this target
        if player.combat.is_in_combat():
            current_target = player.combat.target_id
            if current_target:
                current_target_entity = world.players.get(current_target) or world.npcs.get(current_target)
                if current_target_entity:
                    return [self._msg_to_player(
                        player_id, 
                        f"You're already attacking {current_target_entity.name}! Use 'stop' to disengage first."
                    )]
        
        # Find target
        target, target_type = self._find_targetable_in_room(
            room.id, target_name,
            include_players=True,
            include_npcs=True,
            include_items=False
        )
        
        if not target or target_type == TargetableType.ITEM:
            return [self._msg_to_player(player_id, f"'{target_name}' not found.")]
        
        # Can't attack yourself
        if target.id == player_id:
            return [self._msg_to_player(player_id, "You can't attack yourself!")]
        
        # Get target entity
        target_entity: WorldEntity
        if target_type == TargetableType.PLAYER:
            target_entity = world.players[target.id]
        else:
            target_entity = world.npcs[target.id]
        
        # Check if target is alive
        if not target_entity.is_alive():
            return [self._msg_to_player(player_id, f"{target_entity.name} is already dead.")]
        
        # Start the attack (pass item_templates for equipped weapon lookup)
        player.start_attack(target.id, world.item_templates)
        
        # Schedule the swing completion
        weapon = player.combat.current_weapon
        self._schedule_swing_completion(player_id, target.id, weapon)
        
        # Generate attack message - get weapon name from equipped weapon
        swing_time = weapon.swing_speed
        weapon_name = self._get_equipped_weapon_name(player_id)
        
        events.append(self._msg_to_player(
            player_id,
            f"You begin attacking {target_entity.name} with your {weapon_name}... ({swing_time:.1f}s)"
        ))
        
        # Notify target
        if target_type == TargetableType.PLAYER:
            events.append(self._msg_to_player(
                target.id,
                f"⚔️ {player.name} attacks you!"
            ))
        
        # Broadcast to room
        events.append(self._msg_to_room(
            room.id,
            f"⚔️ {player.name} attacks {target_entity.name}!",
            exclude={player_id, target.id}
        ))
        
        # Trigger on_combat_start for NPC targets
        if target_type == TargetableType.NPC:
            # Add threat from player
            target_entity.combat.add_threat(player_id, 100.0)
            # Schedule NPC reaction
            asyncio.create_task(self._trigger_npc_combat_start(target.id, player_id))
        
        return events
    
    def _schedule_swing_completion(
        self, 
        attacker_id: EntityId, 
        target_id: EntityId,
        weapon: WeaponStats
    ) -> None:
        """Schedule the completion of a swing (when damage is applied)."""
        import random
        
        async def swing_complete_callback():
            """Called when swing timer completes - apply damage and continue."""
            attacker = self.world.players.get(attacker_id) or self.world.npcs.get(attacker_id)
            target = self.world.players.get(target_id) or self.world.npcs.get(target_id)
            
            if not attacker or not target:
                return
            
            if not attacker.is_alive():
                attacker.combat.clear_combat()
                return
            
            # Check if attacker moved or target moved/died
            if attacker.room_id != target.room_id:
                attacker.combat.clear_combat()
                if attacker_id in self.world.players:
                    await self._dispatch_events([
                        self._msg_to_player(attacker_id, "Your target is no longer here.")
                    ])
                return
            
            if not target.is_alive():
                attacker.combat.clear_combat()
                if attacker_id in self.world.players:
                    await self._dispatch_events([
                        self._msg_to_player(attacker_id, f"{target.name} is already dead!")
                    ])
                return
            
            # Transition from WINDUP to SWING
            if attacker.combat.phase == CombatPhase.WINDUP:
                attacker.combat.start_phase(CombatPhase.SWING, weapon.swing_time)
                # Schedule damage application
                self._schedule_damage_application(attacker_id, target_id, weapon)
        
        # Schedule windup completion
        event_id = f"combat_windup_{attacker_id}_{time.time()}"
        attacker = self.world.players.get(attacker_id) or self.world.npcs.get(attacker_id)
        if attacker:
            attacker.combat.swing_event_id = event_id
        
        self.schedule_event(
            delay_seconds=weapon.windup_time,
            callback=swing_complete_callback,
            event_id=event_id
        )
    
    def _schedule_damage_application(
        self,
        attacker_id: EntityId,
        target_id: EntityId,
        weapon: WeaponStats
    ) -> None:
        """Schedule the actual damage application after swing commits."""
        import random
        
        async def damage_callback():
            """Apply damage and handle combat continuation."""
            attacker = self.world.players.get(attacker_id) or self.world.npcs.get(attacker_id)
            target = self.world.players.get(target_id) or self.world.npcs.get(target_id)
            
            if not attacker or not target or not attacker.is_alive():
                if attacker:
                    attacker.combat.clear_combat()
                return
            
            # Check target still valid
            if attacker.room_id != target.room_id or not target.is_alive():
                attacker.combat.clear_combat()
                return
            
            # Calculate damage
            damage = random.randint(weapon.damage_min, weapon.damage_max)
            
            # Apply strength modifier
            str_bonus = (attacker.get_effective_strength() - 10) // 2
            damage = max(1, damage + str_bonus)
            
            # Apply target's armor
            armor_reduction = target.get_effective_armor_class() // 5
            damage = max(1, damage - armor_reduction)
            
            # Check for critical hit (10% base chance)
            is_crit = random.random() < 0.10
            if is_crit:
                damage = int(damage * 1.5)
            
            # Apply damage
            old_health = target.current_health
            target.current_health = max(0, target.current_health - damage)
            
            # Build result
            result = CombatResult(
                success=True,
                damage_dealt=damage,
                damage_type=weapon.damage_type,
                was_critical=is_crit,
                attacker_id=attacker_id,
                defender_id=target_id
            )
            
            # Generate messages and events
            events: List[Event] = []
            
            crit_text = " **CRITICAL!**" if is_crit else ""
            
            # Message to attacker
            if attacker_id in self.world.players:
                events.append(self._msg_to_player(
                    attacker_id,
                    f"You hit {target.name} for {damage} damage!{crit_text}"
                ))
            
            # Message to target
            if target_id in self.world.players:
                events.append(self._msg_to_player(
                    target_id,
                    f"💥 {attacker.name} hits you for {damage} damage!{crit_text}"
                ))
                events.append(self._stat_update_to_player(
                    target_id,
                    {"current_health": target.current_health, "max_health": target.max_health}
                ))
            
            # Room broadcast
            room = self.world.rooms.get(attacker.room_id)
            if room:
                events.append(self._msg_to_room(
                    room.id,
                    f"{attacker.name} hits {target.name}!{crit_text}",
                    exclude={attacker_id, target_id}
                ))
            
            # Check for death
            if not target.is_alive():
                events.extend(await self._handle_death(target_id, attacker_id))
                attacker.combat.clear_combat()
            else:
                # Trigger on_damaged for NPC targets
                if target_id in self.world.npcs:
                    asyncio.create_task(
                        self._trigger_npc_damaged(target_id, attacker_id, damage)
                    )
                
                # Continue auto-attack if enabled
                if attacker.combat.auto_attack and attacker.is_alive():
                    attacker.combat.start_phase(CombatPhase.RECOVERY, 0.5)
                    self._schedule_next_swing(attacker_id, target_id, weapon)
                else:
                    attacker.combat.clear_combat()
            
            await self._dispatch_events(events)
        
        # Schedule damage
        event_id = f"combat_damage_{attacker_id}_{time.time()}"
        self.schedule_event(
            delay_seconds=weapon.swing_time,
            callback=damage_callback,
            event_id=event_id
        )
    
    def _schedule_next_swing(
        self,
        attacker_id: EntityId,
        target_id: EntityId,
        weapon: WeaponStats
    ) -> None:
        """Schedule the next swing in auto-attack sequence."""
        
        async def next_swing_callback():
            """Start the next attack in the sequence."""
            attacker = self.world.players.get(attacker_id) or self.world.npcs.get(attacker_id)
            target = self.world.players.get(target_id) or self.world.npcs.get(target_id)
            
            if not attacker or not attacker.is_alive():
                return
            
            if not target or not target.is_alive() or attacker.room_id != target.room_id:
                attacker.combat.clear_combat()
                if attacker_id in self.world.players:
                    await self._dispatch_events([
                        self._msg_to_player(attacker_id, "Combat ended.")
                    ])
                return
            
            # Start next swing
            attacker.start_attack(target_id)
            self._schedule_swing_completion(attacker_id, target_id, weapon)
        
        # Short recovery before next swing
        self.schedule_event(
            delay_seconds=0.5,
            callback=next_swing_callback,
            event_id=f"combat_recovery_{attacker_id}_{time.time()}"
        )
    
    def _roll_and_drop_loot(self, drop_table: list, room_id: RoomId, npc_name: str) -> List[Event]:
        """
        Roll loot from a drop table and create items in the room.
        
        Args:
            drop_table: List of {"template_id": str, "chance": float, "quantity": int|[min,max]}
            room_id: Room to drop items into
            npc_name: Name of the NPC for broadcast messages
        
        Returns:
            List of events for loot drop messages
        """
        import random
        
        events: List[Event] = []
        room = self.world.rooms.get(room_id)
        if not room:
            return events
        
        for drop in drop_table:
            template_id = drop.get("template_id")
            chance = drop.get("chance", 1.0)
            quantity_spec = drop.get("quantity", 1)
            
            # Roll for drop chance
            if random.random() > chance:
                continue
            
            # Determine quantity
            if isinstance(quantity_spec, list) and len(quantity_spec) == 2:
                quantity = random.randint(quantity_spec[0], quantity_spec[1])
            else:
                quantity = int(quantity_spec)
            
            if quantity <= 0:
                continue
            
            # Get template
            template = self.world.item_templates.get(template_id)
            if not template:
                continue
            
            # Create item instance
            item_id = f"loot_{uuid.uuid4().hex[:12]}"
            item = WorldItem(
                id=item_id,
                template_id=template_id,
                name=template.name,
                keywords=list(template.keywords),
                room_id=room_id,
                quantity=quantity,
                current_durability=template.max_durability if template.has_durability else None,
                _description=template.description,
            )
            
            # Add to world and room
            self.world.items[item_id] = item
            room.items.add(item_id)
            
            # Broadcast drop message
            quantity_str = f" x{quantity}" if quantity > 1 else ""
            events.append(self._msg_to_room(
                room_id,
                f"💎 {npc_name} drops {template.name}{quantity_str}."
            ))
        
        return events
    
    async def _handle_death(self, victim_id: EntityId, killer_id: EntityId) -> List[Event]:
        """Handle entity death - generate messages and trigger effects."""
        events: List[Event] = []
        
        victim = self.world.players.get(victim_id) or self.world.npcs.get(victim_id)
        killer = self.world.players.get(killer_id) or self.world.npcs.get(killer_id)
        
        if not victim:
            return events
        
        victim_name = victim.name
        killer_name = killer.name if killer else "unknown forces"
        
        # Death message to room
        room = self.world.rooms.get(victim.room_id)
        if room:
            events.append(self._msg_to_room(
                room.id,
                f"💀 {victim_name} has been slain by {killer_name}!"
            ))
        
        # If victim was an NPC, trigger respawn timer
        if victim_id in self.world.npcs:
            npc = self.world.npcs[victim_id]
            
            # Remove from room
            if room:
                room.entities.discard(victim_id)
            
            # Cancel behavior timers
            self._cancel_npc_timers(victim_id)
            
            # Record death time for respawn
            npc.last_killed_at = time.time()
            
            # Get template for loot and XP
            template = self.world.npc_templates.get(npc.template_id)
            
            # Drop loot to room floor
            if template and template.drop_table and room:
                loot_events = self._roll_and_drop_loot(template.drop_table, room.id, victim_name)
                events.extend(loot_events)
            
            # Award XP to killer if it's a player
            if killer_id in self.world.players and template:
                xp_reward = template.experience_reward
                killer_player = self.world.players[killer_id]
                killer_player.experience += xp_reward
                events.append(self._msg_to_player(
                    killer_id,
                    f"✨ You gain {xp_reward} experience!"
                ))
                
                # Check for level-up
                level_ups = killer_player.check_level_up()
                for level_data in level_ups:
                    new_level = level_data["new_level"]
                    gains = level_data["stat_gains"]
                    
                    # Build stat gain message
                    gain_parts = []
                    if gains.get("max_health"):
                        gain_parts.append(f"+{gains['max_health']} HP")
                    if gains.get("max_energy"):
                        gain_parts.append(f"+{gains['max_energy']} Energy")
                    if gains.get("strength"):
                        gain_parts.append(f"+{gains['strength']} STR")
                    if gains.get("dexterity"):
                        gain_parts.append(f"+{gains['dexterity']} DEX")
                    if gains.get("intelligence"):
                        gain_parts.append(f"+{gains['intelligence']} INT")
                    if gains.get("vitality"):
                        gain_parts.append(f"+{gains['vitality']} VIT")
                    
                    gains_str = ", ".join(gain_parts)
                    events.append(self._msg_to_player(
                        killer_id,
                        f"🎉 **LEVEL UP!** You reached level {new_level}! ({gains_str})"
                    ))
        
        # If victim was a player, handle death state
        if victim_id in self.world.players:
            events.append(self._msg_to_player(
                victim_id,
                "☠️ You have been slain! (Use 'respawn' to return)"
            ))
        
        return events
    
    def _stop_combat(self, player_id: PlayerId, flee: bool = False) -> List[Event]:
        """Stop attacking / disengage from combat."""
        import random as flee_random
        
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        if not player.combat.is_in_combat():
            return [self._msg_to_player(player_id, "You're not in combat.")]
        
        target_id = player.combat.target_id
        target = None
        if target_id:
            target = self.world.players.get(target_id) or self.world.npcs.get(target_id)
        
        events: List[Event] = []
        
        if flee:
            # Flee uses a dex check that becomes easier at low health
            # DC = 15 - (10 * missing_health_percent)
            # At full health: DC 15, at 50% health: DC 10, at 0% health: DC 5
            health_percent = player.current_health / player.max_health if player.max_health > 0 else 1.0
            missing_percent = 1.0 - health_percent
            flee_dc = max(5, 15 - int(10 * missing_percent))
            
            roll = flee_random.randint(1, 20)
            dex_mod = (player.get_effective_dexterity() - 10) // 2
            total = roll + dex_mod
            
            if total >= flee_dc:
                # Flee successful - find a random exit and move
                room = self.world.rooms.get(player.room_id)
                if room and room.exits:
                    direction = flee_random.choice(list(room.exits.keys()))
                    exit_target = room.exits[direction]
                    
                    # Cancel scheduled combat events
                    if player.combat.swing_event_id:
                        self.cancel_event(player.combat.swing_event_id)
                    
                    # Clear combat state
                    player.combat.clear_combat()
                    
                    # Remove player from old room
                    room.entities.discard(player_id)
                    
                    # Move player to new room
                    new_room = self.world.rooms.get(exit_target)
                    if new_room:
                        player.room_id = new_room.id
                        new_room.entities.add(player_id)
                        
                        events.append(self._msg_to_room(
                            room.id,
                            f"🏃 {player.name} flees {direction}!"
                        ))
                        events.append(self._msg_to_player(
                            player_id,
                            f"🏃 You flee {direction}! (Roll: {roll} + {dex_mod} DEX = {total} vs DC {flee_dc})"
                        ))
                        
                        # Show new room
                        events.extend(self._look(player_id))
                    else:
                        # Exit leads nowhere - shouldn't happen
                        events.append(self._msg_to_player(player_id, "You try to flee but the exit leads nowhere!"))
                else:
                    # No exits - can't flee
                    events.append(self._msg_to_player(player_id, "There's nowhere to flee!"))
            else:
                # Flee failed - stay in combat
                events.append(self._msg_to_player(
                    player_id,
                    f"😰 You fail to escape! (Roll: {roll} + {dex_mod} DEX = {total} vs DC {flee_dc})"
                ))
                # Don't clear combat state on failed flee
        else:
            # Cancel scheduled combat events
            if player.combat.swing_event_id:
                self.cancel_event(player.combat.swing_event_id)
            
            # Clear combat state
            player.combat.clear_combat()
            
            if target:
                events.append(self._msg_to_player(
                    player_id, 
                    f"You stop attacking {target.name}."
                ))
            else:
                events.append(self._msg_to_player(player_id, "You disengage from combat."))
        
        return events
    
    def _show_combat_status(self, player_id: PlayerId) -> List[Event]:
        """Show current combat status."""
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        combat = player.combat
        
        if not combat.is_in_combat():
            return [self._msg_to_player(player_id, "You are not in combat.")]
        
        target = None
        if combat.target_id:
            target = self.world.players.get(combat.target_id) or self.world.npcs.get(combat.target_id)
        
        target_name = target.name if target else "unknown"
        target_health = ""
        if target:
            health_pct = (target.current_health / target.max_health) * 100
            target_health = f" ({health_pct:.0f}% health)"
        
        phase_name = combat.phase.value
        progress = combat.get_phase_progress() * 100
        remaining = combat.get_phase_remaining()
        
        weapon = combat.current_weapon
        
        lines = [
            f"⚔️ **Combat Status**",
            f"Target: {target_name}{target_health}",
            f"Phase: {phase_name} ({progress:.0f}% - {remaining:.1f}s remaining)",
            f"Weapon: {weapon.damage_min}-{weapon.damage_max} damage, {weapon.swing_speed:.1f}s speed",
            f"Auto-attack: {'ON' if combat.auto_attack else 'OFF'}"
        ]
        
        return [self._msg_to_player(player_id, "\n".join(lines))]
    
    async def _trigger_npc_player_enter(self, room_id: str, player_id: str) -> None:
        """Trigger on_player_enter for all NPCs in a room when a player enters."""
        room = self.world.rooms.get(room_id)
        if not room:
            return
        
        for entity_id in list(room.entities):
            if entity_id not in self.world.npcs:
                continue
            
            npc = self.world.npcs[entity_id]
            if not npc.is_alive():
                continue
            
            result = await self._run_behavior_hook(entity_id, "on_player_enter", player_id)
            
            # Handle attack_target (aggressive NPCs)
            if result and result.attack_target:
                if not npc.combat.is_in_combat():
                    npc.combat.add_threat(player_id, 100.0)
                    npc.start_attack(result.attack_target, self.world.item_templates)
                    weapon = npc.get_weapon_stats(self.world.item_templates)
                    self._schedule_swing_completion(entity_id, result.attack_target, weapon)
                    
                    # Announce the attack
                    if result.message:
                        await self._dispatch_events([
                            self._msg_to_room(room_id, result.message)
                        ])
    
    async def _trigger_npc_combat_start(self, npc_id: str, attacker_id: str) -> None:
        """Trigger on_combat_start behavior hooks for an NPC."""
        result = await self._run_behavior_hook(npc_id, "on_combat_start", attacker_id)
        
        # If NPC behavior wants to retaliate, start their attack
        if result and result.attack_target:
            npc = self.world.npcs.get(npc_id)
            if npc and npc.is_alive() and not npc.combat.is_in_combat():
                npc.start_attack(result.attack_target, self.world.item_templates)
                weapon = npc.get_weapon_stats(self.world.item_templates)
                self._schedule_swing_completion(npc_id, result.attack_target, weapon)
    
    async def _trigger_npc_damaged(self, npc_id: str, attacker_id: str, damage: int) -> None:
        """Trigger on_damaged behavior hooks for an NPC."""
        result = await self._run_behavior_hook(npc_id, "on_damaged", attacker_id, damage)
        
        npc = self.world.npcs.get(npc_id)
        if not npc or not npc.is_alive():
            return
        
        # Handle flee result
        if result and result.flee and result.move_to:
            # NPC flees - cancel combat and move
            npc.combat.clear_combat()
            old_room = self.world.rooms.get(npc.room_id)
            new_room = self.world.rooms.get(result.move_to)
            
            if old_room and new_room:
                old_room.entities.discard(npc_id)
                npc.room_id = result.move_to
                new_room.entities.add(npc_id)
        
        # Handle call for help
        if result and result.call_for_help:
            # Alert nearby allies
            await self._npc_call_for_help(npc_id, attacker_id)
        
        # Handle retaliation
        if result and result.attack_target and not npc.combat.is_in_combat():
            npc.start_attack(result.attack_target, self.world.item_templates)
            weapon = npc.get_weapon_stats(self.world.item_templates)
            self._schedule_swing_completion(npc_id, result.attack_target, weapon)
    
    async def _npc_call_for_help(self, caller_id: str, enemy_id: str) -> None:
        """Have nearby NPCs of same type join combat."""
        caller = self.world.npcs.get(caller_id)
        if not caller:
            return
        
        room = self.world.rooms.get(caller.room_id)
        if not room:
            return
        
        caller_template = self.world.npc_templates.get(caller.template_id)
        
        # Find allies in the same room
        for entity_id in list(room.entities):
            if entity_id == caller_id or entity_id not in self.world.npcs:
                continue
            
            ally = self.world.npcs[entity_id]
            if not ally.is_alive() or ally.combat.is_in_combat():
                continue
            
            # Check if same faction/type (simplified - same template type)
            ally_template = self.world.npc_templates.get(ally.template_id)
            if ally_template and caller_template:
                if ally_template.npc_type == caller_template.npc_type:
                    # Ally joins the fight
                    ally.combat.add_threat(enemy_id, 50.0)
                    ally.start_attack(enemy_id, self.world.item_templates)
                    weapon = ally.get_weapon_stats(self.world.item_templates)
                    self._schedule_swing_completion(entity_id, enemy_id, weapon)
                    
                    await self._dispatch_events([
                        self._msg_to_room(
                            room.id,
                            f"{ally.name} joins the fight!"
                        )
                    ])

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
        Apply a temporary armor class buff to an entity (Phase 2b example).
        Uses Targetable protocol for unified player/NPC targeting.
        """
        world = self.world
        events: List[Event] = []
        
        player = world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        room = world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "You are nowhere. (Room not found)")]

        # Use unified targeting to find target entity
        target, target_type = self._find_targetable_in_room(
            room.id, target_name,
            include_players=True,
            include_npcs=True,
            include_items=False
        )
        
        if not target or target_type == TargetableType.ITEM:
            return [self._msg_to_player(player_id, f"'{target_name}' not found.")]
        
        # Get entity reference
        entity: WorldEntity
        if target_type == TargetableType.PLAYER:
            entity = world.players[target.id]
        else:
            entity = world.npcs[target.id]
        
        # Create blessing effect
        effect_id = str(uuid.uuid4())
        effect = Effect(
            effect_id=effect_id,
            name="Blessed",
            effect_type="buff",
            stat_modifiers={"armor_class": 5},
            duration=30.0,  # 30 seconds
        )
        
        # Apply effect to entity
        entity.apply_effect(effect)
        
        # Schedule effect expiration
        async def expiration_callback():
            removed_effect = entity.remove_effect(effect_id)
            if removed_effect:
                if target_type == TargetableType.PLAYER:
                    # Send expiration message to player
                    expire_event = self._msg_to_player(
                        target.id,
                        "✨ The divine blessing fades away."
                    )
                    await self._dispatch_events([expire_event])
                    
                    # Send stat update with recalculated AC
                    stat_event = self._stat_update_to_player(
                        target.id,
                        {"armor_class": entity.get_effective_armor_class()}
                    )
                    await self._dispatch_events([stat_event])
        
        expiration_event_id = self.schedule_event(effect.duration, expiration_callback)
        effect.expiration_event_id = expiration_event_id
        
        # Send stat update with new AC (only for players)
        if target_type == TargetableType.PLAYER:
            events.append(self._stat_update_to_player(
                target.id,
                {"armor_class": entity.get_effective_armor_class()}
            ))
            
            # Send message to target player
            events.append(self._msg_to_player(
                target.id,
                "✨ *Divine light surrounds you!* You feel blessed. (+5 Armor Class for 30 seconds)"
            ))
        
        # Send confirmation to caster
        if target_type == TargetableType.PLAYER and player_id != target.id:
            events.append(self._msg_to_player(
                player_id,
                f"You bless {entity.name} with divine protection."
            ))
        elif target_type == TargetableType.NPC:
            events.append(self._msg_to_player(
                player_id,
                f"You bless {entity.name} with divine protection."
            ))
        
        # Broadcast to others in the room
        room_player_ids = self._get_player_ids_in_room(room.id)
        if len(room_player_ids) > 1:
            caster_name = player.name
            exclude_set = {player_id}
            if target_type == TargetableType.PLAYER:
                exclude_set.add(target.id)
            
            if target_type == TargetableType.PLAYER and player_id == target.id:
                room_msg = f"✨ *Divine light surrounds {entity.name}!*"
            else:
                room_msg = f"✨ *{caster_name} blesses {entity.name} with divine light!*"
            events.append(self._msg_to_room(room.id, room_msg, exclude=exclude_set))
        
        return events

    def _poison(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """
        Apply a damage over time (DoT) poison effect to an entity (Phase 2b example).
        Uses Targetable protocol for unified player/NPC targeting.
        """
        world = self.world
        events: List[Event] = []
        
        player = world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        room = world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "You are nowhere. (Room not found)")]

        # Use unified targeting to find target entity
        target, target_type = self._find_targetable_in_room(
            room.id, target_name,
            include_players=True,
            include_npcs=True,
            include_items=False
        )
        
        if not target or target_type == TargetableType.ITEM:
            return [self._msg_to_player(player_id, f"'{target_name}' not found.")]
        
        # Get entity reference
        entity: WorldEntity
        if target_type == TargetableType.PLAYER:
            entity = world.players[target.id]
        else:
            entity = world.npcs[target.id]
        
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
        
        # Apply effect to entity
        entity.apply_effect(effect)
        
        # Periodic damage callback
        async def poison_tick():
            # Check if effect still active
            if effect_id not in entity.active_effects:
                return
            
            # Apply damage
            old_health = entity.current_health
            entity.current_health = max(entity.current_health - effect.magnitude, 1)
            actual_damage = old_health - entity.current_health
            
            if target_type == TargetableType.PLAYER:
                # Send damage message to player
                damage_event = self._msg_to_player(
                    target.id,
                    f"🤢 *The poison burns through your veins!* You take {actual_damage} poison damage."
                )
                await self._dispatch_events([damage_event])
                
                # Send stat update
                stat_event = self._stat_update_to_player(
                    target.id,
                    {
                        "current_health": entity.current_health,
                        "max_health": entity.max_health,
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
            removed_effect = entity.remove_effect(effect_id)
            if removed_effect and target_type == TargetableType.PLAYER:
                # Send expiration message to player
                expire_event = self._msg_to_player(
                    target.id,
                    "🧪 The poison has run its course."
                )
                await self._dispatch_events([expire_event])
        
        expiration_event_id = self.schedule_event(effect.duration, expiration_callback)
        effect.expiration_event_id = expiration_event_id
        
        # Send message to target (only for players)
        if target_type == TargetableType.PLAYER:
            events.append(self._msg_to_player(
                target.id,
                "🤢 *Vile toxins course through your body!* You are poisoned. (5 damage every 3 seconds for 15 seconds)"
            ))
        
        # Send confirmation to poisoner
        if target_type == TargetableType.PLAYER and player_id != target.id:
            events.append(self._msg_to_player(
                player_id,
                f"You poison {entity.name} with toxic energy."
            ))
        elif target_type == TargetableType.NPC:
            events.append(self._msg_to_player(
                player_id,
                f"You poison {entity.name} with toxic energy."
            ))
        
        # Broadcast to others in the room
        room_player_ids = self._get_player_ids_in_room(room.id)
        if len(room_player_ids) > 1:
            poisoner_name = player.name
            exclude_set = {player_id}
            if target_type == TargetableType.PLAYER:
                exclude_set.add(target.id)
            
            if target_type == TargetableType.PLAYER and player_id == target.id:
                room_msg = f"🤢 *Vile toxins course through {entity.name}!*"
            else:
                room_msg = f"🤢 *{poisoner_name} poisons {entity.name} with toxic energy!*"
            events.append(self._msg_to_room(room.id, room_msg, exclude=exclude_set))
        
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
                
                # Get player IDs from unified entity set
                player_ids = self._get_player_ids_in_room(room_id)

                for pid in player_ids:
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
        """Give an item from your inventory to another entity (player or NPC)."""
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
        
        # Use unified targeting to find the target entity (player or NPC)
        target, target_type = self._find_targetable_in_room(
            room.id, target_name,
            include_players=True,
            include_npcs=True,
            include_items=False  # Can't give items to items
        )
        
        if not target:
            return [self._msg_to_player(player_id, f"You don't see '{target_name}' here.")]
        
        # Don't give to self
        if target_type == TargetableType.PLAYER and target.id == player_id:
            return [self._msg_to_player(player_id, "You can't give items to yourself.")]
        
        # Handle giving to a player
        if target_type == TargetableType.PLAYER:
            target_player = world.players[target.id]
            
            # Check if target is connected
            if not target_player.is_connected:
                return [self._msg_to_player(player_id, f"{target_player.name} is in stasis and cannot receive items.")]
            
            # Remove from giver's inventory
            player.inventory_items.remove(found_item_id)
            item.player_id = None
            
            # Update giver's inventory metadata
            if player.inventory_meta:
                player.inventory_meta.current_weight = calculate_inventory_weight(world, player_id)
                player.inventory_meta.current_slots = len(player.inventory_items)
            
            # Try to add to target's inventory
            try:
                add_item_to_inventory(world, target.id, found_item_id)
                
                return [
                    self._msg_to_player(player_id, f"You give {template.name} to {target_player.name}."),
                    self._msg_to_player(target.id, f"{player.name} gives you {template.name}."),
                    self._msg_to_room(room.id, f"{player.name} gives {template.name} to {target_player.name}.", exclude={player_id, target.id})
                ]
                
            except InventoryFullError as e:
                # Revert: give item back to giver
                item.player_id = player_id
                player.inventory_items.add(found_item_id)
                if player.inventory_meta:
                    player.inventory_meta.current_weight = calculate_inventory_weight(world, player_id)
                    player.inventory_meta.current_slots = len(player.inventory_items)
                
                return [self._msg_to_player(player_id, f"{target_player.name}'s inventory is full.")]
        
        # Handle giving to an NPC
        elif target_type == TargetableType.NPC:
            npc = world.npcs[target.id]
            npc_template = world.npc_templates.get(npc.template_id)
            display_name = npc.instance_data.get("name_override", npc.name) if npc.instance_data else npc.name
            
            # Remove from giver's inventory  
            player.inventory_items.remove(found_item_id)
            item.player_id = None
            
            # Update giver's inventory metadata
            if player.inventory_meta:
                player.inventory_meta.current_weight = calculate_inventory_weight(world, player_id)
                player.inventory_meta.current_slots = len(player.inventory_items)
            
            # Add to NPC's inventory (NPCs have unlimited inventory for now)
            npc.inventory_items.add(found_item_id)
            
            # Generate NPC response based on type
            npc_response = ""
            if npc_template:
                if npc_template.npc_type == "merchant":
                    npc_response = f'\n{display_name} says "Hmm, interesting. I\'ll take a look at this."'
                elif npc_template.npc_type == "friendly":
                    npc_response = f'\n{display_name} accepts your gift graciously.'
                elif npc_template.npc_type == "hostile":
                    npc_response = f'\n{display_name} snatches the item from your hand.'
                else:
                    npc_response = f'\n{display_name} takes the item.'
            
            return [
                self._msg_to_player(player_id, f"You give {template.name} to {display_name}.{npc_response}"),
                self._msg_to_room(room.id, f"{player.name} gives {template.name} to {display_name}.", exclude={player_id})
            ]
        
        return [self._msg_to_player(player_id, f"You can't give items to that.")]
