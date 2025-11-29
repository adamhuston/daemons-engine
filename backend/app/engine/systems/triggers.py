# backend/app/engine/systems/triggers.py
"""
TriggerSystem - Room-based reactive trigger system.

Provides:
- Data-driven triggers defined in YAML
- Condition evaluation (flag_set, has_item, level, etc.)
- Action execution (message, set_flag, spawn_npc, etc.)
- Cooldown and max_fires enforcement
- Variable substitution in messages ({player.name}, etc.)
- Command pattern matching with wildcards
- Timer-based recurring triggers

Triggers make rooms reactive entities that respond to:
- on_enter: Player enters the room
- on_exit: Player leaves the room
- on_command: Player types a command matching a pattern
- on_timer: Recurring time-based events
"""

from __future__ import annotations
import fnmatch
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List

if TYPE_CHECKING:
    from .context import GameContext
    from ..world import World, WorldRoom, WorldArea, WorldPlayer, WorldNpc, PlayerId, RoomId, NpcId


# Type alias for events
Event = Dict[str, Any]

# Type aliases for handler functions
ConditionHandler = Callable[["TriggerContext", Dict[str, Any]], bool]
ActionHandler = Callable[["TriggerSystem", "TriggerContext", Dict[str, Any]], List[Event]]


# =============================================================================
# Trigger Data Structures
# =============================================================================

@dataclass
class TriggerCondition:
    """
    A condition that must be met for a trigger to fire.
    
    Conditions are evaluated with AND logic by default.
    Use the 'any' condition type for OR logic.
    """
    type: str  # "has_item", "health_below", "flag_set", etc.
    params: Dict[str, Any] = field(default_factory=dict)
    negate: bool = False  # Invert the condition result


@dataclass
class TriggerAction:
    """
    An atomic action to perform when a trigger fires.
    
    Actions execute in sequence. Use delay to insert pauses.
    """
    type: str  # "message_player", "spawn_npc", "set_flag", etc.
    params: Dict[str, Any] = field(default_factory=dict)
    delay: float = 0.0  # Seconds to wait before executing


@dataclass
class RoomTrigger:
    """
    A trigger attached to a room.
    
    Triggers respond to specific events and execute actions
    when their conditions are met.
    """
    id: str
    event: str  # "on_enter", "on_exit", "on_command", "on_timer"
    conditions: List[TriggerCondition] = field(default_factory=list)
    actions: List[TriggerAction] = field(default_factory=list)
    cooldown: float = 0.0  # Minimum seconds between firings
    max_fires: int = -1  # -1 = unlimited
    enabled: bool = True
    permanent: bool = False  # If True, trigger state persists across sessions
    
    # Event-specific fields
    command_pattern: str | None = None  # For on_command: "pull *", "press button"
    timer_interval: float | None = None  # For on_timer: seconds between fires
    timer_initial_delay: float = 0.0  # For on_timer: delay before first fire


@dataclass
class TriggerState:
    """
    Runtime state for a trigger instance.
    
    Tracks firing history and timer event IDs.
    """
    fire_count: int = 0
    last_fired_at: float | None = None
    timer_event_id: str | None = None
    enabled: bool = True


@dataclass
class TriggerContext:
    """
    Context object passed to condition/action handlers.
    
    Provides access to the triggering player, room, world state,
    and helper methods for common operations.
    """
    player_id: "PlayerId"
    room_id: "RoomId"
    world: "World"
    event_type: str  # "on_enter", "on_exit", "on_command", "on_timer"
    
    # Event-specific context
    direction: str | None = None  # For movement events
    raw_command: str | None = None  # For command events
    
    # Resolved references (populated by TriggerSystem)
    player: "WorldPlayer | None" = None
    room: "WorldRoom | None" = None
    
    def get_player(self) -> "WorldPlayer | None":
        """Get the triggering player."""
        if self.player is None:
            self.player = self.world.players.get(self.player_id)
        return self.player
    
    def get_room(self) -> "WorldRoom | None":
        """Get the trigger's room."""
        if self.room is None:
            self.room = self.world.rooms.get(self.room_id)
        return self.room


# =============================================================================
# TriggerSystem
# =============================================================================

class TriggerSystem:
    """
    Manages room triggers and their execution.
    
    Features:
    - Condition evaluation with AND logic
    - Action execution with delay support
    - Cooldown and max_fires enforcement
    - Variable substitution in message text
    
    Usage:
        trigger_system = TriggerSystem(ctx)
        events = trigger_system.fire_event(room_id, "on_enter", trigger_ctx)
    """
    
    def __init__(self, ctx: "GameContext") -> None:
        self.ctx = ctx
        
        # Registered handlers
        self.condition_handlers: Dict[str, ConditionHandler] = {}
        self.action_handlers: Dict[str, ActionHandler] = {}
        
        # Register built-in conditions and actions
        self._register_builtin_conditions()
        self._register_builtin_actions()
    
    # ---------- Event Firing ----------
    
    def fire_event(
        self,
        room_id: "RoomId",
        event_type: str,
        trigger_ctx: TriggerContext,
    ) -> List[Event]:
        """
        Check and fire all triggers for a room event.
        
        Args:
            room_id: The room to check triggers in
            event_type: The event type ("on_enter", "on_exit", etc.)
            trigger_ctx: Context with player/event information
        
        Returns:
            List of events generated by trigger actions
        """
        room = self.ctx.world.rooms.get(room_id)
        if not room:
            return []
        
        # Check for triggers field (Phase 5.1 extension)
        if not hasattr(room, 'triggers'):
            return []
        
        events: List[Event] = []
        current_time = time.time()
        
        for trigger in room.triggers:
            if not self._should_fire(trigger, room, event_type, current_time):
                continue
            
            # Check conditions
            if not self.check_conditions(trigger.conditions, trigger_ctx):
                continue
            
            # Update trigger state
            state = self._get_or_create_state(room, trigger.id)
            state.fire_count += 1
            state.last_fired_at = current_time
            
            # Execute actions
            trigger_events = self.execute_actions(trigger.actions, trigger_ctx)
            events.extend(trigger_events)
        
        return events
    
    def fire_command(
        self,
        room_id: "RoomId",
        raw_command: str,
        trigger_ctx: TriggerContext,
    ) -> List[Event]:
        """
        Check and fire on_command triggers that match the player's input.
        
        Uses fnmatch-style pattern matching:
        - "pull lever" matches exactly "pull lever"
        - "pull *" matches "pull lever", "pull rope", etc.
        - "open *door*" matches "open door", "open the door", etc.
        
        Args:
            room_id: The room to check triggers in
            raw_command: The raw command string from the player
            trigger_ctx: Context with player/event information
        
        Returns:
            List of events generated by trigger actions, or empty if no match
        """
        room = self.ctx.world.rooms.get(room_id)
        if not room:
            return []
        
        if not hasattr(room, 'triggers'):
            return []
        
        events: List[Event] = []
        current_time = time.time()
        command_lower = raw_command.lower().strip()
        
        for trigger in room.triggers:
            # Only process on_command triggers
            if trigger.event != "on_command":
                continue
            
            # Check pattern match
            if not trigger.command_pattern:
                continue
            
            pattern = trigger.command_pattern.lower()
            if not fnmatch.fnmatch(command_lower, pattern):
                continue
            
            # Check cooldown and max_fires
            if not self._should_fire(trigger, room, "on_command", current_time):
                continue
            
            # Check conditions
            if not self.check_conditions(trigger.conditions, trigger_ctx):
                continue
            
            # Update trigger state
            state = self._get_or_create_state(room, trigger.id)
            state.fire_count += 1
            state.last_fired_at = current_time
            
            # Execute actions
            trigger_events = self.execute_actions(trigger.actions, trigger_ctx)
            events.extend(trigger_events)
            
            # First matching trigger wins (don't process multiple)
            break
        
        return events
    
    # ---------- Timer Triggers ----------
    
    def start_room_timers(self, room: "WorldRoom") -> None:
        """
        Initialize and start all timer triggers for a room.
        
        Called when a room is loaded or when timers need to be restarted.
        """
        if not hasattr(room, 'triggers'):
            return
        
        for trigger in room.triggers:
            if trigger.event != "on_timer" or not trigger.enabled:
                continue
            
            if trigger.timer_interval is None or trigger.timer_interval <= 0:
                print(f"[TriggerSystem] Timer trigger {trigger.id} has no valid interval")
                continue
            
            # Get or create state
            state = self._get_or_create_state(room, trigger.id)
            
            # Cancel existing timer if any
            if state.timer_event_id:
                self.ctx.time_manager.cancel(state.timer_event_id)
            
            # Schedule the timer
            initial_delay = trigger.timer_initial_delay if trigger.timer_initial_delay > 0 else trigger.timer_interval
            
            event_id = self.ctx.time_manager.schedule(
                delay_seconds=initial_delay,
                callback=self._make_timer_callback(room.id, trigger.id),
                event_id=f"trigger_{room.id}_{trigger.id}",
                recurring=True,
            )
            
            state.timer_event_id = event_id
            print(f"[TriggerSystem] Started timer {trigger.id} for room {room.id} (interval={trigger.timer_interval}s)")
    
    def stop_room_timers(self, room: "WorldRoom") -> None:
        """
        Stop all timer triggers for a room.
        
        Called when a room is unloaded or server shuts down.
        """
        if not hasattr(room, 'trigger_states'):
            return
        
        for trigger_id, state in room.trigger_states.items():
            if state.timer_event_id:
                self.ctx.time_manager.cancel(state.timer_event_id)
                state.timer_event_id = None
    
    def _make_timer_callback(self, room_id: "RoomId", trigger_id: str):
        """Create a callback for a timer trigger."""
        async def timer_callback():
            room = self.ctx.world.rooms.get(room_id)
            if not room or not hasattr(room, 'triggers'):
                return
            
            # Find the trigger
            trigger = None
            for t in room.triggers:
                if t.id == trigger_id:
                    trigger = t
                    break
            
            if not trigger or not trigger.enabled:
                return
            
            # Check max_fires
            state = self._get_state(room, trigger_id)
            if trigger.max_fires >= 0 and state and state.fire_count >= trigger.max_fires:
                # Stop the timer
                if state.timer_event_id:
                    self.ctx.time_manager.cancel(state.timer_event_id)
                    state.timer_event_id = None
                return
            
            # Timer triggers don't have a specific player, so we need to handle that
            # For room broadcasts, we'll use None as player_id
            # Get any player in the room for context (or None)
            player_id = None
            for entity_id in room.entities:
                if entity_id in self.ctx.world.players:
                    player_id = entity_id
                    break
            
            # Create trigger context (player_id may be None for timer triggers)
            trigger_ctx = TriggerContext(
                player_id=player_id or "",
                room_id=room_id,
                world=self.ctx.world,
                event_type="on_timer",
            )
            
            # Check conditions
            if not self.check_conditions(trigger.conditions, trigger_ctx):
                return
            
            # Update state
            if state:
                state.fire_count += 1
                state.last_fired_at = time.time()
            
            # Execute actions
            events = self.execute_actions(trigger.actions, trigger_ctx)
            if events:
                await self.ctx.dispatch_events(events)
        
        return timer_callback
    
    # ---------- Area Triggers ----------
    
    def fire_area_event(
        self,
        area_id: str,
        event_type: str,
        trigger_ctx: TriggerContext,
    ) -> List[Event]:
        """
        Fire area-level triggers (on_area_enter, on_area_exit).
        
        Args:
            area_id: The area to check triggers in
            event_type: "on_area_enter" or "on_area_exit"
            trigger_ctx: Context with player/event information
        
        Returns:
            List of events generated by trigger actions
        """
        area = self.ctx.world.areas.get(area_id)
        if not area:
            return []
        
        if not hasattr(area, 'triggers'):
            return []
        
        events: List[Event] = []
        current_time = time.time()
        
        for trigger in area.triggers:
            if not self._should_fire_area(trigger, area, event_type, current_time):
                continue
            
            if not self.check_conditions(trigger.conditions, trigger_ctx):
                continue
            
            # Update trigger state
            state = self._get_or_create_area_state(area, trigger.id)
            state.fire_count += 1
            state.last_fired_at = current_time
            
            # Execute actions
            trigger_events = self.execute_actions(trigger.actions, trigger_ctx)
            events.extend(trigger_events)
        
        return events
    
    def _should_fire_area(
        self,
        trigger: RoomTrigger,
        area: "WorldArea",
        event_type: str,
        current_time: float,
    ) -> bool:
        """Check if an area trigger should fire."""
        if trigger.event != event_type:
            return False
        
        if not trigger.enabled:
            return False
        
        state = self._get_area_state(area, trigger.id)
        if state and not state.enabled:
            return False
        
        if trigger.max_fires >= 0 and state and state.fire_count >= trigger.max_fires:
            return False
        
        if trigger.cooldown > 0 and state and state.last_fired_at is not None:
            if current_time - state.last_fired_at < trigger.cooldown:
                return False
        
        return True
    
    def _get_area_state(self, area: "WorldArea", trigger_id: str) -> TriggerState | None:
        """Get area trigger state if it exists."""
        if not hasattr(area, 'trigger_states'):
            return None
        return area.trigger_states.get(trigger_id)
    
    def _get_or_create_area_state(self, area: "WorldArea", trigger_id: str) -> TriggerState:
        """Get or create area trigger state."""
        if not hasattr(area, 'trigger_states'):
            area.trigger_states = {}
        
        if trigger_id not in area.trigger_states:
            area.trigger_states[trigger_id] = TriggerState()
        
        return area.trigger_states[trigger_id]
    
    # ---------- Initialization ----------
    
    def initialize_all_timers(self) -> None:
        """
        Start timer triggers for all rooms in the world.
        
        Called once at engine startup after world is loaded.
        """
        for room in self.ctx.world.rooms.values():
            self.start_room_timers(room)
        
        print(f"[TriggerSystem] Initialized timers for {len(self.ctx.world.rooms)} rooms")
    
    def _should_fire(
        self,
        trigger: RoomTrigger,
        room: "WorldRoom",
        event_type: str,
        current_time: float,
    ) -> bool:
        """Check if a trigger should fire based on event type, cooldown, and max_fires."""
        # Wrong event type
        if trigger.event != event_type:
            return False
        
        # Trigger disabled
        if not trigger.enabled:
            return False
        
        # Get runtime state
        state = self._get_state(room, trigger.id)
        if state and not state.enabled:
            return False
        
        # Max fires reached
        if trigger.max_fires >= 0 and state and state.fire_count >= trigger.max_fires:
            return False
        
        # Cooldown not elapsed
        if trigger.cooldown > 0 and state and state.last_fired_at is not None:
            elapsed = current_time - state.last_fired_at
            if elapsed < trigger.cooldown:
                return False
        
        return True
    
    def _get_state(self, room: "WorldRoom", trigger_id: str) -> TriggerState | None:
        """Get trigger state if it exists."""
        if not hasattr(room, 'trigger_states'):
            return None
        return room.trigger_states.get(trigger_id)
    
    def _get_or_create_state(self, room: "WorldRoom", trigger_id: str) -> TriggerState:
        """Get or create trigger state."""
        if not hasattr(room, 'trigger_states'):
            room.trigger_states = {}
        
        if trigger_id not in room.trigger_states:
            room.trigger_states[trigger_id] = TriggerState()
        
        return room.trigger_states[trigger_id]
    
    # ---------- Condition Evaluation ----------
    
    def check_conditions(
        self,
        conditions: List[TriggerCondition],
        ctx: TriggerContext,
    ) -> bool:
        """
        Evaluate all conditions with AND logic.
        
        Empty conditions list = always passes.
        """
        for condition in conditions:
            handler = self.condition_handlers.get(condition.type)
            if handler is None:
                print(f"[TriggerSystem] Unknown condition type: {condition.type}")
                return False
            
            result = handler(ctx, condition.params)
            
            # Apply negation
            if condition.negate:
                result = not result
            
            # AND logic - fail on first false
            if not result:
                return False
        
        return True
    
    # ---------- Action Execution ----------
    
    def execute_actions(
        self,
        actions: List[TriggerAction],
        ctx: TriggerContext,
    ) -> List[Event]:
        """
        Execute a list of actions, handling delays via TimeEventManager.
        
        Actions with delay=0 execute immediately.
        Actions with delay>0 are scheduled for later execution.
        """
        events: List[Event] = []
        
        for action in actions:
            handler = self.action_handlers.get(action.type)
            if handler is None:
                print(f"[TriggerSystem] Unknown action type: {action.type}")
                continue
            
            if action.delay > 0:
                # Schedule delayed execution
                self._schedule_delayed_action(handler, ctx, action.params, action.delay)
            else:
                # Execute immediately
                action_events = handler(self, ctx, action.params)
                events.extend(action_events)
        
        return events
    
    def _schedule_delayed_action(
        self,
        handler: ActionHandler,
        ctx: TriggerContext,
        params: Dict[str, Any],
        delay: float,
    ) -> None:
        """Schedule an action to execute after a delay."""
        async def delayed_callback():
            events = handler(self, ctx, params)
            if events:
                await self.ctx.dispatch_events(events)
        
        self.ctx.time_manager.schedule(
            delay_seconds=delay,
            callback=delayed_callback,
        )
    
    # ---------- Variable Substitution ----------
    
    def substitute_variables(self, text: str, ctx: TriggerContext) -> str:
        """
        Replace variables in text with actual values.
        
        Supported variables:
        - {player.name}: Triggering player's name
        - {player.level}: Triggering player's level
        - {room.name}: Room's name
        - {direction}: Direction of movement (for enter/exit)
        """
        player = ctx.get_player()
        room = ctx.get_room()
        
        # Build substitution dict
        subs: Dict[str, str] = {}
        
        if player:
            subs["player.name"] = player.name
            subs["player.level"] = str(getattr(player, 'level', 1))
        
        if room:
            subs["room.name"] = room.name
        
        if ctx.direction:
            subs["direction"] = ctx.direction
        
        # Perform substitution using regex for {var} pattern
        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)
            return subs.get(var_name, match.group(0))  # Keep original if not found
        
        return re.sub(r'\{([^}]+)\}', replace_var, text)
    
    # ---------- Built-in Conditions ----------
    
    def _register_builtin_conditions(self) -> None:
        """Register the built-in condition handlers."""
        self.condition_handlers["flag_set"] = self._condition_flag_set
        self.condition_handlers["has_item"] = self._condition_has_item
        self.condition_handlers["level"] = self._condition_level
        # Phase 5.2 conditions
        self.condition_handlers["health_percent"] = self._condition_health_percent
        self.condition_handlers["in_combat"] = self._condition_in_combat
        self.condition_handlers["has_effect"] = self._condition_has_effect
        self.condition_handlers["entity_present"] = self._condition_entity_present
        self.condition_handlers["player_count"] = self._condition_player_count
        # Phase 11 conditions - Light and Vision
        self.condition_handlers["light_level"] = self._condition_light_level
        self.condition_handlers["visibility_level"] = self._condition_visibility_level
    
    def _condition_flag_set(self, ctx: TriggerContext, params: Dict[str, Any]) -> bool:
        """
        Check if a room flag is set to a specific value.
        
        Params:
            flag_name: Name of the flag to check
            value: Expected value (default: True for boolean check)
        """
        room = ctx.get_room()
        if not room or not hasattr(room, 'room_flags'):
            return False
        
        flag_name = params.get("flag_name")
        expected = params.get("value", True)
        
        actual = room.room_flags.get(flag_name)
        return actual == expected
    
    def _condition_has_item(self, ctx: TriggerContext, params: Dict[str, Any]) -> bool:
        """
        Check if the player has an item in their inventory.
        
        Params:
            template_id: The item template ID to check for
            quantity: Minimum quantity required (default: 1)
        """
        player = ctx.get_player()
        if not player:
            return False
        
        template_id = params.get("template_id")
        quantity = params.get("quantity", 1)
        
        # Get player inventory
        inventory = ctx.world.player_inventories.get(ctx.player_id)
        if not inventory:
            return False
        
        # Count items matching template
        count = 0
        for item_id in inventory.items:
            item = ctx.world.items.get(item_id)
            if item and item.template_id == template_id:
                count += getattr(item, 'quantity', 1)
        
        return count >= quantity
    
    def _condition_level(self, ctx: TriggerContext, params: Dict[str, Any]) -> bool:
        """
        Check if the player's level meets a comparison.
        
        Params:
            operator: Comparison operator (">=", "<=", ">", "<", "==", "!=")
            value: Level value to compare against
        """
        player = ctx.get_player()
        if not player:
            return False
        
        operator = params.get("operator", ">=")
        value = params.get("value", 1)
        player_level = getattr(player, 'level', 1)
        
        if operator == ">=":
            return player_level >= value
        elif operator == "<=":
            return player_level <= value
        elif operator == ">":
            return player_level > value
        elif operator == "<":
            return player_level < value
        elif operator == "==":
            return player_level == value
        elif operator == "!=":
            return player_level != value
        else:
            print(f"[TriggerSystem] Unknown operator: {operator}")
            return False
    
    def _condition_health_percent(self, ctx: TriggerContext, params: Dict[str, Any]) -> bool:
        """
        Check if the player's health percentage meets a comparison.
        
        Params:
            operator: Comparison operator (">=", "<=", ">", "<", "==", "!=")
            value: Health percentage to compare against (0-100)
        """
        player = ctx.get_player()
        if not player:
            return False
        
        operator = params.get("operator", ">=")
        value = params.get("value", 100)
        
        max_hp = getattr(player, 'max_hp', 100)
        current_hp = getattr(player, 'hp', max_hp)
        health_percent = (current_hp / max_hp * 100) if max_hp > 0 else 0
        
        return self._compare(health_percent, operator, value)
    
    def _condition_in_combat(self, ctx: TriggerContext, params: Dict[str, Any]) -> bool:
        """
        Check if the player is currently in combat.
        
        No params required.
        """
        player = ctx.get_player()
        if not player:
            return False
        
        combat = getattr(player, 'combat', None)
        if combat is None:
            return False
        
        return combat.is_in_combat()
    
    def _condition_has_effect(self, ctx: TriggerContext, params: Dict[str, Any]) -> bool:
        """
        Check if the player has an active effect.
        
        Params:
            effect_name: Name of the effect to check for
        """
        player = ctx.get_player()
        if not player:
            return False
        
        effect_name = params.get("effect_name", "")
        
        # Check via effect system
        if self.ctx.effect_system:
            effects = self.ctx.effect_system.get_effects(ctx.player_id)
            for effect in effects:
                if effect.name == effect_name:
                    return True
        
        return False
    
    def _condition_entity_present(self, ctx: TriggerContext, params: Dict[str, Any]) -> bool:
        """
        Check if an NPC with a specific template or name is in the room.
        
        Params:
            template_id: The NPC template ID to check for (optional)
            name: The NPC name to check for (optional, case-insensitive)
        """
        room = ctx.get_room()
        if not room:
            return False
        
        template_id = params.get("template_id")
        name = params.get("name", "").lower()
        
        for entity_id in room.entities:
            npc = ctx.world.npcs.get(entity_id)
            if npc:
                if template_id and npc.template_id == template_id:
                    return True
                if name and npc.name.lower() == name:
                    return True
        
        return False
    
    def _condition_player_count(self, ctx: TriggerContext, params: Dict[str, Any]) -> bool:
        """
        Check the number of players in the room.
        
        Params:
            operator: Comparison operator (">=", "<=", ">", "<", "==", "!=")
            value: Number of players to compare against
        """
        room = ctx.get_room()
        if not room:
            return False
        
        operator = params.get("operator", ">=")
        value = params.get("value", 1)
        
        # Count players in room
        player_count = sum(1 for eid in room.entities if eid in ctx.world.players)
        
        return self._compare(player_count, operator, value)
    
    def _condition_light_level(self, ctx: TriggerContext, params: Dict[str, Any]) -> bool:
        """
        Check if the room's light level meets a comparison.
        
        Params:
            operator: Comparison operator (">=", "<=", ">", "<", "==", "!=")
            value: Light level to compare against (0-100)
        """
        room = ctx.get_room()
        if not room:
            return False
        
        # Get lighting system from context
        lighting_system = getattr(self.ctx, 'lighting_system', None)
        if not lighting_system:
            return False
        
        operator = params.get("operator", ">=")
        value = params.get("value", 0)
        
        # Get current light level for room
        current_light = lighting_system.calculate_room_light(room)
        
        return self._compare(current_light, operator, value)
    
    def _condition_visibility_level(self, ctx: TriggerContext, params: Dict[str, Any]) -> bool:
        """
        Check if the room's visibility level matches a specific level.
        
        Params:
            level: Visibility level name ("none", "minimal", "partial", "normal", "enhanced")
        """
        room = ctx.get_room()
        if not room:
            return False
        
        # Get lighting system from context
        lighting_system = getattr(self.ctx, 'lighting_system', None)
        if not lighting_system:
            return False
        
        expected_level = params.get("level", "normal").lower()
        
        # Calculate current light and get visibility level
        current_light = lighting_system.calculate_room_light(room)
        visibility = lighting_system.get_visibility_level(current_light)
        
        return visibility.value == expected_level
    
    def _compare(self, actual: float, operator: str, expected: float) -> bool:
        """Helper to perform numeric comparison."""
        if operator == ">=":
            return actual >= expected
        elif operator == "<=":
            return actual <= expected
        elif operator == ">":
            return actual > expected
        elif operator == "<":
            return actual < expected
        elif operator == "==":
            return actual == expected
        elif operator == "!=":
            return actual != expected
        else:
            print(f"[TriggerSystem] Unknown operator: {operator}")
            return False
    
    # ---------- Built-in Actions ----------
    
    def _register_builtin_actions(self) -> None:
        """Register the built-in action handlers."""
        self.action_handlers["message_player"] = self._action_message_player
        self.action_handlers["message_room"] = self._action_message_room
        self.action_handlers["set_flag"] = self._action_set_flag
        self.action_handlers["toggle_flag"] = self._action_toggle_flag
        # Phase 5.2 actions
        self.action_handlers["damage"] = self._action_damage
        self.action_handlers["heal"] = self._action_heal
        self.action_handlers["apply_effect"] = self._action_apply_effect
        self.action_handlers["spawn_npc"] = self._action_spawn_npc
        self.action_handlers["despawn_npc"] = self._action_despawn_npc
        # Phase 5.3 actions - Dynamic World
        self.action_handlers["open_exit"] = self._action_open_exit
        self.action_handlers["close_exit"] = self._action_close_exit
        self.action_handlers["set_description"] = self._action_set_description
        self.action_handlers["reset_description"] = self._action_reset_description
        self.action_handlers["spawn_item"] = self._action_spawn_item
        self.action_handlers["despawn_item"] = self._action_despawn_item
        self.action_handlers["give_item"] = self._action_give_item
        self.action_handlers["take_item"] = self._action_take_item
        self.action_handlers["enable_trigger"] = self._action_enable_trigger
        self.action_handlers["disable_trigger"] = self._action_disable_trigger
        self.action_handlers["fire_trigger"] = self._action_fire_trigger
        # Phase 11 actions - Darkness Events
        self.action_handlers["stumble_in_darkness"] = self._action_stumble_in_darkness
        self.action_handlers["despawn_item"] = self._action_despawn_item
        self.action_handlers["give_item"] = self._action_give_item
        self.action_handlers["take_item"] = self._action_take_item
        self.action_handlers["enable_trigger"] = self._action_enable_trigger
        self.action_handlers["disable_trigger"] = self._action_disable_trigger
        self.action_handlers["fire_trigger"] = self._action_fire_trigger
    
    def _action_message_player(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Send a message to the triggering player.
        
        Params:
            text: The message text (supports {variable} substitution)
        """
        text = params.get("text", "")
        text = self.substitute_variables(text, ctx)
        
        return [self.ctx.msg_to_player(ctx.player_id, text)]
    
    def _action_message_room(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Broadcast a message to the room.
        
        Params:
            text: The message text (supports {variable} substitution)
            exclude_player: If True, exclude the triggering player
        """
        text = params.get("text", "")
        text = self.substitute_variables(text, ctx)
        
        exclude: set | None = None
        if params.get("exclude_player", False):
            exclude = {ctx.player_id}
        
        return [self.ctx.msg_to_room(ctx.room_id, text, exclude=exclude)]
    
    def _action_set_flag(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Set a room flag to a value.
        
        Params:
            name: Flag name
            value: Value to set
        """
        room = ctx.get_room()
        if not room:
            return []
        
        if not hasattr(room, 'room_flags'):
            room.room_flags = {}
        
        flag_name = params.get("name")
        value = params.get("value", True)
        
        room.room_flags[flag_name] = value
        return []
    
    def _action_toggle_flag(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Toggle a boolean room flag.
        
        Params:
            name: Flag name to toggle
        """
        room = ctx.get_room()
        if not room:
            return []
        
        if not hasattr(room, 'room_flags'):
            room.room_flags = {}
        
        flag_name = params.get("name")
        current = room.room_flags.get(flag_name, False)
        room.room_flags[flag_name] = not current
        return []
    
    def _action_damage(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Deal damage to the triggering player.
        
        Params:
            amount: Damage amount
            damage_type: Type of damage (for flavor, e.g., "piercing", "fire")
        """
        player = ctx.get_player()
        if not player:
            return []
        
        amount = params.get("amount", 10)
        damage_type = params.get("damage_type", "physical")
        
        # Apply damage
        old_hp = player.hp
        player.hp = max(0, player.hp - amount)
        
        events: List[Event] = []
        
        # Send stat update
        if self.ctx.event_dispatcher:
            events.extend(self.ctx.event_dispatcher.emit_stat_update(ctx.player_id))
        
        # Check for death
        if player.hp <= 0 and old_hp > 0:
            events.append(self.ctx.msg_to_player(
                ctx.player_id,
                f"💀 The {damage_type} damage was too much. You have fallen!"
            ))
        
        return events
    
    def _action_heal(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Heal the triggering player.
        
        Params:
            amount: Healing amount
        """
        player = ctx.get_player()
        if not player:
            return []
        
        amount = params.get("amount", 10)
        max_hp = getattr(player, 'max_hp', 100)
        
        player.hp = min(max_hp, player.hp + amount)
        
        events: List[Event] = []
        
        # Send stat update
        if self.ctx.event_dispatcher:
            events.extend(self.ctx.event_dispatcher.emit_stat_update(ctx.player_id))
        
        return events
    
    def _action_apply_effect(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Apply a buff/debuff effect to the triggering player.
        
        Params:
            effect_name: Name of the effect
            effect_type: Type ("buff", "debuff", "dot", "hot")
            duration: Duration in seconds
            stat_modifiers: Dict of stat modifications
            magnitude: For DoT/HoT, damage/heal per tick
            interval: For DoT/HoT, seconds between ticks
        """
        if not self.ctx.effect_system:
            return []
        
        effect_name = params.get("effect_name", "trigger_effect")
        effect_type = params.get("effect_type", "buff")
        duration = params.get("duration", 30.0)
        stat_modifiers = params.get("stat_modifiers", {})
        magnitude = params.get("magnitude", 0)
        interval = params.get("interval", 0)
        
        self.ctx.effect_system.apply_effect(
            entity_id=ctx.player_id,
            effect_name=effect_name,
            effect_type=effect_type,
            duration=duration,
            stat_modifiers=stat_modifiers,
            magnitude=magnitude,
            interval=interval,
        )
        
        return []
    
    def _action_spawn_npc(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Spawn an NPC in the room.
        
        Params:
            template_id: The NPC template ID to spawn
            count: Number to spawn (default: 1)
        """
        room = ctx.get_room()
        if not room:
            return []
        
        template_id = params.get("template_id")
        count = params.get("count", 1)
        
        if not template_id:
            print("[TriggerSystem] spawn_npc requires template_id")
            return []
        
        template = ctx.world.npc_templates.get(template_id)
        if not template:
            print(f"[TriggerSystem] NPC template not found: {template_id}")
            return []
        
        # Import WorldNpc to create instances
        from ..world import WorldNpc, CombatState
        
        for _ in range(count):
            npc_id = f"npc_{template_id}_{uuid.uuid4().hex[:8]}"
            
            npc = WorldNpc(
                id=npc_id,
                template_id=template_id,
                name=template.name,
                room_id=ctx.room_id,
                hp=template.max_hp,
                max_hp=template.max_hp,
                combat=CombatState(),
            )
            
            # Add to world
            ctx.world.npcs[npc_id] = npc
            room.entities.add(npc_id)
        
        return []
    
    def _action_despawn_npc(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Remove an NPC from the room.
        
        Params:
            template_id: The NPC template ID to remove (optional)
            name: The NPC name to remove (optional, case-insensitive)
            all: If True, remove all matching NPCs (default: False, removes first match)
        """
        room = ctx.get_room()
        if not room:
            return []
        
        template_id = params.get("template_id")
        name = params.get("name", "").lower()
        remove_all = params.get("all", False)
        
        to_remove: List[str] = []
        
        for entity_id in list(room.entities):
            npc = ctx.world.npcs.get(entity_id)
            if npc:
                match = False
                if template_id and npc.template_id == template_id:
                    match = True
                elif name and npc.name.lower() == name:
                    match = True
                
                if match:
                    to_remove.append(entity_id)
                    if not remove_all:
                        break
        
        for npc_id in to_remove:
            room.entities.discard(npc_id)
            del ctx.world.npcs[npc_id]
        
        return []
    
    # ---------- Phase 5.3: Dynamic World Actions ----------
    
    def _action_open_exit(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Open/add an exit from this room.
        
        Params:
            direction: The exit direction ("north", "south", etc.)
            target_room: The room ID the exit leads to
        """
        room = ctx.get_room()
        if not room:
            return []
        
        direction = params.get("direction")
        target_room = params.get("target_room")
        
        if not direction or not target_room:
            print("[TriggerSystem] open_exit requires direction and target_room")
            return []
        
        if not hasattr(room, 'dynamic_exits'):
            room.dynamic_exits = {}
        
        room.dynamic_exits[direction] = target_room
        return []
    
    def _action_close_exit(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Close/remove an exit from this room.
        
        Params:
            direction: The exit direction to close
        
        Note: This sets the dynamic exit to None, which will be filtered out
        by get_effective_exits(). To restore a base exit, use reset mechanics.
        """
        room = ctx.get_room()
        if not room:
            return []
        
        direction = params.get("direction")
        if not direction:
            print("[TriggerSystem] close_exit requires direction")
            return []
        
        if not hasattr(room, 'dynamic_exits'):
            room.dynamic_exits = {}
        
        # Set to None to indicate "closed" - get_effective_exits will filter it
        room.dynamic_exits[direction] = None
        return []
    
    def _action_set_description(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Set the room's dynamic description.
        
        Params:
            text: The new description text (supports variable substitution)
        """
        room = ctx.get_room()
        if not room:
            return []
        
        text = params.get("text", "")
        text = self.substitute_variables(text, ctx)
        
        room.dynamic_description = text
        return []
    
    def _action_reset_description(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Reset the room's description to the original.
        
        No params required.
        """
        room = ctx.get_room()
        if not room:
            return []
        
        room.dynamic_description = None
        return []
    
    def _action_spawn_item(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Spawn an item in the room.
        
        Params:
            template_id: The item template ID to spawn
            quantity: Number to spawn (default: 1)
        """
        room = ctx.get_room()
        if not room:
            return []
        
        template_id = params.get("template_id")
        quantity = params.get("quantity", 1)
        
        if not template_id:
            print("[TriggerSystem] spawn_item requires template_id")
            return []
        
        template = ctx.world.item_templates.get(template_id)
        if not template:
            print(f"[TriggerSystem] Item template not found: {template_id}")
            return []
        
        # Import WorldItem to create instance
        from ..world import WorldItem
        
        item_id = f"item_{template_id}_{uuid.uuid4().hex[:8]}"
        
        item = WorldItem(
            id=item_id,
            template_id=template_id,
            quantity=quantity,
            room_id=ctx.room_id,
        )
        
        ctx.world.items[item_id] = item
        room.items.add(item_id)
        
        return []
    
    def _action_despawn_item(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Remove an item from the room.
        
        Params:
            template_id: The item template ID to remove
            all: If True, remove all matching items (default: False)
        """
        room = ctx.get_room()
        if not room:
            return []
        
        template_id = params.get("template_id")
        remove_all = params.get("all", False)
        
        if not template_id:
            print("[TriggerSystem] despawn_item requires template_id")
            return []
        
        to_remove: List[str] = []
        
        for item_id in list(room.items):
            item = ctx.world.items.get(item_id)
            if item and item.template_id == template_id:
                to_remove.append(item_id)
                if not remove_all:
                    break
        
        for item_id in to_remove:
            room.items.discard(item_id)
            del ctx.world.items[item_id]
        
        return []
    
    def _action_give_item(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Give an item to the triggering player.
        
        Params:
            template_id: The item template ID to give
            quantity: Number to give (default: 1)
        """
        player = ctx.get_player()
        if not player:
            return []
        
        template_id = params.get("template_id")
        quantity = params.get("quantity", 1)
        
        if not template_id:
            print("[TriggerSystem] give_item requires template_id")
            return []
        
        template = ctx.world.item_templates.get(template_id)
        if not template:
            print(f"[TriggerSystem] Item template not found: {template_id}")
            return []
        
        # Get or create player inventory
        inventory = ctx.world.player_inventories.get(ctx.player_id)
        if not inventory:
            from ..world import PlayerInventory
            inventory = PlayerInventory(player_id=ctx.player_id)
            ctx.world.player_inventories[ctx.player_id] = inventory
        
        # Create item
        from ..world import WorldItem
        
        item_id = f"item_{template_id}_{uuid.uuid4().hex[:8]}"
        item = WorldItem(
            id=item_id,
            template_id=template_id,
            quantity=quantity,
            owner_id=ctx.player_id,
        )
        
        ctx.world.items[item_id] = item
        inventory.items.add(item_id)
        
        return []
    
    def _action_take_item(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Take an item from the triggering player's inventory.
        
        Params:
            template_id: The item template ID to take
            quantity: Number to take (default: 1, or all if quantity exceeds owned)
        """
        player = ctx.get_player()
        if not player:
            return []
        
        template_id = params.get("template_id")
        quantity = params.get("quantity", 1)
        
        if not template_id:
            print("[TriggerSystem] take_item requires template_id")
            return []
        
        inventory = ctx.world.player_inventories.get(ctx.player_id)
        if not inventory:
            return []
        
        # Find items to remove
        remaining = quantity
        to_remove: List[str] = []
        
        for item_id in list(inventory.items):
            if remaining <= 0:
                break
            
            item = ctx.world.items.get(item_id)
            if item and item.template_id == template_id:
                if item.quantity <= remaining:
                    remaining -= item.quantity
                    to_remove.append(item_id)
                else:
                    item.quantity -= remaining
                    remaining = 0
        
        for item_id in to_remove:
            inventory.items.discard(item_id)
            del ctx.world.items[item_id]
        
        return []
    
    def _action_enable_trigger(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Enable another trigger in this room.
        
        Params:
            trigger_id: The ID of the trigger to enable
        """
        room = ctx.get_room()
        if not room:
            return []
        
        trigger_id = params.get("trigger_id")
        if not trigger_id:
            print("[TriggerSystem] enable_trigger requires trigger_id")
            return []
        
        state = self._get_or_create_state(room, trigger_id)
        state.enabled = True
        
        # Also check if we need to restart a timer
        for trigger in room.triggers:
            if trigger.id == trigger_id and trigger.event == "on_timer":
                self.start_room_timers(room)  # This will restart the timer if needed
                break
        
        return []
    
    def _action_disable_trigger(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Disable another trigger in this room.
        
        Params:
            trigger_id: The ID of the trigger to disable
        """
        room = ctx.get_room()
        if not room:
            return []
        
        trigger_id = params.get("trigger_id")
        if not trigger_id:
            print("[TriggerSystem] disable_trigger requires trigger_id")
            return []
        
        state = self._get_or_create_state(room, trigger_id)
        state.enabled = False
        
        # Cancel timer if it's a timer trigger
        if state.timer_event_id:
            self.ctx.time_manager.cancel(state.timer_event_id)
            state.timer_event_id = None
        
        return []
    
    def _action_fire_trigger(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Manually fire another trigger in this room.
        
        Params:
            trigger_id: The ID of the trigger to fire
        
        Note: This bypasses event type matching but still checks conditions,
        cooldown, and max_fires.
        """
        room = ctx.get_room()
        if not room:
            return []
        
        trigger_id = params.get("trigger_id")
        if not trigger_id:
            print("[TriggerSystem] fire_trigger requires trigger_id")
            return []
        
        # Find the trigger
        target_trigger = None
        for trigger in room.triggers:
            if trigger.id == trigger_id:
                target_trigger = trigger
                break
        
        if not target_trigger:
            print(f"[TriggerSystem] Trigger not found: {trigger_id}")
            return []
        
        # Check if it can fire (skip event type check)
        current_time = time.time()
        state = self._get_state(room, trigger_id)
        
        if not target_trigger.enabled:
            return []
        if state and not state.enabled:
            return []
        if target_trigger.max_fires >= 0 and state and state.fire_count >= target_trigger.max_fires:
            return []
        if target_trigger.cooldown > 0 and state and state.last_fired_at is not None:
            if current_time - state.last_fired_at < target_trigger.cooldown:
                return []
        
        # Check conditions
        if not self.check_conditions(target_trigger.conditions, ctx):
            return []
        
        # Update state
        state = self._get_or_create_state(room, trigger_id)
        state.fire_count += 1
        state.last_fired_at = current_time
        
        # Execute actions
        return self.execute_actions(target_trigger.actions, ctx)

    # ---------- Phase 11: Darkness Events ----------
    
    def _action_stumble_in_darkness(
        self,
        ctx: TriggerContext,
        params: Dict[str, Any],
    ) -> List[Event]:
        """
        Cause the player to stumble in darkness, taking minor damage.
        
        Params:
            damage_min: Minimum damage (default: 1)
            damage_max: Maximum damage (default: 5)
            message: Custom message (optional, supports substitution)
        
        Only triggers if the room has low light (< 26, i.e., PARTIAL or worse).
        """
        import random
        
        player = ctx.get_player()
        room = ctx.get_room()
        if not player or not room:
            return []
        
        # Check light level
        lighting_system = getattr(self.ctx, 'lighting_system', None)
        if lighting_system:
            current_light = lighting_system.calculate_room_light(room)
            # Only stumble in PARTIAL or worse visibility (< 26)
            if current_light >= 26:
                return []
        
        damage_min = params.get("damage_min", 1)
        damage_max = params.get("damage_max", 5)
        damage = random.randint(damage_min, damage_max)
        
        # Apply damage
        player.hp = max(0, player.hp - damage)
        
        # Default message
        default_message = "You stumble in the darkness and hurt yourself!"
        message = params.get("message", default_message)
        message = self.substitute_variables(message, ctx)
        
        events = [
            {
                "type": "message",
                "player_id": ctx.player_id,
                "text": f"{message} (-{damage} HP)",
                "style": "combat",
            }
        ]
        
        # Notify room if player takes serious damage
        if damage >= 3:
            room_message = f"{player.name} stumbles and cries out in pain!"
            for entity_id in room.entities:
                if entity_id != ctx.player_id and entity_id in ctx.world.players:
                    events.append({
                        "type": "message",
                        "player_id": entity_id,
                        "text": room_message,
                        "style": "narrative",
                    })
        
        return events

    # ---------- Phase 6: Trigger State Persistence ----------
    
    async def save_permanent_trigger_states(self, session: Any) -> int:
        """
        Save all permanent trigger states to database.
        
        Only saves triggers with permanent=True that have fired.
        
        Returns number of states saved.
        """
        from sqlalchemy import text
        import time as time_module
        
        saved_count = 0
        
        # Save room trigger states
        for room_id, room in self.ctx.world.rooms.items():
            if not hasattr(room, 'triggers') or not hasattr(room, 'trigger_states'):
                continue
            
            for trigger in room.triggers:
                if not trigger.permanent:
                    continue
                
                state = room.trigger_states.get(trigger.id)
                if not state or state.fire_count == 0:
                    continue
                
                try:
                    await session.execute(text("""
                        INSERT INTO trigger_state (trigger_id, scope, scope_id, fire_count, last_fired_at)
                        VALUES (:trigger_id, :scope, :scope_id, :fire_count, :last_fired_at)
                        ON CONFLICT (trigger_id, scope, scope_id) DO UPDATE SET
                            fire_count = :fire_count,
                            last_fired_at = :last_fired_at
                    """), {
                        "trigger_id": trigger.id,
                        "scope": "room",
                        "scope_id": room_id,
                        "fire_count": state.fire_count,
                        "last_fired_at": state.last_fired_at or time_module.time(),
                    })
                    saved_count += 1
                except Exception as e:
                    print(f"[TriggerSystem] Error saving trigger {trigger.id}: {e}")
        
        # Save area trigger states
        for area_id, area in self.ctx.world.areas.items():
            if not hasattr(area, 'triggers') or not hasattr(area, 'trigger_states'):
                continue
            
            for trigger in area.triggers:
                if not trigger.permanent:
                    continue
                
                state = area.trigger_states.get(trigger.id)
                if not state or state.fire_count == 0:
                    continue
                
                try:
                    await session.execute(text("""
                        INSERT INTO trigger_state (trigger_id, scope, scope_id, fire_count, last_fired_at)
                        VALUES (:trigger_id, :scope, :scope_id, :fire_count, :last_fired_at)
                        ON CONFLICT (trigger_id, scope, scope_id) DO UPDATE SET
                            fire_count = :fire_count,
                            last_fired_at = :last_fired_at
                    """), {
                        "trigger_id": trigger.id,
                        "scope": "area",
                        "scope_id": area_id,
                        "fire_count": state.fire_count,
                        "last_fired_at": state.last_fired_at or time_module.time(),
                    })
                    saved_count += 1
                except Exception as e:
                    print(f"[TriggerSystem] Error saving trigger {trigger.id}: {e}")
        
        return saved_count
    
    async def restore_permanent_trigger_states(self, session: Any) -> int:
        """
        Restore permanent trigger states from database.
        
        Called during world load to restore trigger fire counts
        for permanent triggers.
        
        Returns number of states restored.
        """
        from sqlalchemy import text
        
        restored_count = 0
        
        try:
            result = await session.execute(text("SELECT * FROM trigger_state"))
            rows = result.fetchall()
        except Exception as e:
            print(f"[TriggerSystem] trigger_state table not available: {e}")
            return 0
        
        for row in rows:
            trigger_id = row.trigger_id
            scope = row.scope
            scope_id = row.scope_id
            fire_count = row.fire_count
            last_fired_at = row.last_fired_at
            
            if scope == "room":
                room = self.ctx.world.rooms.get(scope_id)
                if not room or not hasattr(room, 'triggers'):
                    continue
                
                # Find the trigger to verify it's permanent
                trigger_found = False
                for trigger in room.triggers:
                    if trigger.id == trigger_id and trigger.permanent:
                        trigger_found = True
                        break
                
                if not trigger_found:
                    continue
                
                # Restore state
                state = self._get_or_create_state(room, trigger_id)
                state.fire_count = fire_count
                state.last_fired_at = last_fired_at
                restored_count += 1
                
            elif scope == "area":
                area = self.ctx.world.areas.get(scope_id)
                if not area or not hasattr(area, 'triggers'):
                    continue
                
                # Find the trigger to verify it's permanent
                trigger_found = False
                for trigger in area.triggers:
                    if trigger.id == trigger_id and trigger.permanent:
                        trigger_found = True
                        break
                
                if not trigger_found:
                    continue
                
                # Restore state
                state = self._get_or_create_area_state(area, trigger_id)
                state.fire_count = fire_count
                state.last_fired_at = last_fired_at
                restored_count += 1
        
        if restored_count > 0:
            print(f"[TriggerSystem] Restored {restored_count} permanent trigger states")
        
        return restored_count
