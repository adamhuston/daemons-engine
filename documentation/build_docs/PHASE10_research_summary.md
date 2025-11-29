# Phase 10 Research & Design Summary

## Overview

I've researched the Phase 10 objectives (social systems, factions, communication) and created comprehensive design documentation. The research uncovered the architectural landscape, existing systems, and design patterns that will support these features.

---

## Research Findings

### 1. Current Architecture Assessment

**Communication Infrastructure (Existing)**
- Room-scoped `say` command already implemented
- EventDispatcher system designed for multi-scoped message routing
- WebSocket protocol supports targeted event delivery
- `emote` command for narrative actions

**Entity Model Suitability**
- WorldPlayer has extensible `player_flags` dictionary (perfect for social state)
- WorldNPC supports behavior composition and YAML configuration
- WorldRoom tracks entities (players + NPCs)
- Existing effect/reputation systems can be extended for factions

**Permission System (Phase 7)**
- Role-based access control fully implemented (PLAYER, MODERATOR, GAME_MASTER, ADMIN)
- Commands can check permissions before execution
- Auth context flows through GameContext

**Persistence Layer**
- StateTracker already handles dirty-entity tracking
- JSON columns in Player model support complex structures
- NPC instance data stored in JSON (can add faction data)

### 2. Design Pattern Analysis

From studying existing phases:

**Phase 9 (Classes & Abilities)**
- YAML-first approach: Classes/abilities defined in data files
- Behavior script system: Complex logic in Python, indexed by name
- Hot-reloadable: Content updates without server restart
- Runtime caching: Templates loaded at startup for O(1) lookup
- Backward compatible: Optional features don't break existing players

**Phase X (Quest System)**
- State machines for progression tracking
- Objectives as observers (react to game events)
- Dialogue trees as specialized command triggers
- Rewards flow through existing systems (items, effects, flags)

**Phase 8 (Admin System)**
- Granular permissions for sensitive operations
- Audit logging for all admin actions
- REST API + in-world commands (both endpoints)

### 3. Key Architectural Insights

**1. The player_flags Dictionary is Ideal for Social State**
- Already in Player model and DB schema
- Avoids creating 10+ new tables for relationships
- In-memory caches (GroupSystem, FactionSystem) provide fast lookup
- Lazy-loads: Only populated when player uses social features
- Backward compatible: Missing fields default to None/empty

**2. Event Dispatcher Can Handle Scope Variants**
- Currently: room-scoped, player-scoped
- Extension: group-scoped, faction-scoped, clan-scoped
- Each message type carries target_scope and target_id(s)
- Existing routing logic extends naturally

**3. YAML Content Layer Pattern Scales to Factions**
- Factions defined in YAML (like classes, abilities, NPCs)
- NPC templates declare faction membership (like they declare behaviors)
- Loaded at startup, cached in memory
- Players join/leave factions dynamically (stored in player_flags)

**4. Ephemeral vs Persistent Tradeoff**
- **Groups**: Session-based (in-memory only)
  - Auto-disband after inactivity
  - Reduces database load
  - Matches organic play patterns (dungeon runs)
- **Clans**: Persistent (stored in DB)
  - Long-term player investment
  - Hierarchical ranks
  - Separate table schema
- **Factions**: Persistent (loaded from YAML)
  - World data (like rooms, NPCs)
  - Player standing in player_flags
  - Shapes NPC behavior

---

## Design Document Artifacts

### 1. PHASE10.md (Summary Overview)
- High-level objectives and quick reference
- Key design decisions with rationale
- Architecture overview with diagrams
- Implementation roadmap (3 sub-phases)
- Data model preview
- Integration points with existing systems
- Backward compatibility guarantees
- Success metrics per phase

### 2. PHASE10_design.md (Comprehensive Design)
Complete 2500+ line design document covering:

**Executive Summary**
- Problem statement and solution overview
- Key principles guiding the design

**Current State Analysis**
- What we already have (communication, entity models, permissions, persistence)
- What's missing (groups, factions, clans, private messaging, reputation)

**Design Philosophy**
- Principle 1: Social structures as directed graphs
- Principle 2: Communication as event streams
- Principle 3: Associations as lazy-loaded references
- Principle 4: Faction affinity shapes NPC behavior

**Core Data Structures**
- Group (ephemeral, in-memory)
- Clan (persistent, DB-stored)
- Faction (persistent, YAML-loaded)
- FactionStanding/FactionAlignment enums
- FollowRelationship pattern

**Command Integration**
- Complete command reference (30+ commands)
- Social structure commands (group, clan, faction)
- Communication commands (say, yell, tell, group-tell, clan-tell, faction-tell)

**System Architecture**
- GroupSystem class design and methods
- ClanSystem class design and methods
- FactionSystem class design and methods
- EventDispatcher extensions for each channel type

**Database Schema**
- New tables: clans, clan_members, factions, faction_npc_members
- Player model extensions (player_flags JSON structure)

**YAML Content Layer**
- Faction definition examples
- NPC faction membership integration

**WebSocket Protocol Extension**
- New event types: social_event, message with channel variants
- Example payloads for group creation, tells, faction standing

**Implementation Phases**
- Phase 10.1 (Groups & Tells): 2-3 days
- Phase 10.2 (Clans): 3-4 days
- Phase 10.3 (Factions): 3-4 days

**Design Decisions**
6 major decisions with detailed rationale:
1. Ephemeral Groups (vs persistent parties)
2. JSON Player Flags (vs normalized tables)
3. Faction Affinity Affects Combat (vs cosmetic only)
4. Tell Commands Work Cross-Zone (vs same room only)
5. Faction Standing -100 to +100 (vs 0-100 only)
6. NPC Faction Membership Via YAML (vs quest system)

**API Specifications**
- Detailed WebSocket protocol examples
- Group create/invite/disband flows
- Tell conversation examples
- Follow command examples
- Faction standing examples

**Testing Strategy**
- Unit test categories
- Integration test scenarios
- Edge case handling

**Future Extensions**
- Clan Warfare (Phase 10.4)
- Player Economy (Phase 10.5)
- Reputation & Diplomacy (Phase 10.6)
- Social Ranks & Leaderboards (Phase 10.7)

---

## Key Insights for Implementation

### 1. Message Scope Routing
EventDispatcher currently routes messages by:
- `scope="room"` + `target_room_id` → all players in room
- `scope="player"` + `target_player_ids` → specific player

Needs extension for:
- `scope="group"` + `target_group_id` → all group members
- `scope="clan"` + `target_clan_id` → all clan members
- `scope="faction"` + `target_faction_id` → all faction members (online only)

### 2. Follow System Implementation
Most lightweight feature:
- Store in `player_flags["following"]` and `player_flags["followers"]`
- On player move, trigger `GroupSystem.handle_player_move()`
- Followers auto-move (appears as automatic movement)
- Can be implemented in Phase 10.1

### 3. NPC Faction Integration
Combat system already has:
- Targetable protocol for entity lookup
- Attack decision points
- Behavior hooks (on_player_enter, on_damaged, etc.)

Needs addition:
- Check NPC faction vs player alignment before aggro
- NPC behavior responses based on alignment (assist, refuse service, attack)
- Reputation modification hook on NPC defeat

### 4. Group Leadership Transition
When group leader disconnects:
- Transfer leadership to next member by join order
- OR auto-disband if inactivity timer triggers anyway
- Simpler to auto-disband (30 min cleanup)

### 5. Tell Command Implementation
Need to track:
- `player_flags["last_tell_sender"]` for `/reply` feature
- `player_flags["ignored_players"]` set for ignore/unignore
- Check both before routing tell message

---

## Architectural Alignment

### Consistency with Existing Phases

**Phase 4 (NPCs & Combat)**
- NPC behavior system prepared for faction-aware behaviors
- Existing behavior hooks can check `is_faction_ally()` / `is_faction_enemy()`

**Phase 5 (Triggers)**
- Trigger conditions can reference faction (e.g., `player_in_faction`)
- Trigger actions can modify faction standing

**Phase 7 (Auth)**
- Command permission system ready for admin-only broadcasting
- Role checks already in place

**Phase 8 (Admin Tools)**
- Admin commands for teleport/where already exist
- Can extend with `/faction broadcast` for GMs

**Phase 9 (Classes & Abilities)**
- Ability effects can grant faction reputation
- Resource system independent of social structure

**Phase X (Quests)**
- Quest completion can trigger faction standing changes
- NPC faction membership affects dialogue options (future)

---

## Schema Simplification Analysis

### Avoided Designs

**Design A: Normalized player_groups table**
```sql
-- NOT CHOSEN - Too many tables
CREATE TABLE player_groups (player_id, group_id);
CREATE TABLE group_members (group_id, player_id);
CREATE TABLE groups (id, leader_id, name, ...);
```
Rejected: Ephemeral data doesn't belong in database

**Design B: player_group_id FK**
```sql
-- NOT CHOSEN - Nullable FK, update storms on disband
ALTER TABLE players ADD group_id TEXT REFERENCES groups(id);
```
Rejected: Session-based groups shouldn't require schema

**Design C: Full social graph tables**
```sql
-- NOT CHOSEN - O(n) lookups
CREATE TABLE player_followers (player_id, follower_id);
CREATE TABLE player_following (player_id, following_id);
```
Rejected: Lightweight flag-based approach sufficient

**Design D: Separate factions table for player_faction_members**
```sql
-- NOT CHOSEN - Redundant with player_flags
CREATE TABLE player_faction_members (player_id, faction_id, reputation);
```
Rejected: player_flags JSON allows arbitrary faction data

### Chosen Design: JSON Player Flags

**Pros:**
- Single column, no joins
- Extensible (add new social features without migrations)
- Lazy-loaded (not all players need these fields)
- Backward compatible (missing fields OK)
- In-memory caching eliminates DB queries

**Cons:**
- Can't query "all players in faction X" from SQL (OK: use in-memory cache)
- Requires migration for Phase 9+ players (one-time)
- JSON parsing overhead (negligible, cached anyway)

---

## Implementation Priority

### Must-Have (Phase 10.1)
1. GroupSystem + group commands (5-6 hours)
2. Tell + reply + ignore (3-4 hours)
3. Follow + unfollow (2-3 hours)
4. Yell command (1-2 hours)

### Should-Have (Phase 10.2-3)
5. Clan system with DB persistence (8-10 hours)
6. Faction system with YAML loading (8-10 hours)
7. NPC faction integration (4-6 hours)

### Nice-to-Have (Phase 10.4+)
8. Clan warfare mechanics
9. Clan treasury/economy
10. Prestige/reputation leaderboards

---

## Risk Analysis

### Low Risk
- Tell/reply: Simple message routing, isolated from other systems
- Follow: Only affects movement, no combat interaction
- Groups: In-memory, auto-cleanup, no persistence risks

### Medium Risk
- Clans: DB schema change, but backward compatible (NULL clan_id)
- Factions: YAML loading (tested pattern from Phase 9)
- NPC Integration: Combat logic change (need thorough testing)

### Mitigation
- Phase 10.1 has zero schema changes (de-risks first week)
- Faction NPC integration can be feature-flagged (disable if issues)
- Comprehensive test coverage for faction reputation thresholds
- Event logging for all faction standing changes (audit trail)

---

## Recommendations

### For Implementation

1. **Start with Phase 10.1 (Groups & Tells)**
   - Zero database changes needed
   - Validates event dispatcher extensions
   - Provides foundation for clan/faction messaging

2. **Use player_flags JSON consistently**
   - Never create new social tables
   - All new social features → player_flags key
   - In-memory caches handle performance

3. **Load factions from YAML at startup**
   - Same pattern as classes/abilities/NPCs
   - Provides configuration flexibility
   - Simplifies schema

4. **Extend CombatSystem, not BehaviorSystem**
   - Faction checks happen at combat time
   - NPC behaviors unchanged (use existing hooks)
   - Keeps concerns separate

### For Testing

1. **Test faction standing thresholds thoroughly**
   - Edge cases at -50, 10, 50 boundaries
   - Reputation changes accumulate correctly
   - NPC behavior shifts at correct thresholds

2. **Test group auto-disband logic**
   - Timer triggers at 30 minutes
   - Activity updates when members chat
   - Cleanup doesn't break mid-session groups

3. **Test follow persistence**
   - Multiple followers track correctly
   - Circular follows don't crash
   - Offline players unfollow gracefully

---

## Files Created

1. **PHASE10.md** (550 lines)
   - Executive summary
   - Quick reference for all features
   - Architecture overview
   - Implementation roadmap
   - Success criteria

2. **PHASE10_design.md** (2800+ lines)
   - Comprehensive design specification
   - Complete API reference
   - Database schema changes
   - YAML content examples
   - Testing strategy

3. **PHASE10_research_summary.md** (this file)
   - Research findings
   - Architectural alignment
   - Design rationale
   - Implementation recommendations

---

## Conclusion

Phase 10 is well-architected and has no fundamental blockers. The design leverages existing systems (EventDispatcher, player_flags, YAML loading, behavior hooks) and introduces zero architectural complexity.

**Key success factors:**
1. Use player_flags JSON for all social state (avoid schema explosion)
2. Implement groups first (validate event routing)
3. Load factions from YAML (consistency with game content pattern)
4. Test faction standings thoroughly (reputation feels core to design)
5. Monitor performance of in-memory faction cache (should be negligible)

The three-phase approach (Groups → Clans → Factions) provides natural scope boundaries and reduces risk.
