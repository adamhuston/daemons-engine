# Phase 2: Patrol System Testing Guide

**Date**: December 20, 2024  
**Status**: Ready for Testing  
**Prerequisites**: Phase 1 (Faction Combat) must be complete and tested

---

## Overview

Phase 2 adds patrol route functionality for NPCs. NPCs can now:
- Follow predefined patrol routes with multiple waypoints
- Use different patrol modes (loop, bounce, once)
- Return to patrol after combat ends
- Spawn in coordinated groups with spacing

---

## Test Setup

### 1. Database Migration

Verify the patrol system migration ran successfully:

```bash
cd /Users/adam/Documents/GitHub/1126/backend
/Users/adam/Documents/GitHub/1126/.venv/bin/python -m alembic current
```

**Expected Output**: Should show revision `w6x7y8z9a0b1` (add_npc_patrol_system)

### 2. Reload World Data

Start the server and reload world data to load test spawns:

```bash
cd /Users/adam/Documents/GitHub/1126/backend
uvicorn daemons.main:app --reload
```

In the game client, use an admin command:
```
/admin reload
```

Or via API:
```bash
curl -X POST http://localhost:8000/admin/reload
```

---

## Test Scenarios

### Test 1: Basic Loop Patrol

**Objective**: Verify NPC follows a circular patrol route

**Setup**:
- NPC: "Sanctum Patrol Leader" in room_0_0_0
- Patrol Route: room_0_0_0 → room_1_0_0 → room_2_0_0 → room_1_0_0 → (repeat)
- Patrol Mode: loop
- Interval: 30 seconds

**Steps**:
1. Connect to game and navigate to room_0_0_0
2. Use `/look` to verify "Sanctum Patrol Leader" is present
3. Wait and observe - NPC should move every ~30 seconds
4. Follow the NPC through multiple patrol cycles
5. Verify it returns to starting room after completing circuit

**Expected Behavior**:
- NPC moves in predictable loop pattern
- Movement messages appear: "Sanctum Patrol Leader patrols north."
- After reaching room_2_0_0, NPC returns to room_0_0_0
- Patrol continues indefinitely

**Success Criteria**:
- ✓ NPC completes at least 2 full patrol loops
- ✓ Movement is consistent and predictable
- ✓ No errors in server logs

---

### Test 2: Bounce Patrol

**Objective**: Verify NPC bounces back and forth along patrol route

**Setup**:
- NPC: "Syndicate Scout" in room_0_0_1
- Patrol Route: room_0_0_1 ↔ room_1_0_1 ↔ room_2_0_1
- Patrol Mode: bounce
- Interval: 25 seconds

**Steps**:
1. Navigate to room_0_0_1
2. Verify "Syndicate Scout" is present
3. Watch NPC move: forward → reaches end → reverses → reaches start → repeats
4. Track at least 2 complete bounce cycles

**Expected Behavior**:
- NPC moves forward: 0 → 1 → 2
- NPC reverses: 2 → 1 → 0
- NPC bounces again: 0 → 1 → 2
- Pattern continues indefinitely

**Success Criteria**:
- ✓ NPC reaches both endpoints of patrol route
- ✓ Direction reverses correctly at endpoints
- ✓ No getting stuck or skipping waypoints

---

### Test 3: Group Patrol with Spacing

**Objective**: Verify multiple NPCs spawn with staggered starting positions

**Setup**:
- NPCs: 3x "a Sanctum Warrior" in room_0_1_0
- Patrol Route: room_0_1_0 → room_1_1_0 → room_2_1_0 → room_2_1_1
- Group Spacing: 1 waypoint offset
- Interval: 40 seconds

**Steps**:
1. Navigate to patrol route area (rooms 0_1_0, 1_1_0, 2_1_0, 2_1_1)
2. Use `/look` in each room to find the 3 warriors
3. Verify they start at different waypoints:
   - Warrior 1: waypoint 0 (room_0_1_0)
   - Warrior 2: waypoint 1 (room_1_1_0)
   - Warrior 3: waypoint 2 (room_2_1_0)
4. Watch them patrol - they should maintain spacing

**Expected Behavior**:
- 3 NPCs spawn immediately
- Each starts at a different waypoint
- NPCs move independently but follow same route
- Spacing is maintained throughout patrol

**Success Criteria**:
- ✓ All 3 NPCs spawn successfully
- ✓ NPCs start at different positions
- ✓ No clumping or collision issues

---

### Test 4: Stationary NPC (Control Test)

**Objective**: Verify NPCs without patrol routes stay stationary

**Setup**:
- NPC: "Sanctum Guard Captain" in room_0_2_0
- No patrol route configured

**Steps**:
1. Navigate to room_0_2_0
2. Verify NPC is present
3. Wait 5 minutes
4. Use `/look` - NPC should still be there

**Expected Behavior**:
- NPC remains in spawn room
- No movement messages
- NPC is responsive to combat/interaction

**Success Criteria**:
- ✓ NPC does not move
- ✓ NPC remains functional (can be attacked, etc.)

---

### Test 5: One-Time Patrol

**Objective**: Verify "once" mode patrols to end and stops

**Setup**:
- NPC: "Syndicate Messenger" in room_0_0_2
- Patrol Route: room_0_0_2 → room_1_0_2 → room_2_0_2 → room_2_1_2 → room_2_2_2
- Patrol Mode: once
- Interval: 20 seconds

**Steps**:
1. Navigate to room_0_0_2
2. Verify messenger spawns
3. Follow messenger through entire route
4. At room_2_2_2 (final waypoint), verify messenger stops

**Expected Behavior**:
- NPC moves through waypoints sequentially
- Upon reaching final waypoint (room_2_2_2), NPC stops
- NPC remains at final waypoint indefinitely
- No looping or backtracking

**Success Criteria**:
- ✓ NPC completes full route
- ✓ NPC stops at final waypoint
- ✓ No errors after patrol completes

---

### Test 6: Return to Patrol After Combat

**Objective**: Verify NPC returns to patrol route after combat ends

**Setup**:
- Use "Sanctum Patrol Leader" from Test 1
- Spawn hostile faction NPC in patrol path

**Steps**:
1. Wait for Patrol Leader to enter room_1_0_0
2. Use `/spawn npc_test_syndicate_rogue` to create enemy
3. Observe combat between the two NPCs
4. Wait for combat to end (one NPC dies)
5. Watch surviving NPC behavior

**Expected Behavior**:
- NPCs detect each other as hostile (faction warfare)
- Combat initiates automatically
- After one NPC dies:
  - Surviving NPC clears target
  - On next idle tick, checks if off patrol route
  - If off-route, pathfinds back to nearest waypoint
  - Resumes normal patrol

**Success Criteria**:
- ✓ Faction combat triggers correctly
- ✓ Surviving NPC returns to patrol route
- ✓ Patrol resumes normally after combat

---

### Test 7: Pathfinding to Patrol Route

**Objective**: Verify NPC can find way back to patrol if displaced

**Setup**:
- Use "Sanctum Patrol Leader" from Test 1
- Teleport NPC off patrol route

**Steps**:
1. Use admin command to move NPC to room off patrol:
   ```
   /admin teleport_npc <npc_id> room_3_3_3
   ```
2. Wait for next idle tick (~30-45 seconds)
3. Observe NPC behavior

**Expected Behavior**:
- NPC detects it's off patrol route
- NPC pathfinds to nearest waypoint using BFS
- NPC moves step-by-step toward patrol route
- Once on route, normal patrol resumes

**Success Criteria**:
- ✓ NPC finds path to patrol route
- ✓ Movement is logical (follows exits)
- ✓ Patrol resumes after returning

---

## Debugging Commands

### Check NPC Status
```
/admin inspect npc <npc_name>
```

Look for:
- `patrol_route`: Should list room IDs
- `patrol_index`: Current waypoint index
- `patrol_mode`: loop/bounce/once
- `home_room_id`: Spawn location

### Check Room Contents
```
/look
```

Shows all entities (players and NPCs) in current room

### Spawn Test NPCs Manually
```
/spawn npc_test_sanctum_warrior
/spawn npc_test_syndicate_rogue
```

### Teleport to Test Rooms
```
/teleport room_0_0_0
/teleport room_1_0_0
/teleport room_2_0_0
```

---

## Server Logs to Monitor

### Patrol System Logs
Look for lines starting with `[PATROL]`:
- `[PATROL] <NPC> moving north toward waypoint room_1_0_0`
- `[PATROL] <NPC> already on patrol route at waypoint 2`
- `[PATROL] <NPC> is off patrol route, returning...`

### Faction Combat Logs
Look for lines starting with `[FACTION]`:
- `[FACTION] <NPC> has faction: silver_sanctum`
- `[FACTION] Checking <NPC1> vs <NPC2>`
- `[FACTION] ✓ HOSTILE! <NPC1> will attack <NPC2>`

### Behavior System Logs
Look for lines starting with `[NPC]`:
- `[NPC] Scheduling wander for <NPC>`
- `[NPC] <NPC> wander enabled (behaviors=[...])`

---

## Expected Database State

After spawns load, verify database contains patrol data:

```sql
SELECT id, template_id, room_id, patrol_mode, patrol_route 
FROM npc_instances 
WHERE patrol_route != '[]';
```

**Expected Results**:
- 6 NPC instances with non-empty patrol_route
- patrol_mode values: loop, bounce, once
- patrol_route contains JSON arrays of room IDs

---

## Common Issues & Solutions

### Issue: NPCs don't spawn
**Cause**: Migration not run or spawn YAML not loaded  
**Solution**: Run `alembic upgrade head` and `/admin reload`

### Issue: NPCs spawn but don't move
**Cause**: Patrol behavior not registered or wander disabled  
**Solution**: Check `behaviors` list in NPC template, verify "patrols" behavior exists

### Issue: NPCs move randomly instead of following route
**Cause**: Other wander behaviors have higher priority  
**Solution**: "patrols" behavior has priority 150, should override others

### Issue: NPC gets stuck at a waypoint
**Cause**: Exit doesn't exist between waypoints  
**Solution**: Verify all rooms in patrol_route are connected

### Issue: Return-to-patrol doesn't work
**Cause**: Pathfinding fails or idle tick not firing  
**Solution**: Check server logs for [PATROL] messages, verify idle tick system running

---

## Success Criteria Summary

**Phase 2 is complete when**:
- ✓ All 7 test scenarios pass
- ✓ No errors in server logs during testing
- ✓ Patrol NPCs move predictably and consistently
- ✓ Group spawns work with proper spacing
- ✓ Return-to-patrol functions after combat
- ✓ Database contains patrol data correctly

---

## Next Steps

After Phase 2 testing:
1. **Phase 3**: Create actual battlefield area rooms and areas
2. **Phase 4**: Create production NPC templates for battlefield
3. **Phase 5**: Create battlefield spawn configurations
4. **Phase 6**: Polish and balance

---

## Notes

- Test spawns use `area_ethereal_nexus` for convenience
- Actual battlefield will use dedicated area_id
- Patrol intervals are shortened for testing (20-40s vs production 60-120s)
- Group sizes are small for testing (3 NPCs vs production 5-10 NPCs)

---

**Happy Testing! 🎮⚔️**
