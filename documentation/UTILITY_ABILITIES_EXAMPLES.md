# Utility Abilities - Usage Examples

## Example 1: Light in Dark Areas

```
Player enters dark dungeon:

> look
You are in a deep cave. It is pitch black. You can't see your hand.

> cast light
You create a sphere of magical light around you!

> look
You are in a deep cave. A soft magical light reveals:
- Ancient carved walls
- Glyphs written in draconic
- A locked iron door to the north

The light has a 5-minute duration and illuminates a 1-room radius.
```

---

## Example 2: Unlocking Doors

```
Player encounters a locked door:

> look door
A sturdy wooden door, firmly locked. (Lock difficulty: 2)

> cast unlock door
You sense the magical lock mechanisms and gently manipulate them...
The door swings open!

Game Effects:
- Caster must be level >= lock difficulty (you are level 5, lock is 2)
- Costs 20 mana
- Permanently unlocks the door
- Door remains open for the rest of the session
```

---

## Example 3: Opening Trapped Containers

```
Player finds a treasure chest:

> open chest
The chest is locked and sealed!

> cast open_container chest
You carefully magically manipulate the mechanism...

Case 1: Success (if player perception >= trap difficulty)
You successfully open the chest without triggering the trap!
You find: 500 gold coins, potion of healing, ancient amulet

Case 2: Trap Triggered (if perception too low)
You trigger a poisoned needle trap!
You take 15 damage and are poisoned!

Game Effects:
- Caster must be level >= lock difficulty
- Perception vs. trap_difficulty determines safety
- Costs 25 mana
- Grants permanent access to container contents
```

---

## Example 4: Detecting Magic

```
Player in magical library:

> cast detect_magic
Your senses attune to magical energies...

Over the next 60 seconds, you sense:
- Magical aura: Enchanted staff (weak aura) - on shelf
- Magical aura: Protection ward (strong aura) - on north wall
- Magical aura: Cursed tome (chaotic aura) - in locked box

Game Effects:
- Reveals magical items in area (3-room radius)
- Reveals active magical effects
- Duration: 60 seconds
- Does not trigger alarms or wards
- Perfect for exploring dangerous areas safely
```

---

## Example 5: True Sight vs Illusions

```
Player in enchanted hall:

> look
You see a beautiful ballroom with glittering chandeliers and marble floors.

> cast true_sight
Your vision penetrates the veil of illusion...

> look
You see:
- Crumbling stone room (reality beneath illusion)
- Illusory chandeliers fade away
- Hidden passage revealed (behind fake wall)
- Invisible creature now visible: Shadow Wraith

Game Effects:
- Pierces invisibility and illusions
- Reveals hidden creatures
- Duration: 30 seconds (high mana cost: 50)
- Very useful for high-level challenges
- Can be detected by some enemies
```

---

## Example 6: Teleportation

```
Player learning teleport spell at level 10:

1. First, attune to locations by visiting them:
> visit forest
You arrive at the ancient forest.
[Automatically added to known_locations]

> visit wizard_tower
You arrive at the tower of magic.
[Automatically added to known_locations]

2. Later, use teleport to return:
> cast teleport forest
You gather magical energy around yourself...
Reality warps and you vanish in a flash!
You appear in the ancient forest!

Game Effects:
- Requires 100 mana (high cost for fast travel)
- 30 second cooldown (can't spam)
- Must have visited location before
- Instantaneous travel
- Cannot teleport to occupied spaces
- Useful for escaping danger or fast travel

Learned Locations (Example):
- starting_town (level 1 default)
- forest (level 5)
- cave_system (level 8)
- wizard_tower (level 10)
- elemental_plane (level 15)
```

---

## Example 7: Creating Passages

```
Player in sealed tomb:

> look north
A solid granite wall blocks the way north. It appears impassable.

> cast create_passage north
You channel magic into the wall...
The stone crumbles and shifts, revealing a hidden passage!

The passage remains open for 2 minutes, then closes permanently.

Game Effects:
- Opens temporary doorways (120 second duration)
- Requires 75 mana (significant cost)
- 20 second cooldown
- Can be used on barriers, walls, magical seals
- Passage disappears after duration
- Useful for exploration and puzzle solving

Strategic Uses:
- Create shortcut paths
- Bypass locked areas
- Escape from enclosed spaces
- Solve puzzles requiring multiple passages
```

---

## Example 8: Combination Strategies

```
Advanced dungeon exploration strategy:

Step 1: Enter dark chamber
> cast light
[Creates light to see the room]

Step 2: Scan for magic
> cast detect_magic
[Senses magical auras - finds hidden door]

Step 3: See through illusions
> cast true_sight
[Reveals invisible guardian blocking the door]

Step 4: Unlock the sealed door
> cast unlock sealed_door
[Opens magically locked entrance]

Step 5: Escape if needed
> cast teleport starting_town
[Quick return to safety]

Resource Usage:
- Light: 0 mana, 0.5s cooldown
- Detect Magic: 15 mana, 3s cooldown
- True Sight: 50 mana, 10s cooldown
- Unlock: 20 mana, 2s cooldown
- Teleport: 100 mana, 30s cooldown
Total: 185 mana spent, approximately 45 seconds elapsed

Results: Fully explored, safely navigated, treasure obtained!
```

---

## Adding Custom Utility Abilities

To add a new utility ability:

### 1. Create the Behavior Function

In `app/engine/systems/ability_behaviors/utility.py`:

```python
async def my_utility_behavior(
    caster,
    target,
    ability_template,
    combat_system,
    **context
) -> UtilityResult:
    """Your utility ability implementation."""
    try:
        duration = ability_template.metadata.get("duration", 60.0)

        # Perform ability logic here

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

In `app/engine/systems/classes.py` `_register_core_behaviors()`:

```python
from app.engine.systems.ability_behaviors.utility import my_utility_behavior

self.register_behavior("my_utility", my_utility_behavior)
```

### 3. Create YAML Definition

In `world_data/abilities/utility.yaml`:

```yaml
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

In `app/engine/systems/ability_behaviors/__init__.py`:

```python
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

## Utility Abilities Summary

| Ability | Cost | Cooldown | Level | Use |
|---------|------|----------|-------|-----|
| Light | - | 0.5s | 1 | Illuminate dark areas |
| Daylight | 40 mana | 5.0s | 5 | Room-wide light |
| Darkness | 35 mana | 4.0s | 3 | Create shadow effects |
| Unlock | 20 mana | 2.0s | 3 | Open locked doors |
| Open Container | 25 mana | 2.5s | 4 | Open sealed chests |
| Detect Magic | 15 mana | 3.0s | 2 | Sense magical auras |
| True Sight | 50 mana | 10.0s | 8 | Penetrate illusions |
| Teleport | 100 mana | 30.0s | 10 | Fast travel |
| Create Passage | 75 mana | 20.0s | 7 | Open wall passages |

---

**Status:** Production-ready with comprehensive testing and documentation.
