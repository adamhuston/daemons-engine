# Phase 5 Design Document: World Structure, Triggers, and Scripting

## Executive Summary

Phase 5 transforms our MUD from a static world into a dynamic, event-driven environment where rooms can react to player actions, time-based events can unfold, and world builders can create interactive content without modifying Python code. This phase leverages our existing systems (TimeEventManager, EffectSystem, GameContext, behavior hooks) to create a unified trigger system that treats rooms as first-class reactive entities.

---

## Current State Analysis

### What We Already Have

**WorldArea** - Basic zone segmentation:
```python
@dataclass
class WorldArea:
    id: AreaId
    name: str
    description: str
    time_scale: float = 1.0
    ambient_messages: list[str] = field(default_factory=list)
    entry_points: list[RoomId] = field(default_factory=list)
    default_respawn_time: int = 300
```

**NPC Behavior System** - A proven pattern for reactive entities:
```python
@dataclass
class BehaviorResult:
    messages: list[str] = field(default_factory=list)
    move_to: RoomId | None = None
    attack_target: EntityId | None = None
    call_for_help: bool = False
    flee: bool = False

class BehaviorHook(Protocol):
    def on_player_enter(self, npc, player, room, world) -> BehaviorResult | None: ...
    def on_damaged(self, npc, attacker, damage, world) -> BehaviorResult | None: ...
    def on_idle(self, npc, room, world) -> BehaviorResult | None: ...
```

**TimeEventManager** - Scheduling infrastructure:
- Priority queue for timed events
- Recurring event support
- Cancellation by event ID

**EffectSystem** - Temporary state modifications:
- Duration tracking
- Stat modifiers
- Periodic ticks

**GameContext** - Cross-system communication:
- Access to World state
- Event dispatching
- System references

### The Gap

Rooms are currently passive containers. They have:
- A description
- Exits to other rooms
- A set of entities
- A set of items

But they cannot:
- React when players enter or leave
- Respond to specific commands ("pull lever")
- Change over time (doors that close, traps that reset)
- Spawn entities dynamically
- Alter their own exits or descriptions

---

## Design Philosophy

### Principle 1: Rooms as Reactive Entities

Just as NPCs have behaviors that respond to hooks, rooms should have **triggers** that respond to events. The parallel is intentional:

| NPC Behaviors | Room Triggers |
|---------------|---------------|
| `on_player_enter` | `on_enter` |
| `on_player_leave` | `on_exit` |
| `on_damaged` | `on_command` |
| `on_idle` | `on_timer` |
| `BehaviorResult` | `TriggerResult` |

### Principle 2: Data-Driven Over Code-Driven

World builders should be able to create interactive content through YAML configuration, not Python code. This means:

- Triggers are defined in room YAML files
- Actions are a finite set of well-defined operations
- Complex sequences are chains of simple actions
- No embedded scripting language (initially)

### Principle 3: Composability Over Complexity

Rather than building a complex scripting engine, we compose simple primitives:

- **Conditions**: Check world state before acting
- **Actions**: Modify world state atomically
- **Chains**: Sequence multiple actions
- **Delays**: Insert time between actions

### Principle 4: Leverage Existing Systems

Every new capability should flow through existing infrastructure:

| Capability | Existing System |
|------------|-----------------|
| Delayed actions | TimeEventManager |
| Stat modifications | EffectSystem |
| Message broadcasting | EventDispatcher |
| State queries | World / GameContext |

---

## Proposed Architecture

### Core Data Structures

```python
@dataclass
class TriggerCondition:
    """A condition that must be met for a trigger to fire."""
    type: str  # "has_item", "health_below", "time_between", "flag_set", etc.
    params: dict[str, Any] = field(default_factory=dict)
    negate: bool = False  # Invert the condition

@dataclass
class TriggerAction:
    """An atomic action to perform when a trigger fires."""
    type: str  # "message", "spawn_npc", "open_exit", "apply_effect", etc.
    params: dict[str, Any] = field(default_factory=dict)
    delay: float = 0.0  # Seconds to wait before executing

@dataclass
class RoomTrigger:
    """A trigger attached to a room."""
    id: str
    event: str  # "on_enter", "on_exit", "on_command", "on_timer"
    conditions: list[TriggerCondition] = field(default_factory=list)
    actions: list[TriggerAction] = field(default_factory=list)
    cooldown: float = 0.0  # Minimum seconds between firings
    max_fires: int = -1  # -1 = unlimited
    enabled: bool = True
    
    # Event-specific fields
    command_pattern: str | None = None  # For on_command: "pull *", "press button"
    timer_interval: float | None = None  # For on_timer: seconds between fires
    timer_initial_delay: float = 0.0  # For on_timer: delay before first fire

@dataclass
class TriggerState:
    """Runtime state for a trigger instance."""
    fire_count: int = 0
    last_fired_at: float | None = None
    timer_event_id: str | None = None
    enabled: bool = True
```

### WorldRoom Extensions

```python
@dataclass
class WorldRoom:
    # ... existing fields ...
    
    # New trigger support
    triggers: list[RoomTrigger] = field(default_factory=list)
    trigger_states: dict[str, TriggerState] = field(default_factory=dict)
    
    # Dynamic state (can be modified by triggers)
    dynamic_exits: dict[Direction, RoomId] = field(default_factory=dict)  # Overrides
    dynamic_description: str | None = None  # Override base description
    room_flags: dict[str, Any] = field(default_factory=dict)  # Arbitrary state
```

### WorldArea Extensions

```python
@dataclass
class WorldArea:
    # ... existing fields ...
    
    # New metadata
    recommended_level: tuple[int, int] = (1, 10)  # Min, max level
    theme: str = "default"  # For ambient generation, music, etc.
    spawn_tables: dict[str, list[SpawnEntry]] = field(default_factory=dict)
    area_flags: dict[str, Any] = field(default_factory=dict)
```

### TriggerSystem Class

Following our established pattern, we create a new system:

```python
class TriggerSystem:
    """Manages room triggers and their execution."""
    
    def __init__(self, ctx: GameContext):
        self.ctx = ctx
        self.condition_handlers: dict[str, ConditionHandler] = {}
        self.action_handlers: dict[str, ActionHandler] = {}
        self._register_builtin_conditions()
        self._register_builtin_actions()
    
    def fire_trigger(
        self, 
        room_id: RoomId, 
        event: str, 
        context: TriggerContext
    ) -> list[Event]:
        """Check and fire triggers for a room event."""
        ...
    
    def check_conditions(
        self, 
        conditions: list[TriggerCondition], 
        context: TriggerContext
    ) -> bool:
        """Evaluate all conditions (AND logic by default)."""
        ...
    
    def execute_actions(
        self, 
        actions: list[TriggerAction], 
        context: TriggerContext
    ) -> list[Event]:
        """Execute a list of actions, respecting delays."""
        ...
```

---

## Condition Types

### Player State Conditions

| Type | Params | Description |
|------|--------|-------------|
| `has_item` | `template_id`, `quantity` | Player has item in inventory |
| `has_equipped` | `template_id` or `slot` | Player has item equipped |
| `health_percent` | `operator`, `value` | Compare health percentage |
| `level` | `operator`, `value` | Compare player level |
| `has_effect` | `effect_name` | Player has active effect |
| `in_combat` | - | Player is in combat |

### Room State Conditions

| Type | Params | Description |
|------|--------|-------------|
| `flag_set` | `flag_name`, `value` | Room flag equals value |
| `exit_open` | `direction` | Exit is currently open |
| `entity_present` | `template_id` or `name` | NPC is in room |
| `item_present` | `template_id` | Item is in room |
| `player_count` | `operator`, `value` | Number of players in room |

### Time Conditions

| Type | Params | Description |
|------|--------|-------------|
| `time_of_day` | `start`, `end` | Game time is within range |
| `time_since_fire` | `seconds` | Time since trigger last fired |

### Logical Conditions

| Type | Params | Description |
|------|--------|-------------|
| `any` | `conditions: list` | OR logic - any condition passes |
| `all` | `conditions: list` | AND logic - all conditions pass |
| `not` | `condition` | Negate a condition |

---

## Action Types

### Message Actions

| Type | Params | Description |
|------|--------|-------------|
| `message_player` | `text` | Send message to triggering player |
| `message_room` | `text`, `exclude_player` | Broadcast to room |
| `message_area` | `text` | Broadcast to all in area |

### Entity Actions

| Type | Params | Description |
|------|--------|-------------|
| `spawn_npc` | `template_id`, `count` | Spawn NPC(s) in room |
| `despawn_npc` | `template_id` or `name` | Remove NPC from room |
| `move_npc` | `name`, `direction` | Move NPC to adjacent room |
| `npc_say` | `name`, `text` | Make NPC speak |

### Room Actions

| Type | Params | Description |
|------|--------|-------------|
| `set_flag` | `name`, `value` | Set room flag |
| `toggle_flag` | `name` | Toggle boolean flag |
| `open_exit` | `direction`, `target_room` | Add/enable an exit |
| `close_exit` | `direction` | Remove/disable an exit |
| `set_description` | `text` | Change room description |
| `reset_description` | - | Restore original description |

### Player Actions

| Type | Params | Description |
|------|--------|-------------|
| `teleport` | `room_id` | Move player to room |
| `apply_effect` | `effect_name`, `duration`, `modifiers` | Apply buff/debuff |
| `remove_effect` | `effect_name` | Remove effect |
| `damage` | `amount`, `type` | Deal damage to player |
| `heal` | `amount` | Heal player |
| `give_item` | `template_id`, `quantity` | Add item to inventory |
| `take_item` | `template_id`, `quantity` | Remove item from inventory |
| `give_xp` | `amount` | Award experience |

### Item Actions

| Type | Params | Description |
|------|--------|-------------|
| `spawn_item` | `template_id`, `quantity` | Create item in room |
| `despawn_item` | `template_id` | Remove item from room |

### Control Flow Actions

| Type | Params | Description |
|------|--------|-------------|
| `enable_trigger` | `trigger_id` | Enable another trigger |
| `disable_trigger` | `trigger_id` | Disable another trigger |
| `fire_trigger` | `trigger_id` | Manually fire another trigger |
| `cancel` | - | Stop processing remaining actions |

---

## YAML Configuration Examples

### Simple Door Lever

```yaml
# rooms/dungeon_entrance.yaml
rooms:
  - id: dungeon_gate
    name: "Iron Gate"
    description: "A massive iron gate blocks the passage north. A rusty lever protrudes from the wall."
    exits:
      south: dungeon_hall
    triggers:
      - id: gate_lever
        event: on_command
        command_pattern: "pull lever"
        conditions:
          - type: flag_set
            params: { flag_name: "gate_open", value: false }
        actions:
          - type: message_player
            params: { text: "You pull the rusty lever. With a grinding screech, the iron gate slowly rises." }
          - type: message_room
            params: { text: "{player.name} pulls the lever. The iron gate grinds open!", exclude_player: true }
          - type: set_flag
            params: { name: "gate_open", value: true }
          - type: open_exit
            params: { direction: "north", target_room: "dungeon_depths" }
          
      - id: gate_already_open
        event: on_command
        command_pattern: "pull lever"
        conditions:
          - type: flag_set
            params: { flag_name: "gate_open", value: true }
        actions:
          - type: message_player
            params: { text: "The lever is already pulled. The gate stands open." }
```

### Trap Room

```yaml
rooms:
  - id: trapped_hallway
    name: "Dusty Corridor"
    description: "Dust covers the floor of this ancient corridor. Strange holes line the walls."
    exits:
      north: treasure_room
      south: entrance_hall
    triggers:
      - id: pressure_plate_trap
        event: on_enter
        cooldown: 60.0  # Can only trigger once per minute
        conditions:
          - type: flag_set
            params: { flag_name: "trap_disarmed", value: false }
            negate: false
        actions:
          - type: message_room
            params: { text: "⚠️ *CLICK* The floor shifts beneath {player.name}'s feet!" }
          - type: damage
            params: { amount: 15, type: "piercing" }
            delay: 0.5
          - type: message_player
            params: { text: "💥 Darts shoot from the walls, striking you!" }
            delay: 0.5
          - type: message_room
            params: { text: "Darts whistle through the air, peppering {player.name}!", exclude_player: true }
            delay: 0.5

      - id: disarm_trap
        event: on_command
        command_pattern: "disarm trap"
        conditions:
          - type: has_item
            params: { template_id: "thieves_tools" }
          - type: level
            params: { operator: ">=", value: 3 }
        actions:
          - type: message_player
            params: { text: "Using your thieves' tools, you carefully disable the pressure plate mechanism." }
          - type: set_flag
            params: { name: "trap_disarmed", value: true }
          - type: give_xp
            params: { amount: 50 }
```

### Timed Event - Ambient Horror

```yaml
rooms:
  - id: haunted_library
    name: "Abandoned Library"
    description: "Dusty tomes line rotting shelves. The air is thick with the smell of decay."
    exits:
      east: grand_hall
    triggers:
      - id: ghostly_whispers
        event: on_timer
        timer_interval: 45.0
        timer_initial_delay: 10.0
        actions:
          - type: message_room
            params: 
              text: 
                - "👻 A chill runs down your spine as unintelligible whispers fill the air..."
                - "📚 Books rustle on the shelves, though there is no wind..."
                - "🕯️ The shadows seem to deepen momentarily..."
              # Random selection from list
              random: true

      - id: ghost_spawn
        event: on_timer
        timer_interval: 300.0  # Every 5 minutes
        conditions:
          - type: entity_present
            params: { template_id: "library_ghost" }
            negate: true  # Only if ghost not already present
          - type: player_count
            params: { operator: ">=", value: 1 }
        actions:
          - type: message_room
            params: { text: "❄️ The temperature drops sharply. A translucent figure materializes from the shadows..." }
          - type: spawn_npc
            params: { template_id: "library_ghost" }
            delay: 2.0
```

### Quest Progression

```yaml
rooms:
  - id: wizard_tower_entrance
    name: "Tower Entrance"
    description: "The base of the ancient wizard's tower. Mystical runes glow faintly on the door."
    exits:
      south: forest_clearing
    triggers:
      - id: sealed_door
        event: on_command
        command_pattern: "open door"
        conditions:
          - type: has_item
            params: { template_id: "wizard_key" }
            negate: true
        actions:
          - type: message_player
            params: { text: "The door is sealed with powerful magic. You need some kind of key..." }

      - id: unlock_door
        event: on_command
        command_pattern: "open door"
        conditions:
          - type: has_item
            params: { template_id: "wizard_key" }
        actions:
          - type: message_player
            params: { text: "The wizard's key glows brightly. The runes on the door flare and fade as it swings open." }
          - type: message_room
            params: { text: "Magical light flares from {player.name}'s key. The tower door groans open!", exclude_player: true }
          - type: take_item
            params: { template_id: "wizard_key" }
          - type: open_exit
            params: { direction: "north", target_room: "wizard_tower_foyer" }
          - type: give_xp
            params: { amount: 100 }
          - type: disable_trigger
            params: { trigger_id: "sealed_door" }
          - type: disable_trigger
            params: { trigger_id: "unlock_door" }
```

---

## Integration Points

### Hook into Existing Engine Events

The TriggerSystem will be invoked at key points in the engine:

```python
# In WorldEngine._move_player()
async def _move_player(self, player_id: PlayerId, direction: str) -> List[Event]:
    # ... existing movement logic ...
    
    # Fire exit triggers on old room
    events.extend(await self.trigger_system.fire_event(
        old_room_id, "on_exit", 
        TriggerContext(player_id=player_id, direction=direction)
    ))
    
    # Fire enter triggers on new room
    events.extend(await self.trigger_system.fire_event(
        new_room_id, "on_enter",
        TriggerContext(player_id=player_id, direction=direction)
    ))
    
    return events

# In CommandRouter dispatch, for unrecognized commands
def dispatch(self, player_id: PlayerId, raw: str) -> List[Event]:
    # ... existing command matching ...
    
    if not matched:
        # Check for room command triggers
        player = self.ctx.world.players.get(player_id)
        if player:
            trigger_events = await self.ctx.trigger_system.fire_command(
                player.room_id, raw,
                TriggerContext(player_id=player_id, raw_command=raw)
            )
            if trigger_events:
                return trigger_events
    
    # Fall through to "unknown command"
    return [self._msg_to_player(player_id, "You mutter something unintelligible.")]
```

### TimeEventManager Integration

Timer triggers register with the existing time system:

```python
def _start_room_timers(self, room: WorldRoom):
    """Initialize timer triggers for a room."""
    for trigger in room.triggers:
        if trigger.event == "on_timer" and trigger.enabled:
            state = room.trigger_states.get(trigger.id, TriggerState())
            
            event_id = self.ctx.time_manager.schedule(
                delay=trigger.timer_initial_delay,
                callback=self._make_timer_callback(room.id, trigger.id),
                recurring=True,
                interval=trigger.timer_interval
            )
            
            state.timer_event_id = event_id
            room.trigger_states[trigger.id] = state
```

### EffectSystem Integration

Effect actions delegate to the existing system:

```python
def _action_apply_effect(self, ctx: TriggerContext, params: dict) -> List[Event]:
    """Apply an effect to the triggering player."""
    return self.ctx.effect_system.apply_effect(
        entity_id=ctx.player_id,
        effect_name=params["effect_name"],
        duration=params.get("duration", 30.0),
        modifiers=params.get("modifiers", {}),
        periodic_damage=params.get("periodic_damage"),
        tick_interval=params.get("tick_interval")
    )
```

---

## Implementation Plan

### Phase 5.1: Core Infrastructure (Week 1)

1. **Create `TriggerSystem` class** in `backend/app/engine/systems/triggers.py`
   - TriggerContext dataclass
   - Condition/Action handler registration
   - Basic fire_event() logic

2. **Extend WorldRoom** with trigger fields
   - triggers list
   - trigger_states dict
   - dynamic_exits, dynamic_description, room_flags

3. **Implement basic conditions**
   - flag_set, has_item, level
   - Condition evaluation with AND logic

4. **Implement basic actions**
   - message_player, message_room
   - set_flag, toggle_flag

5. **Hook into movement** for on_enter/on_exit

### Phase 5.2: Commands and Timers (Week 2)

1. **Implement on_command triggers**
   - Pattern matching (exact, prefix, wildcard)
   - Hook into CommandRouter fallback

2. **Implement on_timer triggers**
   - TimeEventManager integration
   - Room timer lifecycle (start on load, cancel on unload)

3. **Add more conditions**
   - health_percent, in_combat, has_effect
   - entity_present, player_count

4. **Add more actions**
   - damage, heal, apply_effect
   - spawn_npc, despawn_npc

### Phase 5.3: Dynamic World (Week 3)

1. **Exit manipulation actions**
   - open_exit, close_exit
   - Dynamic exit resolution

2. **Item actions**
   - spawn_item, despawn_item
   - give_item, take_item

3. **Trigger control actions**
   - enable_trigger, disable_trigger
   - fire_trigger

4. **YAML loader updates**
   - Parse trigger definitions
   - Validate trigger schemas

### Phase 5.4: Area Enhancements (Week 4)

1. **Area metadata extensions**
   - recommended_level
   - theme
   - spawn_tables

2. **Area-level triggers**
   - on_area_enter, on_area_exit
   - Area-wide timer events

3. **Trigger persistence**
   - Save trigger states to database
   - Restore on server restart

4. **Testing and documentation**
   - Unit tests for conditions and actions
   - YAML schema documentation
   - Example trigger library

---

## Future Considerations

### Scriptable Extensions

While Phase 5 focuses on table-driven triggers, the architecture supports future scripting:

```yaml
triggers:
  - id: complex_puzzle
    event: on_command
    command_pattern: "solve puzzle"
    script: |
      # Future: Sandboxed Python or custom DSL
      if player.has_item("red_gem") and player.has_item("blue_gem"):
        room.set_flag("puzzle_solved", true)
        player.message("The gems glow and merge into a purple crystal!")
        player.give_item("purple_crystal")
        player.take_item("red_gem")
        player.take_item("blue_gem")
      else:
        player.message("You're missing something...")
```

### Multiplayer Trigger Coordination

Some triggers may need to track multiple players:

```yaml
triggers:
  - id: cooperative_door
    event: on_command
    command_pattern: "push door"
    conditions:
      - type: player_count
        params: { operator: ">=", value: 2 }
      - type: all_players_action
        params: { command: "push door", within_seconds: 5 }
    actions:
      - type: message_room
        params: { text: "Working together, you force the heavy door open!" }
      - type: open_exit
        params: { direction: "north", target_room: "beyond" }
```

### Visual Trigger Editor

The YAML structure is designed to be machine-readable for future tooling:

- Web-based trigger editor
- Visual node graph for complex sequences
- Real-time trigger testing/simulation

---

## Conclusion

Phase 5 transforms our MUD into a truly dynamic world by treating rooms as reactive entities with their own behaviors. By leveraging our existing systems (TimeEventManager, EffectSystem, EventDispatcher) and following established patterns (GameContext-aware systems, data-driven configuration), we can build a powerful trigger system without introducing architectural complexity.

The table-driven approach prioritizes:
- **Accessibility**: World builders don't need to write Python
- **Safety**: No arbitrary code execution
- **Testability**: Deterministic condition/action evaluation
- **Extensibility**: New conditions and actions are easy to add

This foundation enables rich interactive content: puzzles, traps, quests, dynamic environments, and scripted encounters - all defined in YAML and powered by our battle-tested engine systems.