# Phase 10: Social Systems, Factions, and Communication

> **For detailed design document, see [PHASE10_design.md](./PHASE10_design.md)**

## Quick Reference

**Phase 10 Objectives:**

### Player Association
- **Groups** – Ephemeral parties for coordinated team play (auto-disband on inactivity)
- **Clans** – Persistent player guilds with hierarchical ranks (leader → officer → member)
- **Factions** – World-wide organizations with reputation standings

### NPC Association
- **Faction membership** – NPCs loaded with faction affiliation from YAML
- **Faction allies/enemies** – NPC behavior shaped by player faction standing
- **Combat consequences** – Enemy faction NPCs attack, allied NPCs assist

### Player Communication
- **`say <message>`** – Room-scoped chat (existing, continues from Phase 4)
- **`yell <message>`** – Extended-range broadcast (adjacent rooms)
- **`tell <player> <message>`** – Private messaging with reply feature
- **`group-tell <message>` / `gtell`** – Group-only chat
- **`clan-tell <message>` / `ctell`** – Clan-wide chat
- **`faction-tell <faction> <message>`** – Faction broadcast
- **`follow <player>`** – Auto-follow another player (move with them)

---

## Key Design Decisions

1. **Ephemeral Groups**: Groups auto-disband after 30 min inactivity (reduces DB bloat)
2. **JSON Player Flags**: Social state stored as `player.player_flags` (avoids schema explosion)
3. **Faction Affinity Shapes Combat**: NPCs detect player faction standing and adjust behavior
4. **Cross-Zone Tells**: Private messages work anywhere (enables frictionless coordination)
5. **Reputation Scale**: -100 to +100 with 5 alignment tiers (HOSTILE → ALLIED)
6. **YAML Faction Definitions**: NPC faction membership declared in YAML (immutable, cached)

---

## Architecture Overview

### Three-Layer Social System

```
┌─────────────────────────────────────────┐
│ Player-Centric State (player_flags)     │
│ - group_id, clan_id, followers, etc.    │
└────────────────┬────────────────────────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
┌────────┐  ┌────────┐  ┌──────────┐
│ Groups │  │ Clans  │  │ Factions │
│ (Mem)  │  │ (DB)   │  │ (YAML)   │
└────────┘  └────────┘  └──────────┘
    │            │            │
    └────────────┼────────────┘
                 │
                 ▼
    ┌──────────────────────────────┐
    │ EventDispatcher Extensions   │
    │ tell, group-tell, faction... │
    └──────────────────────────────┘
```

### Event Scoping

| Channel | Scope | Recipients | Persistence |
|---------|-------|-----------|-------------|
| `say` | Room | All in room | Ephemeral |
| `yell` | Extended (2-3 rooms) | Adjacent rooms | Ephemeral |
| `tell` | Private | Single player | Ephemeral |
| `group-tell` | Group | Group members | Ephemeral |
| `clan-tell` | Global | Clan members | Ephemeral |
| `faction-tell` | Global | Faction members | Ephemeral |
| `broadcast` | Global | All players | Ephemeral (admin) |

---

## Implementation Roadmap

### Phase 10.1: Groups & Tells (MVP) – Week 1
- GroupSystem in-memory manager
- `group create|invite|leave|disband|members|rename` commands
- `tell <player> <message>` with reply/ignore
- `follow <player>` / `unfollow` mechanics
- `yell <message>` command (adjacent rooms)
- **Effort**: 2-3 days

### Phase 10.2: Clans (Secondary) – Week 2
- Clan database tables & persistence
- ClanSystem with hierarchical ranks
- `clan create|invite|leave|promote|disband` commands
- `clan-tell` broadcast
- **Effort**: 3-4 days

### Phase 10.3: Factions (Terminal) – Week 3
- Faction YAML loading & database
- FactionSystem with reputation tracking
- `faction join|leave|standing` commands
- `faction-tell` broadcast
- **NPC Integration**: Faction-based combat behavior
- **Effort**: 3-4 days

---

## Data Model Preview

### Player Flags Structure

```python
player.player_flags = {
    "group_id": "group-uuid" | None,
    "clan_id": "clan-uuid" | None,
    "followers": ["player-id-1", "player-id-2"],
    "following": ["player-id-1"],
    "faction_standings": {
        "crimson_guard": {
            "reputation": 42,      # -100 to +100
            "joined_at": 1234567890.0,
            "rank": None
        },
        "council_of_elders": {
            "reputation": -15,
            "joined_at": None      # Never joined
        }
    },
    "ignored_players": ["player-id-1"],
    "last_tell_sender": "player-id-1"  # For /reply
}
```

### Group (Ephemeral, In-Memory)

```python
@dataclass
class Group:
    id: str
    leader_id: str
    name: str = "Unnamed Party"
    member_ids: Set[str] = field(default_factory=set)
    created_at: float
    last_activity: float
    INACTIVITY_TIMEOUT = 1800.0  # 30 minutes
```

### Faction (Persistent, YAML-Loaded)

```yaml
# world_data/factions/crimson_guard.yaml
id: crimson_guard
name: Crimson Guard
description: The elite military protecting the realm
color: "#CC0000"
emblem: "⚔️"
player_joinable: true
max_members: 100
require_level: 5
npc_members:
  - crimson_captain
  - crimson_soldier
  - crimson_mage
```

---

## Integration Points

### WorldEngine
- Register commands: `group`, `clan`, `faction`, `tell`, `yell`, `follow`
- Hook player movement: Auto-move followers
- Hook player disconnect: Clean up groups, unfollow relationships

### EventDispatcher
- Extend with group/faction/tell event types
- Support multi-recipient routing (group members, faction members)

### CombatSystem
- Check faction alignment before NPC attack
- NPC behavior adjusts based on player faction standing
- Reputation changes on NPC defeat

### StateTracker
- Mark player_flags dirty when social state changes
- Periodic saves preserve clan memberships

### TriggerSystem
- Condition: `player_in_faction <faction>`
- Action: `modify_faction_standing <player> <faction> <delta>`

---

## Backward Compatibility

✅ Existing solo players unaffected (all features opt-in)
✅ say/emote commands unchanged
✅ No combat logic changes until faction integration (Phase 10.3)
✅ player_flags missing fields default gracefully
✅ Can run Phase 9 content without social system

---

## Success Metrics

### Phase 10.1
- Players successfully create/join/leave groups
- Group chat messages route only to members
- Tell conversation works bidirectionally
- Players can follow/unfollow others
- Yell broadcasts to correct rooms

### Phase 10.2
- Clans persist across server restarts
- Rank hierarchy enforced (leader/officer/member)
- Clan chat reaches all members globally
- Promotion/demotion works correctly

### Phase 10.3
- Factions load from YAML at startup
- Player standing affects NPC behavior
- NPCs in enemy faction attack on sight
- Reputation changes integrate with quest system
- Faction chat broadcasts correctly

---

## References

- **Detailed Design**: [PHASE10_design.md](./PHASE10_design.md)
- **Architecture**: [ARCHITECTURE.md](./ARCHITECTURE.md) – Systems section
- **EventDispatcher**: `backend/app/engine/systems/events.py`
- **WorldEngine**: `backend/app/engine/engine.py`
- **World Model**: `backend/app/engine/world.py`
