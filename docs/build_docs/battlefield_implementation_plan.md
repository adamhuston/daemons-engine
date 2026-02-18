# Battlefield Implementation Plan - Technical Specification

## Overview
This document provides implementation details for NPC faction warfare required for the battlefield area. Tasks are ordered by dependency - complete Phase 1 before Phase 2.

---

## Phase 1: Core Faction Combat (REQUIRED)

### Task 1.1: Add faction_id field to NPC template schema

**Files to modify:**
- `backend/daemons/world_data/npcs/_schema.yaml`
- `backend/daemons/models.py` (NpcTemplate class)
- `backend/daemons/engine/loader.py` (load_npc_templates_from_yaml)

**Schema addition** (`npcs/_schema.yaml` around line 100):
```yaml
# Faction Affiliation (Phase 10.3+)
# ===========================
faction_id: string | null (default: null)
  # Faction this NPC belongs to (from factions/*.yaml)
  # NPCs with matching faction_id are allies
  # NPCs with different faction_ids may be enemies (see faction hostility matrix)
  # If null, NPC is independent/neutral
  # Example: "Silver Sanctum", "Shadow Syndicate"
```

**Database model** (`models.py` NpcTemplate class, after line 565):
```python
# Phase 10.3+: Faction affiliation
faction_id: Mapped[str | None] = mapped_column(
    String, nullable=True
)  # Faction membership for warfare
```

**Migration required**: Create new Alembic migration to add `faction_id` column to `npc_templates` table.

**Loader update** (`loader.py` in `load_npc_templates_from_yaml` function):
```python
faction_id = npc_def.get("faction_id")  # Around line 300
# Set faction_id=faction_id in NpcTemplate creation
```

**Validation**: Update `FactionSystem.npc_to_faction` dict when loading NPCs with faction_id.

---

### Task 1.2: Implement faction hostility matrix

**Files to modify:**
- `backend/daemons/engine/systems/faction_system.py`

**Add to FactionSystem class** (after `__init__` around line 110):

```python
# Faction hostility matrix: {faction_id: set(enemy_faction_ids)}
self.faction_hostilities: dict[str, set[str]] = {}
```

**Add method** (around line 320 after `list_factions`):
```python
def set_faction_hostility(self, faction_id_1: str, faction_id_2: str, bidirectional: bool = True) -> None:
    """
    Mark two factions as hostile to each other.
    
    Args:
        faction_id_1: First faction ID
        faction_id_2: Second faction ID  
        bidirectional: If True, makes hostility mutual (default)
    """
    if faction_id_1 not in self.faction_hostilities:
        self.faction_hostilities[faction_id_1] = set()
    self.faction_hostilities[faction_id_1].add(faction_id_2)
    
    if bidirectional:
        if faction_id_2 not in self.faction_hostilities:
            self.faction_hostilities[faction_id_2] = set()
        self.faction_hostilities[faction_id_2].add(faction_id_1)

def are_factions_hostile(self, faction_id_1: str | None, faction_id_2: str | None) -> bool:
    """
    Check if two factions are enemies.
    
    Args:
        faction_id_1: First faction ID (None = neutral)
        faction_id_2: Second faction ID (None = neutral)
        
    Returns:
        True if factions are hostile, False otherwise
    """
    if not faction_id_1 or not faction_id_2:
        return False  # Neutral NPCs not hostile
    if faction_id_1 == faction_id_2:
        return False  # Same faction
    
    return faction_id_2 in self.faction_hostilities.get(faction_id_1, set())

def get_npc_faction(self, npc_template_id: str) -> str | None:
    """
    Get faction ID for an NPC template.
    
    Args:
        npc_template_id: NPC template ID
        
    Returns:
        Faction ID or None if independent
    """
    return self.npc_to_faction.get(npc_template_id)
```

**Update `load_factions_from_yaml`** (around line 240):
Add after loading all factions:
```python
# Setup default hostilities for known factions
silver_sanctum_id = None
shadow_syndicate_id = None

for fid, faction_info in self.factions.items():
    if faction_info.name == "Silver Sanctum":
        silver_sanctum_id = fid
    elif faction_info.name == "Shadow Syndicate":
        shadow_syndicate_id = fid

if silver_sanctum_id and shadow_syndicate_id:
    self.set_faction_hostility(silver_sanctum_id, shadow_syndicate_id)
    logger.info(f"Set hostility: Silver Sanctum <-> Shadow Syndicate")
```

---

### Task 1.3: Extend NPC AI to detect and target enemy faction NPCs

**Files to modify:**
- `backend/daemons/engine/engine.py`

**Location**: In NPC AI system around line 6400-6500 where `aggro_on_sight` is checked.

**Add new method** (around line 6350):
```python
async def _npc_find_hostile_targets(
    self, npc_id: str, npc_room_id: str
) -> list[str]:
    """
    Find all valid hostile targets for an NPC (both NPCs and players).
    
    Priority:
    1. Enemy faction NPCs in same room
    2. Players (if aggro_on_sight enabled)
    
    Args:
        npc_id: NPC instance ID
        npc_room_id: Room ID where NPC is located
        
    Returns:
        List of entity IDs (npc or player) that are hostile targets
    """
    targets = []
    
    npc_state = self.npc_states.get(npc_id)
    if not npc_state:
        return targets
        
    npc_template = self.npc_templates.get(npc_state.template_id)
    if not npc_template:
        return targets
    
    npc_faction = npc_template.faction_id
    
    # Find enemy faction NPCs in room
    room_npcs = self.room_npcs.get(npc_room_id, set())
    for other_npc_id in room_npcs:
        if other_npc_id == npc_id:
            continue
            
        other_state = self.npc_states.get(other_npc_id)
        if not other_state or other_state.current_health <= 0:
            continue
            
        other_template = self.npc_templates.get(other_state.template_id)
        if not other_template:
            continue
            
        other_faction = other_template.faction_id
        
        # Check if factions are hostile
        if self.ctx.faction_system.are_factions_hostile(npc_faction, other_faction):
            targets.append(other_npc_id)
    
    # Check for players if aggro_on_sight enabled
    behavior_config = await self._resolve_npc_behavior(npc_state)
    if behavior_config.get("aggro_on_sight", True):
        room_players = self.room_players.get(npc_room_id, set())
        for player_id in room_players:
            player = self.players.get(player_id)
            if player and player.current_health > 0:
                targets.append(player_id)
    
    return targets
```

**Update existing NPC idle tick** (around line 6470):
Replace or extend the section that checks `aggro_on_sight`:
```python
# Check for hostile targets (faction enemies + players)
hostile_targets = await self._npc_find_hostile_targets(npc_id, npc_room_id)

if hostile_targets:
    # Priority: faction enemies first, then players
    target_id = hostile_targets[0]
    
    # Determine if target is player or NPC
    is_player = target_id in self.players
    target_name = self.players[target_id].name if is_player else self.npc_states[target_id].name
    
    # Start combat
    npc_state.target_id = target_id
    npc_state.combat_state = "active"
    
    # Broadcast attack message
    npc_display = self._get_npc_display_name(npc_id)
    events.append(
        self.ctx.msg_to_room(
            npc_room_id,
            f"⚔️ {npc_display} attacks {target_name}!",
        )
    )
```

**Update NPC on-player-enters** (around line 6510):
Similar logic: check for faction hostility when player enters room.

**Update NPC combat target selection** (in combat system around line 6580):
Add faction hostility check when selecting targets for attacks.

---

### Task 1.4: Test NPC vs NPC combat thoroughly

**Test requirements:**

1. **Create test NPCs with factions**:
```yaml
# test_sanctum_warrior.yaml
id: npc_test_sanctum_warrior
name: Test Sanctum Warrior
faction_id: Silver Sanctum
npc_type: hostile
level: 5
max_health: 100
armor_class: 12
attack_damage_min: 8
attack_damage_max: 15
behavior:
  - aggressive
  - calls_for_help
```

```yaml
# test_syndicate_rogue.yaml  
id: npc_test_syndicate_rogue
name: Test Syndicate Rogue
faction_id: Shadow Syndicate
npc_type: hostile
level: 5
max_health: 80
armor_class: 10
attack_damage_min: 10
attack_damage_max: 18
behavior:
  - aggressive
  - cowardly
```

2. **Test scenarios** (manual or automated):
   - Spawn both NPCs in same room → should attack each other
   - Spawn 2 Sanctum vs 1 Syndicate → should gang up
   - Verify damage calculations work NPC→NPC
   - Verify death triggers properly
   - Verify XP not awarded to NPC killers (only to players)
   - Verify loot drops when NPC dies

3. **Verification points**:
   - Check logs for faction hostility detection
   - Observe combat messages in room
   - Confirm NPCs prioritize faction enemies over players
   - Ensure no infinite loops or crashes

---

### Task 1.5: Verify loot drops from NPC deaths (regardless of killer)

**Files to check:**
- `backend/daemons/engine/engine.py` (around line 6700-6800, `_npc_die` function)

**Required behavior**:
Current code likely checks if killer is player before dropping loot. Update to:

```python
async def _npc_die(self, npc_id: str, killer_id: str | None = None) -> list[Event]:
    """
    Handle NPC death.
    
    Args:
        npc_id: NPC instance ID
        killer_id: Entity ID of killer (player or NPC), or None
    """
    events = []
    npc_state = self.npc_states.get(npc_id)
    # ... existing death logic ...
    
    # Drop loot regardless of killer type
    loot_events = await self._npc_drop_loot(npc_id, npc_state.room_id)
    events.extend(loot_events)
    
    # Award XP only if killer is a player
    if killer_id and killer_id in self.players:
        xp_events = await self._award_xp_to_player(killer_id, npc_template.experience_reward)
        events.extend(xp_events)
    
    # ... rest of death logic ...
    return events
```

**Test**: Spawn two hostile NPCs, let them fight to death, verify loot appears in room.

---

## Phase 2: Patrol System (REQUIRED)

### Task 2.1: Design patrol route YAML schema

**Files to modify:**
- `backend/daemons/world_data/npcs/_schema.yaml` (add patrol documentation)
- Create example: `backend/daemons/world_data/npc_spawns/_schema.yaml` (new file)

**Schema design** - Two approaches:

**Approach A: Patrol on NPC Spawn** (recommended)
```yaml
# In npc_spawns/*.yaml (new system)
- npc_template_id: npc_sanctum_warrior
  spawn_room_id: room_battlefield_sanctum_gate
  patrol_route:
    - room_battlefield_sanctum_gate
    - room_battlefield_west_forest_1
    - room_battlefield_west_forest_2
    - room_battlefield_ruins_outer_west
  patrol_mode: loop  # loop, bounce, once
  patrol_interval: 60  # seconds between moves
  spawn_as_group: true
  group_size: 3
```

**Approach B: Patrol behavior tag**
```yaml
# In NPC template behavior
behavior:
  - aggressive
  - patrols
  
# Patrol route defined per-spawn in rooms/*.yaml
```

**Recommended: Approach A** - More flexible, allows multiple spawns of same NPC with different routes.

**Database support** - Extend `NpcInstance` model:
```python
# In models.py NpcInstance (around line 620)
patrol_route: Mapped[list] = mapped_column(JSON, default=list)
patrol_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
patrol_mode: Mapped[str] = mapped_column(String, nullable=False, server_default="loop")
home_room_id: Mapped[str | None] = mapped_column(String, nullable=True)  # Spawn point
```

---

### Task 2.2: Implement waypoint navigation system

**Files to modify:**
- `backend/daemons/engine/engine.py` (NPC movement system)
- `backend/daemons/engine/behaviors/wandering.py` (new patrol behavior)

**Add new behavior** in `behaviors/wandering.py` (around line 150):

```python
@register_behavior(
    name="patrols",
    description="NPC follows a defined patrol route",
    defaults={
        "wander_enabled": True,
        "wander_interval_min": 30.0,
        "wander_interval_max": 60.0,
    }
)
class Patrols(BehaviorScript):
    async def on_wander_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        """Move to next waypoint in patrol route."""
        npc_state = ctx.npc_state
        
        # Check if NPC has patrol route
        if not npc_state.patrol_route or len(npc_state.patrol_route) == 0:
            return BehaviorResult(handled=False)
        
        # Get next waypoint
        next_room_id = self._get_next_patrol_waypoint(npc_state)
        
        if not next_room_id:
            return BehaviorResult(handled=False)
        
        # Move to next room
        return BehaviorResult(
            handled=True,
            move_to=next_room_id,
            message=f"{npc_state.name} continues patrol."
        )
    
    def _get_next_patrol_waypoint(self, npc_state) -> str | None:
        """Calculate next room in patrol route."""
        route = npc_state.patrol_route
        current_index = npc_state.patrol_index
        mode = npc_state.patrol_mode
        
        if mode == "loop":
            next_index = (current_index + 1) % len(route)
        elif mode == "bounce":
            # Implementation for back-and-forth patrol
            direction = getattr(npc_state, '_patrol_direction', 1)
            next_index = current_index + direction
            if next_index >= len(route) or next_index < 0:
                direction *= -1
                next_index = current_index + direction
            npc_state._patrol_direction = direction
        elif mode == "once":
            next_index = current_index + 1
            if next_index >= len(route):
                return None  # End of patrol
        else:
            next_index = (current_index + 1) % len(route)
        
        npc_state.patrol_index = next_index
        return route[next_index]
```

**Add patrol route loader** in `engine.py` (around line 3100):
```python
async def _load_npc_spawns_from_yaml(self, spawn_dir: str) -> None:
    """Load NPC spawn configurations with patrol routes."""
    import yaml
    from pathlib import Path
    
    spawn_path = Path(spawn_dir)
    if not spawn_path.exists():
        return
    
    for yaml_file in spawn_path.glob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue
            
        with open(yaml_file, encoding="utf-8") as f:
            spawns = yaml.safe_load(f)
            
        for spawn_def in spawns:
            await self._spawn_npc_with_patrol(spawn_def)
```

---

### Task 2.3: Add "return to patrol" behavior after combat

**Files to modify:**
- `backend/daemons/engine/engine.py` (combat system)

**Approach**: Track when NPC deviates from patrol route during combat.

**Add to NpcState tracking** (in engine.py around line 6200):
```python
# After combat ends (in _npc_combat_tick when target dies/escapes)
if npc_state.combat_state == "active" and not npc_state.target_id:
    # Combat ended
    npc_state.combat_state = "idle"
    
    # If NPC has patrol route and is not on route, return to nearest waypoint
    if npc_state.patrol_route and len(npc_state.patrol_route) > 0:
        current_room = npc_state.room_id
        
        # Find nearest waypoint in patrol route
        if current_room not in npc_state.patrol_route:
            nearest_waypoint = await self._find_nearest_waypoint(
                current_room, npc_state.patrol_route
            )
            
            if nearest_waypoint:
                # Move back toward patrol route
                path = await self._find_path(current_room, nearest_waypoint)
                if path and len(path) > 1:
                    await self._npc_move_to_room(npc_id, path[1])
```

**Add pathfinding helper** (around line 6850):
```python
async def _find_nearest_waypoint(self, from_room: str, waypoints: list[str]) -> str | None:
    """Find closest waypoint in list using BFS."""
    # Simple implementation: return first waypoint
    # Advanced: use BFS to find shortest path to any waypoint
    return waypoints[0] if waypoints else None

async def _find_path(self, from_room: str, to_room: str, max_depth: int = 10) -> list[str] | None:
    """
    Find shortest path between two rooms using BFS.
    
    Returns:
        List of room IDs from source to destination, or None if no path
    """
    if from_room == to_room:
        return [from_room]
    
    from collections import deque
    
    queue = deque([(from_room, [from_room])])
    visited = {from_room}
    
    while queue:
        current_room, path = queue.popleft()
        
        if len(path) > max_depth:
            continue
        
        room = self.rooms.get(current_room)
        if not room:
            continue
        
        # Check all exits
        for direction in ['north', 'south', 'east', 'west', 'up', 'down']:
            exit_room = getattr(room, f'{direction}_id', None)
            if not exit_room or exit_room in visited:
                continue
            
            new_path = path + [exit_room]
            
            if exit_room == to_room:
                return new_path
            
            visited.add(exit_room)
            queue.append((exit_room, new_path))
    
    return None
```

---

### Task 2.4: Support group patrol spawning

**Files to modify:**
- `backend/daemons/engine/engine.py` (spawn system)

**Extend spawn system** (around line 3150):
```python
async def _spawn_npc_with_patrol(self, spawn_def: dict) -> list[str]:
    """
    Spawn NPC(s) with patrol route configuration.
    
    Args:
        spawn_def: Dictionary from npc_spawns YAML
        
    Returns:
        List of spawned NPC instance IDs
    """
    template_id = spawn_def.get("npc_template_id")
    spawn_room = spawn_def.get("spawn_room_id")
    patrol_route = spawn_def.get("patrol_route", [])
    patrol_mode = spawn_def.get("patrol_mode", "loop")
    spawn_as_group = spawn_def.get("spawn_as_group", False)
    group_size = spawn_def.get("group_size", 1)
    
    spawned_ids = []
    
    count = group_size if spawn_as_group else 1
    
    for i in range(count):
        npc_id = await self._spawn_npc_instance(
            template_id=template_id,
            room_id=spawn_room
        )
        
        if npc_id:
            # Set patrol configuration
            npc_state = self.npc_states[npc_id]
            npc_state.patrol_route = patrol_route
            npc_state.patrol_index = 0
            npc_state.patrol_mode = patrol_mode
            npc_state.home_room_id = spawn_room
            
            # Stagger spawn positions if group
            if spawn_as_group and i > 0 and len(patrol_route) > i:
                npc_state.patrol_index = i % len(patrol_route)
            
            spawned_ids.append(npc_id)
    
    return spawned_ids
```

**Group coordination** (optional enhancement):
```python
# Add to NpcState
group_id: str | None = None  # Shared by NPCs in same patrol group

# When one NPC in group enters combat, others nearby also engage
```

---

## Phase 3: Polish (OPTIONAL)

### Task 3.1: Faction-aware call for help

**Files to modify:**
- `backend/daemons/engine/behaviors/social.py`

**Update `calls_for_help` behavior** (around line 50):
```python
# In on_damaged hook
async def on_damaged(self, ctx: BehaviorContext) -> BehaviorResult:
    """Call for help from same-faction NPCs only."""
    npc_faction = ctx.npc_template.faction_id
    
    # Find allies in help radius
    room_npcs = ctx.engine.room_npcs.get(ctx.npc_state.room_id, set())
    
    for ally_id in room_npcs:
        if ally_id == ctx.npc_state.id:
            continue
        
        ally_state = ctx.engine.npc_states.get(ally_id)
        ally_template = ctx.engine.npc_templates.get(ally_state.template_id)
        
        # Only call same-faction NPCs
        if ally_template.faction_id == npc_faction:
            # Set ally to attack attacker
            ally_state.target_id = ctx.attacker_id
            ally_state.combat_state = "active"
```

### Task 3.2: Cooperative NPC abilities prioritize faction members

**Files to modify:**
- `backend/daemons/engine/behaviors/*.py` (heal, buff abilities)

**Example for heal ability**:
```python
# When NPC casts heal, prioritize:
# 1. Self if low HP
# 2. Same-faction NPCs with low HP
# 3. No target if no allies need healing

def _select_heal_target(self, ctx: BehaviorContext) -> str | None:
    """Select best target for healing ability."""
    npc_faction = ctx.npc_template.faction_id
    
    candidates = []
    
    # Check NPCs in room
    for npc_id in ctx.engine.room_npcs.get(ctx.npc_state.room_id, set()):
        other_state = ctx.engine.npc_states.get(npc_id)
        other_template = ctx.engine.npc_templates.get(other_state.template_id)
        
        # Only heal same faction
        if other_template.faction_id != npc_faction:
            continue
        
        hp_percent = other_state.current_health / other_template.max_health
        if hp_percent < 0.7:  # Below 70% HP
            candidates.append((npc_id, hp_percent))
    
    if not candidates:
        return None
    
    # Heal lowest HP ally
    candidates.sort(key=lambda x: x[1])
    return candidates[0][0]
```

### Task 3.3: Territory/aggro radius for patrol groups

**Implementation**: Add chase distance limit based on patrol route.

```python
# In combat system, track distance from home territory
max_chase_distance = 3  # rooms

if npc_state.home_room_id:
    distance = await self._calculate_room_distance(
        npc_state.room_id, 
        npc_state.home_room_id
    )
    
    if distance > max_chase_distance:
        # Too far from home, disengage and return
        npc_state.target_id = None
        npc_state.combat_state = "idle"
        events.append(
            self.ctx.msg_to_room(
                npc_state.room_id,
                f"{npc_state.name} gives up the chase and returns to patrol."
            )
        )
```

### Task 3.4: Dynamic faction balance tracking

**Implementation**: Track NPC kill counts per faction.

```python
# Add to GameContext or AreaState
faction_kill_counts: dict[str, int] = {}  # faction_id -> kill count

# When NPC dies
if killer_faction and victim_faction:
    self.ctx.faction_kill_counts[killer_faction] = \
        self.ctx.faction_kill_counts.get(killer_faction, 0) + 1
    
    # Check if one faction is dominating
    sanctum_kills = self.ctx.faction_kill_counts.get("Silver Sanctum", 0)
    syndicate_kills = self.ctx.faction_kill_counts.get("Shadow Syndicate", 0)
    
    if abs(sanctum_kills - syndicate_kills) > 10:
        # Trigger reinforcement event or buff losing faction
        pass
```

---

## Migration Requirements

**Alembic migration needed for Phase 1**:
```python
# Create: backend/daemons/alembic/versions/xxxxx_add_npc_faction_support.py

def upgrade():
    # Add faction_id to npc_templates
    op.add_column('npc_templates', sa.Column('faction_id', sa.String(), nullable=True))
    
    # Add patrol fields to npc_instances
    op.add_column('npc_instances', sa.Column('patrol_route', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('npc_instances', sa.Column('patrol_index', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('npc_instances', sa.Column('patrol_mode', sa.String(), nullable=False, server_default='loop'))
    op.add_column('npc_instances', sa.Column('home_room_id', sa.String(), nullable=True))
```

---

## Testing Checklist

**Phase 1 Tests**:
- [ ] NPC with faction_id loads from YAML
- [ ] Faction hostility matrix correctly identifies enemies
- [ ] NPC detects and targets enemy faction NPC in same room
- [ ] NPC vs NPC combat completes without errors
- [ ] Loot drops when NPC killed by another NPC
- [ ] XP only awarded when player kills NPC

**Phase 2 Tests**:
- [ ] NPC follows patrol route waypoints
- [ ] NPC loops back to start of patrol route
- [ ] NPC returns to patrol after combat ends
- [ ] Multiple NPCs spawn as coordinated group
- [ ] Group patrol has staggered starting positions

**Phase 3 Tests**:
- [ ] NPC calls only same-faction allies for help
- [ ] Heal abilities target same-faction NPCs
- [ ] NPCs stop chasing beyond territory limit
- [ ] Faction kill counts tracked correctly

---

## Files Summary

**Modified**:
- `backend/daemons/models.py` (NpcTemplate, NpcInstance)
- `backend/daemons/world_data/npcs/_schema.yaml`
- `backend/daemons/engine/systems/faction_system.py`
- `backend/daemons/engine/engine.py` (AI, combat, spawning)
- `backend/daemons/engine/behaviors/wandering.py`
- `backend/daemons/engine/loader.py`

**Created**:
- `backend/daemons/world_data/npc_spawns/_schema.yaml`
- `backend/daemons/alembic/versions/xxxxx_add_npc_faction_support.py`

**Test files**:
- `backend/tests/engine/test_faction_combat.py` (create)
- `backend/tests/engine/test_patrol_system.py` (create)
