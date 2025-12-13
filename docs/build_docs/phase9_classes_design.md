
# Phase 9 – Character Classes & Abilities System

**Goals**: Extensible character class system with unique abilities, resource management, and progression paths.

This document details the design and implementation of the Classes & Abilities system—a content-driven, extensible framework for character progression and mechanical gameplay. It enables game designers and content creators to define classes, abilities, and progression without touching backend code.

**Key principles:**
- **YAML-first**: All class and ability definitions live in YAML files
- **Behavior as scripts**: Complex ability logic is implemented as registered Python functions
- **System agnostic**: Abilities work through the existing EffectSystem
- **Hot-reloadable**: Content can be updated without server restart (Phase 8)
- **Backward compatible**: Existing players without classes can still function
- **Extensible**: Designers can add new ability types, resources, and mechanics

---

## Quick Navigation

### For **Architects & Implementers**
- [Architecture Overview](#architecture-overview) – System design, data flow, file structure
- [Domain Models](#domain-models-dataclasses) – ClassTemplate, AbilityTemplate, ResourceDef, CharacterSheet
- [ClassSystem](#classsystem-runtime-manager) – Runtime manager for classes/abilities
- [Ability Executor](#ability-executor) – Validation, cooldown, GCD mechanics
- [Integration Points](#integration-points) – How to wire into WorldEngine and admin API

### For **Content Creators**
- [YAML Examples](#loaders-yaml-parsing) – Class and ability definition examples
- [Content Creator Workflow](#content-creator-workflow) – Step-by-step for creating new classes/abilities
- [Behavior Scripts](#ability-behaviors-extensibility) – How to implement custom ability logic
- [Resource System](#resource-definition) – Understanding mana, rage, energy, custom resources

### For **Reference & Details**
- [Database Schema](#database-schema-migrations) – How player data is stored
- [Player Migration](#player-migration-path-from-old-to-new-system) – Converting existing players
- [WebSocket Protocol](#websocket-protocol-extension) – Event types sent to clients
- [Resource Persistence](#resource-pool-persistence) – Save/restore and offline regen
- [Future Extensions](#future-extensions) – Planned enhancements (talent trees, combos, etc.)

### Implementation Checklist
| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| Domain Models | `app/engine/world.py` | Design ✓ | CharacterSheet, ResourcePool, AbilitySlot |
| ClassSystem | `app/engine/systems/classes.py` | Design ✓ | Load YAML, manage templates, register behaviors |
| AbilityExecutor | `app/engine/systems/abilities.py` | Design ✓ | Validation, cooldowns, GCD, behavior execution |
| Behavior Scripts | `app/engine/systems/ability_behaviors/` | Design ✓ | core.py (built-in), custom.py (extensible) |
| Loaders | `app/engine/loader.py` | Design ✓ | Load classes/abilities from YAML |
| YAML Content | `world_data/classes/`, `world_data/abilities/` | Template Ready | Warrior, Mage, Rogue examples needed |
| Admin Routes | `app/routes/admin.py` | Design ✓ | `/api/admin/classes`, `/api/admin/abilities` |
| Commands | `app/engine/systems/router.py` | Design ✓ | `cast`, `ability`, `skills`, `abilities` |
| Persistence | `app/engine/systems/persistence.py` | Design ✓ | Resource save/restore, offline regen |
| Migrations | `backend/alembic/versions/` | Design ✓ | Add to player.data JSON column |
| WebSocket Events | `app/engine/systems/events.py` | Design ✓ | ability_cast, ability_error, resource_update, etc. |

---

## Architecture Overview

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ Content (YAML files)                                            │
│ ├── world_data/classes/*.yaml                                  │
│ └── world_data/abilities/*.yaml                                │
└──────────────────────┬──────────────────────────────────────────┘
                       │ (ClassLoader, AbilityLoader)
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Domain Models (Dataclasses)                                     │
│ ├── ClassTemplate                                              │
│ ├── AbilityTemplate                                            │
│ ├── ResourceDef                                                │
│ └── ResourcePool (in WorldPlayer)                              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ ClassSystem (Runtime Manager)                                   │
│ ├── class_templates: Dict[str, ClassTemplate]                  │
│ ├── ability_templates: Dict[str, AbilityTemplate]              │
│ ├── behavior_registry: Dict[str, Callable]                     │
│ └── Methods: get_class(), get_ability(), execute_ability()     │
└──────────────────────┬──────────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
┌──────────────────┐        ┌─────────────────────┐
│ EffectSystem     │        │ CombatSystem        │
│ (buffs/debuffs) │        │ (damage/healing)    │
└──────────────────┘        └─────────────────────┘
        ▲                             ▲
        │                             │
        └──────────────┬──────────────┘
                       │
                       ▼
         ┌─────────────────────────┐
         │ AbilityExecutor         │
         │ (validates, executes)   │
         └─────────────────────────┘
```

### File Structure

```
backend/
├── app/
│   ├── engine/
│   │   ├── systems/
│   │   │   ├── classes.py          ← ClassSystem
│   │   │   ├── abilities.py        ← AbilityExecutor + loaders
│   │   │   ├── ability_behaviors/
│   │   │   │   ├── __init__.py     ← Behavior registration
│   │   │   │   ├── core.py         ← Built-in behaviors
│   │   │   │   └── custom.py       ← Extensible for admins
│   │   │   └── [existing systems]
│   │   ├── loader.py               ← Updated for classes/abilities
│   │   └── world.py                ← Add ResourcePool to WorldPlayer
│   └── routes/
│       └── admin.py                ← Add class/ability management
│
└── world_data/
    ├── classes/
    │   ├── adventurer.yaml
    │   ├── warrior.yaml
    │   ├── mage.yaml
    │   └── _schema.yaml             ← Schema reference
    ├── abilities/
    │   ├── core.yaml
    │   ├── warrior.yaml
    │   ├── mage.yaml
    │   └── _schema.yaml             ← Schema reference
    └── [existing: triggers/, quests/, etc.]
```

---

## Domain Models (Dataclasses)

### Resource Definition

```python
@dataclass
class ResourceDef:
    """Defines a character resource (mana, rage, energy, etc.)"""
    resource_id: str               # "mana", "rage", "energy", "focus"
    name: str                       # "Mana", "Rage", "Energy", etc.
    description: str                # Flavor text
    max_amount: int                 # Base max value (before modifiers)
    regen_rate: float              # Per-second regeneration (base)
    regen_type: str                # "passive", "in_combat", "out_of_combat"
    regen_modifiers: Dict[str, float] = None  # {"strength": 0.1, "vigor": 0.05}
    color: str                     # UI hint: "#0088FF"
```

**Example:** Rage resource for Warriors
```yaml
rage:
  resource_id: rage
  name: Rage
  description: "Combat energy that builds with attacks"
  max_amount: 100
  regen_rate: 5.0
  regen_type: "in_combat"
  regen_modifiers:
    strength: 0.1  # +0.1 regen per point of strength
  color: "#FF4444"
```

Regen calculation:
```
current_regen = base_regen + sum(stat * modifier for each stat)
# Warrior with 14 strength in combat: 5.0 + (14 * 0.1) = 6.4 per second
```

### Stat Growth

```python
@dataclass
class StatGrowth:
    """How a stat grows per level"""
    per_level: float               # +1.5 per level
    per_milestone: Dict[int, int]  # {10: +5, 20: +10} at specific levels

# Calculation for a stat:
# effective_value = base_value + (level * per_level) + sum(milestones_at_or_below_level)
# Example - Warrior strength at level 15:
#   base: 14
#   per_level: 1.5 * 15 = 22.5
#   milestones: +5 (at level 10)
#   total: 14 + 22.5 + 5 = 41.5
```

### Class Template

```python
@dataclass
class ClassTemplate:
    """Defines a playable class"""
    class_id: str                  # "warrior", "mage", "rogue"
    name: str                       # Display name
    description: str                # Flavor text

    # Base stats (level 1)
    base_stats: Dict[str, int]     # {"strength": 12, "dexterity": 10, ...}

    # Stat growth per level
    stat_growth: Dict[str, StatGrowth]  # How each stat progresses

    # Starting resources (at level 1)
    starting_resources: Dict[str, int]  # {"health": 100, "mana": 50}

    # Resource definitions for this class (custom regen rates, modifiers)
    resources: Dict[str, ResourceDef]   # Overrides/adds resources

    # Abilities available to this class
    available_abilities: List[str]  # ["slash", "power_attack", "whirlwind"]

    # Ability slots unlock per level
    ability_slots: Dict[int, int]  # {1: 2, 5: 3, 10: 4} slots at levels

    # Global cooldown (GCD) configuration per ability category
    gcd_config: Dict[str, float] = None  # {"melee": 1.0, "spell": 1.5, "shared": 1.0}

    # Flavor
    icon: Optional[str]
    keywords: List[str]
```

### Ability Template

```python
@dataclass
class AbilityTemplate:
    """Defines a usable ability"""
    ability_id: str                # "slash", "fireball", "heal"
    name: str                       # Display name
    description: str                # Flavor text

    # Classification
    ability_type: str              # "active", "passive", "reactive"
    ability_category: str          # "melee", "ranged", "magic", "utility"

    # Resource costs
    costs: Dict[str, int]          # {"mana": 30, "health": 0}

    # Cooldown mechanics
    cooldown: float                # Seconds between uses (personal cooldown)
    gcd_category: str              # GCD category: "melee", "spell", "shared", or null

    # Effect execution
    behavior_id: str               # "slash_behavior", "fireball_behavior"
    effects: List[str]             # Effect template IDs to apply (via EffectSystem)

    # Targeting
    target_type: str               # "self", "enemy", "ally", "room"
    target_range: int              # 0 = self, 1+ = distance (rooms)

    # Execution requirements
    requires_target: bool
    requires_los: bool             # Line of sight
    can_use_while_moving: bool

    # Unlock condition
    required_level: int            # Minimum level to learn
    required_class: Optional[str]  # Restricted to specific class, or null for any

    # Scaling (optional)
    scaling: Dict[str, float] = None  # {"strength": 1.2, "intelligence": 0.5, "level": 0.1}

    # UI/flavor
    icon: Optional[str]
    animation: Optional[str]
    sound: Optional[str]
    keywords: List[str]
```

**Scaling example:**
```python
# Fireball ability with intelligence scaling and level scaling
scaling:
  intelligence: 1.2  # 120% of intelligence stat
  level: 0.1         # +10 damage per level
  # damage = base_damage * (1 + int_stat * 1.2) + (level * 0.1)
```

### Enhanced WorldPlayer

```python
@dataclass
class ResourcePool:
    """Runtime resource state for a player"""
    resource_id: str               # Reference to ResourceDef
    current: int                   # Current amount
    max: int                        # Maximum capacity (from ResourceDef + effects)
    regen_per_second: float        # Calculated from ResourceDef + stat modifiers
    last_regen_tick: float         # Unix timestamp for offline regen

@dataclass
class AbilitySlot:
    """An equipped ability in a loadout"""
    slot_id: int                   # Position in loadout (0, 1, 2, ...)
    ability_id: Optional[str]      # None if slot is empty
    last_used_at: float            # Unix timestamp for cooldown/GCD tracking
    learned_at: int                # Level when ability was learned

@dataclass
class CharacterSheet:
    """Character class and progression data (OPTIONAL - for backward compatibility)"""
    class_id: str
    level: int
    experience: int

    # Computed from class_template + stat effects:
    # effective_stats: Dict[str, int]  (calculated on-the-fly, not stored)

    # Learned abilities
    learned_abilities: Set[str]    # Can be equipped in ability slots
    ability_loadout: List[AbilitySlot]  # Currently equipped (ordered)

    # Resources (mana, rage, etc.)
    resource_pools: Dict[str, ResourcePool]

# Update WorldPlayer to include:
@dataclass
class WorldPlayer(WorldEntity):
    # ... existing fields ...

    # Phase 9 additions (optional - players without classes still work)
    character_sheet: Optional[CharacterSheet] = None

    # For backward compatibility, also support:
    # character_class: Optional[str] = None  (deprecated, prefer character_sheet.class_id)
    # level: Optional[int] = None            (deprecated, prefer character_sheet.level)
```

**Backward Compatibility Note:**
- Existing players without `character_sheet` can still function in the game
- They won't have classes/abilities until explicitly assigned
- New players get a `CharacterSheet` on character creation or first class selection

---

## Loaders (YAML Parsing)

### Class Loader

**Location:** `app/engine/systems/classes.py`

```python
async def load_classes_from_yaml(path: Path) -> Dict[str, ClassTemplate]:
    """Load all class definitions from YAML files"""
    classes = {}
    for yaml_file in path.glob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        class_template = ClassTemplate(**data)
        classes[class_template.class_id] = class_template
    return classes
```

**Example YAML: `world_data/classes/warrior.yaml`**

```yaml
class_id: warrior
name: Warrior
description: "Master of melee combat with heavy armor and strong defense"

base_stats:
  strength: 14
  dexterity: 10
  intelligence: 8
  vitality: 12

stat_growth:
  strength:
    per_level: 1.5
    per_milestone:
      10: 5
      20: 10
  dexterity:
    per_level: 0.5
  vitality:
    per_level: 1.2

starting_resources:
  health: 120
  rage: 100

resources:
  rage:
    resource_id: rage
    name: Rage
    description: "Combat energy that builds with attacks"
    max_amount: 100
    regen_rate: 5.0
    regen_type: "in_combat"
    regen_modifiers:
      strength: 0.1
    color: "#FF4444"

available_abilities:
  - slash
  - power_attack
  - whirlwind
  - shield_bash
  - rally

ability_slots:
  1: 2    # 2 slots at level 1
  5: 3    # 3 slots at level 5
  10: 4   # 4 slots at level 10

gcd_config:
  melee: 1.0
  shared: 1.0

keywords: ["melee", "tank", "heavy-armor"]
```

**Class Storage Note:** Classes are stored **YAML-only**. No database table for class templates.
- Content creators edit YAML files directly
- Hot-reload via Phase 8 admin API updates in-memory class_templates
- Single source of truth (one location, not duplicated in DB)

### Ability Loader

**Location:** `app/engine/systems/abilities.py`

```python
async def load_abilities_from_yaml(path: Path) -> Dict[str, AbilityTemplate]:
    """Load all ability definitions from YAML files"""
    abilities = {}
    for yaml_file in path.glob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        for ability_data in data.get("abilities", []):
            ability = AbilityTemplate(**ability_data)
            abilities[ability.ability_id] = ability
    return abilities
```

**Example YAML: `world_data/abilities/warrior.yaml`**

```yaml
abilities:
  - ability_id: slash
    name: "Slash"
    description: "A basic melee attack"
    ability_type: "active"
    ability_category: "melee"
    costs: {}
    cooldown: 1.0
    gcd_category: "melee"
    behavior_id: "melee_attack"
    effects: []
    target_type: "enemy"
    target_range: 1
    requires_target: true
    requires_los: true
    can_use_while_moving: false
    required_level: 1
    required_class: null
    scaling:
      strength: 1.2
    keywords: ["physical", "basic"]

  - ability_id: power_attack
    name: "Power Attack"
    description: "A devastating strike that costs rage"
    ability_type: "active"
    ability_category: "melee"
    costs:
      rage: 25
    cooldown: 3.0
    gcd_category: "melee"
    behavior_id: "power_attack_behavior"
    effects:
      - "power_attack_effect"
    target_type: "enemy"
    target_range: 1
    requires_target: true
    requires_los: true
    can_use_while_moving: false
    required_level: 5
    required_class: null
    scaling:
      strength: 1.8
    keywords: ["physical", "rage-spender"]

  - ability_id: rally
    name: "Rally"
    description: "A passive ability: gain +10% armor when above 50% health"
    ability_type: "passive"
    ability_category: "utility"
    costs: {}
    cooldown: 0
    gcd_category: null
    behavior_id: "rally_passive"
    effects: []
    target_type: "self"
    target_range: 0
    requires_target: false
    requires_los: false
    can_use_while_moving: true
    required_level: 10
    required_class: null
    keywords: ["passive", "defense"]
```

**Ability Storage Note:** Abilities are also stored **YAML-only**. No database table.
- Each YAML file can contain multiple abilities
- Organized by class or theme (e.g., `warrior.yaml`, `mage.yaml`, `shared.yaml`)
- Hot-reload updates ability_templates via Phase 8 admin API

---

## ClassSystem (Runtime Manager)

**Location:** `app/engine/systems/classes.py`

class ClassSystem:
    """Manages class and ability data at runtime"""

    def __init__(self, context: GameContext):
        self.context = context
        self.class_templates: Dict[str, ClassTemplate] = {}
        self.ability_templates: Dict[str, AbilityTemplate] = {}
        self.behavior_registry: Dict[str, Callable] = {}

        # Register built-in behaviors
        self._register_core_behaviors()

    async def load_content(self, world_data_path: Path):
        """Load all class and ability definitions from YAML"""
        self.class_templates = await load_classes_from_yaml(
            world_data_path / "classes"
        )
        self.ability_templates = await load_abilities_from_yaml(
            world_data_path / "abilities"
        )

    def get_class(self, class_id: str) -> ClassTemplate:
        """Retrieve a class template by ID"""
        if class_id not in self.class_templates:
            raise ValueError(f"Unknown class: {class_id}")
        return self.class_templates[class_id]

    def get_ability(self, ability_id: str) -> AbilityTemplate:
        """Retrieve an ability template by ID"""
        if ability_id not in self.ability_templates:
            raise ValueError(f"Unknown ability: {ability_id}")
        return self.ability_templates[ability_id]

    def register_behavior(self, behavior_id: str, handler: Callable):
        """
        Register a behavior function.

        Behaviors can be registered at startup or dynamically via admin API.
        """
        self.behavior_registry[behavior_id] = handler

    def get_behavior(self, behavior_id: str) -> Optional[Callable]:
        """Retrieve a registered behavior function"""
        return self.behavior_registry.get(behavior_id)

    def _register_core_behaviors(self):
        """Register built-in ability behaviors"""
        from .ability_behaviors import core

        self.register_behavior("melee_attack", core.melee_attack_behavior)
        self.register_behavior("power_attack_behavior", core.power_attack_behavior)
        self.register_behavior("rally_passive", core.rally_passive_behavior)
        # ... etc

    def reload_behaviors(self):
        """
        Reload behaviors from custom.py (called by Phase 8 hot-reload).

        Useful for admins iterating on custom ability behavior scripts.
        """
        try:
            from .ability_behaviors import custom
            # Re-import to get latest code
            import importlib
            importlib.reload(custom)
            # Custom module can register behaviors with self.register_behavior()
        except ImportError:
            pass  # No custom behaviors yet
```

---

## Ability Behaviors (Extensibility)

Behaviors are Python functions registered with the ClassSystem. They execute the core logic of abilities.

### Core Behaviors

**Location:** `app/engine/systems/ability_behaviors/core.py`

Behaviors are async functions that execute the core logic of abilities.

```python
@dataclass
class BehaviorContext:
    """Context passed to behavior functions"""
    context: GameContext
    caster: WorldPlayer
    ability: AbilityTemplate
    targets: List[WorldPlayer]

async def melee_attack_behavior(behavior_ctx: BehaviorContext) -> List[dict]:
    """Basic melee attack: scale damage and apply to target"""
    caster = behavior_ctx.caster
    target = behavior_ctx.targets[0]
    context = behavior_ctx.context

    # Calculate damage using scaling from ability template
    base_damage = caster.get_effective_stat("strength") * 1.0

    # Apply ability scaling if defined
    if behavior_ctx.ability.scaling:
        for stat, multiplier in behavior_ctx.ability.scaling.items():
            if stat == "strength":
                base_damage *= (1 + multiplier)
            elif stat == "level":
                base_damage += caster.character_sheet.level * multiplier

    # Add variance
    variance = random.randint(0, int(base_damage * 0.2))
    total_damage = int(base_damage + variance)

    # Apply through combat system
    events = await context.combat_system.deal_damage(
        attacker=caster,
        target=target,
        damage=total_damage,
        damage_type="physical",
        ability_id="slash"
    )

    return events

async def power_attack_behavior(behavior_ctx: BehaviorContext) -> List[dict]:
    """Heavy attack: higher damage scaling"""
    caster = behavior_ctx.caster
    target = behavior_ctx.targets[0]
    context = behavior_ctx.context

    base_damage = caster.get_effective_stat("strength") * 1.5
    variance = random.randint(0, int(base_damage * 0.3))
    total_damage = int(base_damage + variance)

    events = await context.combat_system.deal_damage(
        attacker=caster,
        target=target,
        damage=total_damage,
        damage_type="physical",
        ability_id="power_attack"
    )

    return events

async def rally_passive_behavior(behavior_ctx: BehaviorContext) -> List[dict]:
    """Passive: if above 50% health, gain +10% armor"""
    caster = behavior_ctx.caster

    health_pct = caster.current_health / caster.max_health

    if health_pct > 0.5:
        # Apply armor buff via EffectSystem
        effect = Effect(
            effect_id="rally_armor",
            name="Rally",
            effect_type="buff",
            stat_modifiers={"armor_class": -1},
            duration=999999,
            applied_at=time.time()
        )
        caster.apply_effect(effect)

    return []  # Passive effects don't generate immediate events
```

**Behavior Registration Strategy:**
1. **Core behaviors** (melee_attack, power_attack, etc.) are registered in `_register_core_behaviors()`
2. **Custom behaviors** can be added to `custom.py` and registered at startup or via admin API
3. **Hot-reload** via `/api/admin/content/reload` calls `class_system.reload_behaviors()`

**Location:** `app/engine/systems/ability_behaviors/custom.py`

Custom behaviors can be added here and are hot-reloadable via Phase 8 admin API:

```python
# This file is a hook for custom behaviors
# Reload via: POST /api/admin/content/reload
# The ClassSystem.reload_behaviors() method re-imports this module

async def fireball_behavior(behavior_ctx: BehaviorContext) -> List[dict]:
    """Custom fireball: AoE damage in target room"""
    caster = behavior_ctx.caster
    context = behavior_ctx.context
    target_room = context.world.rooms[caster.room_id]

    events = []
    base_damage = caster.get_effective_stat("intelligence") * 1.5

    # Apply scaling if defined in ability template
    if behavior_ctx.ability.scaling:
        for stat, multiplier in behavior_ctx.ability.scaling.items():
            if stat == "intelligence":
                base_damage *= (1 + multiplier)

    # AoE damage to all enemies in room
    for player_id in target_room.players:
        if player_id == caster.id:
            continue  # Skip caster

        target = context.world.players[player_id]
        damage = int(base_damage + random.randint(-10, 10))

        room_events = await context.combat_system.deal_damage(
            attacker=caster,
            target=target,
            damage=damage,
            damage_type="fire",
            ability_id="fireball"
        )
        events.extend(room_events)

    return events
```

**Registering Custom Behaviors:**

Option 1: At startup in code
```python
# In app/engine/engine.py startup
from app.engine.systems.ability_behaviors import custom
engine.class_system.register_behavior("fireball_behavior", custom.fireball_behavior)
```

Option 2: Via admin API (future enhancement)
```
POST /api/admin/behaviors/register
{
  "behavior_id": "fireball_behavior",
  "module": "custom"  # loads from ability_behaviors/custom.py
}
```

---

## Ability Executor

**Location:** `app/engine/systems/abilities.py`

The executor validates ability use, deducts costs, manages cooldowns/GCD, and triggers behaviors.

```python
class AbilityExecutor:
    """Validates and executes abilities"""

    def __init__(self, context: GameContext):
        self.context = context

    async def execute_ability(
        self,
        player_id: str,
        ability_id: str,
        target_id: Optional[str] = None
    ) -> List[dict]:
        """
        Execute an ability for a player.

        Returns list of events to dispatch.
        Generates error events if validation fails.
        """
        events = []
        player = self.context.world.players[player_id]
        ability = self.context.class_system.get_ability(ability_id)

        # Validation checks
        validation_error = self._validate_ability_use(
            player, ability, target_id
        )
        if validation_error:
            return [self._error_event(player_id, validation_error)]

        # Deduct costs
        for resource_id, cost in ability.costs.items():
            pool = player.character_sheet.resource_pools[resource_id]
            pool.current -= cost
            events.append({
                "type": "resource_update",
                "player_id": player_id,
                "resource_id": resource_id,
                "current": pool.current,
                "max": pool.max
            })

        # Find targets based on ability targeting rules
        targets = self._resolve_targets(player, ability, target_id)
        if ability.requires_target and not targets:
            return [self._error_event(player_id, f"No valid target for {ability.name}")]

        # Execute behavior (core ability logic)
        behavior = self.context.class_system.get_behavior(ability.behavior_id)
        if not behavior:
            return [self._error_event(
                player_id,
                f"Ability {ability_id} has no behavior registered"
            )]

        behavior_ctx = BehaviorContext(
            context=self.context,
            caster=player,
            ability=ability,
            targets=targets
        )

        try:
            behavior_events = await behavior(behavior_ctx)
            events.extend(behavior_events)
        except Exception as e:
            return [self._error_event(player_id, f"Ability execution error: {str(e)}")]

        # Mark ability as used (cooldown + GCD)
        self._apply_cooldowns(player, ability)

        return events

    def _validate_ability_use(
        self,
        player: WorldPlayer,
        ability: AbilityTemplate,
        target_id: Optional[str]
    ) -> Optional[str]:
        """Check if ability can be used. Return error message if not."""

        if not player.character_sheet:
            return "You don't have a class yet"

        # Check if learned
        if ability.ability_id not in player.character_sheet.learned_abilities:
            return f"You haven't learned {ability.name}"

        # Check level
        if player.character_sheet.level < ability.required_level:
            return f"Requires level {ability.required_level}"

        # Check resources
        for resource_id, cost in ability.costs.items():
            if resource_id not in player.character_sheet.resource_pools:
                return f"Missing resource: {resource_id}"
            pool = player.character_sheet.resource_pools[resource_id]
            if pool.current < cost:
                return f"Insufficient {resource_id} ({pool.current}/{cost})"

        # Check personal cooldown
        for slot in player.character_sheet.ability_loadout:
            if slot.ability_id == ability.ability_id:
                time_since_use = time.time() - slot.last_used_at
                if time_since_use < ability.cooldown:
                    remaining = ability.cooldown - time_since_use
                    return f"{ability.name} is on cooldown ({remaining:.1f}s remaining)"

        # Check target requirements
        if ability.requires_target and not target_id:
            return f"{ability.name} requires a target"

        return None

    def _resolve_targets(
        self,
        caster: WorldPlayer,
        ability: AbilityTemplate,
        target_id: Optional[str]
    ) -> List[WorldPlayer]:
        """Resolve ability targets based on target_type"""

        if ability.target_type == "self":
            return [caster]

        elif ability.target_type == "enemy":
            target = self.context.world.players.get(target_id)
            if not target or target.room_id != caster.room_id:
                return []
            return [target]

        elif ability.target_type == "ally":
            target = self.context.world.players.get(target_id)
            if not target or target.room_id != caster.room_id:
                return []
            return [target]

        elif ability.target_type == "room":
            room = self.context.world.rooms[caster.room_id]
            return [
                self.context.world.players[p_id]
                for p_id in room.players
                if p_id != caster.id
            ]

        return []

    def _apply_cooldowns(self, player: WorldPlayer, ability: AbilityTemplate):
        """Mark ability as used (personal cooldown) and apply GCD"""

        # Update personal cooldown
        for slot in player.character_sheet.ability_loadout:
            if slot.ability_id == ability.ability_id:
                slot.last_used_at = time.time()
                break

        # Apply GCD to all abilities in same category (if configured)
        if ability.gcd_category:
            gcd_time = player.character_sheet.class_id  # Get from class template
            class_template = self.context.class_system.get_class(
                player.character_sheet.class_id
            )
            gcd_duration = class_template.gcd_config.get(ability.gcd_category, 0)

            # Mark all abilities in same GCD category as recently used
            for slot in player.character_sheet.ability_loadout:
                if not slot.ability_id:
                    continue
                slot_ability = self.context.class_system.get_ability(slot.ability_id)
                if slot_ability.gcd_category == ability.gcd_category:
                    slot.last_used_at = time.time() - (ability.cooldown - gcd_duration)

    def _error_event(self, player_id: str, message: str) -> dict:
        """Generate an error event"""
        return {
            "type": "ability_error",
            "player_id": player_id,
            "message": message
        }
```

---

## Integration Points

### WorldEngine Initialization

Update `app/engine/engine.py`:

```python
class WorldEngine:
    def __init__(self, ...):
        # ... existing init ...

        # Initialize ClassSystem
        self.class_system = ClassSystem(context)

        # Initialize AbilityExecutor
        self.ability_executor = AbilityExecutor(context)

    async def startup(self):
        # ... existing startup ...

        # Load class and ability content
        await self.class_system.load_content(
            Path("world_data")
        )
```

### CommandRouter Extensions

Update `app/engine/systems/router.py`:

```python
@cmd("cast", "ability", "skill")
async def cmd_cast_ability(engine, player_id, args):
    """
    Usage: cast <ability_name> [target]
           ability <ability_name> [target]
           skill <ability_name> [target]
    """
    if not args:
        return [engine._message_event(
            player_id,
            "Usage: cast <ability-name> [target]"
        )]

    ability_name = args[0].lower()
    target_name = args[1] if len(args) > 1 else None

    # Resolve ability by name (case-insensitive)
    ability_id = None
    for a_id, a_tmpl in engine.class_system.ability_templates.items():
        if a_tmpl.name.lower() == ability_name:
            ability_id = a_id
            break

    if not ability_id:
        return [engine._message_event(
            player_id,
            f"Unknown ability: {ability_name}"
        )]

    # Execute ability
    events = await engine.ability_executor.execute_ability(
        player_id, ability_id, target_name
    )

    return events

@cmd("abilities", "skills")
async def cmd_list_abilities(engine, player_id, args):
    """List available abilities"""
    player = engine.world.players[player_id]

    if not player.character_sheet:
        return [engine._message_event(player_id, "You don't have a class yet")]

    class_template = engine.class_system.get_class(player.character_sheet.class_id)

    msg = f"=== {class_template.name} Abilities ===\n"

    for slot in player.character_sheet.ability_loadout:
        if not slot.ability_id:
            msg += f"[{slot.slot_id}] - (empty)\n"
            continue

        ability = engine.class_system.get_ability(slot.ability_id)
        time_since_use = time.time() - slot.last_used_at
        is_ready = time_since_use >= ability.cooldown

        status = "✓ ready" if is_ready else f"{ability.cooldown - time_since_use:.1f}s"
        msg += f"[{slot.slot_id}] {ability.name} - {status}\n"

    return [engine._message_event(player_id, msg)]
```

### Admin API Endpoints

Update `app/routes/admin.py`:

```python
@router.get("/api/admin/classes")
async def get_classes(current_user: UserAccount = Depends(requires_role("MODERATOR"))):
    """List all loaded classes"""
    return {
        "classes": [
            {
                "class_id": c.class_id,
                "name": c.name,
                "available_abilities": c.available_abilities
            }
            for c in engine.class_system.class_templates.values()
        ]
    }

@router.get("/api/admin/abilities")
async def get_abilities(current_user: UserAccount = Depends(requires_role("MODERATOR"))):
    """List all loaded abilities"""
    return {
        "abilities": [
            {
                "ability_id": a.ability_id,
                "name": a.name,
                "category": a.ability_category,
                "cooldown": a.cooldown
            }
            for a in engine.class_system.ability_templates.values()
        ]
    }

@router.post("/api/admin/classes/reload")
async def reload_classes(current_user: UserAccount = Depends(requires_role("GAME_MASTER"))):
    """Hot-reload class and ability definitions from YAML"""
    try:
        await engine.class_system.load_content(Path("world_data"))
        engine.class_system.reload_behaviors()

        return {
            "status": "ok",
            "message": "Classes, abilities, and behaviors reloaded",
            "classes_loaded": len(engine.class_system.class_templates),
            "abilities_loaded": len(engine.class_system.ability_templates)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
```

---

## WebSocket Protocol Extension

Ability-related events sent to clients:

```json
{
  "type": "ability_cast",
  "player_id": "uuid",
  "ability_id": "slash",
  "targets": ["target-uuid"],
  "timestamp": 1234567890
}
```

```json
{
  "type": "ability_error",
  "player_id": "uuid",
  "message": "Insufficient mana",
  "ability_id": "fireball"
}
```

```json
{
  "type": "ability_cast_complete",
  "player_id": "uuid",
  "ability_id": "slash",
  "damage_dealt": 15,
  "timestamp": 1234567890
}
```

```json
{
  "type": "ability_learned",
  "player_id": "uuid",
  "ability_id": "power_attack",
  "ability_name": "Power Attack",
  "level": 5
}
```

```json
{
  "type": "resource_update",
  "player_id": "uuid",
  "resource_id": "mana",
  "current": 45,
  "max": 100,
  "regen_rate": 2.5
}
```

```json
{
  "type": "cooldown_update",
  "player_id": "uuid",
  "ability_id": "slash",
  "cooldown_remaining": 1.5,
  "cooldown_total": 1.0
}
```

---

## Resource Pool Persistence

**Saving on disconnect:**
```python
# In persistence.py
async def save_player_resources(player: WorldPlayer, db_session):
    """Serialize resource pools to player.data JSON"""
    if not player.character_sheet:
        return

    resources_data = {}
    for resource_id, pool in player.character_sheet.resource_pools.items():
        resources_data[resource_id] = {
            "current": pool.current,
            "max": pool.max,
            "last_regen_tick": pool.last_regen_tick
        }

    # Store in player.data JSON column
    player_record = await db_session.get(Player, player.id)
    player_record.data["resource_pools"] = resources_data
    await db_session.commit()
```

**Restoring on connect:**
```python
# In loader.py
async def restore_player_resources(player: WorldPlayer, player_record: Player):
    """Restore resource pools from saved data"""
    if not player.character_sheet:
        return

    class_template = context.class_system.get_class(player.character_sheet.class_id)

    # Get saved resource data
    saved_resources = player_record.data.get("resource_pools", {})

    # Restore each resource
    for resource_id in class_template.resources:
        resource_def = class_template.resources[resource_id]
        saved_data = saved_resources.get(resource_id, {})

        # Offline regen: calculate regen during disconnect time
        time_offline = time.time() - (player_record.last_disconnect or time.time())
        offline_regen = resource_def.regen_rate * (time_offline / 60)  # per minute

        current = min(
            saved_data.get("current", resource_def.max_amount) + offline_regen,
            resource_def.max_amount
        )

        pool = ResourcePool(
            resource_id=resource_id,
            current=int(current),
            max=resource_def.max_amount,
            regen_per_second=resource_def.regen_rate,
            last_regen_tick=time.time()
        )
        player.character_sheet.resource_pools[resource_id] = pool
```

---

## Database Schema (Migrations)

**Player Model Extensions:**

```python
# In app/models.py
class Player(Base):
    __tablename__ = "players"

    # ... existing fields ...

    # Phase 9: Class and abilities
    data: Dict = Column(JSON, default={})  # Stores:
    # {
    #   "class_id": "warrior",
    #   "level": 5,
    #   "experience": 1200,
    #   "learned_abilities": ["slash", "power_attack"],
    #   "ability_loadout": [
    #     {"slot_id": 0, "ability_id": "slash", "last_used_at": 1234567890},
    #     {"slot_id": 1, "ability_id": "power_attack", "last_used_at": 1234567885}
    #   ],
    #   "resource_pools": {
    #     "health": {"current": 100, "max": 120, "last_regen_tick": 1234567890},
    #     "rage": {"current": 50, "max": 100, "last_regen_tick": 1234567890}
    #   }
    # }
```

**Important Note:** Character data is stored in the `data` JSON column, NOT as separate database columns. This provides:
- Flexibility for schema-less player data
- Easy migration of existing players (backward compatible)
- Reduced migration burden (no ALTER TABLE needed)

---

## Player Migration Path (from old to new system)

**For existing players:**

```python
# One-time migration script (Phase 9 startup)
async def migrate_existing_players():
    """Convert old character_class/level to new CharacterSheet"""
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(Player).where(
                and_(
                    Player.data["class_id"].astext == None,
                    Player.data["character_class"].astext != None
                )
            )
        )

        for player_record in result.scalars():
            old_class = player_record.data.get("character_class")
            old_level = player_record.data.get("level", 1)

            if not old_class:
                # Assign default class if missing
                old_class = "adventurer"

            # Get class template
            try:
                class_template = engine.class_system.get_class(old_class)
            except ValueError:
                # Class was deleted, use default
                class_template = engine.class_system.get_class("adventurer")

            # Create CharacterSheet
            player_record.data["class_id"] = class_template.class_id
            player_record.data["level"] = old_level
            player_record.data["experience"] = 0
            player_record.data["learned_abilities"] = class_template.available_abilities[:2]  # Start with first 2
            player_record.data["ability_loadout"] = [
                {"slot_id": i, "ability_id": None, "last_used_at": 0}
                for i in range(class_template.ability_slots.get(old_level, 2))
            ]
            player_record.data["resource_pools"] = {
                resource_id: {
                    "current": amount,
                    "max": amount,
                    "last_regen_tick": time.time()
                }
                for resource_id, amount in class_template.starting_resources.items()
            }

            await session.commit()
```

---

## Content Creator Workflow

### Step 1: Define the Class

Create `world_data/classes/my_class.yaml`:

```yaml
class_id: my_class
name: "My Custom Class"
description: "..."
base_stats:
  strength: 10
  dexterity: 10
# ... etc
```

### Step 2: Define Abilities

Create `world_data/abilities/my_class.yaml`:

```yaml
abilities:
  - ability_id: custom_ability
    name: "Custom Ability"
    behavior_id: "custom_behavior"
    # ... etc
```

### Step 3: Implement Behavior (if needed)

Add to `app/engine/systems/ability_behaviors/custom.py`:

```python
async def custom_behavior(behavior_ctx: BehaviorContext):
    # Your logic here
    return events
```

### Step 4: Hot-Reload (Phase 8)

Call: `POST /api/admin/classes/reload`

Classes, abilities, and behaviors reload without server restart.

---

## Future Extensions

- **Talent Trees**: Progression branches with conditional ability unlocks
- **Combo System**: Bonus effects for ability sequences (slash → power_attack)
- **Ability Scaling**: Detailed scaling calculations with multiple stat sources
- **Channeling**: Abilities that take time to cast (interruptible via damage)
- **Projectiles**: Ranged ability travel time and line-of-sight checking
- **Animations**: Client-side animation hints for cosmetics
- **Macros**: Player-defined ability combinations and sequences
- **Resource Builders**: Abilities that build resource instead of spending it
- **Conditional Abilities**: Abilities that only work under certain conditions
- **Ability Synergies**: Bonuses for using certain ability combinations

---

## Design Philosophy Summary

This system achieves extensibility and maintainability by:

1. **YAML as the content language**: Designers write declarative configurations, not code
2. **Behavior registration**: Complex logic is Python functions, not embedded in YAML
3. **Hot-reload ready**: Content updates don't require server restart (Phase 8)
4. **Reusing existing systems**: Abilities trigger effects via EffectSystem, damage via CombatSystem
5. **Clear separation of concerns**: Templates (data) vs. Executor (validation) vs. Behaviors (logic)
6. **Event-driven dispatch**: All ability outcomes produce events for client consumption
7. **Backward compatible**: Existing players without classes can still function
8. **Scalable design**: Resource pools, cooldowns, and GCD managed cleanly
9. **Content-driven**: No code changes needed for new classes/abilities

This aligns with the existing codebase philosophy:
- Authoritative server (all logic server-side)
- Event-driven architecture
- Content-driven world design
- Extensibility without code changes


---

## Summary

I've researched and planned a mature **Character Classes & Abilities System** that maintains alignment with your existing architecture. Here are the key findings:

### **Design Highlights:**

1. **Dual-Layer Content Model**
   - YAML files for declarative class/ability definitions (classes, cooldowns, costs)
   - Python behavior scripts for complex execution logic (damage calculation, effects)
   - Separates "what" (YAML) from "how" (behaviors)

2. **Extensibility for Content Creators**
   - New classes require only YAML (no code)
   - New abilities require YAML + optional behavior registration
   - Hot-reload support (Phase 8) enables iteration without server restart
   - Admin API for registering custom behaviors

3. **Alignment with Codebase**
   - Reuses `EffectSystem` for buffs/debuffs/DoT
   - Reuses `CombatSystem` for damage/healing
   - Follows event-driven architecture (abilities emit events)
   - Maintains DB ↔ in-memory World separation

4. **Resource System**
   - Flexible resource pools (Mana, Rage, Energy, Focus, custom)
   - Per-resource regen rates and types (passive, active, in-combat)
   - Abilities deduct costs and trigger behaviors

5. **Ability Types**
   - **Active**: Instant or channeled, require costs/targets, have cooldowns
   - **Passive**: Always-on benefits, no costs, no action needed
   - **Reactive**: Trigger on conditions (future enhancement)

The document above is **production-ready** and can serve as both technical spec and content creator guide. Would you like me to begin implementing these systems?
