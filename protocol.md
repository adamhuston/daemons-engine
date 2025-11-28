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
- `look` or `l` - Examine current room, exits, and other players
- `north`, `south`, `east`, `west`, `up`, `down` - Movement in cardinal directions
- `n`, `s`, `e`, `w`, `u`, `d` - Short forms of movement commands
- `say <message>` - Speak to other players in the same room
- `stats`, `sheet`, `status` - View your character stats
- `effects`, `status` - View active buffs/debuffs with durations
- `time` - View current in-game time with area-specific context
- `smile`, `nod`, `laugh`, `cringe`, `smirk`, `frown`, `wink`, `lookaround` - Emotes
- `heal <player_name>`, `hurt <player_name>` - Debug/admin commands for stat manipulation
- `bless <player_name>` - Apply +5 Armor Class buff for 30 seconds (debug/admin)
- `poison <player_name>` - Apply damage over time: 5 damage every 3s for 15s (debug/admin)
- `testtimer [seconds]` - Test the time event system (debug)
- **Keyword:** `self` - Auto-replaces with your character name in commands

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
- **Room descriptions** - Name, description, exits, and other players
- **Movement feedback** - "You move north." or error messages
- **Chat messages** - Speech from other players
- **Flavor text** - Movement effects, stasis messages, etc.
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

## Event Scoping

The server uses internal scoping to determine which players receive which events:

- **`scope: "player"`** - Sent only to the specific player
- **`scope: "room"`** - Sent to all connected players in the same room
- **`exclude: [player_ids]`** - Room-scoped events can exclude specific players

*Note: Scope fields are internal and stripped before sending to clients. Clients only see the `type`, `player_id`, and `text` fields.*

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

## Future Extensions

The protocol is designed to be extensible. Implemented event types:
- ✅ `message` - Text-based messages and room descriptions
- ✅ `stat_update` - Player stat changes

Potential future message types:
- `combat` events with structured damage/health data
- `inventory` updates with item lists
- `quest` notifications
- `effect` messages for status effects/buffs/debuffs