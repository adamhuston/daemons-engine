# Phase 1 Faction Combat Testing Guide

## Implementation Status: ✅ COMPLETE

All code and database migrations have been successfully implemented and deployed.

## What Was Implemented

### Core Features
1. **NPC Faction Membership** - NPCs can now belong to factions via `faction_id` field
2. **Faction Hostility Matrix** - Factions can be marked as enemies (bidirectional)
3. **Automatic Faction Detection** - Silver Sanctum ↔ Shadow Syndicate configured as hostile
4. **NPC Combat AI** - NPCs detect and attack hostile faction members during idle ticks
5. **Loot System** - Verified working for NPC vs NPC combat

### Test NPCs Created

#### Silver Sanctum Warrior (`npc_test_sanctum_warrior`)
- **Level**: 5
- **Health**: 80 HP
- **Armor Class**: 14
- **Damage**: 8-15 (3.0s speed)
- **Faction**: `silver_sanctum`
- **Behavior**: Aggressive, never flees, guards position
- **Loot**: Ancient coins (70% chance), iron sword (15% chance)

#### Shadow Syndicate Rogue (`npc_test_syndicate_rogue`)
- **Level**: 5
- **Health**: 70 HP
- **Armor Class**: 15
- **Damage**: 6-18 (2.5s speed - faster attacks)
- **Faction**: `shadow_syndicate`
- **Behavior**: Aggressive, never flees, guards position
- **Loot**: Ancient coins (70% chance), iron dagger (15% chance)

## Testing Instructions

### Prerequisites
- Server must be running
- Admin account required for `/spawn` command
- Connect via client or telnet

### Step 1: Spawn Test NPCs

Connect to the game and navigate to any room, then:

```
spawn npc npc_test_sanctum_warrior
spawn npc npc_test_syndicate_rogue
```

**Note**: Commands do NOT use a slash (`/`) prefix in this MUD. Just type the command directly.

### Step 2: Observe Combat

**Expected Behavior:**
- Within 15-45 seconds (idle tick interval), one NPC should detect the other
- Combat should automatically initiate
- You should see combat messages like:
  - "Silver Sanctum Warrior attacks Shadow Syndicate Rogue!"
  - Damage rolls and hit/miss messages
  - "Shadow Syndicate Rogue attacks Silver Sanctum Warrior!"

### Step 3: Verify Death & Loot

**When one NPC dies:**
- Death message: "💀 [NPC name] has been slain by [killer name]!"
- Loot should drop to the room floor (ancient coins or weapon)
- Winner should continue to exist
- Loser should be removed from room (respawn after configured time)
- **No XP should be awarded** (both are NPCs)

### Step 4: Check Combat Mechanics

**Things to verify:**
- Combat messages show correct attacker and target
- Damage values are within expected ranges
- Armor class affects hit/miss (AC 14 vs AC 15)
- Attack speed differences (2.5s vs 3.0s)
- NPCs fight until one dies (fearless behavior)

### Step 5: Test Respawn (Optional)

Wait for the default respawn time (~5 minutes) and verify:
- Dead NPC respawns at spawn location
- Respawned NPC detects enemy and re-engages if still in same room

## Advanced Testing Scenarios

### Scenario A: NPC vs Player Combat
Spawn one faction NPC and attack it as a player:
- NPC should retaliate (already implemented)
- Verify loot drops when NPC dies
- Verify XP is awarded to player

### Scenario B: Multiple NPCs per Faction
Spawn 2 Sanctum warriors and 2 Syndicate rogues:
- Verify multiple targets are detected
- Check if NPCs coordinate or attack randomly
- Observe group combat dynamics

### Scenario C: Faction + Aggro_on_Sight
Test that NPCs still attack players with aggro_on_sight enabled:
- Both test NPCs have aggressive behavior
- Should attack both hostile NPCs AND players

### Scenario D: Room Transitions
1. Spawn both NPCs in Room A
2. Let combat start
3. `/teleport` one NPC to Room B
4. Verify combat stops cleanly
5. Move them back together, verify re-engagement

## Known Behaviors

### Combat Timing
- **Idle tick**: Every 15-45 seconds (randomized)
- **First detection**: May take up to 45 seconds after spawn
- **Combat speed**: Based on weapon speed (2.5s or 3.0s per attack)

### Target Selection
- NPCs prioritize faction enemies over aggro_on_sight players
- Only first hostile target is engaged (no multi-target)
- NPCs already in combat won't switch targets

### Limitations (Phase 1)
- No patrol routes yet (coming in Phase 2)
- NPCs don't call for help across factions
- No strategic AI (just first-detected target)
- Fixed spawn positions (no waypoints)

## Troubleshooting

### NPCs Not Fighting
- **Check idle tick timing**: Wait at least 45 seconds
- **Verify factions loaded**: Check server logs for "Loaded factions"
- **Check hostility config**: Should see "Setting faction hostility" in logs
- **Verify NPCs alive**: Use `/look` to check they're both present

### Combat Seems Wrong
- **Check weapon speeds**: Rogue attacks faster (2.5s vs 3.0s)
- **Check AC differences**: Warrior has lower AC (14 vs 15)
- **Verify damage ranges**: Random within min-max values
- **Check behaviors**: Both should be fearless (never flee)

### No Loot Drops
- **Verify death occurred**: Check for death message
- **Check room**: Use `/look` to see items on ground
- **Loot is chance-based**: Ancient coins = 70% chance
- **Check templates**: Verify loot_table in YAML files

## Success Criteria

Phase 1 is successful when:
- ✅ NPCs spawn with faction_id successfully
- ✅ NPCs detect each other as hostile
- ✅ Combat automatically initiates
- ✅ Combat messages display correctly
- ✅ Winner survives, loser dies
- ✅ Loot drops from dead NPC
- ✅ No XP awarded (NPC vs NPC)
- ✅ Respawn works correctly

## Next Steps: Phase 2

Once Phase 1 is validated, implement:
1. **Patrol Routes** - NPCs move along waypoints
2. **Waypoint System** - Define patrol paths in YAML
3. **Combat While Moving** - NPCs engage during patrols
4. **Patrol Behaviors** - Different patrol patterns

## Files Modified

- `backend/daemons/models.py` - Added faction_id to NpcTemplate
- `backend/daemons/engine/world.py` - Added faction_id to WorldNpcTemplate
- `backend/daemons/engine/loader.py` - Load faction_id from database
- `backend/daemons/engine/engine.py` - NPC targeting AI
- `backend/daemons/engine/systems/faction_system.py` - Hostility matrix
- `backend/daemons/alembic/versions/v5w6x7y8z9a0_add_npc_faction_id.py` - Migration
- `backend/daemons/world_data/npcs/test_sanctum_warrior.yaml` - Test NPC
- `backend/daemons/world_data/npcs/test_syndicate_rogue.yaml` - Test NPC

## Testing Completed By

- **Date**: ___________
- **Tester**: ___________
- **Result**: [ ] Pass  [ ] Fail  [ ] Needs Revision
- **Notes**:

