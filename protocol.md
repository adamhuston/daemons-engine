# WebSocket Protocol Documentation

This document describes the communication protocol between the dungeon crawler client and server.

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