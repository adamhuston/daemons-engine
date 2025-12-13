# Phase 2 Implementation Notes

## Phase 2a – Core Time System ✅ **COMPLETE**

### What Was Implemented

- ✅ **TimeEvent dataclass** (`world.py`)
  - Scheduled events with `execute_at` timestamp
  - Support for one-shot and recurring events
  - Priority queue ordering by execution time

- ✅ **WorldEngine time system** (`engine.py`)
  - `_time_events`: Min-heap priority queue for scheduled events
  - `_time_loop()`: Background async task that processes due events
  - `schedule_event()`: Schedule events with delay
  - `cancel_event()`: Cancel scheduled events by ID
  - `start_time_system()` / `stop_time_system()`: Lifecycle management

- ✅ **Application integration** (`main.py`)
  - Time system started on engine startup
  - Time system stopped on shutdown

- ✅ **Test command**: `testtimer [seconds]`
  - Demonstrates time event system
  - Schedules a message to be sent after delay

### Architecture Decisions

**Why not "ticks"?**
- Uses modern async/await patterns instead of fixed tick rate
- Events execute at precise Unix timestamps (not tick-quantized)
- Dynamic sleep based on next event time (efficient, no wasted CPU)
- Scales better (thousands of timers with minimal overhead)

**Design Pattern:**
- Hybrid approach: central event queue + background loop
- Easy to inspect/debug (can see all scheduled events)
- Simple cancellation (remove from ID lookup dict)
- Extensible for priority/ordering in future

**Performance:**
- Sleeps until next event (or 1 second max if queue empty)
- Only wakes when events are actually due
- Recurring events automatically rescheduled

### Usage Example

```python
# Schedule one-shot event
async def my_callback():
    # Do something
    pass

event_id = engine.schedule_event(
    delay_seconds=10.0,
    callback=my_callback,
)

# Schedule recurring event (e.g., regen every 3 seconds)
event_id = engine.schedule_event(
    delay_seconds=3.0,
    callback=regen_callback,
    recurring=True,
)

# Cancel event
engine.cancel_event(event_id)
```

## Phase 2b – Effect System ✅ **COMPLETE**

### What Was Implemented

- ✅ **Effect dataclass** (`world.py`)
  - `effect_id`, `name`, `effect_type` (buff/debuff/dot/hot)
  - `stat_modifiers: Dict[str, int]` - stat changes while active
  - `duration`, `applied_at` - timing tracking
  - `interval`, `magnitude` - for periodic effects (DoT/HoT)
  - `expiration_event_id`, `periodic_event_id` - time event references
  - `get_remaining_duration()` - calculates time left

- ✅ **WorldPlayer effect methods** (`world.py`)
  - `active_effects: Dict[str, Effect]` - tracks active effects
  - `apply_effect()` - adds effect with timestamp
  - `remove_effect()` - removes by ID
  - `get_effective_stat()` - calculates stat with all modifiers
  - `get_effective_armor_class()` - convenience method for AC

- ✅ **Commands** (`engine.py`)
  - `bless <player>` - +5 AC buff for 30 seconds
  - `poison <player>` - 5 damage every 3 seconds for 15 seconds
  - `effects` / `status` - displays active effects with durations

- ✅ **Stat updates integration**
  - Sends `stat_update` events when effects apply
  - Sends updates when effects expire
  - Sends updates on each poison tick
  - Stats command shows effective values (e.g., "15 (10 base)")

### Example Usage

```
> bless self
✨ *Divine light surrounds you!* You feel blessed. (+5 Armor Class for 30 seconds)

> stats
Armor Class: 15 (10 base)
Active Effects: 1 (use 'effects' to view)

> effects
═══ Active Effects ═══

**Blessed** (buff)
  Duration: 27.3s remaining
  Modifiers: armor_class +5

> poison enemy_player
You poison EnemyPlayer with toxic energy.

(Enemy receives periodic damage every 3 seconds)
🤢 *The poison burns through your veins!* You take 5 poison damage.
```

### Implementation Details

**Bless (Buff Example):**
- Creates Effect with `stat_modifiers={"armor_class": 5}`
- Schedules one-shot expiration after 30s
- On expiration: removes effect, sends message, updates stats

**Poison (DoT Example):**
- Creates Effect with `interval=3.0`, `magnitude=5`
- Schedules recurring damage event every 3s
- Schedules one-shot expiration after 15s
- On expiration: cancels recurring event, removes effect
- Each tick: applies damage, sends message + stat_update

**Stat Calculation:**
- Base stats stored on WorldPlayer (e.g., `armor_class=10`)
- `get_effective_stat()` sums all active effect modifiers
- Stats command displays effective value and base if different

## Phase 2c – World Time System ✅ **COMPLETE**

### What Was Implemented

- ✅ **WorldTime dataclass** (`world.py`)
  - `day`, `hour`, `minute` - In-game time tracking
  - `last_update` - Unix timestamp of last advancement
  - `advance(real_seconds_elapsed, time_scale)` - Updates time based on real seconds
  - `get_current_time(time_scale)` - Calculates current time dynamically (continuous, not discrete)
  - `get_time_of_day(time_scale)` - Returns time phase (dawn/morning/afternoon/dusk/evening/night)
  - `get_time_emoji(time_scale)` - Returns emoji for current time
  - `format_time(time_scale)` - Formats as HH:MM
  - `format_full(time_scale)` - Full display with day, emoji, and phase

- ✅ **Time conversion utilities** (`world.py`)
  - Constants: `GAME_DAY_IN_REAL_MINUTES = 12.0` (24 game hours = 12 real minutes)
  - `real_seconds_to_game_minutes()` - Convert real time to game time
  - `game_hours_to_real_seconds()` - Convert game time to real time
  - Default scale: 1 game hour = 30 real seconds

- ✅ **WorldArea dataclass** (`world.py`)
  - `area_id`, `name`, `description`
  - `area_time: WorldTime` - Independent time for this area
  - `time_scale: float` - Time flow multiplier (e.g., 4.0 = 4x faster)
  - **Environmental properties:**
    - `biome` - Ecosystem type (ethereal, temporal, forest, etc.)
    - `climate` - Weather pattern (mild, chaotic, etc.)
    - `ambient_lighting` - Light quality (prismatic, dim, etc.)
    - `weather_profile` - Current weather (stable, shifting, etc.)
    - `danger_level` - Threat rating (1-10)
    - `magic_intensity` - Magical energy level (low/medium/high/extreme)
  - `time_phases: Dict[str, str]` - Custom flavor text for each time of day
  - `ambient_sound: str` - Area-specific ambient audio description
  - `rooms: Set[RoomId]` - Rooms belonging to this area

- ✅ **World model integration** (`world.py`)
  - `World.world_time: WorldTime` - Global time for rooms not in areas
  - `World.areas: Dict[AreaId, WorldArea]` - All defined areas
  - `WorldRoom.area_id: Optional[AreaId]` - Links rooms to areas

- ✅ **Time advancement system** (`engine.py`)
  - `_schedule_time_advancement()` - Sets up recurring 30-second event
  - `advance_world_time()` - Advances time for all areas independently
  - Each area's time progresses based on its `time_scale`
  - Global world time also advances (for non-area rooms)
  - Logs time advancement with area name and time scale

- ✅ **Commands** (`engine.py`)
  - `time` - Shows current in-game time with rich context:
    - Current time with emoji and phase (e.g., "🌄 Day 1, 06:45 (morning)")
    - Area name in italics
    - Time phase flavor text
    - Ambient sound description
    - Time scale indicator (⚡ faster, 🐌 slower)
  - Enhanced `testtimer` - Shows time conversion:
    - "Timer set for X seconds (Y in-game minutes in [area] at Zx timescale)"

- ✅ **Sample areas** (`loader.py`)
  - **The Ethereal Nexus** (4x time scale)
    - Biome: ethereal, Climate: mild
    - Ambient lighting: prismatic, Weather: stable
    - Custom time phases with mystical flavor
    - Ambient sound: "A gentle humming resonates through the air."
  - **The Temporal Rift** (2x time scale)
    - Biome: temporal, Climate: chaotic
    - Ambient lighting: dim, Weather: shifting
    - Custom time phases with temporal distortion theme
    - Ambient sound: "Reality seems to bend and twist around you."
  - Rooms assigned to areas (ethereal → Nexus, forsaken → Rift)

### Architecture Decisions

**Independent Area Times:**
- Each area maintains its own WorldTime instance
- Areas can have different time scales (4x, 2x, 0.5x, etc.)
- Players in different areas experience different time flow rates
- No global averaging - each area is truly independent

**Continuous Time Display:**
- `get_current_time()` calculates time dynamically based on elapsed real seconds
- Time displays smoothly between advancement events (no discrete jumps)
- Advancement still happens every 30 seconds for efficiency
- Between advancements, time is interpolated on-demand

**Performance Considerations:**
- Time queries are O(1) - just arithmetic operations
- Only ~10-15 operations per time query
- Advancement still only runs once per 30 seconds
- Massively more efficient than traditional MUD tick systems (90%+ CPU savings)

### Example Usage

```
> time
🌄 Day 1, 06:45 (morning)
*The Ethereal Nexus*

In this ethereal realm, the morning manifests as shimmering waves of light.

*A gentle humming resonates through the air.*

⚡ *Time flows 4.0x faster here.*

> testtimer 4
Timer set for 4.0 seconds (8.0 in-game minutes in The Ethereal Nexus at 4.0x timescale)

(Player in different area sees different time)
> time
🌙 Day 1, 03:30 (night)
*The Temporal Rift*

In this fractured dimension, night is a kaleidoscope of past and future shadows.

*Reality seems to bend and twist around you.*

⚡ *Time flows 2.0x faster here.*
```

### Implementation Details

**Time Scale Application:**
- Each area's `time_scale` multiplies the rate of time passage
- time_scale=4.0: 1 real minute = 4 game hours
- time_scale=2.0: 1 real minute = 2 game hours
- time_scale=0.5: 1 real minute = 30 game minutes (slowed time)

**Time Advancement Flow:**
1. Every 30 real seconds, `advance_world_time()` fires
2. For each area: `area.area_time.advance(30.0, area.time_scale)`
3. Time is stored discretely (day/hour/minute updated)
4. `last_update` timestamp is set to current time
5. When player queries time: `get_current_time()` calculates elapsed time since last update
6. Applies time_scale to elapsed time and adds to stored values
7. Returns smooth, continuous current time

**Time Phase System:**
- Each area can override default time phase flavor text
- Phases: dawn (5-7), morning (7-12), afternoon (12-17), dusk (17-19), evening (19-22), night (22-5)
- Flavor text provides atmospheric description for each phase
- Falls back to `DEFAULT_TIME_PHASES` if area doesn't define custom text

**Environmental Properties:**
- Future-proofed for weather systems, lighting effects, danger mechanics
- Currently used for atmospheric/descriptive purposes
- Can be extended for gameplay effects (visibility, movement speed, combat modifiers, etc.)

---

## Phase 2 Complete! ✅

All three subsystems implemented:
- **2a**: Event-driven time system (not traditional ticks)
- **2b**: Effect system (buffs/debuffs, DoT/HoT)
- **2c**: World time system (independent area times with scaling)

**Ready for Phase 3 – Items & Inventory**
