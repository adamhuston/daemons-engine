# Utility Abilities System

## Overview

The ability framework has been extended to support **non-combat abilities** for exploration, interaction, and environmental manipulation. These utility abilities complement combat abilities and enable rich gameplay mechanics beyond combat encounters.

**Status:** ✅ Implemented and tested in Phase 9j+

## Utility Ability Categories

### 1. **Light/Visibility Abilities**
Create and manipulate light sources for exploration.

| Ability ID | Name | Cost | Cooldown | Range | Level |
|-----------|------|------|----------|-------|-------|
| `light` | Light | - | 0.5s | Self | 1 |
| `daylight` | Daylight | 40 mana | 5.0s | Room (3) | 5 |
| `darkness` | Darkness | 35 mana | 4.0s | Self | 3 |

**Behaviors:**
- `create_light`: Personal light aura (brightness 0-100, customizable duration)
- `darkness`: Obscures vision, opposes light effects

**Use Cases:**
- Navigate dark areas
- Reduce visibility for stealth
- Environmental atmosphere

---

### 2. **Unlock/Container Abilities**
Magically open locked doors and containers without keys.

| Ability ID | Name | Cost | Cooldown | Range | Level |
|-----------|------|------|----------|-------|-------|
| `unlock` | Unlock | 20 mana | 2.0s | 1 room | 3 |
| `open_container` | Open Container | 25 mana | 2.5s | 2 rooms | 4 |

**Behaviors:**
- `unlock_door`: Opens locked doors (difficulty-based)
- `unlock_container`: Opens sealed containers, detects and may trigger traps

**Features:**
- Respects lock difficulty (must be level >= lock_difficulty)
- Trap detection based on caster perception vs. trap difficulty
- Permanent effect (no duration)

**Use Cases:**
- Access restricted areas
- Loot containers without keys
- Create alternate paths

---

### 3. **Detection/Sensing Abilities**
Enhance perception and reveal hidden magical properties.

| Ability ID | Name | Cost | Cooldown | Range | Level |
|-----------|------|------|----------|-------|-------|
| `detect_magic` | Detect Magic | 15 mana | 3.0s | Self | 2 |
| `true_sight` | True Sight | 50 mana | 10.0s | Self | 8 |

**Behaviors:**
- `detect_magic`: Sense magical auras in area (radius configurable)
- `true_sight`: Penetrate illusions and reveal hidden objects/creatures

**Duration:** Configurable per ability (default 60s for detect, 30s for true sight)

**Use Cases:**
- Find magical items and artifacts
- Detect illusions and hidden enemies
- Explore enchanted areas safely

---

### 4. **Environmental Manipulation**
Transform the world and enable new paths.

| Ability ID | Name | Cost | Cooldown | Range | Level |
|-----------|------|------|----------|-------|-------|
| `teleport` | Teleport | 100 mana | 30.0s | Self | 10 |
| `create_passage` | Create Passage | 75 mana | 20.0s | 2 rooms | 7 |

**Behaviors:**
- `teleport`: Move to attuned location (requires `known_locations` list)
- `create_passage`: Open temporary doorway through barriers

**Features:**
- Teleport only works to known/memorized locations
- Passages have time limit (default 120s) before closing
- Cannot teleport to occupied spaces

**Use Cases:**
- Fast travel between areas
- Escape dangerous situations
- Create secret passages to hidden areas

---

## Architecture

### AbilityTemplate Metadata Support

Utility abilities use the new `metadata` field on `AbilityTemplate` to store ability-specific configuration:

```python
# In YAML:
ability_id: light
metadata:
  light_level: 50      # Brightness 0-100
  duration: 300.0      # 5 minutes
  radius: 1            # Effect radius in rooms

# At runtime:
ability = class_system.get_ability('light')
light_level = ability.metadata.get('light_level', 50)
```

### Behavior Result Types

Utility behaviors return `UtilityResult` instead of combat's `BehaviorResult`:

```python
@dataclass
class UtilityResult:
    success: bool                    # Did it work?
    message: str                     # User-facing result message
    state_changes: Dict[str, Any]    # Environmental/object state changes
    affected_targets: List[str]      # IDs of affected objects
    duration: Optional[float]        # Effect duration or None
    error: Optional[str]             # Error message if failed
```

These convert automatically to combat-compatible results for executor consistency.

### Behavior Registration

All 8 utility behaviors are automatically registered during ClassSystem initialization:

```python
# In ClassSystem._register_core_behaviors():
self.register_behavior("create_light", create_light_behavior)
self.register_behavior("darkness", darkness_behavior)
self.register_behavior("unlock_door", unlock_door_behavior)
self.register_behavior("unlock_container", unlock_container_behavior)
self.register_behavior("detect_magic", detect_magic_behavior)
self.register_behavior("true_sight", true_sight_behavior)
self.register_behavior("teleport", teleport_behavior)
self.register_behavior("create_passage", create_passage_behavior)
```

---

## Implementation Details

### File Structure

```
backend/
├── app/engine/systems/ability_behaviors/
│   ├── utility.py              # Utility behavior implementations (8 behaviors)
│   └── __init__.py             # Exports all behaviors
├── app/engine/systems/
│   ├── abilities.py            # Added metadata field to AbilityTemplate
│   └── classes.py              # Updated _register_core_behaviors()
├── world_data/abilities/
│   ├── utility.yaml            # 9 utility ability definitions
│   └── utility_schema.yaml     # Documentation and schema
└── test_utility_abilities.py   # Comprehensive behavior tests (12 tests, all passing)
```

### Ability Category

Utility abilities use `ability_category: "utility"` to distinguish from combat:

```python
# Classification in YAML
ability_category: "utility"        # vs "melee", "magic", "ranged"
ability_type: "active"             # Usually active
gcd_category: "utility"            # Separate GCD from combat
can_use_while_moving: true         # Most utilities allow movement
```

### Target Types

Utility abilities support multiple target scopes:

- `"self"`: Self-targeted (light, darkness, detect_magic)
- `"enemy"`: Directional targeting (unlock, open_container)
- `"room"`: Area effect (daylight, create_passage)

---

## Adding Custom Utility Abilities

To add a new utility ability:

### 1. Create the Behavior Function

```python
# In app/engine/systems/ability_behaviors/utility.py

async def my_utility_behavior(
    caster,
    target,
    ability_template,
    combat_system,
    **context
) -> UtilityResult:
    """
    Your utility ability implementation.
    
    Args:
        caster: WorldPlayer or WorldEntity casting
        target: Target entity (may be caster for self-targeted)
        ability_template: AbilityTemplate with metadata
        combat_system: CombatSystem for any combat interactions
        **context: Additional context (target_object, destination, etc.)
    
    Returns:
        UtilityResult describing outcome
    """
    try:
        # Extract metadata
        duration = ability_template.metadata.get("duration", 60.0)
        
        # Perform ability logic
        # Update state on caster or context
        
        return UtilityResult(
            success=True,
            message=f"{caster.name} used ability!",
            state_changes={"effect_applied": True},
            affected_targets=[caster.id],
            duration=duration
        )
    except Exception as e:
        return UtilityResult(
            success=False,
            message="Ability failed",
            error=str(e)
        )
```

### 2. Register the Behavior

```python
# In app/engine/systems/classes.py ClassSystem._register_core_behaviors()

from app.engine.systems.ability_behaviors.utility import my_utility_behavior

self.register_behavior("my_utility", my_utility_behavior)
```

### 3. Create YAML Definition

```yaml
# In world_data/abilities/utility.yaml

- ability_id: my_ability
  name: "My Ability"
  description: "Description of what it does"
  ability_type: "active"
  ability_category: "utility"
  costs: { mana: 30 }
  cooldown: 5.0
  gcd_category: "utility"
  behavior_id: "my_utility"
  target_type: "self"
  can_use_while_moving: true
  required_level: 3
  metadata:
    duration: 60.0
    param1: "value1"
```

### 4. Export from Package

```python
# In app/engine/systems/ability_behaviors/__init__.py

from .utility import (
    # ... existing utilities ...
    my_utility_behavior,
)

__all__ = [
    # ... existing ...
    "my_utility_behavior",
]
```

---

## Execution Flow

When a player casts a utility ability:

```
1. AbilityExecutor.execute_ability() called
   ↓
2. Validation pipeline (level, resources, cooldown, GCD)
   ↓
3. Target resolution (self, enemy, room, etc.)
   ↓
4. Resource costs applied
   ↓
5. ClassSystem.get_behavior(behavior_id) retrieves function
   ↓
6. Behavior function executed:
   - Modifies caster state (active_effects)
   - Modifies target/environment state
   - Returns UtilityResult
   ↓
7. Cooldown applied
   ↓
8. WebSocket events emitted:
   - ability_cast
   - ability_cast_complete
   - cooldown_update
   - resource_update (if costs)
```

---

## Testing

### Unit Tests

All utility behaviors tested with 12 test cases:

```bash
python test_utility_abilities.py
```

Results:
- ✅ Light ability (personal aura)
- ✅ Daylight (room-wide light)
- ✅ Darkness
- ✅ Unlock door (success and insufficient level)
- ✅ Unlock container (success and trap trigger)
- ✅ Detect magic
- ✅ True sight
- ✅ Teleport (success and unknown location)
- ✅ Create passage

### Verification Test

```bash
python test_utility_verify.py
```

Checks:
- ✅ Imports work
- ✅ YAML loading works (12 utility abilities)
- ✅ Metadata support present
- ✅ Proper categorization

### Integration Verification

All utilities integrate with existing Phase 9 systems:
- ✅ Server imports successfully
- ✅ ClassSystem registers behaviors
- ✅ AbilityExecutor validation pipeline works
- ✅ WebSocket events emit properly
- ✅ Cooldown/GCD tracking works

---

## Future Enhancements

### Planned Extensions

1. **Summon/Conjuring**: Create temporary allies or objects
   - Summon familiar, create barriers, conjure weapons

2. **Transmutation**: Transform objects/creatures
   - Polymorph improvements, transmute items, shape-shifting

3. **Divination**: Reveal information
   - Scrying, identify, prophecy, locate objects

4. **Restoration**: Heal and buff allies
   - Cure poison, remove curse, full healing utility

5. **Crafting Integration**: Craft potions, items
   - Transmute materials, enchant items, forge weapons

6. **Social Abilities**: Persuasion, deception, interaction
   - Charm, intimidate, seduce, negotiate

### Architectural Considerations

- Consider event-based detection (detect_magic triggers on ability use)
- Environmental persistence (light effects persist in rooms)
- Threat tracking (true_sight removes invisibility advantages)
- Duration management (game loop checks for expired effects)
- Area effects on multiple targets (create_passage in adjacent rooms)

---

## Statistics

| Metric | Value |
|--------|-------|
| Utility Behaviors | 8 |
| Utility Abilities | 9 (+ variants) |
| Test Cases | 12 |
| YAML Definitions | 2 files |
| Metadata Fields | ~15+ across all abilities |
| Integration Points | Existing Phase 9 systems |

---

## Related Documentation

- **Phase 9 Overview**: `PHASE9_implementation.md`
- **Ability System**: `backend/app/engine/systems/abilities.py`
- **Behavior Registry**: `backend/app/engine/systems/classes.py`
- **Schema**: `backend/world_data/abilities/utility_schema.yaml`

---

**Status:** Production-ready with comprehensive testing and documentation.
