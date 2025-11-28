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
3. If player was in stasis, other players in room see reconnection message
4. Client typically sends initial "look" command

### On Disconnect
1. WebSocket connection closes
2. Server marks player as disconnected (stasis mode)
3. Other players in room see stasis message
4. Player remains in world but listed as "(In Stasis)"

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

Client disconnects
← (Other players receive: "A bright flash engulfs PlayerName. Their form flickers and freezes, suspended in prismatic stasis.")
```

## Future Extensions

The protocol is designed to be extensible. Potential future message types:
- `combat` events with structured damage/health data
- `inventory` updates with item lists
- `quest` notifications
- `effect` messages for status effects/buffs/debuffs