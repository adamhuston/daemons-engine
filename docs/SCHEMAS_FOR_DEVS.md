# Database Schema Reference

## Overview

Technical reference for **backend developers and CMS integrators** documenting all SQLAlchemy database tables, columns, constraints, and JSON field formats. For YAML content schemas used by content creators, see `SCHEMAS_FOR_CONTENT_CREATORS.md`.

**Database**: SQLite via SQLAlchemy ORM  
**Location**: `backend/daemons.db`  
**Migrations**: Alembic (`backend/alembic/`)

---

## Table of Contents

1. [World & Geography](#world--geography)
   - room_types
   - rooms
   - areas
2. [Items & Inventory](#items--inventory)
   - item_templates
   - item_instances
   - player_inventories
3. [NPCs & AI](#npcs--ai)
   - npc_templates
   - npc_instances
4. [Players & Characters](#players--characters)
   - players
5. [Persistence & State](#persistence--state)
   - player_effects
   - room_state
   - trigger_state
   - npc_state
6. [Authentication & Security](#authentication--security)
   - user_accounts
   - refresh_tokens
   - security_events
   - admin_actions
7. [Metrics & Monitoring](#metrics--monitoring)
   - server_metrics
8. [Social & Organizations](#social--organizations)
   - clans
   - clan_members
   - factions
   - faction_npc_members

---

## World & Geography

### room_types

**Purpose**: Dynamic room type registry with emoji icons

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| name | String | PRIMARY KEY | Room type identifier (e.g., "forest", "urban") |
| emoji | String | NOT NULL, default="❓" | Emoji icon for UI display |
| description | String | NULL | Optional description of room type |

**Notes**:
- Dynamically populated from room definitions
- Allows new room types without code changes

---

### rooms

**Purpose**: Individual locations in the game world

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Unique room identifier |
| name | String | NOT NULL | Display name of room |
| description | String | NOT NULL | Full room description text |
| room_type | String | NOT NULL, default="ethereal" | Type of room (links to room_types) |
| room_type_emoji | String | NULL | Optional per-room emoji override |
| area_id | String | FOREIGN KEY (areas.id), NULL | Parent area reference |
| north_id | String | FOREIGN KEY (rooms.id), NULL | Exit to north |
| south_id | String | FOREIGN KEY (rooms.id), NULL | Exit to south |
| east_id | String | FOREIGN KEY (rooms.id), NULL | Exit to east |
| west_id | String | FOREIGN KEY (rooms.id), NULL | Exit to west |
| up_id | String | FOREIGN KEY (rooms.id), NULL | Exit upward |
| down_id | String | FOREIGN KEY (rooms.id), NULL | Exit downward |
| on_enter_effect | String | NULL | Message when player enters |
| on_exit_effect | String | NULL | Message when player exits |
| lighting_override | String | NULL | Per-room lighting level (Phase 11) |
| yaml_managed | Boolean | NOT NULL, default=1 | True if managed by YAML files |

**Indexes**: area_id (for efficient area queries)

**Notes**:
- Self-referencing foreign keys for exits create room network
- Custom exits (e.g., "secret") may require special handling
- Boolean stored as integer (0/1) in SQLite

---

### areas

**Purpose**: Cohesive regions with shared properties and independent time systems

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Unique area identifier |
| name | String | NOT NULL | Display name of area |
| description | Text | NOT NULL | Full area description |
| time_scale | Float | NOT NULL, default=1.0 | Time speed multiplier |
| starting_day | Integer | NOT NULL, default=1 | Initial day number |
| starting_hour | Integer | NOT NULL, default=6 | Initial hour (0-23) |
| starting_minute | Integer | NOT NULL, default=0 | Initial minute (0-59) |
| biome | String | NOT NULL, default="ethereal" | Environmental biome type |
| climate | String | NOT NULL, default="mild" | Climate classification |
| ambient_lighting | String | NOT NULL, default="normal" | Base lighting level |
| weather_profile | String | NOT NULL, default="clear" | Weather pattern |
| danger_level | Integer | NOT NULL, default=1 | Difficulty rating (1-10) |
| magic_intensity | String | NOT NULL, default="low" | Magical energy level |
| default_respawn_time | Integer | NOT NULL, default=300 | NPC respawn seconds |
| ambient_sound | Text | NULL | Atmospheric sound description |
| time_phases | JSON | default={} | Custom time-of-day flavor text |
| entry_points | JSON | default=[] | Room IDs where players can spawn |

**Notes**:
- time_phases format: `{"dawn": "text", "morning": "text", ...}`
- entry_points is array of room ID strings

---

## Items & Inventory

### item_templates

**Purpose**: Static item definitions (blueprints)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Template identifier (e.g., "item_rusty_sword") |
| name | String | NOT NULL | Display name |
| description | Text | NOT NULL | Full item description |
| item_type | String | NOT NULL | Category: weapon, armor, consumable, container, quest, junk |
| item_subtype | String | NULL | Subcategory (sword, potion, etc.) |
| equipment_slot | String | NULL | Where it can be equipped |
| stat_modifiers | JSON | default={} | Stat bonuses when equipped |
| weight | Float | NOT NULL, default=1.0 | Weight in pounds/kg |
| max_stack_size | Integer | NOT NULL, default=1 | Max stackable quantity |
| has_durability | Boolean | NOT NULL, default=0 | Whether item degrades |
| max_durability | Integer | NULL | Max durability points |
| is_container | Boolean | NOT NULL, default=0 | Can hold other items |
| container_capacity | Integer | NULL | Max items/weight if container |
| container_type | String | NULL | "weight_based" or "slot_based" |
| is_consumable | Boolean | NOT NULL, default=0 | Can be consumed |
| consume_effect | JSON | NULL | Effect when consumed |
| damage_min | Integer | NOT NULL, default=0 | Min weapon damage |
| damage_max | Integer | NOT NULL, default=0 | Max weapon damage |
| attack_speed | Float | NOT NULL, default=2.0 | Weapon attack interval |
| damage_type | String | NOT NULL, default="physical" | Damage type |
| provides_light | Boolean | NOT NULL, default=0 | Emits light (Phase 11) |
| light_intensity | Integer | NOT NULL, default=0 | Light contribution (0-50) |
| light_duration | Integer | NULL | Light duration in seconds |
| flavor_text | Text | NULL | Additional lore text |
| rarity | String | NOT NULL, default="common" | Rarity tier |
| value | Integer | NOT NULL, default=0 | Gold value |
| flags | JSON | default={} | Special flags (quest_item, etc.) |
| keywords | JSON | default=[] | Search keywords |

**Notes**:
- stat_modifiers format: `{"strength": 2, "armor_class": 5}`
- keywords format: `["sword", "blade", "weapon"]`
- Boolean fields stored as integers in SQLite

---

### item_instances

**Purpose**: Specific item occurrences in the world

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Instance identifier (UUID) |
| template_id | String | FOREIGN KEY (item_templates.id), NOT NULL | Template reference |
| room_id | String | FOREIGN KEY (rooms.id), NULL | Location: on ground |
| player_id | String | FOREIGN KEY (players.id), NULL | Location: in player inventory |
| container_id | String | FOREIGN KEY (item_instances.id), NULL | Location: inside container |
| quantity | Integer | NOT NULL, default=1 | Stack size |
| current_durability | Integer | NULL | Current durability points |
| equipped_slot | String | NULL | Equipped slot (if equipped) |
| instance_data | JSON | default={} | Custom instance properties |

**Indexes**: template_id, room_id, player_id, container_id

**Notes**:
- Exactly one location field (room/player/container) should be set
- Self-referencing container_id allows nested items

---

### player_inventories

**Purpose**: Player inventory metadata and limits

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| player_id | String | PRIMARY KEY, FOREIGN KEY (players.id) | Player reference |
| max_weight | Float | NOT NULL, default=100.0 | Weight capacity |
| max_slots | Integer | NOT NULL, default=20 | Slot capacity |
| current_weight | Float | NOT NULL, default=0.0 | Current weight (denormalized) |
| current_slots | Integer | NOT NULL, default=0 | Current slots used (denormalized) |

**Notes**:
- current_weight and current_slots are cached for performance
- Should be recalculated periodically or on inventory changes

---

## NPCs & AI

### npc_templates

**Purpose**: Static NPC definitions (blueprints)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Template identifier (e.g., "npc_goblin_scout") |
| name | String | NOT NULL | Display name |
| description | Text | NOT NULL | Full NPC description |
| npc_type | String | NOT NULL, default="hostile" | hostile, neutral, friendly, merchant |
| level | Integer | NOT NULL, default=1 | NPC level |
| max_health | Integer | NOT NULL, default=50 | Maximum HP |
| armor_class | Integer | NOT NULL, default=10 | Defense rating |
| strength | Integer | NOT NULL, default=10 | STR attribute |
| dexterity | Integer | NOT NULL, default=10 | DEX attribute |
| intelligence | Integer | NOT NULL, default=10 | INT attribute |
| attack_damage_min | Integer | NOT NULL, default=1 | Min attack damage |
| attack_damage_max | Integer | NOT NULL, default=5 | Max attack damage |
| attack_speed | Float | NOT NULL, default=3.0 | Seconds between attacks |
| experience_reward | Integer | NOT NULL, default=10 | XP on kill |
| behavior | JSON | default={} | AI behavior configuration |
| loot_table | JSON | default=[] | Loot drop configuration |
| idle_messages | JSON | default=[] | Random idle emotes/messages |
| keywords | JSON | default=[] | Targeting keywords |

**Notes**:
- behavior format: `{"wanders": true, "aggro_on_sight": true, ...}` or array of tags
- loot_table format: `[{"template_id": "...", "chance": 0.5, "quantity": [1, 3]}]`

---

### npc_instances

**Purpose**: Specific NPC occurrences in the world

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Instance identifier (UUID) |
| template_id | String | FOREIGN KEY (npc_templates.id), NOT NULL | Template reference |
| room_id | String | FOREIGN KEY (rooms.id), NOT NULL | Current location |
| spawn_room_id | String | FOREIGN KEY (rooms.id), NOT NULL | Respawn location |
| current_health | Integer | NOT NULL | Current HP |
| is_alive | Boolean | NOT NULL, default=1 | Alive status |
| respawn_time | Integer | NULL | Override respawn seconds (NULL = use area default) |
| last_killed_at | Float | NULL | Unix timestamp of death |
| instance_data | JSON | default={} | Instance-specific data |

**Indexes**: template_id, room_id, spawn_room_id

**Notes**:
- respawn_time = -1 disables respawning (unique/boss NPCs)
- instance_data can override template properties

---

## Players & Characters

### players

**Purpose**: Player character data

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Player identifier |
| name | String | UNIQUE, NOT NULL | Character name |
| current_room_id | String | FOREIGN KEY (rooms.id), NOT NULL | Current location |
| account_id | String | FOREIGN KEY (user_accounts.id, ondelete=SET NULL), NULL, INDEXED | Linked account (Phase 7) |
| character_class | String | NOT NULL, default="adventurer" | Class/archetype |
| level | Integer | NOT NULL, default=1 | Character level |
| experience | Integer | NOT NULL, default=0 | Experience points |
| strength | Integer | NOT NULL, default=10 | STR attribute |
| dexterity | Integer | NOT NULL, default=10 | DEX attribute |
| intelligence | Integer | NOT NULL, default=10 | INT attribute |
| vitality | Integer | NOT NULL, default=10 | VIT attribute |
| max_health | Integer | NOT NULL, default=100 | Maximum HP |
| current_health | Integer | NOT NULL, default=100 | Current HP |
| armor_class | Integer | NOT NULL, default=10 | Defense rating |
| max_energy | Integer | NOT NULL, default=50 | Maximum energy/mana |
| current_energy | Integer | NOT NULL, default=50 | Current energy |
| data | JSON | default={} | Misc data (deprecated) |
| player_flags | JSON | default={} | Persistent flags for quests/social |
| quest_progress | JSON | default={} | Quest progress data |
| completed_quests | JSON | default=[] | Completed quest IDs |

**Indexes**: name (unique), account_id

**Notes**:
- player_flags includes: group_id, followers, following, ignored_players, last_tell_from
- quest_progress format: `{"quest_id": {"status": "active", "objectives": {...}}}`
- completed_quests is simple array of quest IDs

---

## Persistence & State

### player_effects

**Purpose**: Active buffs/debuffs persisting across disconnects

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| player_id | String | PRIMARY KEY, FOREIGN KEY (players.id) | Player reference |
| effect_id | String | PRIMARY KEY | Effect identifier |
| effect_type | String | NOT NULL | buff, debuff, dot, hot |
| effect_data | JSON | NULL | Full effect serialization |
| expires_at | Float | NOT NULL | Unix timestamp expiration |
| created_at | Float | NULL | Unix timestamp creation |

**Composite Primary Key**: (player_id, effect_id)

**Notes**:
- Effects tick while player is offline
- Expired effects cleaned up on player login

---

### room_state

**Purpose**: Dynamic room state persisting across restarts

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| room_id | String | PRIMARY KEY, FOREIGN KEY (rooms.id) | Room reference |
| room_flags | JSON | default={} | Dynamic flags |
| dynamic_exits | JSON | default={} | Temporary exits |
| dynamic_description | Text | NULL | Override description |
| updated_at | Float | NULL | Unix timestamp of last update |

**Notes**:
- Allows rooms to change state during gameplay
- Dynamic exits for puzzle/trigger-based doors

---

### trigger_state

**Purpose**: Fire counts for permanent triggers

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| trigger_id | String | PRIMARY KEY | Trigger identifier |
| scope | String | PRIMARY KEY | 'room', 'area', or 'global' |
| scope_id | String | PRIMARY KEY | room_id or area_id |
| fire_count | Integer | NOT NULL, default=0 | Times triggered |
| last_fired_at | Float | NULL | Unix timestamp of last fire |

**Composite Primary Key**: (trigger_id, scope, scope_id)

**Notes**:
- Only permanent triggers are saved here
- Non-permanent triggers reset on server restart

---

### npc_state

**Purpose**: Persistent state for special NPCs

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| instance_id | String | PRIMARY KEY | NPC instance identifier |
| template_id | String | FOREIGN KEY (npc_templates.id), NOT NULL | Template reference |
| current_room_id | String | FOREIGN KEY (rooms.id), NULL | Current location |
| current_hp | Integer | NULL | Current health |
| is_alive | Boolean | NOT NULL, default=1 | Alive status |
| owner_player_id | String | FOREIGN KEY (players.id), NULL | Owner (for companions) |
| instance_data | JSON | default={} | Custom state data |
| updated_at | Float | NULL | Unix timestamp of last update |

**Notes**:
- Only NPCs with `persist_state=True` in template are saved
- Used for companions, unique bosses, escort targets

---

## Authentication & Security

### user_accounts

**Purpose**: User authentication and account management (Phase 7)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Account identifier (UUID) |
| username | String(32) | UNIQUE, NOT NULL | Login username |
| email | String(255) | UNIQUE, NULL | Email address |
| password_hash | String(255) | NOT NULL | Hashed password |
| role | String(32) | NOT NULL, default="player" | player, game_master, admin |
| is_active | Boolean | NOT NULL, default=1 | Account active status |
| created_at | Float | NULL | Unix timestamp of creation |
| last_login | Float | NULL | Unix timestamp of last login |
| active_character_id | String | NULL | Currently playing character (players.id) |
| is_banned | Boolean | NOT NULL, default=0 | Ban status (Phase 8) |
| ban_reason | String(500) | NULL | Reason for ban |
| banned_at | Float | NULL | Unix timestamp of ban |
| banned_by | String | NULL | Admin who issued ban |

**Indexes**: username (unique), email (unique)

**Notes**:
- One account can have multiple characters
- Password stored as bcrypt hash
- Role determines admin API access

---

### refresh_tokens

**Purpose**: JWT refresh token management

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Token identifier (UUID) |
| account_id | String | FOREIGN KEY (user_accounts.id, ondelete=CASCADE), NOT NULL | Account reference |
| token_hash | String(64) | NOT NULL, INDEXED | SHA256 hash of token |
| expires_at | Float | NOT NULL | Unix timestamp expiration |
| created_at | Float | NULL | Unix timestamp creation |
| revoked | Boolean | NOT NULL, default=0 | Revocation status |
| device_info | String(255) | NULL | Client device information |

**Indexes**: token_hash, account_id

**Notes**:
- Tokens stored as SHA256 hashes for security
- Supports token rotation and revocation
- Device info helps track sessions

---

### security_events

**Purpose**: Security audit log (Phase 8)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Event identifier (UUID) |
| account_id | String | FOREIGN KEY (user_accounts.id, ondelete=SET NULL), NULL | Account reference |
| event_type | String(50) | NOT NULL, INDEXED | Event category |
| ip_address | String(45) | NULL | Client IP (IPv6 compatible) |
| user_agent | String(255) | NULL | Client user agent |
| details | JSON | NULL | Event-specific data |
| timestamp | Float | NOT NULL, INDEXED | Unix timestamp |

**Indexes**: event_type, timestamp, account_id

**Event Types**: login_success, login_failure, password_change, permission_change, token_refresh

**Notes**:
- Helps detect suspicious activity
- Useful for debugging auth issues

---

### admin_actions

**Purpose**: Administrative action audit log (Phase 8)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Action identifier (UUID) |
| admin_id | String | FOREIGN KEY (user_accounts.id, ondelete=SET NULL), NULL | Admin account reference |
| admin_name | String(32) | NOT NULL | Cached admin name |
| action | String(50) | NOT NULL, INDEXED | Action type |
| target_type | String(50) | NULL | player, npc, item, room |
| target_id | String | NULL | Target identifier |
| details | JSON | NULL | Action-specific data |
| success | Boolean | NOT NULL, default=1 | Whether action succeeded |
| timestamp | Float | NOT NULL, INDEXED | Unix timestamp |

**Indexes**: action, timestamp, admin_id

**Action Types**: teleport, spawn, kick, ban, reload, modify_stats

**Notes**:
- Accountability for privileged actions
- admin_name cached for readability even if admin deleted

---

## Metrics & Monitoring

### server_metrics

**Purpose**: Historical server performance metrics

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Metric identifier (UUID) |
| timestamp | Float | NOT NULL, INDEXED | Unix timestamp |
| metric_type | String(50) | NOT NULL, INDEXED | Metric category |
| value | Float | NOT NULL | Metric value |

**Indexes**: timestamp, metric_type

**Metric Types**: players_online, tick_duration, command_count, npc_count

**Notes**:
- Used for capacity planning
- Performance trend analysis

---

## Social & Organizations

### clans

**Purpose**: Player guilds/clans (Phase 10.2)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Clan identifier (UUID) |
| name | String | UNIQUE, NOT NULL, INDEXED | Clan name |
| leader_id | String | FOREIGN KEY (players.id), NOT NULL, INDEXED | Clan leader |
| description | Text | NULL | Clan description |
| level | Integer | NOT NULL, default=1 | Clan level |
| experience | Integer | NOT NULL, default=0 | Clan XP |
| created_at | Float | NOT NULL | Unix timestamp of creation |

**Indexes**: name (unique), leader_id

**Relationships**:
- One-to-many with clan_members
- Cascades delete to members

**Notes**:
- Clans have progression system (level/XP)
- Leader can promote/demote members

---

### clan_members

**Purpose**: Clan membership tracking

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Membership identifier (UUID) |
| clan_id | String | FOREIGN KEY (clans.id, ondelete=CASCADE), NOT NULL, INDEXED | Clan reference |
| player_id | String | FOREIGN KEY (players.id), NOT NULL, INDEXED | Player reference |
| rank | String | NOT NULL, INDEXED | leader, officer, member, initiate |
| joined_at | Float | NOT NULL | Unix timestamp of join |
| contribution_points | Integer | NOT NULL, default=0 | Player's contribution |
| extra_data | JSON | NULL | Additional member data |

**Indexes**: clan_id, player_id, rank

**Notes**:
- Rank hierarchy: leader > officer > member > initiate
- Contribution points for clan activities

---

### factions

**Purpose**: NPC factions for reputation system (Phase 10.3)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String | PRIMARY KEY | Faction identifier |
| name | String | UNIQUE, NOT NULL, INDEXED | Faction name |
| description | Text | NULL | Faction description |
| color | String | NOT NULL, default="#FFFFFF" | Hex color code |
| emblem | String | NULL | Emoji/symbol |
| player_joinable | Boolean | NOT NULL, default=1, INDEXED | Can players join |
| max_members | Integer | NULL | Max player members (NULL = unlimited) |
| require_level | Integer | NOT NULL, default=1 | Min level to join |
| created_at | Float | NOT NULL | Unix timestamp of creation |

**Indexes**: name (unique), player_joinable

**Notes**:
- Factions loaded from YAML files
- Player reputation stored in player.player_flags

---

### faction_npc_members

**Purpose**: NPC faction membership (many-to-many)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| faction_id | String | PRIMARY KEY, FOREIGN KEY (factions.id, ondelete=CASCADE), INDEXED | Faction reference |
| npc_template_id | String | PRIMARY KEY | NPC template reference |

**Composite Primary Key**: (faction_id, npc_template_id)

**Indexes**: faction_id, npc_template_id

**Notes**:
- Allows quick faction lookup for NPCs
- Affects NPC behavior toward players based on reputation

---

## Migration & Versioning

**Alembic Versions**: See `backend/alembic/versions/` for migration history

**Key Migrations**:
- cc7f91e61ef9: Initial schema
- 921a4875c30b: Areas
- 4f2e8d3c1a5b: Items and inventory
- 5a3f9b7e2d1c: NPCs and AI framework
- e1f2a3b4c5d6: Phase 6 persistence
- f7a8b9c0d1e2: Phase 7 authentication
- a1b2c3d4e5f6: Phase 8 admin audit
- g8h9i0j1k2l3: Phase 9 character classes
- (Phase 10.2): Clans
- (Phase 10.3): Factions

**To upgrade database**: `alembic upgrade head`

---

## JSON Field Schemas

### player.quest_progress
```json
{
  "quest_id": {
    "status": "active" | "completed" | "failed",
    "objectives": {
      "objective_id": current_count
    },
    "started_at": timestamp,
    "completed_at": timestamp  // if completed
  }
}
```

### npc_template.behavior (dictionary format)
```json
{
  "wanders": bool,
  "wander_chance": float,
  "aggro_on_sight": bool,
  "flees_at_health_percent": int,
  "calls_for_help": bool,
  "help_radius": int
}
```

### npc_template.loot_table
```json
[
  {
    "template_id": "item_id",
    "quantity": [min, max] | int,
    "chance": float
  }
]
```

### item_template.stat_modifiers
```json
{
  "strength": int,
  "dexterity": int,
  "armor_class": int,
  "max_health": int
}
```

### area.time_phases
```json
{
  "dawn": "description text",
  "morning": "description text",
  "afternoon": "description text",
  "dusk": "description text",
  "evening": "description text",
  "night": "description text"
}
```

---

## Best Practices for CMS Integration

1. **Read-Only Access**: CMS should primarily read from database for live preview
2. **YAML as Source of Truth**: Modify YAML files, not database directly
3. **Validation**: Use `/api/admin/content/validate` before committing changes
4. **Hot Reload**: Trigger `/api/admin/content/reload` after YAML updates
5. **Backup**: Always backup database before migrations
6. **Indexes**: Respect indexed columns for efficient queries
7. **Transactions**: Use transactions for multi-table operations
8. **JSON Fields**: Validate JSON structure before insertion
9. **Foreign Keys**: Respect referential integrity constraints
10. **Timestamps**: Use Unix timestamps (float) for all time fields

---

## Connection String

**Development**: `sqlite:///./daemons.db`

**Production**: Configure via environment variable `DATABASE_URL`

---

## Tools & Resources

- **ORM**: SQLAlchemy 2.0+
- **Migrations**: Alembic
- **Admin API**: `/api/admin/*` endpoints (requires authentication)
- **Schema Export**: Can generate JSON Schema from Pydantic models
- **ERD Generation**: Use `sqlacodegen` or similar tools

---

**Last Updated**: Based on models.py as of Phase 11
**Contact**: See CONTRIBUTING.md for development questions
