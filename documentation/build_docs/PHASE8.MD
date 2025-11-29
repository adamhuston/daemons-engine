# Phase 8 Design Document: Admin & Content Tools

## Executive Summary

Phase 8 transforms Daemons from a developer-operated engine into a production-ready platform with comprehensive administrative tooling. Building on the authentication and permission system from Phase 7, this phase introduces HTTP APIs for content management, in-world admin commands for live operations, and observability infrastructure for monitoring game health.

This phase also lays the groundwork for **Daemonswright**, the planned visual content management system, by ensuring all administrative operations are available via clean REST APIs.

---

## Current State Analysis

### What We Already Have

**Permission Infrastructure (Phase 7):**
```python
class UserRole(str, Enum):
    PLAYER = "player"
    MODERATOR = "moderator"
    GAME_MASTER = "game_master"
    ADMIN = "admin"

class Permission(str, Enum):
    MODIFY_STATS = "modify_stats"
    SPAWN_ITEM = "spawn_item"
    SPAWN_NPC = "spawn_npc"
    TELEPORT = "teleport"
    # ... more defined but not implemented
```

**Existing Admin Commands (Limited):**
```python
# In engine.py - require GAME_MASTER role
heal <player>   # Restore health
hurt <player>   # Deal damage
bless <player>  # Apply buff
poison <player> # Apply DoT
```

**HTTP Endpoints (Player-Focused):**
```
GET  /players              # List players (debug)
POST /auth/*               # Authentication
POST /characters/*         # Character management
WS   /ws/game/auth         # Game connection
```

**Content Loading:**
- YAML files loaded at startup
- No runtime content modification
- No hot-reload capability

### The Gap

| Current State | Required State |
|---------------|----------------|
| 4 admin commands | Full GM toolkit (20+ commands) |
| No content APIs | CRUD for rooms, items, NPCs, triggers |
| No world inspection | Live state queries |
| Print statements | Structured logging + metrics |
| Restart to update content | Hot-reload YAML changes |
| No audit trail for admin actions | Full admin action logging |

---

## Design Philosophy

### Principle 1: API-First Administration

Every admin operation must be available via REST API. In-world commands are convenience wrappers around API calls. This enables:

- **Daemonswright integration** — CMS calls the same APIs
- **Automation** — Scripts and bots can manage the world
- **Testing** — APIs are easier to test than commands
- **Consistency** — One source of truth for admin logic

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Daemonswright  │     │  In-World Cmd   │     │  Admin Script   │
│     (Future)    │     │   (@cmd admin)  │     │    (httpx)      │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │     Admin REST API     │
                    │   /api/admin/world/*   │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │      WorldEngine       │
                    │   (Authoritative)      │
                    └────────────────────────┘
```

### Principle 2: Least Privilege

Admin capabilities are granular. A MODERATOR can mute players but not spawn items. A GAME_MASTER can spawn items but not modify account roles. This is already defined in Phase 7's permission system—Phase 8 enforces it.

### Principle 3: Observable by Default

Every admin action is logged. Every game metric is exposed. Operators should never wonder "what happened?" or "is the server healthy?"

### Principle 4: Non-Destructive Hot-Reload

Content changes apply without restart. But we never corrupt running state—reload failures are logged and ignored, leaving the previous content in place.

---

## Proposed Architecture

### Admin API Structure

```
/api/admin/
├── world/
│   ├── GET    /state                    # Full world state snapshot
│   ├── GET    /rooms                    # List all rooms
│   ├── GET    /rooms/{id}               # Get room details
│   ├── PUT    /rooms/{id}               # Update room
│   ├── POST   /rooms                    # Create room
│   ├── DELETE /rooms/{id}               # Delete room
│   ├── GET    /rooms/{id}/entities      # NPCs/items in room
│   ├── GET    /areas                    # List areas
│   ├── GET    /areas/{id}               # Get area details
│   └── PUT    /areas/{id}               # Update area
│
├── npcs/
│   ├── GET    /templates                # List NPC templates
│   ├── GET    /templates/{id}           # Get template details
│   ├── PUT    /templates/{id}           # Update template
│   ├── POST   /templates                # Create template
│   ├── GET    /instances                # List spawned NPCs
│   ├── POST   /instances                # Spawn NPC
│   ├── DELETE /instances/{id}           # Despawn NPC
│   └── POST   /instances/{id}/move      # Move NPC to room
│
├── items/
│   ├── GET    /templates                # List item templates
│   ├── GET    /templates/{id}           # Get template details
│   ├── PUT    /templates/{id}           # Update template
│   ├── POST   /templates                # Create template
│   ├── GET    /instances                # List all items
│   ├── POST   /instances                # Spawn item
│   ├── DELETE /instances/{id}           # Destroy item
│   └── POST   /instances/{id}/move      # Move item
│
├── players/
│   ├── GET    /                         # List online players
│   ├── GET    /{id}                     # Get player details
│   ├── POST   /{id}/teleport            # Teleport player
│   ├── POST   /{id}/give                # Give item to player
│   ├── POST   /{id}/effect              # Apply effect
│   ├── POST   /{id}/heal                # Heal player
│   ├── POST   /{id}/kill                # Kill player
│   ├── POST   /{id}/kick                # Disconnect player
│   └── POST   /{id}/message             # Send message to player
│
├── triggers/
│   ├── GET    /                         # List all triggers
│   ├── GET    /{scope}/{id}             # Get trigger state
│   ├── POST   /{scope}/{id}/fire        # Manually fire trigger
│   ├── POST   /{scope}/{id}/enable      # Enable trigger
│   ├── POST   /{scope}/{id}/disable     # Disable trigger
│   └── POST   /{scope}/{id}/reset       # Reset fire count
│
├── quests/
│   ├── GET    /templates                # List quest templates
│   ├── GET    /templates/{id}           # Get quest details
│   ├── GET    /progress/{player_id}     # Get player's quest state
│   ├── POST   /progress/{player_id}     # Modify quest progress
│   └── POST   /chains                   # List quest chains
│
├── content/
│   ├── POST   /reload                   # Hot-reload all YAML
│   ├── POST   /reload/rooms             # Reload room definitions
│   ├── POST   /reload/npcs              # Reload NPC templates
│   ├── POST   /reload/items             # Reload item templates
│   ├── POST   /reload/triggers          # Reload triggers
│   ├── POST   /reload/quests            # Reload quests
│   └── GET    /validate                 # Validate YAML without loading
│
├── accounts/
│   ├── GET    /                         # List accounts
│   ├── GET    /{id}                     # Get account details
│   ├── PUT    /{id}/role                # Change user role
│   ├── POST   /{id}/ban                 # Ban account
│   ├── POST   /{id}/unban               # Unban account
│   └── GET    /{id}/security-events     # Get security log
│
└── server/
    ├── GET    /status                   # Server health
    ├── GET    /metrics                  # Prometheus-style metrics
    ├── POST   /broadcast                # Message all players
    ├── POST   /maintenance              # Enter maintenance mode
    └── POST   /shutdown                 # Graceful shutdown
```

### In-World Admin Commands

Commands are organized by permission level:

**MODERATOR Commands:**
```
mute <player> [duration]     # Prevent player from chatting
unmute <player>              # Remove mute
kick <player> [reason]       # Disconnect player
warn <player> <message>      # Send warning message
where <player>               # Show player location
who                          # List online players with locations
```

**GAME_MASTER Commands:**
```
# Teleportation
goto <room_id>               # Teleport self to room
goto <player>                # Teleport self to player
summon <player>              # Teleport player to you
teleport <player> <room>     # Teleport player to room

# Spawning
spawn item <template_id> [quantity]    # Spawn item in room
spawn npc <template_id>                # Spawn NPC in room
despawn npc <instance_id>              # Remove NPC
despawn item <instance_id>             # Remove item

# Player manipulation
give <player> <item_template> [qty]    # Give item to player
take <player> <item_keyword>           # Remove item from player
heal <player> [amount]                 # Heal player (existing)
hurt <player> <amount>                 # Damage player (existing)
kill <player>                          # Kill player instantly
revive <player>                        # Revive dead player
setstat <player> <stat> <value>        # Modify player stat
effect <player> <effect_id> [duration] # Apply effect

# World inspection
inspect <target>             # Detailed info on player/NPC/item
roominfo                     # Detailed current room info
triggers                     # List triggers in current room
flags                        # Show room flags

# Visibility
invis                        # Toggle invisibility
visible                      # Become visible

# Quest manipulation
questgive <player> <quest_id>          # Give quest to player
questcomplete <player> <quest_id>      # Complete quest for player
questreset <player> <quest_id>         # Reset quest progress
```

**ADMIN Commands:**
```
# Account management
ban <username> <duration> <reason>     # Ban account
unban <username>                       # Remove ban
setrole <username> <role>              # Change user role

# Server control
broadcast <message>          # Message all players
reload                       # Hot-reload all content
reload <type>                # Reload specific content type
maintenance on|off           # Toggle maintenance mode
shutdown [seconds]           # Graceful shutdown with countdown

# Debugging
eval <expression>            # Execute Python (dangerous, optional)
sql <query>                  # Execute SQL query (read-only)
```

### Observability Infrastructure

**Structured Logging:**
```python
import structlog

logger = structlog.get_logger()

# Instead of print()
logger.info(
    "player_connected",
    player_id=player.id,
    player_name=player.name,
    room_id=player.room_id,
    ip_address=request.client.host
)

logger.warning(
    "admin_command_executed",
    admin_id=admin.id,
    command="spawn item sword_of_doom",
    target_room=room.id
)
```

**Metrics (Prometheus-compatible):**
```python
from prometheus_client import Counter, Gauge, Histogram

# Gauges (current values)
players_online = Gauge('daemons_players_online', 'Currently connected players')
npcs_alive = Gauge('daemons_npcs_alive', 'Currently alive NPCs')
rooms_occupied = Gauge('daemons_rooms_occupied', 'Rooms with players')

# Counters (cumulative)
commands_total = Counter('daemons_commands_total', 'Commands processed', ['command'])
events_total = Counter('daemons_events_total', 'Events dispatched', ['type'])
combat_kills = Counter('daemons_combat_kills', 'Combat kills', ['killer_type', 'victim_type'])

# Histograms (distributions)
command_duration = Histogram('daemons_command_duration_seconds', 'Command processing time')
event_queue_size = Histogram('daemons_event_queue_size', 'Event queue depth')
```

**Admin Action Audit Log:**
```python
@dataclass
class AdminAction:
    id: str
    timestamp: float
    admin_account_id: str
    admin_username: str
    action_type: str          # "spawn_item", "teleport", "ban", etc.
    target_type: str | None   # "player", "npc", "room", etc.
    target_id: str | None
    parameters: dict
    result: str               # "success", "failed", "denied"
    error_message: str | None

# Stored in database, queryable via API
```

### Hot-Reload System

```python
class ContentReloader:
    """Handles runtime content updates without restart."""
    
    def __init__(self, world: World, engine: WorldEngine):
        self.world = world
        self.engine = engine
        self._reload_lock = asyncio.Lock()
    
    async def reload_all(self) -> ReloadResult:
        """Reload all YAML content."""
        async with self._reload_lock:
            results = {}
            results['rooms'] = await self._reload_rooms()
            results['npcs'] = await self._reload_npcs()
            results['items'] = await self._reload_items()
            results['triggers'] = await self._reload_triggers()
            results['quests'] = await self._reload_quests()
            return ReloadResult(results)
    
    async def _reload_rooms(self) -> dict:
        """
        Reload room definitions.
        
        Strategy:
        - Update existing rooms in place (preserve player positions)
        - Add new rooms
        - Mark removed rooms as inaccessible (don't delete with players in them)
        """
        try:
            new_rooms = load_rooms_from_yaml()
            
            updated = 0
            added = 0
            
            for room_id, new_room in new_rooms.items():
                if room_id in self.world.rooms:
                    # Update in place
                    existing = self.world.rooms[room_id]
                    existing.name = new_room.name
                    existing.description = new_room.description
                    existing.exits = new_room.exits
                    # Preserve: players, items, dynamic_exits, flags
                    updated += 1
                else:
                    # Add new room
                    self.world.rooms[room_id] = new_room
                    added += 1
            
            return {"status": "success", "updated": updated, "added": added}
            
        except Exception as e:
            logger.error("room_reload_failed", error=str(e))
            return {"status": "failed", "error": str(e)}
```

---

## Data Structures

### Admin Action Types

```python
class AdminActionType(str, Enum):
    # Player actions
    TELEPORT_PLAYER = "teleport_player"
    GIVE_ITEM = "give_item"
    TAKE_ITEM = "take_item"
    HEAL_PLAYER = "heal_player"
    DAMAGE_PLAYER = "damage_player"
    KILL_PLAYER = "kill_player"
    REVIVE_PLAYER = "revive_player"
    APPLY_EFFECT = "apply_effect"
    MODIFY_STAT = "modify_stat"
    KICK_PLAYER = "kick_player"
    MUTE_PLAYER = "mute_player"
    
    # Spawn actions
    SPAWN_ITEM = "spawn_item"
    SPAWN_NPC = "spawn_npc"
    DESPAWN_ITEM = "despawn_item"
    DESPAWN_NPC = "despawn_npc"
    
    # World actions
    MODIFY_ROOM = "modify_room"
    FIRE_TRIGGER = "fire_trigger"
    TOGGLE_TRIGGER = "toggle_trigger"
    
    # Account actions
    BAN_ACCOUNT = "ban_account"
    UNBAN_ACCOUNT = "unban_account"
    CHANGE_ROLE = "change_role"
    
    # Server actions
    BROADCAST = "broadcast"
    RELOAD_CONTENT = "reload_content"
    MAINTENANCE_MODE = "maintenance_mode"
    SHUTDOWN = "shutdown"
```

### Server Status Response

```python
@dataclass
class ServerStatus:
    uptime_seconds: float
    players_online: int
    players_in_combat: int
    npcs_alive: int
    rooms_total: int
    rooms_occupied: int
    
    # Performance
    commands_per_minute: float
    events_per_minute: float
    avg_command_latency_ms: float
    
    # Time system
    scheduled_events: int
    next_event_in_seconds: float | None
    
    # Memory (optional)
    memory_mb: float | None
    
    # State
    maintenance_mode: bool
    last_content_reload: float | None
```

### Reload Result

```python
@dataclass
class ReloadResult:
    success: bool
    timestamp: float
    duration_ms: float
    results: dict[str, ReloadSectionResult]

@dataclass
class ReloadSectionResult:
    status: str  # "success", "failed", "skipped"
    updated: int
    added: int
    removed: int
    errors: list[str]
```

---

## Database Extensions

```python
class AdminAction(Base):
    """Audit log for administrative actions."""
    __tablename__ = "admin_actions"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[float] = mapped_column(Float, index=True)
    
    admin_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_accounts.id"), index=True
    )
    admin_username: Mapped[str] = mapped_column(String(50))
    
    action_type: Mapped[str] = mapped_column(String(50), index=True)
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[str] = mapped_column(String(20))  # success, failed, denied
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Relationship
    admin: Mapped["UserAccount"] = relationship()


class ServerMetricSnapshot(Base):
    """Periodic server metrics for historical analysis."""
    __tablename__ = "server_metrics"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[float] = mapped_column(Float, index=True)
    
    players_online: Mapped[int] = mapped_column(Integer)
    npcs_alive: Mapped[int] = mapped_column(Integer)
    commands_per_minute: Mapped[float] = mapped_column(Float)
    avg_latency_ms: Mapped[float] = mapped_column(Float)
    memory_mb: Mapped[float] = mapped_column(Float)
    
    # Indexed for time-range queries
    __table_args__ = (
        Index('ix_metrics_timestamp', 'timestamp'),
    )
```

---

## Implementation Phases

### Phase 8.1 - Admin API Foundation

1. Create `backend/app/routes/admin.py` with FastAPI router
2. Implement authentication middleware requiring ADMIN/GAME_MASTER roles
3. Add basic endpoints: `/status`, `/players`, `/rooms`
4. Create `AdminService` class for business logic separation

### Phase 8.2 - World Inspection APIs

1. Implement `/world/state` for full snapshot
2. Add entity listing: `/npcs/instances`, `/items/instances`
3. Implement detail endpoints with full state serialization
4. Add filtering and pagination for large result sets

### Phase 8.3 - World Manipulation APIs

1. Player manipulation: teleport, give, heal, kick
2. Entity spawning: spawn/despawn NPCs and items
3. Trigger control: fire, enable, disable, reset
4. Quest manipulation: give, complete, reset

### Phase 8.4 - In-World Commands

1. Implement MODERATOR commands (mute, kick, warn, where, who)
2. Implement GAME_MASTER commands (goto, spawn, give, inspect)
3. Implement ADMIN commands (ban, broadcast, reload)
4. Add `@requires_permission` decorators throughout

### Phase 8.5 - Hot-Reload System

1. Create `ContentReloader` class
2. Implement safe reload for each content type
3. Add validation before applying changes
4. Create `/content/reload` and `/content/validate` endpoints

### Phase 8.6 - Observability

1. Replace print statements with structlog
2. Add prometheus_client metrics
3. Create AdminAction audit logging
4. Implement `/metrics` endpoint
5. Add periodic metric snapshots to database

### Phase 8.7 - Account Management

1. Implement ban/unban with expiration
2. Add role modification with audit trail
3. Create maintenance mode toggle
4. Implement graceful shutdown with player notification

---

## Security Considerations

### API Authentication

All admin endpoints require:
1. Valid JWT access token
2. Appropriate role (checked via middleware)
3. Specific permission for the action

```python
@router.post("/players/{player_id}/teleport")
@requires_permission(Permission.TELEPORT)
async def teleport_player(
    player_id: str,
    request: TeleportRequest,
    current_user: UserAccount = Depends(get_current_admin)
):
    ...
```

### Rate Limiting (Phase 10)

Admin APIs will have separate, higher rate limits than player APIs, but still limited to prevent abuse.

### Audit Trail

Every admin action is logged with:
- Who performed it
- What they did
- When they did it
- What the result was
- Full parameters for replay/investigation

### Dangerous Operations

Some operations require additional confirmation:
- `shutdown` - Requires countdown parameter
- `eval` - Disabled by default, requires config flag
- `DELETE` endpoints - Require confirmation header
- Role changes - Logged to security events

---

## Integration with Daemonswright

The admin API is designed to be the backend for Daemonswright:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Daemonswright                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Room Editor │  │ NPC Builder │  │ Quest Graph │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│         └────────────────┼────────────────┘                      │
│                          │                                       │
│                          ▼                                       │
│              ┌─────────────────────┐                             │
│              │   API Client Layer  │                             │
│              └──────────┬──────────┘                             │
└─────────────────────────┼───────────────────────────────────────┘
                          │ HTTP/REST
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Daemons Engine                              │
│              /api/admin/* endpoints                              │
└─────────────────────────────────────────────────────────────────┘
```

Daemonswright will:
1. Authenticate via `/auth/login`
2. Fetch current state via GET endpoints
3. Apply changes via PUT/POST endpoints
4. Validate before save via `/content/validate`
5. Hot-reload after changes via `/content/reload`

---

## Future Considerations

### Real-Time Admin Dashboard

WebSocket endpoint for live updates:
```
WS /ws/admin/monitor
```

Pushes:
- Player connect/disconnect events
- Combat events
- Error events
- Metric updates

### Multi-Server Support

When Daemons supports multiple engine instances:
- Admin API becomes a coordinator
- Actions are routed to appropriate instance
- Metrics are aggregated

### Content Versioning

Future enhancement for Daemonswright:
- Track content changes over time
- Rollback to previous versions
- Diff between versions

---

## Conclusion

Phase 8 completes the operational tooling needed to run Daemons in production. By exposing all administrative functions via REST APIs, we enable both in-game administration and external tools like Daemonswright. The observability infrastructure ensures operators always know the state of their world, and the audit logging provides accountability for all administrative actions.

The hot-reload system is particularly important—it means content creators using Daemonswright can see their changes immediately without disrupting players. This tight feedback loop is essential for iterative world-building.