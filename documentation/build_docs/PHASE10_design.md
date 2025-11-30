# Phase 10 Design Document: Social Systems, Factions, and Communication

## Executive Summary

Phase 10 introduces comprehensive social systems that transform the dungeon from a collection of isolated players into a living community. Players can form groups, join factions, establish clans, and communicate through multiple channels. NPCs become social entities with faction allegiances and relationship systems. This phase builds on the existing player/NPC entity model and event system to create meaningful social interactions without introducing architectural complexity.

**Key principles:**
- **Event-driven communication**: All messaging flows through the existing EventDispatcher
- **Permission-based channels**: Access to group/faction/clan chat requires membership
- **Faction neutral system**: NPCs and players can join multiple factions with standing/reputation
- **Scalable group mechanics**: Groups auto-disband on inactivity, follow systems prevent AFK harassment
- **YAML-first associations**: Faction definitions and NPC faction membership loaded from data files
- **Backward compatible**: Existing solo players function unchanged; social features are opt-in

---

## Current State Analysis

### What We Already Have

**Communication Infrastructure:**
- `say` command: Broadcasts to all players in the same room
- `emote` command: Narrative actions visible to room occupants
- EventDispatcher system with room-scoped and player-specific message routing
- WebSocket protocol supporting targeted event delivery

**Entity Models:**
- WorldPlayer with `room_id`, `name`, `id`, and persistent `player_flags` dictionary
- WorldNPC with templates, behaviors, and instance-specific configuration
- Extensible `player_flags` dictionary for persistent state
- Character sheet and resource systems (Phase 9)

**Permission System (Phase 7):**
- Role-based access control (PLAYER, MODERATOR, GAME_MASTER, ADMIN)
- Permission enum for granular access
- Auth context available in command handlers

**Persistence:**
- StateTracker system with dirty-entity tracking
- JSON columns in Player model (`data`, `player_flags`, `quest_progress`)
- NPC instance data stored in JSON columns

### The Gap

While we have room-scoped communication, we lack:
- **Group/party mechanics** for coordinated team play
- **Faction system** for world-wide player/NPC organizations
- **Clan system** for long-term player guilds
- **Private messaging** between players
- **Broadcast channels** (global, faction, clan, group)
- **Follow/unfollow** mechanics for player interactions
- **NPC faction allegiance** affecting combat and dialogue
- **Reputation tracking** for faction standing

---

## Design Philosophy

### Principle 1: Social Structures as Directed Graphs

Player relationships form graph structures:
- **Groups**: Temporary, acyclic (players connected to group leader)
- **Clans**: Persistent, hierarchical (members → officers → leader)
- **Factions**: Global, many-to-many (players and NPCs can belong to multiple)

```
Groups (Ephemeral):
  Player A (leader) ←→ Player B
                   ←→ Player C

Clans (Persistent):
  Leader
    ├── Officer 1
    │   └── Member A
    │   └── Member B
    └── Officer 2
        └── Member C

Factions (Global):
  Faction A: {Player 1, Player 2, NPC 1} → Reputation per player
  Faction B: {Player 2, Player 3, NPC 2}
```

### Principle 2: Communication as Event Streams

All messages flow through EventDispatcher with scope targeting:

| Channel Type | Scope | Recipients |
|--------------|-------|------------|
| Room (`say`) | Room-scoped | All in room |
| Tell (private) | Player-scoped | Single player + sender |
| Yell | Extended room (2-3 rooms) | Adjacent rooms |
| Group | Group-scoped | All members + sender |
| Faction | Global | All faction members online |
| Clan | Global | All clan members online |
| Global (broadcast) | Server-wide | All players (admin only) |

### Principle 3: Associations as Lazy Loaded References

Rather than storing full group/clan/faction membership in every player record, we store:
- `player.player_flags["group_id"]` → Points to group (or None)
- `player.player_flags["clan_id"]` → Points to clan
- `player.player_flags["faction_standings"]` → Dict of faction IDs → reputation values
- `player.player_flags["followers"]` → Set of player IDs who follow this player
- `player.player_flags["following"]` → Set of player IDs this player follows

The GroupSystem/ClanSystem/FactionSystem maintain in-memory caches of these relationships for O(1) lookup.

### Principle 4: Faction Affinity Shapes NPC Behavior

NPCs can:
- Belong to factions (loaded from YAML)
- Treat faction members as allies (assist in combat, share information)
- Treat enemy factions as adversaries (attack on sight, refuse service)
- Update player faction reputation on actions (quest completion, NPC defeat)

---

## Proposed Architecture

### Core Data Structures

#### 1. Group System

```python
@dataclass
class Group:
    """Runtime group/party object."""
    id: str                              # UUID
    leader_id: PlayerId                  # Player who created group
    name: str = "Unnamed Party"          # Can be customized
    member_ids: Set[PlayerId] = field(default_factory=set)  # Including leader
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    # Auto-disband after 30 minutes of inactivity
    INACTIVITY_TIMEOUT = 1800.0

    def is_leader(self, player_id: PlayerId) -> bool:
        return player_id == self.leader_id

    def is_member(self, player_id: PlayerId) -> bool:
        return player_id in self.member_ids

    def is_stale(self, current_time: float) -> bool:
        return (current_time - self.last_activity) > self.INACTIVITY_TIMEOUT

    def member_count(self) -> int:
        return len(self.member_ids)
```

Groups are ephemeral (session-based, not persistent). They exist only while the server is running and are re-created when players form new groups.

#### 2. Clan System

```python
class ClanRank(Enum):
    LEADER = "leader"        # Can invite/remove, edit settings
    OFFICER = "officer"      # Can invite/remove members
    MEMBER = "member"        # Regular membership
    INITIATE = "initiate"    # Probationary (can be kicked easily)

@dataclass
class ClanMember:
    """A member of a clan."""
    player_id: PlayerId
    rank: ClanRank
    joined_at: float
    contribution_points: int = 0  # Earned through activities

@dataclass
class Clan:
    """Persistent player guild/clan."""
    id: str                              # UUID, stored in DB
    name: str                            # Clan name (unique)
    description: str = ""
    leader_id: PlayerId
    members: Dict[PlayerId, ClanMember] = field(default_factory=dict)  # Dict for O(1) lookup
    created_at: float = field(default_factory=time.time)
    treasury: int = 0                    # Shared clan currency (future)
    permissions: Dict[ClanRank, Set[str]] = field(default_factory=dict)  # Rank → perms

    # Clan levels/prestige (future)
    level: int = 1
    experience: int = 0

    def get_rank(self, player_id: PlayerId) -> ClanRank | None:
        if player_id not in self.members:
            return None
        return self.members[player_id].rank

    def is_leader(self, player_id: PlayerId) -> bool:
        return player_id == self.leader_id

    def can_invite(self, actor_id: PlayerId) -> bool:
        rank = self.get_rank(actor_id)
        return rank in (ClanRank.LEADER, ClanRank.OFFICER)

    def member_count(self) -> int:
        return len(self.members)
```

Clans are persistent (stored in Player model and DB). Clan data lives in a new `clans` table with references in Player model.

#### 3. Faction System

```python
class FactionAlignment(Enum):
    HOSTILE = "hostile"      # < -50 reputation
    UNFRIENDLY = "unfriendly"  # -50 to -10
    NEUTRAL = "neutral"      # -10 to 10
    FRIENDLY = "friendly"    # 10 to 50
    ALLIED = "allied"        # >= 50

@dataclass
class Faction:
    """A world faction (persistent)."""
    id: str                              # e.g., "crimson_guard", "council_of_elders"
    name: str
    description: str

    # Settings
    color: str = "#FFFFFF"               # Display color for faction
    emblem: str = "🛡️"                  # Emoji/symbol

    # NPC faction memberships (loaded from YAML)
    npc_members: Set[NpcTemplateId] = field(default_factory=set)  # Template IDs

    # Rules
    player_joinable: bool = True         # Can players join via commands?
    max_members: int = 1000
    require_level: int = 1               # Min level to join

    # Metadata
    created_at: float = field(default_factory=time.time)
    creator_id: PlayerId | None = None   # Player who created (if player-created)

@dataclass
class FactionStanding:
    """Player's relationship with a faction."""
    faction_id: str
    reputation: int = 0                  # -100 to +100
    joined_at: float | None = None       # None if never joined
    rank: str | None = None              # Optional: member, officer, etc.

    def get_alignment(self) -> FactionAlignment:
        if self.reputation >= 50:
            return FactionAlignment.ALLIED
        elif self.reputation >= 10:
            return FactionAlignment.FRIENDLY
        elif self.reputation > -10:
            return FactionAlignment.NEUTRAL
        elif self.reputation > -50:
            return FactionAlignment.UNFRIENDLY
        else:
            return FactionAlignment.HOSTILE

    def alignment_text(self) -> str:
        align = self.get_alignment()
        emojis = {
            FactionAlignment.ALLIED: "💚",
            FactionAlignment.FRIENDLY: "💙",
            FactionAlignment.NEUTRAL: "⚪",
            FactionAlignment.UNFRIENDLY: "🧡",
            FactionAlignment.HOSTILE: "❤️",
        }
        return f"{emojis[align]} {align.value.title()}"
```

Factions are persistent and loaded from YAML. Player faction standings stored in `player.player_flags["faction_standings"]`.

#### 4. Follow/Unfollow System

```python
@dataclass
class FollowRelationship:
    """Player A follows Player B."""
    follower_id: PlayerId
    following_id: PlayerId
    since: float = field(default_factory=time.time)

    # Auto-unfollow if following player goes offline for X minutes
    MAX_OFFLINE_TIME = 300.0  # 5 minutes
```

Stored as:
- `player.player_flags["followers"]` → Set of player IDs who follow this player
- `player.player_flags["following"]` → Set of player IDs this player follows

When a player moves rooms, all followers automatically move with them.

---

## Command Integration

### Player Commands - Social Structure

```
# Group/Party Management
group create [name]           # Create a group (become leader)
group invite <player>         # Invite player to group
group leave                   # Leave current group
group disband                 # Disband group (leader only)
group members                 # List group members
group rename <name>           # Rename group (leader only)

# Clan Management
clan create <name>            # Create new clan (requires payment?)
clan invite <player>          # Invite to clan
clan leave                     # Leave clan
clan members [rank_filter]    # List clan members (filter by rank)
clan info                      # View clan info (level, treasury, etc.)
clan promote <player> <rank>  # Promote member (officer/leader only)
clan disband                   # Disband clan (leader only)

# Faction
faction list                   # List all factions
faction info <faction_id>      # View faction details
faction join <faction_id>      # Join a faction
faction leave <faction_id>     # Leave a faction
faction standing               # View your standings with all factions
faction standing <faction>     # View specific faction standing

# Follow/Unfollow
follow <player>               # Follow a player (see their moves, get alerts)
unfollow <player>             # Stop following a player
followers                      # List players following you
following                      # List players you're following
```

### Player Commands - Communication

```
# Direct Messages
tell <player> <message>        # Private message to player (alias: whisper)
reply <message>                # Reply to last tell sender
ignore <player>                # Ignore tells from player
unignore <player>

# Room-based (existing, with enhancements)
say <message>                  # Speak to room (already implemented)
yell <message>                 # Shout to adjacent rooms (2-3 rooms away)
emote <action>                 # Narrative action (already implemented)

# Group Communication
group-tell <message>           # Message all group members
gtell <message>                # Alias: gtell

# Faction Communication
faction-tell <faction> <message>  # Send message to faction (faction shorthand)
ftell <faction> <message>

# Clan Communication
clan-tell <message>            # Message all clan members
ctell <message>

# Broadcast (Admin only)
broadcast <message>            # Message all players (ADMIN)
```

---

## System Architecture

### GroupSystem

Manages ephemeral groups:

```python
class GroupSystem:
    """Runtime manager for player groups/parties."""

    groups: Dict[str, Group] = {}  # group_id -> Group
    player_to_group: Dict[PlayerId, str] = {}  # Quick lookup

    async def create_group(self, ctx: GameContext, leader_id: PlayerId, name: str = "") -> Group
    async def invite_player(self, ctx: GameContext, group_id: str, player_id: PlayerId) -> bool
    async def remove_player(self, ctx: GameContext, group_id: str, player_id: PlayerId) -> bool
    async def disband_group(self, ctx: GameContext, group_id: str) -> bool
    async def get_group(self, group_id: str) -> Group | None
    async def get_player_group(self, player_id: PlayerId) -> Group | None

    async def clean_stale_groups(self, ctx: GameContext, current_time: float) -> None
        """Remove groups that have been inactive for > 30 minutes."""

    async def broadcast_to_group(self, ctx: GameContext, group_id: str,
                                 message: str, exclude: PlayerId | None = None) -> List[Event]

    async def handle_player_move(self, ctx: GameContext, player_id: PlayerId,
                                 new_room_id: RoomId) -> List[Event]
        """When a player moves, move all followers with them."""
```

### ClanSystem (Phase 10.2 - Future)

Manages persistent clans. Data loaded from DB at startup:

```python
class ClanSystem:
    """Persistent manager for player clans."""

    clans: Dict[str, Clan] = {}  # clan_id -> Clan
    player_to_clan: Dict[PlayerId, str] = {}  # Quick lookup

    async def create_clan(self, ctx: GameContext, leader_id: PlayerId, name: str) -> Clan | None
    async def invite_player(self, ctx: GameContext, clan_id: str, player_id: PlayerId) -> bool
    async def remove_player(self, ctx: GameContext, clan_id: str, player_id: PlayerId) -> bool
    async def promote_member(self, ctx: GameContext, clan_id: str, player_id: PlayerId, rank: ClanRank) -> bool
    async def get_clan(self, clan_id: str) -> Clan | None
    async def get_player_clan(self, player_id: PlayerId) -> Clan | None

    async def broadcast_to_clan(self, ctx: GameContext, clan_id: str,
                               message: str, exclude: PlayerId | None = None) -> List[Event]

    # Persistence hooks
    async def save_clan(self, ctx: GameContext, clan: Clan) -> None
    async def load_clans_from_db(self, ctx: GameContext) -> Dict[str, Clan]
```

### FactionSystem

Manages faction memberships and player standings:

```python
class FactionSystem:
    """Manager for world factions and player standings."""

    factions: Dict[str, Faction] = {}  # faction_id -> Faction
    npc_faction_cache: Dict[NpcTemplateId, Set[str]] = {}  # NPC template → factions

    async def load_factions_from_yaml(self, yaml_dir: str) -> Dict[str, Faction]
    async def add_player_to_faction(self, ctx: GameContext, player_id: PlayerId, faction_id: str) -> bool
    async def remove_player_from_faction(self, ctx: GameContext, player_id: PlayerId, faction_id: str) -> bool

    async def modify_faction_standing(self, ctx: GameContext, player_id: PlayerId,
                                      faction_id: str, delta: int) -> FactionAlignment
        """Adjust player's reputation with faction."""

    async def get_faction_standing(self, ctx: GameContext, player_id: PlayerId,
                                    faction_id: str) -> FactionStanding

    async def get_all_standings(self, ctx: GameContext, player_id: PlayerId) -> Dict[str, FactionStanding]

    async def broadcast_to_faction(self, ctx: GameContext, faction_id: str,
                                   message: str, exclude: PlayerId | None = None) -> List[Event]

    # NPC interaction
    def get_npc_factions(self, npc_template_id: NpcTemplateId) -> Set[str]
        """Return all factions this NPC template belongs to."""

    async def is_faction_enemy(self, ctx: GameContext, player_id: PlayerId,
                               npc_template_id: NpcTemplateId) -> bool
        """Check if player and NPC are in opposing factions."""
```

---

## Database Schema Changes

### Clans Table (Phase 10.2)

```sql
CREATE TABLE clans (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    leader_id TEXT NOT NULL,
    description TEXT,
    level INTEGER DEFAULT 1,
    experience INTEGER DEFAULT 0,
    treasury INTEGER DEFAULT 0,
    created_at FLOAT NOT NULL,
    yaml_managed BOOLEAN DEFAULT 0,

    FOREIGN KEY (leader_id) REFERENCES players(id)
);

CREATE TABLE clan_members (
    id TEXT PRIMARY KEY,
    clan_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    rank TEXT NOT NULL,
    joined_at FLOAT NOT NULL,
    contribution_points INTEGER DEFAULT 0,

    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
    UNIQUE(clan_id, player_id)
);

CREATE TABLE factions (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    color TEXT DEFAULT '#FFFFFF',
    emblem TEXT DEFAULT '🛡️',
    player_joinable BOOLEAN DEFAULT 1,
    max_members INTEGER DEFAULT 1000,
    require_level INTEGER DEFAULT 1,
    created_at FLOAT NOT NULL,
    creator_id TEXT,

    FOREIGN KEY (creator_id) REFERENCES players(id)
);

CREATE TABLE faction_npc_members (
    faction_id TEXT NOT NULL,
    npc_template_id TEXT NOT NULL,

    PRIMARY KEY (faction_id, npc_template_id),
    FOREIGN KEY (faction_id) REFERENCES factions(id) ON DELETE CASCADE
);
```

### Player Model Extensions

```python
class Player(Base):
    # ... existing fields ...

    # Social system (Phase 10)
    player_flags: Mapped[dict] = mapped_column(JSON, default=dict)

    # Expected structure:
    # {
    #     "group_id": "group-uuid" or None,
    #     "clan_id": "clan-uuid" or None,
    #     "followers": ["player-id-1", "player-id-2"],
    #     "following": ["player-id-1"],
    #     "faction_standings": {
    #         "crimson_guard": {"reputation": 25, "joined_at": 1234567890.0},
    #         "council_of_elders": {"reputation": -15, "joined_at": None}
    #     },
    #     "ignored_players": ["player-id-1"],
    # }
```

---

## YAML Content Layer

### Faction Definitions

```yaml
# world_data/factions/crimson_guard.yaml
id: crimson_guard
name: Crimson Guard
description: "The elite military force protecting the realm."
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

### NPC Faction Membership

```yaml
# world_data/npcs/crimson_captain.yaml
id: crimson_captain
name: Crimson Captain
npc_type: hostile
level: 10

factions:
  - crimson_guard
  - humans_of_valor

behaviors:
  - aggressive
  - calls_for_help
  - combat_ai
```

---

## Design Decisions & Rationale

### Decision 1: Ephemeral Groups Instead of Persistent Parties

**Chosen**: Auto-disband after 30 minutes inactivity

**Rationale**:
- Reduces DB bloat from abandoned parties
- Prevents "ghost parties" when players disconnect
- Groups form organically around dungeon runs
- Clans handle long-term social structures

### Decision 2: JSON Player Flags for Social State

**Chosen**: Store group_id, clan_id, followers, faction_standings in `player.player_flags`

**Rationale**:
- Avoids foreign key explosion
- Lazy-loads on demand
- In-memory caches provide O(1) lookup
- Backward compatible with null/missing fields
- Extensible without schema changes

### Decision 3: Faction Affinity Affects Combat

**Chosen**: NPCs attack enemy faction players; refuse service to hostiles

**Rationale**:
- Creates mechanical consequences to faction choices
- Adds depth to NPC behavior
- Enables world-building opportunities

### Decision 4: Tell Command Allows Cross-Zone Communication

**Chosen**: `tell <player> <message>` works anywhere

**Rationale**:
- Enables coordination without friction
- Matches classic MUD conventions
- Follows from principle that private messaging should be frictionless

### Decision 5: Faction Standing -100 to +100

**Chosen**: 5 alignment tiers based on reputation range

**Rationale**:
- Simple, understandable scale
- Maps to clear NPC behaviors:
  - ALLIED (≥50): NPCs assist
  - FRIENDLY (10-49): NPCs trade at discount
  - NEUTRAL (-10 to 9): NPCs neutral
  - UNFRIENDLY (-50 to -11): NPCs refuse service
  - HOSTILE (<-50): NPCs attack

### Decision 6: NPC Faction Membership Via YAML

**Chosen**: NPCs declare faction membership in YAML templates

**Rationale**:
- NPC faction is inherent to identity (not earned)
- Loaded at startup, cached in memory
- Can't be modified by players (prevents exploitation)
- Simplifies schema (no NPC-faction standings table)

---

## Implementation Phases

### Phase 10.1: Groups and Tell Commands (MVP)

**In-memory group system with private messaging**

- [ ] GroupSystem class (create, invite, disband, broadcast)
- [ ] Commands: `group create|invite|leave|disband|members|rename`
- [ ] Commands: `tell <player> <message>`, `reply`, `ignore`, `unignore`
- [ ] EventDispatcher extensions for group/tell messages
- [ ] WebSocket event types for social events
- [ ] Follow/unfollow system (lightweight, player_flags only)
- [ ] Commands: `follow <player>`, `unfollow`, `followers`, `following`
- [ ] Yell command (adjacent room broadcast)

**Estimated effort**: 2-3 days

### Phase 10.2: Clans and Persistence

**Persistent player guilds with hierarchy**

- [ ] Clan model and database tables
- [ ] ClanSystem class (create, invite, promote, disband)
- [ ] Commands: `clan create|invite|leave|members|promote|info|disband`
- [ ] Clan treasury and contribution points (schema prep only)
- [ ] Persistence: Save/load clans from DB

**Estimated effort**: 3-4 days

### Phase 10.3: Factions

**World factions with reputation system and NPC integration**

- [ ] Faction model and database tables
- [ ] FactionSystem class (load from YAML, manage standings)
- [ ] Commands: `faction list|info|join|leave|standing`
- [ ] NPC faction loading and alignment checks
- [ ] Combat integration: NPCs detect enemy factions
- [ ] Reputation changes on quest completion/NPC defeat
- [ ] Commands: `faction-tell <faction> <message>`

**Estimated effort**: 3-4 days

---

## Testing Strategy

### Unit Tests
- GroupSystem CRUD operations
- ClanSystem rank verification
- FactionStanding alignment calculation
- Message scoping (group/faction/tell events reach correct recipients)
- Follow relationship logic

### Integration Tests
- Player creates group → others join → auto-disband on inactivity
- Player joins faction → NPC detects alignment → NPC behavior changes
- Player follows another → follower automatically moves with leader
- Tell conversation routes correctly

### Edge Cases
- Group member joins while in combat
- Group leader disconnects
- Player tries to join max-standing faction
- Tell to offline player
- Circular follow relationships don't cause loops

---

## Backward Compatibility

- Existing players function unchanged (social features optional)
- New player_flags fields missing until first use
- Old say/emote commands unchanged
- Combat/quest systems unaffected until faction integration (Phase 10.3)

---

## Success Criteria

✅ Phase 10.1:
- Players form/join/leave groups
- Group messages route only to members
- Players tell each other (private messages)
- Players follow/unfollow
- Yell command broadcasts to adjacent rooms

✅ Phase 10.2:
- Players create persistent clans
- Clan membership persists across sessions
- Clan chat works
- Promotions/demotions work

✅ Phase 10.3:
- Factions load from YAML
- Players join/leave factions
- NPC faction membership affects combat
- Faction chat works
- Reputation changes on actions
