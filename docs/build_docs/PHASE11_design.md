I'll research the Phase 11 requirements and create a design document. Let me start by examining the existing phase documentation and the current system architecture.

Read [](file:///c%3A/Users/adam.huston/Documents/Development/1126/PHASE11.md)

Read [](file:///c%3A/Users/adam.huston/Documents/Development/1126/roadmap.md#1-1), lines 1 to 100

Read [](file:///c%3A/Users/adam.huston/Documents/Development/1126/ARCHITECTURE.md#1-1), lines 1 to 100

Searched codebase for "light lighting vision darkness visibility room darkness dark", 20 results

Read [](file:///c%3A/Users/adam.huston/Documents/Development/1126/PHASE10.md#1-1), lines 1 to 150

Read [](file:///c%3A/Users/adam.huston/Documents/Development/1126/roadmap.md#100-100), lines 100 to 200

Read [](file:///c%3A/Users/adam.huston/Documents/Development/1126/roadmap.md#200-200), lines 200 to 400

Searched for regex `light|lighting|dark|darkness|visibility|vision|sight|ambient` (`**/backend/app/models.py`), 4 results

Read [](file:///c%3A/Users/adam.huston/Documents/Development/1126/backend/world_data/areas/ethereal_nexus.yaml#1-1), lines 1 to 50

Searched for regex `class WorldRoom|room_flags|ambient|lighting|dark` (`**/backend/app/engine/world.py`), 6 results

Searched codebase for "room description look command visibility see perceive environment", 26 results

Now let me check what other phases have been completed to understand the progression:

Read [](file:///c%3A/Users/adam.huston/Documents/Development/1126/roadmap.md#400-400), lines 400 to 600

Searched for regex `class Room|class Area` (`**/backend/app/models.py`), 4 results

Let me look at the Area and Room models to understand lighting capabilities:

Read [](file:///c%3A/Users/adam.huston/Documents/Development/1126/backend/app/models.py#101-101), lines 101 to 160

Read [](file:///c%3A/Users/adam.huston/Documents/Development/1126/backend/app/models.py#34-34), lines 34 to 100

Searched for regex `light|dark|visibility` (`**/backend/world_data/rooms/*.yaml`), no results

Now let me examine the existing utility abilities to understand how light/darkness currently work:

Read [](file:///c%3A/Users/adam.huston/Documents/Development/1126/backend/world_data/abilities/utility.yaml#1-1), lines 1 to 200

Read [](file:///c%3A/Users/adam.huston/Documents/Development/1126/backend/app/engine/systems/ability_behaviors/utility.py#50-50), lines 50 to 300

Perfect! Now I have enough context. Let me create the Phase 11 design document based on my research.

# Phase 11 Design Document: Light and Vision System

## Executive Summary

Phase 11 implements a **comprehensive lighting and visibility system** that transforms room exploration from a static text experience into a dynamic environmental challenge. The system integrates seamlessly with existing utility abilities (light/darkness spells from Phase 9), area properties (ambient_lighting from Phase 2), and the trigger system (Phase 5) to create atmospheric, puzzle-driven gameplay.

---

## Current State Analysis

### What Exists
- **Area ambient_lighting** field in database (Phase 2) - currently cosmetic only
- **Utility abilities** for light/darkness (Phase 9j+):
  - `light` - Personal light aura (300s duration)
  - `daylight` - Room-wide illumination (600s duration)
  - `darkness` - Shadow effects (180s duration)
  - These currently only track effects in `player.active_effects` but don't affect visibility
- **Room descriptions** are always fully visible regardless of lighting conditions
- **Item/NPC detection** works regardless of darkness

### The Gap
Players can currently see everything in every room with perfect clarity. There's no mechanical difference between:
- A sunlit forest clearing
- A pitch-black dungeon corridor
- An underground cavern
- A room shrouded in magical darkness

This eliminates potential for:
- Atmospheric tension in dangerous areas
- Light-based puzzle mechanics
- Tactical use of darkness for stealth/ambushes
- Environmental storytelling through visibility limitations
- Resource management (light sources, mana for spells)

---

## Design Philosophy

### Core Principles

1. **Mechanical Integration, Not Cosmetic**: Light affects actual gameplay - what you can see, detect, and interact with
2. **Multiple Light Sources**: Natural (ambient), magical (spells), and item-based (torches, lanterns) all stack
3. **Gradual Degradation**: Not binary visible/invisible - partial visibility at low light levels
4. **Spell Empowerment**: Existing utility abilities become essential tools, not optional flavor
5. **Backward Compatibility**: Areas without light configuration default to "always visible"

### Inspiration from MUD Design Patterns

Classic MUDs like DikuMUD and CircleMUD used binary light systems (dark/lit). Modern MUDs evolved to use **light level gradients** (0-100) where:
- 0-20: Complete darkness (no description, entities hidden)
- 21-40: Dim (abbreviated description, partial entity list)
- 41-60: Moderate (full description, all entities visible)
- 61-100: Bright (bonus perception checks, reveals hidden objects)

We adopt this gradient approach with thresholds tailored to our existing systems.

---

## Technical Architecture

### 1. Light Level Calculation

Each room's effective light level is computed from multiple sources:

```python
def calculate_room_light_level(room: WorldRoom, area: WorldArea, players: list[WorldPlayer]) -> int:
    """
    Calculate effective light level (0-100) for a room.

    Sources (additive):
    - Area ambient_lighting (base): 0-60
    - Time-of-day modifier: -20 to +20
    - Player light spells: +0 to +50 per spell
    - Item light sources: +10 to +30 per torch/lantern
    - Darkness effects: -50 to -100

    Returns: Clamped to 0-100 range
    """
```

**Base Light from Area** (`ambient_lighting` field):
| Value | Light Level | Description |
|-------|-------------|-------------|
| `pitch_black` | 0 | Absolute darkness (deep caves, void) |
| `very_dark` | 15 | Starlight equivalent |
| `dark` | 30 | Moonlit night |
| `dim` | 45 | Twilight/shadowy |
| `normal` | 60 | Overcast day (default) |
| `bright` | 75 | Clear sunny day |
| `brilliant` | 90 | Desert sun, snow glare |
| `prismatic` | 60* | Ethereal glow (*can't be darkened by time) |

**Time-of-Day Modifiers** (from existing WorldArea.time system):
- **Night** (21:00-05:00): -20 light
- **Dawn/Dusk** (05:00-07:00, 18:00-21:00): -10 light
- **Day** (07:00-18:00): +0 light
- **Special biomes** (ethereal, underground): ignore time modifiers

**Active Effect Modifiers**:
- `light_aura` (personal spell): +40 light in current room only
- `daylight` (room spell): +50 light, persists for duration, affects all in room
- `darkness_veil`: -60 light
- Torches (equipped item): +25 light
- Lanterns (equipped item): +35 light

### 2. Visibility Thresholds

Different content requires different light levels to perceive:

| Light Level | Room Description | Exits | Players/NPCs | Items | Special |
|-------------|------------------|-------|--------------|-------|---------|
| 0-10 | "It is pitch black." | Hidden | Hidden | Hidden | Can't use `look <target>` |
| 11-25 | Abbreviated (1 line) | Visible | Names only | Hidden | No detail inspection |
| 26-50 | Full description | Visible | Full info | Visible (no details) | Limited inspection |
| 51-75 | Full description | Visible | Full info | Full details | Normal gameplay |
| 76-100 | Enhanced description* | Visible | Full info + hidden** | Full details | Reveals secrets |

\* Enhanced: Trigger action `reveal_hidden_description` if light_level >= 80
\*\* Hidden NPCs/items with `hidden: true` flag become visible

### 3. Database Schema Extensions

**No new tables needed!** Leverage existing infrastructure:

```python
# Area model - already has ambient_lighting field (Phase 2)
class Area(Base):
    ambient_lighting: Mapped[str]  # ✅ Already exists

# Room model - add optional per-room lighting override
class Room(Base):
    lighting_override: Mapped[str | None]  # NEW: Override area default
    # Example: deep_cave room in forest area = "pitch_black"

# WorldRoom dataclass - add runtime light tracking
@dataclass
class WorldRoom:
    current_light_level: int = 60  # Cached, recalculated on change
    active_light_sources: Dict[str, LightSource] = field(default_factory=dict)
    # key = player_id or "global_daylight", value = LightSource(level, expires_at)
```

**Item additions** (for torches/lanterns):
```python
class ItemTemplate(Base):
    provides_light: Mapped[bool] = False  # NEW
    light_intensity: Mapped[int] = 0  # NEW: 0-50
    light_duration: Mapped[int | None] = None  # NEW: seconds (torches burn out)
```

### 4. WorldEngine Integration

**New System: `LightingSystem`**

```python
class LightingSystem:
    def __init__(self, world: World, time_manager: TimeEventManager):
        self.world = world
        self.time_manager = time_manager

    def calculate_room_light(self, room: WorldRoom) -> int:
        """Calculate current effective light level."""

    def update_light_source(self, room_id: str, source_id: str, level: int, duration: float):
        """Add/update a light source (spell, torch)."""

    def remove_light_source(self, room_id: str, source_id: str):
        """Remove expired light source."""

    def get_visible_description(self, room: WorldRoom, light_level: int) -> str:
        """Return appropriate description based on light."""

    def filter_visible_entities(self, entities: List[Entity], light_level: int) -> List[Entity]:
        """Filter entities by visibility threshold."""
```

**Integration Points**:

1. **`_look()` command** - Check light level before showing description
2. **`_move_player()` - Recalculate light when entering/leaving rooms
3. **Utility abilities** - Call `update_light_source()` when casting light/darkness
4. **Item equip/unequip** - Update light sources when torch is equipped
5. **Time system** - Recalculate all room light levels at dawn/dusk/night transitions

---

## Implementation Plan

### Phase 11.1: Core Light Calculation (Week 1, 2-3 days)

**Goal**: Calculate and track light levels without affecting gameplay yet.

- [ ] Add `LightingSystem` class to `backend/app/engine/systems/lighting.py`
- [ ] Add `current_light_level` and `active_light_sources` to `WorldRoom`
- [ ] Implement `calculate_room_light()` with all modifiers
- [ ] Add migration for `Room.lighting_override` column
- [ ] Hook light recalculation to time system (dawn/dusk events)
- [ ] Add admin command `lightlevel` to debug current room light

**Testing**: Rooms correctly calculate light from area + time + spells

### Phase 11.2: Visibility Filtering (Week 1, 2 days)

**Goal**: Restrict what players can see based on light levels.

- [ ] Implement visibility thresholds in `LightingSystem.filter_visible_entities()`
- [ ] Modify `_look()` to show light-appropriate description
- [ ] Add darkness messages: "It is pitch black. You can't see anything."
- [ ] Filter entity lists by light level
- [ ] Hide item details in low light
- [ ] Block `look <target>` in complete darkness

**Testing**: Players in dark rooms see limited/no information

### Phase 11.3: Light Source Integration (Week 2, 2 days)

**Goal**: Make light spells and items functional.

- [ ] Modify `create_light_behavior` to call `LightingSystem.update_light_source()`
- [ ] Modify `darkness_behavior` to reduce room light
- [ ] Add duration tracking with TimeEventManager for spell expiration
- [ ] Add `provides_light` to torch/lantern item templates
- [ ] Hook equip/unequip to add/remove light sources
- [ ] Add torch burn-out mechanic (optional)

**Testing**: Casting light reveals dark rooms, equipping torch provides illumination

### Phase 11.4: Environmental Content (Week 2, 2 days)

**Goal**: Create compelling light-based content.

- [ ] Update existing areas with meaningful `ambient_lighting` values
- [ ] Create dark dungeon area (`pitch_black` base)
- [ ] Add hidden items revealed only at high light (80+)
- [ ] Create trigger-based puzzles (light reveals secret passage)
- [ ] Add NPC that only appears in darkness (shadow creature)
- [ ] Create quest requiring light management (escort through dark caves)

**Testing**: Light-based puzzles and encounters function correctly

### Phase 11.5: Polish & Events (Week 2, 1 day)

**Goal**: Smooth player experience and feedback.

- [ ] Add ambient flavor text when light level changes dramatically
- [ ] Event type `light_level_changed` for client UI updates
- [ ] Add sound cues in Area ambient_sound for dark areas
- [ ] Add help documentation for light mechanics
- [ ] Performance optimization (cache light calculations)

**Testing**: System feels responsive and atmospheric

---

## Event Protocol Extensions

### New Event Types

```json
{
  "event_type": "light_level_changed",
  "room_id": "room_dark_cave",
  "old_level": 15,
  "new_level": 55,
  "reason": "daylight_spell_cast",
  "message": "Magical light floods the cavern!"
}
```

### Modified Events

**`room_description` event** now includes:
```json
{
  "event_type": "room_description",
  "room_id": "room_dungeon_1",
  "light_level": 25,  // NEW
  "visibility": "dim",  // NEW: "none"/"dim"/"normal"/"bright"
  "description": "You can barely make out...",  // Modified by light
  "entities": [...],  // Filtered by visibility
  "items": [...]  // Filtered by visibility
}
```

---

## Content Examples

### Example 1: Dark Dungeon Puzzle

```yaml
# world_data/areas/forgotten_crypt.yaml
ambient_lighting: "pitch_black"
biome: "underground"

# world_data/rooms/crypt_entrance.yaml
triggers:
  - trigger_id: reveal_secret_passage
    event_type: on_timer
    timer_interval: 1.0
    conditions:
      - type: light_level
        min_level: 80  # Requires daylight spell or 3+ torches
    actions:
      - type: open_exit
        direction: "down"
        target_room: "crypt_treasure_vault"
      - type: message_room
        text: "In the brilliant light, you notice a concealed trapdoor!"
```

### Example 2: Shadow Creature

```yaml
# world_data/npcs/shadow_stalker.yaml
visibility_conditions:
  max_light: 30  # Only visible in darkness
  reveal_message: "A shadow detaches itself from the darkness!"
  hide_message: "The creature dissolves into shadows as the light grows."
```

### Example 3: Torch Item

```yaml
# world_data/items/torch.yaml
id: torch_simple
name: "Wooden Torch"
item_type: "light_source"
equipment_slot: "offhand"
provides_light: true
light_intensity: 25
light_duration: 600  # Burns for 10 minutes
consumable_on_burn_out: true  # Destroyed when spent
```

---

## Performance Considerations

### Optimization Strategies

1. **Cached Light Levels**: Recalculate only on change events (spell cast, time transition, player enter/exit)
2. **Zone-Based Updates**: When time changes, batch-update all rooms in affected areas
3. **Lazy Evaluation**: Only calculate light for rooms with active players
4. **Effect Expiration**: Use TimeEventManager for precise duration tracking without polling

### Expected Load

- **Light calculation**: O(1) per room (sum of 3-5 sources)
- **Visibility filtering**: O(n) where n = entities in room (typically < 10)
- **Time transitions**: 2-4 global recalculations per game-hour
- **Spell casts**: 1 light update per spell (< 5/second peak)

**Verdict**: Negligible performance impact. Light system adds <1ms per room view.

---

## Backward Compatibility

### Migration Strategy

1. **Existing areas** without `ambient_lighting` default to `"normal"` (60)
2. **Existing rooms** default to area's ambient_lighting
3. **Existing spells** retroactively integrated (no YAML changes needed)
4. **Client compatibility**: Events include light_level field, older clients ignore it

### Rollback Safety

All new fields are nullable/default-valued. Disabling `LightingSystem` reverts to Phase 10 behavior (full visibility everywhere).

---

## Future Enhancements (Post-Phase 11)

- **Infrared/Darkvision**: Racial abilities to see in darkness (Drow, Dwarves)
- **Light-Based Stealth**: Hiding in shadows, ambush mechanics
- **Dynamic Weather**: Rain extinguishes torches, fog reduces visibility
- **Light Spectrum**: Different colored lights reveal different secrets
- **Bioluminescent Items**: Glowing mushrooms, enchanted crystals
- **Light Reflection**: Mirrors redirect light, solve beam puzzles

---

## Success Criteria

**Minimum Viable Product (Phase 11 Complete)**:
- [ ] Dark rooms hide descriptions until illuminated
- [ ] Light spell makes dark areas fully visible for duration
- [ ] Equipped torch provides functional illumination
- [ ] Time of day affects outdoor area visibility
- [ ] At least one dark dungeon with light-based puzzle
- [ ] No performance regression on room view commands

**Stretch Goals**:
- [ ] 3+ light-dependent quests
- [ ] NPC with visibility-conditional behavior
- [ ] Client UI indicator for current light level
- [ ] Admin tools for tuning light balance

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Performance impact on `look` | Low | Caching + lazy evaluation |
| Breaking existing areas | Low | Default to "normal" lighting |
| Spell balance issues | Medium | Playtesting + admin override commands |
| Player frustration (too dark) | Medium | Generous light spell availability, clear feedback |
| Edge cases (NPCs with torches) | Low | Phase 11.1 handles only players, defer NPC lights |

---

## Conclusion

Phase 11 transforms lighting from cosmetic flavor text into a **core gameplay mechanic** that:
- **Empowers existing systems**: Utility spells become essential tools
- **Enables new content**: Light-based puzzles, atmospheric dungeons, visibility mechanics
- **Maintains simplicity**: Builds on existing infrastructure (effects, triggers, time)
- **Preserves compatibility**: Defaults ensure existing content works unchanged

The system integrates naturally with Phase 2 (time), Phase 3 (items), Phase 5 (triggers), and Phase 9 (utility abilities), demonstrating the architectural payoff of modular design. Implementation is incremental and low-risk, with each sub-phase delivering testable value.

**Estimated Total Effort**: 8-10 development days across 2 weeks.
