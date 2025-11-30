Let me research the current architecture and systems to understand what Phase 6 needs to address. Let me also check the current save/load mechanisms: Let me check how player data is currently saved and restored: Now let me check the world state - what else needs persistence beyond players: Let me check what runtime state exists that would be lost on restart: Now let me understand the current database schema to see what's already persisted: Now let me check how NPCs and their state are handled: Let me now synthesize everything I've learned into a comprehensive Phase 6 design:

---

## Phase 6 Analysis: Persistence & Scaling

### Current State Assessment

#### What's Already Persisted ✅

| Data | Storage | When Saved |
|------|---------|------------|
| Player core stats | `players` table | On disconnect via `save_player_stats()` |
| Player inventory | `item_instances` table | On disconnect |
| Player equipment | `item_instances.equipped_slot` | On disconnect |
| Player quest progress | `players.quest_progress` JSON | On disconnect |
| Player completed quests | `players.completed_quests` JSON | On disconnect |
| Player flags | `players.player_flags` JSON | On disconnect |
| Item templates | `item_templates` table | YAML migration |
| NPC templates | `npc_templates` table | YAML migration |
| Room definitions | `rooms` table | YAML migration |

#### What's Lost on Restart ❌

| Data | Current Storage | Risk |
|------|-----------------|------|
| **Room flags** | `WorldRoom.room_flags` dict | Medium - puzzle/trigger state lost |
| **Dynamic exits** | `WorldRoom.dynamic_exits` dict | High - opened doors close |
| **Dynamic descriptions** | `WorldRoom.dynamic_description` | Low - cosmetic |
| **Spawned NPCs** | `WorldNpc` in memory | Medium - respawn timers reset |
| **NPC positions** | `npc.current_room_id` | Medium - wandered NPCs reset |
| **NPC health** | `npc.current_hp` | Low - respawns heal anyway |
| **Ground items** | `WorldItem` instances | High - dropped items lost |
| **Active effects** | `WorldPlayer.active_effects` | Medium - buffs/debuffs lost |
| **Combat state** | `CombatState` | Low - combat resets |
| **Trigger state** | `TriggerState.fire_count` | Medium - one-time triggers re-fire |
| **Area trigger state** | `area.trigger_states` | Medium - area events re-fire |
| **Dialogue state** | `player.in_dialogue` | Low - conversation resets |
| **Scheduled events** | `TimeEventManager._events` | High - timers lost |

#### Architecture Constraints

From ARCHITECTURE.md:
- **Single async engine** with command queue serialization
- **Event-driven** time system (not traditional ticks)
- **In-memory World** with DB as source of truth for static data
- **WebSocket connections** managed per-player with reconnect support

### Design Decisions Needed

1. **Snapshot Strategy**: Full world state vs. delta changes?
2. **Save Frequency**: Periodic interval vs. event-driven vs. hybrid?
3. **What to Persist**: Everything vs. "important" state only?
4. **Recovery Model**: Exact restoration vs. "close enough" approximation?

---

## Proposed Phase 6 Design

Based on our architecture, I recommend an **event-driven persistence model** that matches our existing patterns:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Persistence Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ WorldEngine  │───▶│ StateTracker │───▶│   Database   │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                   │                    │               │
│         │ events            │ dirty flags        │ snapshots     │
│         ▼                   ▼                    ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  Commands    │    │  Periodic    │    │   Startup    │       │
│  │  (mutate)    │    │  Save Loop   │    │   Restore    │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 6.1 - State Tracking Infrastructure

New `StateTracker` system that marks entities as "dirty" when modified:

```python
@dataclass
class StateTracker:
    dirty_rooms: set[str]      # Room IDs with changed flags/exits
    dirty_npcs: set[str]       # NPC instance IDs with changed state
    dirty_items: set[str]      # Item instance IDs with changed location
    dirty_triggers: set[str]   # Trigger IDs with changed fire_count
    dirty_players: set[str]    # Player IDs (already handled, but unify)
```

### Phase 6.2 - Database Schema Extensions

New tables for runtime state:

```sql
-- Room runtime state (flags, dynamic exits)
CREATE TABLE room_state (
    room_id VARCHAR PRIMARY KEY,
    room_flags JSON,
    dynamic_exits JSON,
    dynamic_description TEXT,
    updated_at TIMESTAMP
);

-- NPC instance runtime state
CREATE TABLE npc_state (
    instance_id VARCHAR PRIMARY KEY,
    template_id VARCHAR,
    current_room_id VARCHAR,
    current_hp INTEGER,
    spawn_room_id VARCHAR,
    is_alive BOOLEAN,
    updated_at TIMESTAMP
);

-- Ground items (items not in player inventory)
CREATE TABLE ground_items (
    item_instance_id VARCHAR PRIMARY KEY,
    room_id VARCHAR,
    container_id VARCHAR,  -- NULL if on ground
    updated_at TIMESTAMP
);

-- Trigger fire counts
CREATE TABLE trigger_state (
    trigger_id VARCHAR,
    scope VARCHAR,  -- 'room' or 'area'
    scope_id VARCHAR,  -- room_id or area_id
    fire_count INTEGER,
    last_fired_at TIMESTAMP,
    PRIMARY KEY (trigger_id, scope, scope_id)
);

-- Player active effects (so buffs survive disconnect)
CREATE TABLE player_effects (
    player_id INTEGER,
    effect_id VARCHAR,
    effect_data JSON,  -- Full Effect serialized
    expires_at TIMESTAMP,
    PRIMARY KEY (player_id, effect_id)
);
```

### Phase 6.3 - Periodic Save System

Leverage existing `TimeEventManager` for save scheduling:

```python
class PersistenceSystem:
    """Handles periodic state snapshots."""

    SAVE_INTERVAL_SECONDS = 60  # Configurable

    def schedule_periodic_save(self, time_manager: TimeEventManager):
        """Schedule recurring save events."""
        time_manager.schedule_event(
            TimeEvent(
                event_id="persistence_save",
                fire_at=time.time() + self.SAVE_INTERVAL_SECONDS,
                callback=self._do_periodic_save,
                recurring=True,
                interval=self.SAVE_INTERVAL_SECONDS
            )
        )

    async def _do_periodic_save(self):
        """Save all dirty state to database."""
        # Only save what's changed (dirty tracking)
```

### Phase 6.4 - Startup Restoration

Extend `load_world()` to restore runtime state:

```python
async def restore_world_state(world: World, db: AsyncSession):
    """Restore runtime state from database."""
    # 1. Restore room flags and dynamic exits
    # 2. Restore NPC positions and health
    # 3. Restore ground items to rooms
    # 4. Restore trigger fire counts
    # 5. Restore player effects (on player load)
```

### Phase 6.5 - Graceful Shutdown

Add shutdown handler to save all state before exit:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... startup ...
    yield
    # Shutdown: save everything
    await persistence_system.save_all_dirty_state()
    await persistence_system.save_all_connected_players()
```

### Phase 6.6 - Disconnect Handling

Decide player disconnect behavior:

| Option | Pros | Cons |
|--------|------|------|
| **Immediate vanish** | Simple, no ghost players | Abrupt for others |
| **Linger N seconds** | Allows reconnect | Vulnerable to attack |
| **Safe logout zone** | Thematic | Limits where you can quit |

Recommendation: **Linger 30 seconds** with invulnerability flag, then vanish.

---

## Implementation Order

```
Phase 6.1 - StateTracker infrastructure (dirty flags)
    └── Phase 6.2 - Database migrations for state tables
        └── Phase 6.3 - Periodic save system using TimeEventManager
            └── Phase 6.4 - Startup restoration in loader.py
                └── Phase 6.5 - Graceful shutdown handling
                    └── Phase 6.6 - Disconnect linger behavior
```

---

## Questions Before Implementation

1. **Save frequency**: Is 60 seconds appropriate, or should critical changes (quest completion, item drops) save immediately?

2. **Ground item persistence**: Should dropped items persist forever, or decay after N minutes?

3. **NPC state scope**: Should we persist NPC health/position, or just let them respawn fresh on restart?

4. **Effect persistence**: Should active buffs/debuffs pause while logged out, or continue ticking (and potentially expire)?

5. **Trigger resets**: Should one-time triggers reset on server restart, or stay fired permanently?

---

## Design Decisions

### 1. Save Frequency: Hybrid Approach

**Decision**: 60-second periodic saves + immediate saves for critical events.

| Event Type | Save Timing | Rationale |
|------------|-------------|-----------|
| Player movement | Periodic (60s) | High frequency, low criticality |
| Room flag changes | Periodic (60s) | Recoverable state |
| NPC position changes | Periodic (60s) | Resets on respawn anyway |
| **Quest completion** | **Immediate** | Player progress is sacred |
| **Item drops/pickups** | **Immediate** | Inventory changes are critical |
| **Quest turn-in** | **Immediate** | Rewards must not be lost |
| **Player death** | **Immediate** | XP/inventory consequences |
| **Equipment changes** | **Immediate** | Stat-affecting changes |

**Implementation**: Add `save_critical=True` parameter to relevant methods that triggers immediate DB write.

```python
class StateTracker:
    async def mark_dirty(self, entity_type: str, entity_id: str, critical: bool = False):
        """Mark entity as needing save. If critical, save immediately."""
        self._dirty[entity_type].add(entity_id)
        if critical:
            await self._save_entity(entity_type, entity_id)
```

### 2. Ground Item Decay: 1 Hour TTL

**Decision**: Dropped items persist for 1 hour, then decay and are removed.

| Item Location | Persistence | Decay |
|---------------|-------------|-------|
| Player inventory | Permanent | Never |
| Equipped | Permanent | Never |
| Container (chest, bag) | Permanent | Never |
| Ground (dropped) | 1 hour | Auto-remove |
| Ground (spawned by trigger) | Configurable | Per-trigger setting |

**Implementation**: Add `dropped_at` timestamp to ground items, periodic cleanup job.

```python
@dataclass
class GroundItem:
    item_instance_id: str
    room_id: str
    dropped_at: float  # Unix timestamp
    decay_minutes: int = 60  # Default 1 hour, configurable

class ItemDecaySystem:
    DECAY_CHECK_INTERVAL = 300  # Check every 5 minutes

    async def cleanup_decayed_items(self, world: World):
        """Remove items that have exceeded their decay time."""
        now = time.time()
        for room in world.rooms.values():
            expired = [
                item for item in room.items
                if item.dropped_at and (now - item.dropped_at) > (item.decay_minutes * 60)
            ]
            for item in expired:
                room.items.remove(item)
                # Emit decay event for logging/notification
```

### 3. NPC State Persistence: Selective by Type

**Decision**: Most NPCs reset on restart. Specific NPC types persist.

| NPC Type | Persist Position | Persist HP | Rationale |
|----------|------------------|------------|-----------|
| `monster` | ❌ No | ❌ No | Respawns fresh |
| `vendor` | ❌ No | ❌ No | Static locations |
| `quest_giver` | ❌ No | ❌ No | Static locations |
| `wanderer` | ❌ No | ❌ No | Random movement is fine |
| **`companion`** | ✅ Yes | ✅ Yes | Player investment |
| **`unique_boss`** | ✅ Yes | ✅ Yes | World state matters |
| **`escort_target`** | ✅ Yes | ✅ Yes | Quest continuity |

**Implementation**: Add `persist_state: bool` flag to NPC templates.

```yaml
# world_data/npcs/companions/faithful_hound.yaml
id: faithful_hound
name: Faithful Hound
type: companion
persist_state: true  # Position and HP saved
behavior: follow_owner
```

```python
@dataclass
class NPCTemplate:
    # ...existing fields...
    persist_state: bool = False  # Default: don't persist
```

### 4. Effect Persistence: Continue Ticking Offline

**Decision**: Effects continue to tick and can expire while player is logged out.

| Scenario | Behavior |
|----------|----------|
| Player logs out with 5min buff | Buff continues counting down |
| Player logs in after 3min | Buff has 2min remaining |
| Player logs in after 10min | Buff has expired, removed on load |
| DoT applied, player logs out | DoT expires, no damage while offline |
| HoT applied, player logs out | HoT expires, no healing while offline |

**Implementation**: Store `expires_at` absolute timestamp, not remaining duration.

```python
@dataclass
class PersistedEffect:
    effect_id: str
    effect_type: str  # buff, debuff, dot, hot
    stat_modifiers: dict[str, int]
    expires_at: float  # Unix timestamp when effect ends
    # Note: periodic effects (DoT/HoT) don't tick offline, just expire

async def restore_player_effects(player: WorldPlayer, db_effects: list[PersistedEffect]):
    """Restore effects, filtering out expired ones."""
    now = time.time()
    for eff in db_effects:
        if eff.expires_at > now:
            # Still active, restore it
            remaining_duration = eff.expires_at - now
            player.apply_effect(Effect(
                effect_id=eff.effect_id,
                duration=remaining_duration,
                # ...other fields...
            ))
        # else: expired, don't restore
```

### 5. Trigger Reset Behavior: Default Reset with Permanent Option

**Decision**: Triggers reset by default. Specific triggers can be marked permanent.

| Trigger Type | Reset on Restart | Use Case |
|--------------|------------------|----------|
| Room ambiance | ✅ Yes | "A cold wind blows..." |
| Puzzle hint | ✅ Yes | Can re-discover |
| Trap (one-time) | ✅ Yes | Resets for new players |
| **Story moment** | ❌ No | "The king has fallen" - permanent |
| **Achievement unlock** | ❌ No | Player accomplishment |
| **World event** | ❌ No | Global state change |

**Implementation**: Add `permanent: bool` flag to trigger definitions.

```yaml
# Resets on restart (default)
- id: welcome_message
  event: on_enter
  max_fires: 1
  actions:
    - type: message_player
      text: "Welcome to the Ethereal Nexus!"

# Persists across restarts
- id: ancient_seal_broken
  event: on_command
  command_pattern: "break seal"
  max_fires: 1
  permanent: true  # This trigger state survives restart
  actions:
    - type: message_room
      text: "The ancient seal shatters! Dark energy floods the chamber..."
    - type: set_flag
      flag: ancient_seal_broken
      value: true
```

```python
@dataclass
class TriggerDefinition:
    # ...existing fields...
    permanent: bool = False  # If True, fire_count persists across restarts
```

**Database storage**: Only permanent triggers are saved.

```sql
-- Only stores permanent triggers that have fired
CREATE TABLE trigger_state (
    trigger_id VARCHAR,
    scope VARCHAR,  -- 'room', 'area', or 'global'
    scope_id VARCHAR,
    fire_count INTEGER,
    last_fired_at TIMESTAMP,
    PRIMARY KEY (trigger_id, scope, scope_id)
);
```

---

## Revised Implementation Order

Based on these decisions, the implementation order becomes:

```
Phase 6.1 - StateTracker with critical save support
    │
    ├── Phase 6.2a - Database migrations
    │       - player_effects table
    │       - ground_items table (with dropped_at)
    │       - trigger_state table (permanent only)
    │       - npc_state table (persist_state NPCs only)
    │
    ├── Phase 6.2b - Model updates
    │       - NPCTemplate.persist_state flag
    │       - TriggerDefinition.permanent flag
    │       - GroundItem.dropped_at field
    │
    └── Phase 6.3 - Periodic systems
            │
            ├── Periodic save (60s) via TimeEventManager
            ├── Item decay check (5min) via TimeEventManager
            │
            └── Phase 6.4 - Restoration
                    │
                    ├── Restore room state
                    ├── Restore persistent NPCs
                    ├── Restore ground items (non-expired)
                    ├── Restore permanent triggers
                    ├── Restore player effects (on login)
                    │
                    └── Phase 6.5 - Graceful shutdown
                            │
                            └── Phase 6.6 - Disconnect handling (30s linger)
```

---

## Critical Save Integration Points

Commands/events that trigger immediate saves:

| Location | Event | What to Save |
|----------|-------|--------------|
| `QuestSystem.turn_in_quest()` | Quest turned in | Player quest state |
| `QuestSystem.update_objective()` | Objective completed | Player quest progress |
| `engine.do_get()` | Item picked up | Item location, inventory |
| `engine.do_drop()` | Item dropped | Item location + dropped_at |
| `InventorySystem.equip()` | Equipment changed | Player equipment |
| `InventorySystem.unequip()` | Equipment changed | Player equipment |
| `CombatSystem.handle_death()` | Player/NPC death | Player state, NPC state if persistent |
| `engine.do_give()` | Item transferred | Both player inventories |
| `TriggerSystem.fire_event()` | Permanent trigger fired | Trigger state |
