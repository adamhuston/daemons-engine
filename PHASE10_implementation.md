# Phase 10 Implementation Plan

## Quick Overview

Three sequential phases building social systems on top of existing EventDispatcher and player_flags infrastructure.

---

## Phase 10.1: Groups & Tell Commands 

### Core Implementation
1. **GroupSystem** (`systems/group_system.py`)
   - In-memory group storage with O(1) lookups via `player_to_group` mapping
   - Auto-disband after 30 min inactivity
   - Broadcast method for group messages

2. **Commands** (`commands/social/`)
   - `group create|invite|leave|disband|members|rename`
   - `tell|reply|ignore|unignore`
   - `follow|unfollow|followers|following`
   - `yell` (broadcast to adjacent rooms)

3. **Event System**
   - Add `GroupMessageEvent`, `TellEvent`, `FollowEvent` to EventDispatcher
   - Route group messages → all members
   - Route tells → sender + recipient only
   - Follow triggers auto-move on room change

4. **Player Model**
   - Extend `player_flags` with: `group_id`, `followers`, `following`, `ignored_players`, `last_tell_from`

### Success Criteria
- ✅ Players form/join/leave groups
- ✅ Group messages are member-only
- ✅ Tell conversations work bidirectionally
- ✅ Follow mechanics prevent AFK abuse
- ✅ Stale groups auto-disband

---

## Phase 10.2: Clans & Persistence

### Database Setup
```sql
CREATE TABLE clans (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE,
    leader_id TEXT NOT NULL,
    description TEXT,
    level INT DEFAULT 1,
    experience INT DEFAULT 0,
    created_at FLOAT,
    FOREIGN KEY (leader_id) REFERENCES players(id)
);

CREATE TABLE clan_members (
    id TEXT PRIMARY KEY,
    clan_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    rank TEXT NOT NULL,  -- leader|officer|member|initiate
    joined_at FLOAT,
    contribution_points INT DEFAULT 0,
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id),
    UNIQUE(clan_id, player_id)
);
```

### Core Implementation
1. **ClanSystem** (`systems/clan_system.py`)
   - Load clans from DB at startup
   - CRUD operations with persistence
   - Rank-based permission checks
   - Broadcast method for clan messages

2. **Models** (`models/clan.py`)
   - Clan ORM model with relationships
   - ClanMember tracking ranks and joined_at

3. **Commands** (`commands/social/clan.py`)
   - `clan create|invite|leave|members|info|promote|disband`
   - Permission enforcement (leader/officer only)
   - `clan-tell` (ctell) for clan chat

4. **Player Model**
   - Add `clan_id` to `player_flags`

### Success Criteria
- ✅ Clans persist across server restarts
- ✅ Rank hierarchy enforced
- ✅ Only leader/officer can invite/promote
- ✅ Clan chat reaches all members online

---

## Phase 10.3: Factions

### Database Setup
```sql
CREATE TABLE factions (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE,
    description TEXT,
    color TEXT DEFAULT '#FFFFFF',
    emblem TEXT,
    player_joinable BOOLEAN,
    max_members INT,
    require_level INT,
    created_at FLOAT
);

CREATE TABLE faction_npc_members (
    faction_id TEXT NOT NULL,
    npc_template_id TEXT NOT NULL,
    PRIMARY KEY (faction_id, npc_template_id),
    FOREIGN KEY (faction_id) REFERENCES factions(id) ON DELETE CASCADE
);
```

### Core Implementation
1. **FactionSystem** (`systems/faction_system.py`)
   - Load factions from `world_data/factions/*.yaml`
   - Cache NPC faction memberships for O(1) lookup
   - Reputation tracking (-100 to +100)
   - 5 alignment tiers → NPC behavior changes

2. **YAML Factions** (`world_data/factions/`)
   - Define 3-5 example factions with NPC members
   - Pattern matches Phase 9 YAML loading

3. **Commands** (`commands/social/faction.py`)
   - `faction list|info|join|leave|standing`
   - `faction-tell` (ftell) for faction broadcast

4. **NPC Integration**
   - Update NPC templates with `factions` field
   - In combat: Check if player is faction enemy → NPC attacks
   - In dialogue: Adjust responses based on standing

5. **Reputation Hooks**
   - Quest completion: Adjust faction standing
   - NPC defeat: Decrease standing with NPC's faction
   - Commands modify `player_flags["faction_standings"]`

### Success Criteria
- ✅ Factions load from YAML at startup
- ✅ Players join/leave factions
- ✅ NPC behavior changes based on player standing
- ✅ Reputation tiers trigger mechanical effects
- ✅ Faction chat works correctly

---

## Cross-Phase Integration

### Engine Startup
```python
# In WorldEngine.__init__():
self.group_system = GroupSystem()
self.clan_system = ClanSystem()
self.faction_system = FactionSystem()

# Async initialization:
await self.clan_system.load_clans_from_db()
await self.faction_system.load_factions_from_yaml("world_data/factions/")

# Periodic cleanup:
self.add_ticker(5 * 60, self.group_system.clean_stale_groups)
```

### Event Routing
```python
# EventDispatcher routes based on event type:
GroupMessageEvent → room.broadcast() to group members only
TellEvent → direct to sender + recipient
FollowEvent → auto-move followers on player move
FactionMessageEvent → room.broadcast() to all faction members online
```

### Player Commands
Register all commands in `CommandRegistry`:
```python
registry.register("group", GroupCreateCommand, ...)
registry.register("tell", TellCommand, ...)
registry.register("clan", ClanCreateCommand, ...)
registry.register("faction", FactionListCommand, ...)
```

---

## Key Implementation Details

### No N+1 Queries
- GroupSystem uses `player_to_group` dict for O(1) lookup
- ClanSystem caches clans in memory, lazy-loads on demand
- FactionSystem pre-caches NPC faction memberships at startup

### Backward Compatible
- All social fields optional in `player_flags`
- Existing players unaffected (solo play unchanged)
- Factions loaded from YAML (not player-created initially)

### Permission Model
| Action | Group | Clan | Faction |
|--------|-------|------|---------|
| Invite | Leader only | Leader/Officer | N/A (auto-join) |
| Promote | N/A | Leader/Officer | N/A |
| Chat | Members only | Members only | Members only |
| Leave | Anyone | Anyone | Anyone |
| Disband | Leader | Leader | Admin only |

---

## Testing (100+ tests total)

### Phase 10.1 (40+ tests)
- GroupSystem CRUD, stale detection, broadcasting
- Tell routing, reply, ignore list
- Follow mechanics, circular relationships

### Phase 10.2 (35+ tests)
- ClanSystem persistence, rank enforcement
- Invitation/promotion/removal, edge cases

### Phase 10.3 (40+ tests)
- Faction loading, standing calculation, tiers
- NPC behavior changes, reputation hooks
- Faction chat routing

---

## Deliverables Checklist

### Phase 10.1 ✅ COMPLETE
- [x] GroupSystem 
- [x] Group commands 
- [x] Tell/reply/ignore commands 
- [x] Follow commands 
- [x] Yell command 
- [x] Event types + routing 
- [x] Tests (80+ cases)
- [x] Documentation (COMPLETION, QUICKREF, INTEGRATION guides)

### Phase 10.2 ✅ COMPLETE
- [x] Migration file (i1j2k3l4m5n6_phase10_2_clans.py) 
- [x] Clan models (Clan, ClanMember with relationships)
- [x] ClanSystem (load_clans_from_db, CRUD, rank permissions)
- [x] Clan commands (create, invite, join, leave, promote, members, info, disband)
- [x] Clan event routing (clan_message scope in EventDispatcher)
- [x] WorldEngine integration (async loading, command registration)
- [x] Tests (50+ cases)

### Phase 10.3 ✅ COMPLETE
- [x] Migration file (j2k3l4m5n6o7_phase10_3_factions.py)
- [x] Faction models (Faction, FactionNPCMember with relationships)
- [x] FactionSystem (load from YAML, CRUD, reputation tracking, alignment tiers)
- [x] Faction commands (list, info, join, leave, standing)
- [x] Faction event routing (faction_message scope in EventDispatcher)
- [x] YAML faction definitions (4 factions with NPC members)
- [x] WorldEngine integration (YAML loading at startup, command registration)
- [x] Tests (45+ cases)

---

## Build

```
Phase 10.1 (Groups, Tells, Follow)
  Mon: GroupSystem + tests
  Tue-Wed: Commands + integration
  Thu: EventDispatcher routing + WebSocket
  Fri: Edge cases, documentation

Phase 10.2 (Clans)
  Mon: Database + models
  Tue-Wed: ClanSystem + commands
  Thu-Fri: Integration + tests

Phase 10.3 (Factions)
  Mon-Tue: FactionSystem + YAML loading
  Wed: Faction commands
  Thu: NPC integration + combat changes
  Fri: Testing + refinement
```

**End file**