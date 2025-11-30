# WebSocket Protocol Documentation

This document describes the communication protocol between a Daemons engine server and a Daemons client (like Scry)

## Connection

**Endpoint:** `ws://host:port/ws/game?player_id={player_id}`

**Query Parameters:**
- `player_id` (required): UUID of the player connecting

## Client → Server Messages

All messages are JSON objects sent as text frames.

### Command Message
```json
{
  "type": "command",
  "text": "look"
}
```

**Fields:**
- `type`: Always `"command"`
- `text`: The command string (e.g., "look", "north", "say hello")

**Supported Commands:**

### Movement
- `north`, `south`, `east`, `west`, `up`, `down` - Movement in cardinal directions
- `n`, `s`, `e`, `w`, `u`, `d` - Short forms of movement commands
- `flee` - Escape from combat in a random direction

### Looking & Information
- `look` or `l` - Examine current room, exits, entities, and items
- `look <target>` - Examine a specific player, NPC, or item
- `stats`, `sheet`, `status` - View your character stats
- `effects` - View active buffs/debuffs with durations
- `time` - View current in-game time with area-specific context

### Communication
- `say <message>` - Speak to others in the same room
- `smile`, `nod`, `laugh`, `cringe`, `smirk`, `frown`, `wink`, `lookaround` - Emotes

### Inventory & Items
- `inventory`, `inv`, `i` - View your inventory with weight/slots
- `get <item>`, `take <item>`, `pickup <item>` - Pick up item from room
- `drop <item>` - Drop item to room floor
- `give <item> to <player>` - Transfer item to another player
- `put <item> in <container>` - Store item in a container
- `get <item> from <container>` - Retrieve item from container

### Equipment
- `equip <item>`, `wear <item>`, `wield <item>` - Equip an item
- `unequip <item>`, `remove <item>` - Unequip an item
- `use <item>`, `consume <item>`, `drink <item>` - Use a consumable

### Combat
- `attack <target>`, `kill <target>`, `k <target>` - Start attacking a target
- `stop` - Stop auto-attacking and disengage from combat

### Debug/Admin Commands
- `heal <player_name>` - Heal a player for 20 HP
- `hurt <player_name>` - Damage a player for 10 HP
- `bless <player_name>` - Apply +5 Armor Class buff for 30 seconds
- `poison <player_name>` - Apply DoT: 5 damage every 3s for 15s
- `testtimer [seconds]` - Test the time event system

### Special Keywords
- `self` - Auto-replaces with your character name in commands

## Server → Client Messages

All messages are JSON objects sent as text frames.

### Message Event
```json
{
  "type": "message",
  "player_id": "uuid-string",
  "text": "You are in a dark room.\n\nExits: north, south"
}
```

**Fields:**
- `type`: Always `"message"`
- `player_id`: UUID of the player this message is for
- `text`: The message content (may contain `\n` for formatting)

**Message Types:**
- **Room descriptions** - Name, description, exits, entities, and items
- **Movement feedback** - "You move north." or error messages
- **Chat messages** - Speech from other players
- **Combat messages** - Attack, damage, death notifications
- **Item messages** - Pickup, drop, equip, use feedback
- **Effect messages** - Buff/debuff application and expiration
- **Flavor text** - Movement effects, stasis messages, respawn text
- **System messages** - Connection/disconnection notifications

**Error Handling:**
- Unknown commands receive: "You mutter something unintelligible. (Unknown command)"
- Invalid movement directions: "You can't go that way."
- Malformed JSON or invalid message types are logged server-side but not sent to client

### Stat Update Event
```json
{
  "type": "stat_update",
  "player_id": "uuid-string",
  "payload": {
    "current_health": 85,
    "max_health": 100,
    "current_energy": 50,
    "max_energy": 50
  }
}
```

**Fields:**
- `type`: Always `"stat_update"`
- `player_id`: UUID of the player this update is for
- `payload`: Object containing updated stat values

**When Sent:**
- When a player's stats change (damage, healing, level up, effects applied/expired, etc.)
- When effects tick (e.g., poison damage every 3 seconds)
- Client should update its local stat display if maintained
- Common stats include: `current_health`, `max_health`, `current_energy`, `max_energy`, `level`, `experience`, `armor_class`

**Note:** Stats can have modifiers from active effects. The `stats` command shows effective values (e.g., "15 (10 base)" for armor_class with a +5 buff).

**Common Payload Fields:**
- `current_health`, `max_health` - Health points
- `current_energy`, `max_energy` - Energy/mana points
- `level`, `experience` - Progression
- `armor_class` - Defense rating
- `strength`, `dexterity`, `intelligence`, `vitality` - Base stats

### Respawn Countdown Event
```json
{
  "type": "respawn_countdown",
  "player_id": "uuid-string",
  "payload": {
    "seconds_remaining": 10,
    "respawn_location": "Ethereal Nexus"
  }
}
```

**Fields:**
- `type`: Always `"respawn_countdown"`
- `player_id`: UUID of the player who died
- `payload.seconds_remaining`: Seconds until respawn (counts down from 10 to 1)
- `payload.respawn_location`: Name of the area where player will respawn

**When Sent:**
- After a player dies, one event per second counting down
- Client should display a countdown overlay/modal
- When countdown reaches 0, player is respawned and receives normal messages

**Player Death Flow:**
1. Player health reaches 0 → receives death message
2. Player removed from current room
3. Respawn countdown events sent (10, 9, 8... 1)
4. Player respawned at area entry point with full health
5. Player receives resurrection message and room description

### Ability-Related Events (Phase 9)

#### ability_cast Event
```json
{
  "type": "ability_cast",
  "caster_id": "uuid-string",
  "ability_id": "slash",
  "ability_name": "Slash",
  "target_ids": ["enemy-uuid-1", "enemy-uuid-2"]
}
```

**Fields:**
- `type`: Always `"ability_cast"`
- `caster_id`: UUID of the player casting the ability
- `ability_id`: The ability identifier
- `ability_name`: Human-readable ability name
- `target_ids`: List of affected target UUIDs (optional, may be empty for self-targeted abilities)

**When Sent:**
- Immediately when an ability cast begins
- Broadcast to all players in the caster's room
- Appears on clients in combat/action logs

#### ability_error Event
```json
{
  "type": "ability_error",
  "player_id": "uuid-string",
  "ability_id": "slash",
  "ability_name": "Slash",
  "error": "Not enough mana"
}
```

**Fields:**
- `type`: Always `"ability_error"`
- `player_id`: UUID of the player who attempted the ability
- `ability_id`: The ability identifier
- `ability_name`: Human-readable ability name
- `error`: Reason the ability failed

**When Sent:**
- When ability execution fails validation (insufficient resources, on cooldown, etc.)
- Sent only to the caster
- Clients should display as error message in combat log

**Common Error Scenarios:**
- "Not enough mana" - Insufficient resource cost
- "Ability is on cooldown (X.Xs remaining)" - Cooldown not expired
- "No valid target found" - Required target not in range/visible
- "Ability not learned" - Player hasn't unlocked this ability

#### ability_cast_complete Event
```json
{
  "type": "ability_cast_complete",
  "player_id": "uuid-string",
  "ability_id": "slash",
  "ability_name": "Slash",
  "payload": {
    "success": true,
    "message": "You slash the enemy for 25 damage!",
    "damage_dealt": 25,
    "targets_hit": 1
  }
}
```

**Fields:**
- `type`: Always `"ability_cast_complete"`
- `player_id`: UUID of the caster
- `ability_id`: The ability identifier
- `ability_name`: Human-readable ability name
- `payload.success`: Whether the ability executed successfully
- `payload.message`: Result message (flavor text)
- `payload.damage_dealt`: Total damage dealt (optional)
- `payload.targets_hit`: Number of targets affected (optional)

**When Sent:**
- After ability behavior completes
- Contains detailed outcome information
- Broadcast to all players in the caster's room

#### cooldown_update Event
```json
{
  "type": "cooldown_update",
  "player_id": "uuid-string",
  "ability_id": "slash",
  "cooldown_remaining": 6.5
}
```

**Fields:**
- `type`: Always `"cooldown_update"`
- `player_id`: UUID of the caster
- `ability_id`: The ability identifier
- `cooldown_remaining`: Seconds remaining on cooldown

**When Sent:**
- Immediately after an ability is cast
- Sent only to the caster
- Clients should update ability UI cooldown indicators

#### resource_update Event
```json
{
  "type": "resource_update",
  "player_id": "uuid-string",
  "payload": {
    "mana": {
      "current": 40,
      "max": 50,
      "percent": 80
    },
    "energy": {
      "current": 45,
      "max": 100,
      "percent": 45
    }
  }
}
```

**Fields:**
- `type`: Always `"resource_update"`
- `player_id`: UUID of the player whose resources changed
- `payload`: Object mapping resource_id → {current, max, percent}

**When Sent:**
- When a player's abilities/resources are modified (mana spent, stamina regenerated, etc.)
- Sent only to the affected player
- Clients should update resource bars

**Resource Types:**
- `mana` - Magical resource for spellcasting abilities
- `energy` - Physical resource for physical abilities
- `stamina` - Endurance resource

#### ability_learned Event
```json
{
  "type": "ability_learned",
  "player_id": "uuid-string",
  "ability_id": "power_attack",
  "ability_name": "Power Attack"
}
```

**Fields:**
- `type`: Always `"ability_learned"`
- `player_id`: UUID of the player who learned the ability
- `ability_id`: The ability identifier
- `ability_name`: Human-readable ability name

**When Sent:**
- When a player learns a new ability (leveling, questing, class selection)
- Sent only to the player who learned it
- Clients should update ability list/learnt abilities UI

## Event Scoping

The server uses internal scoping to determine which players receive which events:

- **`scope: "player"`** - Sent only to the specific player
- **`scope: "room"`** - Sent to all connected players in the same room
- **`exclude: [player_ids]`** - Room-scoped events can exclude specific players

*Note: Scope fields are internal and stripped before sending to clients. Clients only see the `type`, `player_id`, and `text` fields.*

## Time System

The server maintains an event-driven time system:

**World Time:**
- Each area has independent time that advances continuously
- Areas can have different time scales (e.g., 4x faster in Ethereal Nexus)
- Time of day affects ambient descriptions
- Use `time` command to see current time and area info

**Effects System:**
- Buffs and debuffs are time-limited effects
- Effects can modify stats (e.g., +5 armor_class)
- Periodic effects tick at intervals (e.g., poison every 3s)
- Effects expire automatically and trigger stat updates
- Use `effects` command to see active effects with remaining duration

**Effect Types:**
- **Buff** - Positive stat modifiers (e.g., Blessed)
- **Debuff** - Negative stat modifiers
- **DoT** - Damage over time (e.g., Poison)
- **HoT** - Healing over time

## Connection Lifecycle

### On Connect
1. Client opens WebSocket connection with `player_id` parameter
2. Server registers player and marks them as connected
3. Server sends initial `stat_update` event with current HP/energy
4. If player was in stasis, other players in room see reconnection message
5. Client typically sends initial "look" command

### On Disconnect
1. WebSocket connection closes
2. **Server persists player stats to database** (current_health, current_energy, level, experience, location)
3. Server marks player as disconnected (stasis mode)
4. Other players in room see stasis message
5. Player remains in world but listed as "(In Stasis)"

### Stasis State
- Disconnected players remain visible in their last location
- Other players see: `(In Stasis) The form of {name} is here, flickering in prismatic stasis.`
- Players in stasis cannot be harmed (future feature)
- On reconnect, player returns from stasis in the same location

## Example Flow

```
Client connects with player_id=abc123

→ {"type": "command", "text": "look"}
← {"type": "message", "player_id": "abc123", "text": "Central Chamber\n..."}

→ {"type": "command", "text": "north"}
← {"type": "message", "player_id": "abc123", "text": "You move north.\n..."}

→ {"type": "command", "text": "say Hello everyone!"}
← {"type": "message", "player_id": "abc123", "text": "You say: Hello everyone!"}
← (Other players in room receive: "PlayerName says: Hello everyone!")

→ {"type": "command", "text": "heal test_player"}
← {"type": "stat_update", "player_id": "abc123", "payload": {"current_health": 100, "max_health": 100}}
← {"type": "message", "player_id": "abc123", "text": "*A warm glow surrounds you.* You are healed for 20 HP."}

→ {"type": "command", "text": "bless self"}
← {"type": "stat_update", "player_id": "abc123", "payload": {"armor_class": 15}}
← {"type": "message", "player_id": "abc123", "text": "✨ *Divine light surrounds you!* You feel blessed. (+5 Armor Class for 30 seconds)"}

→ {"type": "command", "text": "effects"}
← {"type": "message", "player_id": "abc123", "text": "═══ Active Effects ═══\n\n**Blessed** (buff)\n  Duration: 27.3s remaining\n  Modifiers: armor_class +5"}

→ {"type": "command", "text": "time"}
← {"type": "message", "player_id": "abc123", "text": "🌄 Day 1, 06:45 (morning)\n*The Ethereal Nexus*\n\nThe morning sun shines brightly overhead.\n\n*A gentle humming resonates through the air.*\n\n⚡ *Time flows 4.0x faster here.*"}

Client disconnects
← (Other players receive: "A bright flash engulfs PlayerName. Their form flickers and freezes, suspended in prismatic stasis.")
```

## Implemented Event Types

The protocol supports the following event types:

| Event Type | Description |
|------------|-------------|
| `message` | Text-based messages, room descriptions, combat feedback |
| `stat_update` | Player stat changes (health, level, XP, etc.) |
| `respawn_countdown` | Death countdown timer with respawn location |

## Combat System

Combat is **real-time** with auto-attack:

1. Player uses `attack <target>` to start combat
2. Weapon determines swing speed (windup → swing → recovery phases)
3. Auto-attack continues until target dies or player uses `stop`/`flee`
4. Movement is blocked while in combat (must `flee` to escape)
5. Players automatically retaliate when attacked

**Combat Messages:**
- `⚔️ You attack Goblin Scout!` - Combat initiated
- `You hit Goblin Scout for 5 damage!` - Damage dealt
- `💥 Goblin Scout hits you for 3 damage! **CRITICAL!**` - Damage received
- `💀 Goblin Scout has been slain by PlayerName!` - Death broadcast
- `✨ You gain 25 experience!` - XP reward

**Death & Respawn:**
- On death, player sees countdown messages (10 seconds)
- Player respawns at area entry point with full health
- Other players see resurrection announcement

## NPC System

NPCs appear in rooms and can have various behaviors:

**NPC Display in Room:**
```
Creatures:
  🧌 Goblin Scout - A small, wiry goblin with beady eyes.
```

**NPC Behaviors:**
- **Aggressive** - Attacks players on sight
- **Defensive** - Only retaliates when attacked
- **Wandering** - Moves between rooms periodically
- **Fleeing** - Runs away when health is low
- **Social** - Calls for help from nearby allies

**NPC Respawn:**
- Dead NPCs respawn after area-configured time (default 300s)
- Per-NPC overrides possible (-1 = never respawn)

## Item System

Items can be in rooms, containers, or player inventories.

**Room Items Display:**
```
Items:
  ⚔️ Rusty Sword - A worn blade, still sharp enough to cut.
  🧪 Health Potion (x2)
```

**Item Properties:**
- Weight and slot requirements
- Equipment slots (weapon, head, chest, etc.)
- Stat modifiers when equipped
- Consumable effects (healing, buffs)
- Container capacity

**Container System:**
- Items can contain other items (e.g., backpacks)
- `put <item> in <container>` / `get <item> from <container>`

## REST API Endpoints

The server exposes REST endpoints for authentication, character management, and administrative functions. All endpoints use JSON for request/response bodies unless otherwise specified.

### Base URL
`http://host:port`

### Authentication Endpoints

#### POST /auth/register
Register a new user account.

**Request:**
```json
{
  "username": "string (3-32 chars)",
  "password": "string (8-128 chars)",
  "email": "string (optional)"
}
```

**Response (200):**
```json
{
  "user_id": "uuid",
  "username": "string",
  "message": "Account created successfully"
}
```

#### POST /auth/login
Authenticate and receive JWT tokens.

**Request:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response (200):**
```json
{
  "access_token": "jwt_token",
  "refresh_token": "jwt_token",
  "token_type": "bearer",
  "user_id": "uuid",
  "username": "string",
  "role": "player|moderator|game_master|admin",
  "active_character_id": "uuid|null"
}
```

**Error (401):**
```json
{
  "detail": "Invalid credentials"
}
```

#### POST /auth/refresh
Refresh access token using refresh token (implements token rotation).

**Request:**
```json
{
  "refresh_token": "jwt_token"
}
```

**Response (200):**
```json
{
  "access_token": "new_jwt_token",
  "refresh_token": "new_refresh_token",
  "token_type": "bearer"
}
```

#### POST /auth/logout
Logout by revoking refresh token for current device.

**Request:**
```json
{
  "refresh_token": "jwt_token"
}
```

**Response (200):**
```json
{
  "message": "Logged out successfully"
}
```

#### GET /auth/me
Get current user information from access token.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "user_id": "uuid",
  "username": "string",
  "email": "string|null",
  "role": "player|moderator|game_master|admin",
  "is_active": true,
  "active_character_id": "uuid|null",
  "characters": [
    {
      "id": "uuid",
      "name": "string",
      "level": 1,
      "character_class": "string"
    }
  ]
}
```

### Character Management Endpoints

All character endpoints require authentication via `Authorization: Bearer <access_token>` header.

#### POST /characters
Create a new character for the authenticated account (max 3 per account).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "name": "string (2-32 chars)",
  "character_class": "string (default: adventurer)"
}
```

**Response (200):**
```json
{
  "id": "uuid",
  "name": "string",
  "level": 1,
  "character_class": "string",
  "current_room_id": "room_1_1_1"
}
```

**Error (400):**
```json
{
  "detail": "Character name already taken"
}
```

#### GET /characters
List all characters for the authenticated account.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "characters": [
    {
      "id": "uuid",
      "name": "string",
      "level": 1,
      "character_class": "string",
      "current_room_id": "string",
      "is_active": true
    }
  ]
}
```

#### POST /characters/{character_id}/select
Set a character as the active character for the account.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "message": "Character selected",
  "active_character_id": "uuid"
}
```

#### DELETE /characters/{character_id}
Permanently delete a character.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "message": "Character deleted",
  "character_id": "uuid"
}
```

### Admin API Endpoints

All admin endpoints require authentication with elevated roles and use the `/api/admin` prefix.

**Required Headers:**
```
Authorization: Bearer <access_token>
```

**Role Requirements:**
- **MODERATOR**: Basic admin operations (view data, kick players)
- **GAME_MASTER**: Content management (spawn NPCs/items, modify stats, reload content)
- **ADMIN**: Server administration (shutdown, maintenance mode, account management)

#### Server Management

##### GET /api/admin/server/status
Get current server status and metrics.

**Requires:** MODERATOR+

**Response (200):**
```json
{
  "uptime_seconds": 12345.67,
  "players_online": 5,
  "players_in_combat": 2,
  "npcs_alive": 30,
  "rooms_total": 100,
  "rooms_occupied": 8,
  "areas_total": 5,
  "scheduled_events": 42,
  "next_event_in_seconds": 3.5,
  "maintenance_mode": false,
  "maintenance_reason": null,
  "shutdown_pending": false,
  "shutdown_at": null,
  "shutdown_reason": null,
  "content_version": "1.0.0",
  "server_time": 1638360000.0
}
```

##### POST /api/admin/server/maintenance
Enable or disable maintenance mode.

**Requires:** ADMIN (Permission.SERVER_COMMANDS)

**Request:**
```json
{
  "enabled": true,
  "reason": "Scheduled maintenance",
  "kick_players": false
}
```

**Response (200):**
```json
{
  "enabled": true,
  "reason": "Scheduled maintenance",
  "enabled_at": 1638360000.0,
  "players_kicked": 0
}
```

##### POST /api/admin/server/shutdown
Initiate graceful server shutdown with countdown.

**Requires:** ADMIN (Permission.SERVER_COMMANDS)

**Request:**
```json
{
  "countdown_seconds": 60,
  "reason": "Server restart for updates"
}
```

**Response (200):**
```json
{
  "success": true,
  "countdown_seconds": 60,
  "shutdown_at": 1638360060.0,
  "reason": "Server restart for updates",
  "players_warned": 5
}
```

##### POST /api/admin/server/shutdown/cancel
Cancel a pending shutdown.

**Requires:** ADMIN

**Response (200):**
```json
{
  "success": true,
  "message": "Shutdown cancelled"
}
```

##### GET /api/admin/server/metrics
Get Prometheus-format metrics for monitoring.

**Requires:** MODERATOR+

**Response (200):** Prometheus text exposition format

**Example Prometheus scrape config:**
```yaml
scrape_configs:
  - job_name: 'daemons'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/admin/server/metrics'
    bearer_token: '<admin_jwt_token>'
```

##### POST /api/admin/server/broadcast
Broadcast a message to all connected players.

**Requires:** MODERATOR+ (Permission.KICK_PLAYER)

**Request:**
```json
{
  "message": "Server restart in 5 minutes",
  "sender_name": "SYSTEM"
}
```

#### World Inspection

##### GET /api/admin/world/players
List all online players.

**Requires:** MODERATOR+

**Response (200):**
```json
[
  {
    "id": "uuid",
    "name": "PlayerName",
    "room_id": "room_1_1_1",
    "level": 5,
    "current_health": 85,
    "max_health": 100,
    "is_connected": true,
    "in_combat": false
  }
]
```

##### GET /api/admin/world/players/{player_id}
Get detailed information about a specific player.

**Requires:** MODERATOR+

##### GET /api/admin/world/rooms
List all rooms, optionally filtered by area.

**Requires:** MODERATOR+

**Query Parameters:**
- `area_id` (optional): Filter by area ID

**Response (200):**
```json
[
  {
    "id": "room_1_1_1",
    "name": "Central Chamber",
    "area_id": "ethereal_nexus",
    "player_count": 2,
    "npc_count": 1,
    "item_count": 3,
    "exits": {"north": "room_1_1_2", "south": "room_1_1_0"}
  }
]
```

##### GET /api/admin/world/rooms/{room_id}
Get detailed information about a specific room.

**Requires:** MODERATOR+

**Response (200):**
```json
{
  "id": "room_1_1_1",
  "name": "Central Chamber",
  "description": "A mystical chamber...",
  "room_type": "ethereal",
  "area_id": "ethereal_nexus",
  "exits": {"north": "room_1_1_2"},
  "dynamic_exits": {},
  "players": ["player_uuid_1"],
  "npcs": ["npc_uuid_1"],
  "items": ["item_uuid_1"],
  "flags": {},
  "triggers": ["trigger_1"]
}
```

##### PUT /api/admin/world/rooms/{room_id}
Update a room's properties.

**Requires:** GAME_MASTER+ (Permission.MODIFY_WORLD)

**Request:**
```json
{
  "name": "New Room Name",
  "description": "Updated description",
  "room_type": "forest",
  "on_enter_effect": "You feel a chill",
  "on_exit_effect": null
}
```

##### POST /api/admin/world/rooms
Create a new room.

**Requires:** GAME_MASTER+ (Permission.MODIFY_WORLD)

**Request:**
```json
{
  "id": "custom_room_1",
  "name": "Custom Room",
  "description": "A custom room",
  "room_type": "urban",
  "area_id": "my_area",
  "exits": {"north": "room_1_1_1"}
}
```

##### PATCH /api/admin/world/rooms/{room_id}/exits
Update a room's exits.

**Requires:** GAME_MASTER+ (Permission.MODIFY_WORLD)

**Request:**
```json
{
  "exits": {
    "north": "target_room_id",
    "south": null
  },
  "bidirectional": true
}
```

##### POST /api/admin/world/rooms/{room_id}/reset-yaml-managed
Reset a YAML-managed room to its original configuration.

**Requires:** GAME_MASTER+

##### GET /api/admin/world/areas
List all areas.

**Requires:** MODERATOR+

**Response (200):**
```json
[
  {
    "id": "ethereal_nexus",
    "name": "Ethereal Nexus",
    "room_count": 50,
    "player_count": 3,
    "time_scale": 4.0
  }
]
```

##### GET /api/admin/world/npcs
List all NPCs.

**Requires:** MODERATOR+

##### GET /api/admin/world/items
List all items.

**Requires:** MODERATOR+

##### GET /api/admin/world/state
Get complete world state snapshot (for debugging/dashboards).

**Requires:** MODERATOR+

#### Player Management

##### POST /api/admin/players/{player_id}/teleport
Teleport a player to a different room.

**Requires:** GAME_MASTER+ (Permission.MODIFY_STATS)

**Request:**
```json
{
  "room_id": "target_room"
}
```

##### POST /api/admin/players/{player_id}/heal
Heal a player.

**Requires:** GAME_MASTER+ (Permission.MODIFY_STATS)

**Request:**
```json
{
  "amount": 50
}
```

##### POST /api/admin/players/{player_id}/kick
Kick a player from the server.

**Requires:** MODERATOR+ (Permission.KICK_PLAYER)

##### POST /api/admin/players/{player_id}/give
Give an item to a player.

**Requires:** GAME_MASTER+ (Permission.SPAWN_ITEM)

**Request:**
```json
{
  "template_id": "health_potion",
  "quantity": 5
}
```

##### POST /api/admin/players/{player_id}/effect
Apply a temporary effect (buff/debuff) to a player.

**Requires:** GAME_MASTER+ (Permission.MODIFY_STATS)

**Request:**
```json
{
  "effect_name": "buff_strength",
  "duration": 60,
  "magnitude": 0
}
```

##### POST /api/admin/players/{player_id}/kill
Instantly kill a player.

**Requires:** GAME_MASTER+ (Permission.MODIFY_STATS)

##### POST /api/admin/players/{player_id}/message
Send a direct message to a player.

**Requires:** MODERATOR+ (Permission.KICK_PLAYER)

**Request:**
```json
{
  "message": "Please follow server rules",
  "sender_name": "MODERATOR"
}
```

#### Entity Spawning

##### POST /api/admin/npcs/spawn
Spawn an NPC in a room.

**Requires:** GAME_MASTER+ (Permission.SPAWN_NPC)

**Request:**
```json
{
  "template_id": "goblin_scout",
  "room_id": "room_1_1_1"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Spawned Goblin Scout in Central Chamber",
  "npc_id": "uuid",
  "room_id": "room_1_1_1"
}
```

##### DELETE /api/admin/npcs/{npc_id}
Despawn an NPC.

**Requires:** GAME_MASTER+ (Permission.SPAWN_NPC)

##### POST /api/admin/items/spawn
Spawn an item in a room.

**Requires:** GAME_MASTER+ (Permission.SPAWN_ITEM)

**Request:**
```json
{
  "template_id": "rusty_sword",
  "room_id": "room_1_1_1",
  "quantity": 1
}
```

##### DELETE /api/admin/items/{item_id}
Despawn an item.

**Requires:** GAME_MASTER+ (Permission.SPAWN_ITEM)

##### POST /api/admin/npcs/{npc_id}/move
Move an NPC to a different room.

**Requires:** GAME_MASTER+ (Permission.SPAWN_NPC)

**Request:**
```json
{
  "target_room_id": "room_1_1_2",
  "reason": "Admin relocation"
}
```

##### POST /api/admin/items/{item_id}/move
Move an item to a different location.

**Requires:** GAME_MASTER+ (Permission.SPAWN_ITEM)

#### Content Management

##### POST /api/admin/content/reload
Hot-reload content from YAML files without restarting the server.

**Requires:** ADMIN

**Request:**
```json
{
  "content_type": "all|areas|rooms|items|npcs|item_templates|npc_templates",
  "file_path": "/path/to/file.yaml (optional)",
  "force": false
}
```

**Response (200):**
```json
{
  "success": true,
  "content_type": "all",
  "items_loaded": 45,
  "items_updated": 12,
  "items_failed": 0,
  "errors": []
}
```

##### POST /api/admin/content/validate
Validate YAML content files without loading them.

**Requires:** GAME_MASTER+

**Request:**
```json
{
  "content_type": "rooms|items|npcs|areas",
  "file_path": "/path/to/file.yaml (optional)"
}
```

**Response (200):**
```json
{
  "success": true,
  "content_type": "rooms",
  "files_checked": 10,
  "files_valid": 9,
  "files_invalid": 1,
  "results": [
    {
      "file_path": "/path/to/room.yaml",
      "is_valid": false,
      "errors": ["Missing required field: description"]
    }
  ]
}
```

##### GET /api/admin/classes
Get all loaded character classes.

**Requires:** MODERATOR+

**Response (200):**
```json
{
  "success": true,
  "count": 3,
  "classes": [
    {
      "class_id": "warrior",
      "name": "Warrior",
      "description": "A strong melee fighter",
      "base_stats": {...},
      "available_abilities": ["slash", "power_attack"]
    }
  ]
}
```

##### GET /api/admin/abilities
Get all loaded abilities.

**Requires:** MODERATOR+

##### POST /api/admin/classes/reload
Hot-reload character classes and abilities from YAML.

**Requires:** GAME_MASTER+ (Permission.SERVER_COMMANDS)

**Response (200):**
```json
{
  "success": true,
  "detail": "Classes and abilities reloaded successfully",
  "classes_loaded": 3,
  "abilities_loaded": 15,
  "behavior_count": 10
}
```

#### Schema Registry (Phase 12.1)

The Schema Registry provides API access to all YAML schema definitions (_schema.yaml files) for CMS integration and TypeScript type generation.

##### GET /api/admin/schemas
Get all schema definitions with optional filtering.

**Requires:** MODERATOR+

**Query Parameters:**
- `content_type` (optional): Filter by content type (e.g., "classes", "items", "rooms")

**Response (200):**
```json
{
  "success": true,
  "detail": "Retrieved 13 schemas",
  "count": 13,
  "schemas": [
    {
      "content_type": "classes",
      "file_path": "C:\\...\\world_data\\classes\\_schema.yaml",
      "content": "# Class Schema Documentation\n# Reference for content creators...",
      "checksum": "8b99261438de2991012f263d897199e837ab208ab61cc392b9f1d48c027d626f",
      "last_modified": "2025-11-29T11:23:27.825053",
      "size_bytes": 2588
    }
    // ... more schemas
  ],
  "filter_applied": null
}
```

**Example Filtered Request:**
```
GET /api/admin/schemas?content_type=classes
```

**Available Schema Types:**
- `abilities` - Ability/spell definitions
- `areas` - World region definitions
- `classes` - Character class definitions
- `dialogues` - NPC dialogue trees
- `factions` - Faction and reputation systems
- `item_instances` - Specific item spawns
- `items` - Item template definitions
- `npc_spawns` - NPC spawn configurations
- `npcs` - NPC template definitions
- `quest_chains` - Linked quest series
- `quests` - Quest definitions
- `rooms` - Room definitions
- `triggers` - Event trigger definitions

##### GET /api/admin/schemas/version
Get schema version information for cache invalidation.

**Requires:** MODERATOR+

**Response (200):**
```json
{
  "success": true,
  "version": "1.0.0",
  "engine_version": "0.12.1",
  "last_modified": "2025-11-29T21:30:37.107781",
  "schema_count": 13
}
```

**Use Case:** CMS clients can poll this endpoint to detect schema changes and invalidate cached TypeScript types.

##### POST /api/admin/schemas/reload
Hot-reload all schema definitions from disk.

**Requires:** GAME_MASTER+ (Permission.SERVER_COMMANDS)

**Response (200):**
```json
{
  "success": true,
  "detail": "Reloaded 13 schemas",
  "schemas_loaded": 13,
  "version": "1.0.0",
  "engine_version": "0.12.1",
  "last_modified": "2025-11-29T21:30:37.107781"
}
```

#### File Management (Phase 12.2)

The File Management API provides secure access to YAML content files for editing and management.

##### GET /api/admin/content/files
List all YAML files in world_data directory.

**Requires:** MODERATOR+

**Query Parameters:**
- `content_type` (optional): Filter by content type (e.g., "classes", "items", "rooms")
- `include_schema_files` (optional): Include _schema.yaml files (default: false)

**Response (200):**
```json
{
  "success": true,
  "detail": "Retrieved 73 files",
  "count": 73,
  "files": [
    {
      "file_path": "classes/warrior.yaml",
      "content_type": "classes",
      "size_bytes": 1245,
      "last_modified": "2025-11-29T11:23:27.825053"
    }
    // ... more files
  ],
  "stats": {
    "total": 73,
    "classes": 3,
    "items": 7,
    "npcs": 4,
    "rooms": 36,
    "quests": 2
    // ... other content types
  },
  "filter_applied": null
}
```

##### GET /api/admin/content/download
Download a specific YAML file.

**Requires:** MODERATOR+

**Query Parameters:**
- `file_path`: Relative path from world_data root (e.g., "classes/warrior.yaml")

**Response (200):**
```json
{
  "success": true,
  "file_path": "classes/warrior.yaml",
  "content": "# Warrior Class\\nclass_id: warrior\\nname: Warrior\\n...",
  "checksum": "a1b2c3d4e5f6...",
  "last_modified": "2025-11-29T11:23:27.825053",
  "size_bytes": 1245
}
```

**Error Responses:**
- `400 Bad Request`: Invalid or unsafe file path (path traversal attempt)
- `404 Not Found`: File not found

##### POST /api/admin/content/upload
Upload or update a YAML file.

**Requires:** GAME_MASTER+ (Permission.SERVER_COMMANDS)

**Request Body:**
```json
{
  "file_path": "classes/my_class.yaml",
  "content": "# My Custom Class\\nclass_id: my_class\\n...",
  "validate_only": false
}
```

**Response (200):**
```json
{
  "success": true,
  "detail": "File written successfully",
  "file_path": "classes/my_class.yaml",
  "checksum": "a1b2c3d4e5f6...",
  "file_written": true,
  "errors": []
}
```

**Validation-Only Mode:**
Set `validate_only: true` to validate YAML syntax without writing to disk.

**Error Response (400):**
```json
{
  "success": false,
  "detail": "Validation failed",
  "errors": [
    "Invalid YAML syntax: mapping values are not allowed here in ..."
  ],
  "file_written": false
}
```

**Security Features:**
- Path traversal attack prevention
- Atomic file operations (temp file + rename)
- YAML syntax validation
- Automatic parent directory creation

##### DELETE /api/admin/content/file
Delete a YAML file.

**Requires:** GAME_MASTER+ (Permission.SERVER_COMMANDS)

**Query Parameters:**
- `file_path`: Relative path from world_data root

**Response (200):**
```json
{
  "success": true,
  "detail": "File deleted successfully",
  "file_path": "classes/old_class.yaml"
}
```

**Protection:**
- Schema files (_schema.yaml) cannot be deleted
- Path traversal attempts are blocked

##### GET /api/admin/content/stats
Get file statistics.

**Requires:** MODERATOR+

**Response (200):**
```json
{
  "success": true,
  "stats": {
    "total": 73,
    "classes": 3,
    "items": 7,
    "npcs": 4,
    "rooms": 36,
    "quests": 2,
    "abilities": 5,
    "areas": 3,
    "dialogues": 2,
    "factions": 4,
    "item_instances": 0,
    "npc_spawns": 3,
    "quest_chains": 1,
    "triggers": 3,
    "unknown": 0
  }
}
```

---

### Phase 12.3: Enhanced Validation API

Enhanced validation with detailed error reporting for real-time CMS feedback.

##### POST /api/admin/content/validate-enhanced
Comprehensive YAML validation with line/column errors.

**Requires:** MODERATOR+

**Request:**
```json
{
  "yaml_content": "class_id: warrior\nname: \"unclosed quote\n",
  "content_type": "classes",
  "check_references": true,
  "file_path": "classes/warrior.yaml"
}
```

**Response (200):**
```json
{
  "success": false,
  "valid": false,
  "errors": [
    {
      "severity": "error",
      "message": "YAML syntax error: found unexpected end of stream (while scanning a quoted scalar)",
      "line": 2,
      "column": 7,
      "field_path": null,
      "error_type": "syntax",
      "suggestion": "Check YAML indentation and special characters"
    }
  ],
  "warnings": [],
  "content_type": "classes",
  "file_path": "classes/warrior.yaml",
  "error_count": 1,
  "warning_count": 0
}
```

**Validation Features:**
- **Syntax validation**: YAML parsing with line/column error extraction
- **Schema validation**: Required fields and type checking for 11 content types
- **Reference validation**: Cross-content link checking (room exits, abilities, etc.)
- **Error types**: `syntax`, `schema`, `reference`, `validation`
- **Warning types**: `deprecated`, `style`, `performance`, `general`

**Example - Missing Required Fields:**
```json
{
  "valid": false,
  "errors": [
    {
      "severity": "error",
      "message": "Missing required field: 'description'",
      "field_path": "description",
      "error_type": "schema",
      "suggestion": "Add 'description' field to the YAML file"
    },
    {
      "severity": "error",
      "message": "Missing required field: 'base_stats'",
      "field_path": "base_stats",
      "error_type": "schema",
      "suggestion": "Add 'base_stats' field to the YAML file"
    }
  ],
  "content_type": "classes"
}
```

**Example - Broken References:**
```json
{
  "valid": false,
  "errors": [
    {
      "severity": "error",
      "message": "Exit 'north' points to non-existent room 'tavern_upstairs'",
      "field_path": "exits.north",
      "error_type": "reference",
      "suggestion": "Create room 'tavern_upstairs' or fix the exit destination"
    },
    {
      "severity": "error",
      "message": "Class references non-existent ability 'super_slash'",
      "field_path": "available_abilities",
      "error_type": "reference",
      "suggestion": "Create ability 'super_slash' or remove from available_abilities"
    }
  ],
  "content_type": "rooms"
}
```

##### POST /api/admin/content/validate-references
Reference-only validation (check cross-content links).

**Requires:** MODERATOR+

**Request:**
```json
{
  "yaml_content": "room_id: inn\nexits:\n  north: nonexistent_room",
  "content_type": "rooms",
  "file_path": "rooms/inn.yaml"
}
```

**Response (200):**
```json
{
  "success": false,
  "valid": false,
  "errors": [
    {
      "severity": "error",
      "message": "Exit 'north' points to non-existent room 'nonexistent_room'",
      "field_path": "exits.north",
      "error_type": "reference",
      "suggestion": "Create room 'nonexistent_room' or fix the exit destination"
    }
  ],
  "warnings": [],
  "content_type": "rooms",
  "file_path": "rooms/inn.yaml",
  "cache_built": true,
  "cached_entities": {
    "rooms": 36,
    "items": 7,
    "npcs": 4,
    "abilities": 5,
    "quests": 2,
    "classes": 3,
    "areas": 3,
    "factions": 4,
    "dialogues": 2
  }
}
```

**Validated References by Content Type:**
- **Rooms**: exits → room_ids, area_id → area_ids
- **Classes**: available_abilities → ability_ids
- **NPCs**: faction_id → faction_ids, dialogue_id → dialogue_ids
- **Quests**: (objectives reference NPCs, items, etc.)

##### POST /api/admin/content/rebuild-reference-cache
Rebuild the reference validation cache.

**Requires:** GAME_MASTER+

**Use Case:** Call after bulk content changes to refresh the entity index.

**Response (200):**
```json
{
  "success": true,
  "detail": "Reference cache rebuilt successfully",
  "cached_entities": {
    "rooms": 36,
    "items": 7,
    "npcs": 4,
    "abilities": 5,
    "quests": 2,
    "classes": 3,
    "areas": 3,
    "factions": 4,
    "dialogues": 2,
    "triggers": 3,
    "quest_chains": 1
  }
}
```

---

### Phase 12.4: Content Querying API

Content search, dependency analysis, and health metrics for CMS.

##### GET /api/admin/content/search
Full-text search across YAML content files.

**Requires:** MODERATOR+

**Query Parameters:**
- `q`: Search query string (required)
- `content_type`: Optional filter by content type
- `limit`: Max results (default: 50, max: 200)

**Response (200):**
```json
{
  "success": true,
  "query": "warrior",
  "content_type_filter": null,
  "result_count": 4,
  "results": [
    {
      "content_type": "classes",
      "file_path": "classes/warrior.yaml",
      "entity_id": "warrior",
      "entity_name": "Warrior",
      "match_field": "id",
      "match_value": "warrior",
      "context_snippet": "warrior",
      "score": 10.0
    },
    {
      "content_type": "abilities",
      "file_path": "abilities/power_attack.yaml",
      "entity_id": "power_attack",
      "entity_name": "Power Attack",
      "match_field": "description",
      "match_value": "A powerful melee attack favored by warriors",
      "context_snippet": "...powerful melee attack favored by warriors...",
      "score": 1.0
    }
  ]
}
```

**Search Features:**
- Searches: entity IDs, names, descriptions
- Relevance scoring: exact ID match (10.0) > exact match (5.0) > starts with (3.0) > contains (1.0)
- Context snippets show surrounding text
- Results sorted by score descending

##### GET /api/admin/content/dependencies
Get dependency graph for a specific entity.

**Requires:** MODERATOR+

**Query Parameters:**
- `entity_type`: Content type (e.g., "rooms", "classes")
- `entity_id`: Entity identifier

**Response (200):**
```json
{
  "success": true,
  "entity_type": "classes",
  "entity_id": "warrior",
  "entity_name": "Warrior",
  "references": [
    {
      "target_type": "abilities",
      "target_id": "slash",
      "relationship": "has_ability",
      "field_path": "available_abilities"
    },
    {
      "target_type": "abilities",
      "target_id": "power_attack",
      "relationship": "has_ability",
      "field_path": "available_abilities"
    }
  ],
  "referenced_by": [],
  "reference_count": 2,
  "referenced_by_count": 0,
  "is_orphaned": true,
  "safe_to_delete": true,
  "blocking_references": []
}
```

**Dependency Relationships Tracked:**
- **Rooms**: exits → rooms, area_id → areas
- **Classes**: available_abilities → abilities
- **NPCs**: faction_id → factions, dialogue_id → dialogues
- **NPC Spawns**: npc_id → npcs, room_id → rooms
- **Quest Chains**: quests → quests

**Safe Delete Check:**
- `safe_to_delete: true` - No entities depend on this one
- `safe_to_delete: false` - Other entities reference this (see blocking_references)

##### GET /api/admin/content/analytics
Comprehensive content health metrics.

**Requires:** MODERATOR+

**Response (200):**
```json
{
  "success": true,
  "total_entities": 73,
  "entities_by_type": {
    "rooms": 36,
    "items": 7,
    "npcs": 4,
    "abilities": 5,
    "quests": 2,
    "classes": 3,
    "areas": 3,
    "factions": 4,
    "dialogues": 2,
    "triggers": 3,
    "quest_chains": 1,
    "npc_spawns": 3
  },
  "broken_reference_count": 2,
  "broken_references": [
    {
      "source_type": "rooms",
      "source_id": "tavern",
      "target_type": "rooms",
      "target_id": "tavern_upstairs",
      "relationship": "exit",
      "field_path": "exits.up"
    }
  ],
  "orphaned_entity_count": 5,
  "orphaned_entities": [
    {"type": "items", "id": "old_sword"},
    {"type": "npcs", "id": "unused_guard"}
  ],
  "average_references_per_entity": 2.3,
  "most_referenced_entities": [
    {"type": "rooms", "id": "town_square", "reference_count": 8},
    {"type": "abilities", "id": "slash", "reference_count": 5}
  ]
}
```

**Analytics Metrics:**
- **Broken References**: Links to non-existent entities (should be fixed)
- **Orphaned Entities**: Nothing references these (candidates for cleanup)
- **Most Referenced**: Popular entities that many others depend on
- **Average References**: Overall connectivity metric

**Use Cases:**
- Content health monitoring
- Finding cleanup opportunities
- Impact analysis before deletion
- Identifying important entities

##### POST /api/admin/content/rebuild-dependency-graph
Rebuild the dependency graph index.

**Requires:** GAME_MASTER+

**Use Case:** Call after bulk content changes to refresh the dependency index.

**Response (200):**
```json
{
  "success": true,
  "detail": "Dependency graph rebuilt successfully",
  "entity_count": 73,
  "dependency_count": 156
}
```

---

#### Account Management

##### GET /api/admin/accounts
List user accounts with pagination and filters.

**Requires:** ADMIN

**Query Parameters:**
- `limit`, `offset`: Pagination
- `role`, `is_banned`, `is_active`: Filters

##### GET /api/admin/accounts/{account_id}
Get detailed account information.

**Requires:** ADMIN

##### PUT /api/admin/accounts/{account_id}/role
Change an account's role.

**Requires:** ADMIN

**Request:**
```json
{
  "role": "moderator|game_master|admin|player"
}
```

##### POST /api/admin/accounts/{account_id}/ban
Ban an account.

**Requires:** ADMIN

**Request:**
```json
{
  "reason": "Violation of terms",
  "duration_hours": 168,
  "is_permanent": false
}
```

##### POST /api/admin/accounts/{account_id}/unban
Unban an account.

**Requires:** ADMIN

##### GET /api/admin/accounts/{account_id}/security-events
Get security events for an account.

**Requires:** ADMIN

#### Trigger Management

##### GET /api/admin/triggers/rooms/{room_id}
Get all triggers in a room.

**Requires:** GAME_MASTER+

##### POST /api/admin/triggers/{trigger_id}/fire
Manually fire a trigger.

**Requires:** GAME_MASTER+

##### POST /api/admin/triggers/{trigger_id}/enable
Enable a trigger.

**Requires:** GAME_MASTER+

##### POST /api/admin/triggers/{trigger_id}/disable
Disable a trigger.

**Requires:** GAME_MASTER+

##### POST /api/admin/triggers/{trigger_id}/reset
Reset a trigger's state.

**Requires:** GAME_MASTER+

#### Quest Management

##### GET /api/admin/quests/templates
List all quest templates.

**Requires:** GAME_MASTER+

##### GET /api/admin/quests/progress/{player_id}
Get quest progress for a player.

**Requires:** GAME_MASTER+

##### POST /api/admin/quests/modify
Modify a player's quest progress.

**Requires:** GAME_MASTER+

## YAML Content System

The game engine loads world content from YAML files in the `world_data/` directory. This allows for hot-reloading and CMS-driven content management without code changes.

### Directory Structure

```
world_data/
├── areas/           # Area definitions
├── rooms/           # Room definitions
├── items/           # Item templates
├── item_instances/  # Item spawns in rooms
├── npcs/            # NPC templates
├── npc_spawns/      # NPC spawn locations
├── classes/         # Character class definitions
├── abilities/       # Ability definitions
├── quests/          # Quest templates
├── quest_chains/    # Quest chain definitions
├── dialogues/       # NPC dialogue trees
├── triggers/        # Room triggers
└── factions/        # Faction definitions
```

### Area YAML Format

**File:** `world_data/areas/ethereal_nexus.yaml`

```yaml
id: ethereal_nexus
name: Ethereal Nexus
description: A mystical realm between worlds
time_scale: 4.0
biome: mystical
climate: temperate
ambient_lighting: dim
danger_level: 1
magic_intensity: high
ambient_sound: "gentle humming"
default_respawn_time: 300
starting_day: 1
starting_hour: 6
starting_minute: 0
entry_points:
  - room_1_1_1
time_phases:
  night:
    start_hour: 0
    ambient: "The ethereal mists glow faintly in the darkness."
  morning:
    start_hour: 6
    ambient: "Morning light filters through the prismatic mists."
  day:
    start_hour: 12
    ambient: "The realm shimmers with full daylight."
  evening:
    start_hour: 18
    ambient: "Twilight casts long shadows."
```

### Room YAML Format

**File:** `world_data/rooms/ethereal/room_1_1_1.yaml`

```yaml
id: room_1_1_1
name: Central Chamber
description: A vast chamber filled with swirling prismatic mists.
room_type: ethereal
area_id: ethereal_nexus
exits:
  north: room_1_1_2
  south: room_1_1_0
  east: room_1_2_1
on_enter_effect: "You step into the shimmering mists."
on_exit_effect: null
lighting_override: null  # Uses area ambient_lighting
```

### Item Template YAML Format

**File:** `world_data/items/weapons/rusty_sword.yaml`

```yaml
id: rusty_sword
name: Rusty Sword
description: A worn blade, still sharp enough to cut.
item_type: weapon
item_subtype: sword
equipment_slot: weapon
weight: 5.0
max_stack_size: 1
rarity: common
value: 10
has_durability: true
max_durability: 100
damage_min: 3
damage_max: 8
attack_speed: 2.0
damage_type: slashing
stat_modifiers:
  strength: 1
flavor_text: "Once wielded by a novice adventurer."
keywords:
  - sword
  - weapon
  - rusty
```

### NPC Template YAML Format

**File:** `world_data/npcs/goblin_scout.yaml`

```yaml
id: goblin_scout
name: Goblin Scout
description: A small, wiry goblin with beady eyes.
npc_type: aggressive
level: 2
max_health: 20
armor_class: 12
strength: 8
dexterity: 14
intelligence: 6
attack_damage_min: 2
attack_damage_max: 5
attack_speed: 1.2
experience_reward: 15
behavior:
  aggressive: true
  wander: true
  flee_health_percent: 20
  social: true
  call_for_help_radius: 2
idle_messages:
  - "The goblin scout scans the area nervously."
  - "A goblin mutters something in its guttural language."
keywords:
  - goblin
  - scout
loot_table:
  - item_id: rusty_dagger
    drop_chance: 0.4
  - item_id: small_health_potion
    drop_chance: 0.2
```

### NPC Spawn YAML Format

**File:** `world_data/npc_spawns/ethereal/spawns.yaml`

```yaml
spawns:
  - template_id: goblin_scout
    room_id: room_1_1_2
    respawn_time_override: 180  # 3 minutes
  - template_id: ethereal_guardian
    room_id: room_1_1_5
    respawn_time_override: -1  # Never respawn
```

### Character Class YAML Format

**File:** `world_data/classes/warrior.yaml`

```yaml
class_id: warrior
name: Warrior
description: A strong melee fighter who excels in close combat.
base_stats:
  strength: 16
  dexterity: 12
  intelligence: 8
  vitality: 14
stat_growth:
  strength: 3
  dexterity: 1
  intelligence: 0
  vitality: 2
resources:
  rage:
    name: Rage
    max_value: 100
    regen_per_second: 0
    regen_in_combat: 5
available_abilities:
  - slash
  - power_attack
  - defensive_stance
```

### Ability YAML Format

**File:** `world_data/abilities/slash.yaml`

```yaml
ability_id: slash
name: Slash
description: A quick melee attack.
ability_type: active
costs:
  energy: 10
cooldown_seconds: 3.0
gcd_seconds: 1.0
target_mode: single_enemy
behavior:
  type: damage
  base_damage: 15
  scaling_stat: strength
  scaling_multiplier: 1.5
```

### Faction YAML Format

**File:** `world_data/factions/order_of_light.yaml`

```yaml
faction_id: order_of_light
name: Order of Light
description: A holy order dedicated to protecting the realm.
faction_type: guild
alignment: good
opposed_factions:
  - shadow_cult
allied_factions:
  - merchants_guild
default_standing: neutral
standing_thresholds:
  hostile: -50
  unfriendly: -10
  neutral: 0
  friendly: 25
  allied: 50
member_npcs:
  - paladin_guard
  - priest_healer
```

### Loading Process

1. **Server Startup**: All YAML files are loaded into the database via `load_yaml.py`
2. **Database to Memory**: `loader.py` loads database records into in-memory `World` object
3. **Hot Reload**: Admin API `/api/admin/content/reload` reloads YAML without restart
4. **Validation**: `/api/admin/content/validate` checks YAML syntax before loading

### CMS Integration Points

The Daemonswright CMS can interact with the game engine by:

1. **Reading current content** via Admin API endpoints (GET /api/admin/world/*)
2. **Creating YAML files** in `world_data/` directories
3. **Triggering hot-reload** via POST /api/admin/content/reload
4. **Validating before save** via POST /api/admin/content/validate
5. **Monitoring errors** via reload response errors array

**Example CMS Workflow:**
```
1. CMS UI creates/edits room in web form
2. CMS generates YAML and writes to world_data/rooms/custom/new_room.yaml
3. CMS calls POST /api/admin/content/reload {"content_type": "rooms", "file_path": "..."}
4. Engine validates and loads new room
5. CMS receives success/error response
6. Players can immediately access new room via movement commands
```

## Internal Architecture

This section documents internal protocols used by the game engine. These are not part of the client-server protocol but are important for understanding the codebase.

### Entity System

The game uses a unified entity system where players and NPCs share a common base.

**EntityType Enum:**
```
PLAYER = "player"
NPC = "npc"
```

**WorldEntity Base Class:**
All entities (players, NPCs) inherit from `WorldEntity`:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `EntityId` | Unique identifier (UUID for players, generated for NPCs) |
| `name` | `str` | Display name |
| `room_id` | `RoomId` | Current location |
| `level` | `int` | Entity level |
| `current_health` | `int` | Current HP |
| `max_health` | `int` | Maximum HP |
| `current_energy` | `int` | Current energy/mana |
| `max_energy` | `int` | Maximum energy/mana |
| `base_strength` | `int` | Base STR stat |
| `base_dexterity` | `int` | Base DEX stat |
| `base_intelligence` | `int` | Base INT stat |
| `base_vitality` | `int` | Base VIT stat |
| `base_armor_class` | `int` | Base AC |
| `inventory` | `List[ItemId]` | Items carried |
| `equipped_items` | `Dict[str, ItemTemplateId]` | Slot → equipped template |
| `active_effects` | `Dict[str, Effect]` | Active buffs/debuffs |
| `combat` | `CombatState` | Real-time combat state |
| `death_time` | `float \| None` | Unix timestamp when died |
| `respawn_event_id` | `str \| None` | Scheduled respawn event |

**Key Methods:**
- `is_alive()` → `bool` - Check if health > 0
- `get_effective_stat(stat_name)` → `int` - Base + effect modifiers
- `get_weapon_stats(item_templates)` → `WeaponStats` - Equipped or unarmed

**WorldPlayer** extends WorldEntity with:
- `experience` - Current XP
- `is_connected` - WebSocket connection status
- `inventory_meta` - Weight/slot tracking

**WorldNpc** extends WorldEntity with:
- `template_id` - Reference to NpcTemplate
- `spawn_room_id` - Where to respawn
- `last_killed_at` - For respawn timing
- `respawn_time_override` - Per-NPC respawn time (-1 = never)
- `idle_event_id`, `wander_event_id` - Behavior timers

### Targetable Protocol

The `Targetable` protocol enables unified command targeting across entity types.

**Protocol Definition:**
```python
class Targetable(Protocol):
    id: str
    name: str
    room_id: RoomId

    def get_target_type(self) -> TargetableType: ...
```

**TargetableType Enum:**
```
PLAYER = "player"
NPC = "npc"
ITEM = "item"
```

**Usage:**
Commands like `attack`, `look`, `give` use the Targetable protocol to find targets by name in the current room, regardless of whether the target is a player, NPC, or item.

### CombatState

Tracks real-time combat for an entity:

| Field | Type | Description |
|-------|------|-------------|
| `phase` | `CombatPhase` | IDLE, WINDUP, SWING, RECOVERY |
| `target_id` | `EntityId \| None` | Current attack target |
| `phase_started_at` | `float` | Unix timestamp |
| `phase_duration` | `float` | Duration of current phase |
| `swing_event_id` | `str \| None` | Scheduled swing event |
| `auto_attack` | `bool` | Continue attacking after swing |
| `current_weapon` | `WeaponStats` | Cached weapon stats |
| `threat_table` | `Dict[EntityId, float]` | Aggro tracking (NPCs) |

**Combat Phases:**
1. **IDLE** - Not in combat
2. **WINDUP** - Preparing attack (interruptible)
3. **SWING** - Attack committed (damage applies at end)
4. **RECOVERY** - Cooldown before next swing

### Room Entity Management

Rooms track entities via a unified `entities` set:

```python
class WorldRoom:
    entities: Set[EntityId]  # Both players and NPCs
```

**Helper Methods on WorldEngine:**
- `_get_players_in_room(room_id)` - Filter to players only
- `_get_npcs_in_room(room_id)` - Filter to NPCs only
- `_find_entity_in_room(room_id, name)` - Find by name match
