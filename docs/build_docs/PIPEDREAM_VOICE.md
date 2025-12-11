# Pipedream Voice Chat
An idea for proximity-bound voice chat and ambient audio in the text-based environment

## High-Level Service Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Client (Web/Desktop)                │
│  ┌──────────────────┬──────────────────┬──────────────┐ │
│  │  Game Protocol   │ Voice Protocol   │ Audio Engine │ │
│  │  (WebSocket)     │ (WebRTC/custom)  │ (Web Audio)  │ │
│  └────────┬─────────┴────────┬─────────┴──────────┬───┘ │
└───────────┼──────────────────┼────────────────────┼─────┘
            │                  │                    │
            ▼                  ▼                    ▼
    ┌──────────────┐  ┌──────────────┐    ┌──────────────┐
    │ Game Server  │  │ Voice Server │    │ Audio CDN    │
    │ (FastAPI)    │  │ (WebRTC SFU  │    │ (Ambient     │
    │              │  │  or Mesh)    │    │  Streams)    │
    │ • Tracks     │  │              │    │              │
    │   proximity  │  │ • Maintains  │    │ • Location-  │
    │ • Emits room │  │   voice      │    │   based      │
    │   discovery  │  │   state      │    │   ambient    │
    │   events     │  │ • Routes     │    │   audio      │
    │              │  │   audio      │    │              │
    └──────────────┘  └──────────────┘    └──────────────┘
            │                  │
            └──────────────────┴──────────────────────────►  Database
                        (sync state)
```

---

## Engine Changes Required

### 1. **Voice State Tracking** (New Domain Model)

Add to `app/engine/world.py`:

```python
@dataclass
class VoiceState:
    """Tracks a player's voice capabilities and status."""
    player_id: str
    is_voice_enabled: bool
    is_microphone_muted: bool
    voice_server_url: str  # SFU endpoint
    session_token: str     # Ephemeral token for WebRTC
    proximity_radius: int  # meters/units in game world
    voice_distance_falloff: float  # volume reduction per unit
    last_heartbeat: float  # Unix timestamp
    current_voice_users: set[str]  # Who can hear this player

@dataclass
class AmbientAudioZone:
    """Defines areas with ambient sound."""
    zone_id: str
    room_ids: set[str]
    audio_stream_url: str  # CDN URL to spatial audio
    volume_base: float  # Default amplitude
    fade_distance: int  # Units before audio fades
    audio_type: str  # "wind", "cave_drip", "tavern", etc.

# Add to WorldRoom
@dataclass
class WorldRoom:
    # ... existing fields ...
    ambient_audio_zone_id: str | None = None  # Reference to AmbientAudioZone
    voice_ceiling_height: int = 50  # Max distance for voice travel
```

### 2. **VoiceSystem** (New System)

Create `app/engine/systems/voice.py`:

```python
class VoiceSystem(GameSystem):
    """Manages proximity voice chat, voice state, and SFU coordination."""

    def __init__(self, context: GameContext, voice_server_url: str):
        self.context = context
        self.voice_server_url = voice_server_url
        self.voice_states: dict[str, VoiceState] = {}
        self.ambient_zones: dict[str, AmbientAudioZone] = {}
        # Cache of proximity groups (expensive to recalculate)
        self._proximity_cache: dict[str, set[str]] = {}

    async def initialize_player_voice(self, player_id: str) -> VoiceState:
        """Generate voice session token and return SFU details."""
        # Call voice server to create ephemeral session
        session = await self._create_voice_session(player_id)
        state = VoiceState(
            player_id=player_id,
            is_voice_enabled=True,
            is_microphone_muted=False,
            voice_server_url=self.voice_server_url,
            session_token=session.token,
            proximity_radius=30,  # Units
            voice_distance_falloff=0.1,  # Per-unit volume reduction
            last_heartbeat=time.time(),
            current_voice_users=set()
        )
        self.voice_states[player_id] = state

        # Notify proximity group that this player joined voice
        await self._update_proximity_group(player_id)
        return state

    async def calculate_proximity_group(
        self,
        player_id: str,
        include_self: bool = True
    ) -> set[str]:
        """Find all players within earshot of this player."""
        player = self.context.world.players.get(player_id)
        if not player:
            return set()

        nearby = set()
        room = self.context.world.rooms.get(player.room_id)
        if not room:
            return set()

        # Same room = definitely in range
        for entity_id in room.entities:
            if entity_id == player_id and not include_self:
                continue
            if entity_id in self.context.world.players:
                nearby.add(entity_id)

        # Optional: nearby rooms (vertical/adjacent with attenuation)
        # for direction in ["north", "south", "east", "west"]:
        #     exit_id = room.exits.get(direction)
        #     # Add players in adjacent room with falloff

        return nearby

    async def _update_proximity_group(self, player_id: str):
        """Recalculate and update who hears this player's voice."""
        proximity = await self.calculate_proximity_group(player_id)
        if player_id in self.voice_states:
            self.voice_states[player_id].current_voice_users = proximity

        # Invalidate cache for affected players
        for other_id in proximity:
            self._proximity_cache.pop(other_id, None)

    async def handle_movement(self, player_id: str, new_room_id: str):
        """Update voice state when player moves to new room."""
        await self._update_proximity_group(player_id)

        # Notify voice server of room change (for spatial audio routing)
        await self._send_to_voice_server({
            "action": "player_moved",
            "player_id": player_id,
            "new_room_id": new_room_id
        })

    async def handle_disconnect(self, player_id: str):
        """Clean up voice session on disconnect."""
        if player_id in self.voice_states:
            await self._close_voice_session(player_id)
            del self.voice_states[player_id]

        # Notify nearby players that this voice user left
        for other_id in list(self._proximity_cache.keys()):
            if player_id in self._proximity_cache[other_id]:
                self._proximity_cache[other_id].discard(player_id)

    async def _create_voice_session(self, player_id: str) -> VoiceSession:
        """Request ephemeral voice session from SFU."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.voice_server_url}/api/sessions",
                json={"player_id": player_id}
            ) as resp:
                data = await resp.json()
                return VoiceSession(
                    token=data["session_token"],
                    sfu_url=data["sfu_url"],
                    ice_servers=data["ice_servers"]
                )

    async def _close_voice_session(self, player_id: str):
        """Revoke ephemeral voice session."""
        if player_id not in self.voice_states:
            return

        token = self.voice_states[player_id].session_token
        async with aiohttp.ClientSession() as session:
            await session.delete(
                f"{self.voice_server_url}/api/sessions/{token}"
            )

    async def _send_to_voice_server(self, payload: dict):
        """Send state updates to voice server for spatial routing."""
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{self.voice_server_url}/api/state",
                json=payload
            )
```

### 3. **Protocol Extensions**

Add to protocol.md:

```json
{
  "type": "voice_init",
  "player_id": "uuid",
  "payload": {
    "sfu_url": "wss://voice.example.com/sfu",
    "session_token": "eyJ...",
    "ice_servers": [
      {"urls": ["stun:stun.l.google.com:19302"]},
      {"urls": ["turn:turn.example.com"], "username": "...", "credential": "..."}
    ],
    "proximity_radius": 30,
    "proximity_group": ["player-uuid-1", "player-uuid-2"]
  }
}
```

```json
{
  "type": "proximity_update",
  "player_id": "uuid",
  "added": ["player-uuid-3"],
  "removed": ["player-uuid-4"],
  "payload": {
    "current_voice_users": ["player-uuid-1", "player-uuid-2", "player-uuid-3"]
  }
}
```

```json
{
  "type": "ambient_audio_zone",
  "player_id": "uuid",
  "room_id": "room-123",
  "zone_id": "cave_drip_zone",
  "audio_stream_url": "https://cdn.example.com/ambient/cave_drip.aac",
  "volume": 0.6
}
```

### 4. **Integration into WorldEngine**

Modify `app/engine/engine.py`:

```python
class WorldEngine:
    def __init__(self, world: World, voice_server_url: str = None):
        self.world = world
        self.voice_system = (
            VoiceSystem(self.context, voice_server_url)
            if voice_server_url
            else None
        )
        # ... rest of init ...

    async def _handle_player_connect(self, player_id: str):
        """Initialize voice session on connect."""
        if self.voice_system:
            voice_state = await self.voice_system.initialize_player_voice(player_id)
            # Send voice_init event to client
            await self._dispatch_events([{
                "type": "voice_init",
                "scope": "player",
                "player_id": player_id,
                "payload": {
                    "sfu_url": voice_state.voice_server_url,
                    "session_token": voice_state.session_token,
                    "proximity_radius": voice_state.proximity_radius,
                    "proximity_group": list(
                        await self.voice_system.calculate_proximity_group(player_id)
                    )
                }
            }])

    async def _move_player(self, player_id: str, direction: str):
        """Existing movement logic + voice proximity update."""
        # ... existing move logic ...

        if self.voice_system:
            await self.voice_system.handle_movement(player_id, new_room_id)
```

---

## Voice Server Architecture (Separate Service)

This is a **dedicated microservice**, not part of the game engine. Here's what it needs:

### **Tech Stack Options:**

1. **Janus WebRTC Gateway** (open-source, battle-tested)
   - SFU (Selective Forwarding Unit) = each participant sends one stream, receives N streams
   - Low-latency, minimal bandwidth per client
   - Supports up to 100+ participants per room

2. **Livekit** (hosted or self-hosted)
   - Commercial SFU with great client SDKs
   - Built-in spatial audio support
   - Room-based routing (maps well to game rooms)

3. **Mediasoup** (open-source, modern)
   - More complex setup, but very flexible
   - Can implement custom spatial audio routing
   - Good for custom proximity logic

### **Voice Server Responsibilities:**

```python
# Pseudo-code for voice server
class VoiceServer:
    async def create_session(player_id: str) -> VoiceSession:
        """Generate ephemeral token + SFU room ID."""
        # Create room: game_room_{room_id}
        # Create participant: {player_id}
        # Return WebRTC offer + ICE candidates

    async def update_room_state(room_id: str, state: dict):
        """Update room's spatial configuration."""
        # room_state = {
        #   "player_positions": {player_id: {x, y, z}},
        #   "attenuation_curve": (distance) -> volume
        # }
        # Apply to all active connections in room

    async def mute_player(player_id: str):
        """Server-side mute (client sends silent packets)."""

    async def list_active_participants(room_id: str) -> list[str]:
        """For debugging/monitoring."""
```

---

## Ambient Audio & Spatial Sound

### **Audio Delivery Strategy:**

1. **Ambient Zones** (per-room or multi-room):
   - Stream from CDN (not real-time)
   - Opus/AAC codecs, low bitrate (32kbps)
   - Client cross-fades when entering/leaving zones

2. **Spatial Audio Processing** (client-side):
   - Use Web Audio API or **Resonance Audio** library
   - Pan voice streams based on player positions
   - Apply distance attenuation (volume ∝ 1/distance)

3. **Server doesn't handle audio bytes** — only signaling:
   - Game server tracks positions
   - Sends position deltas to voice server
   - Voice server relays to clients
   - Clients apply spatial effects locally

**Example spatial audio math (client-side):**

```javascript
// When receiving audio from another player
const dx = otherPlayer.x - myPlayer.x;
const dy = otherPlayer.y - myPlayer.y;
const distance = Math.sqrt(dx*dx + dy*dy);

// Pan based on horizontal displacement
const pan = (dx / proximityRadius).clamp(-1, 1);
panner.setPosition(dx, 0, dy);

// Attenuate volume based on distance
const falloff = Math.max(0, 1 - (distance / proximityRadius));
gainNode.gain.setValueAtTime(baseGain * falloff, ctx.currentTime);
```

---

## Database Schema Additions

Add to `app/models.py`:

```python
class VoiceConfiguration(Base):
    """Per-room or per-area voice settings."""
    __tablename__ = "voice_configurations"

    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=True)
    area_id = Column(String, nullable=True)
    proximity_radius = Column(Integer, default=30)  # Units
    voice_ceiling_height = Column(Integer, default=50)  # Vertical limit
    allow_voice = Column(Boolean, default=True)
    allow_ambient = Column(Boolean, default=True)

class AmbientAudioDefinition(Base):
    """Maps zones to audio streams."""
    __tablename__ = "ambient_audio"

    id = Column(String, primary_key=True)
    zone_id = Column(String, unique=True)
    room_ids = Column(JSON)  # [room_id, room_id, ...]
    audio_stream_url = Column(String)
    volume_base = Column(Float, default=0.5)
    fade_distance = Column(Integer, default=20)
    audio_type = Column(String)  # "wind", "tavern", etc.
```

---

## Deployment Topology

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (AWS ALB)                  │
└────────┬──────────────────┬──────────────────┬──────────────┘
         │                  │                  │
    ┌────▼────┐        ┌────▼────┐       ┌────▼────┐
    │ Game    │        │ Game    │       │ Game    │
    │ Server  │        │ Server  │       │ Server  │
    │ (x3)    │        │ (x3)    │       │ (x3)    │
    └────┬────┘        └────┬────┘       └────┬────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                    ┌───────▼───────┐
                    │  Shared DB    │
                    │  (Postgres)   │
                    └───────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 Voice Server Cluster                        │
│  (Separate VM/container set, possibly multi-region)        │
├─────────────────────────────────────────────────────────────┤
│  Load Balancer (for voice)                                 │
│  ├─ Janus/Mediasoup Instance 1                             │
│  ├─ Janus/Mediasoup Instance 2                             │
│  ├─ Janus/Mediasoup Instance 3                             │
│  └─ Redis (session state, player→SFU routing)              │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────────────┐
│ Audio CDN                        │
│ (CloudFront, Bunny, etc.)       │
│ - Ambient audio streams          │
│ - Pre-rendered spatial effects   │
└──────────────────────────────────┘
```

---

## Implementation Roadmap

**Phase PD.1 – Voice Protocol & State**
- ✅ Add VoiceState, AmbientAudioZone to world.py
- ✅ Extend protocol.md with voice_init, proximity_update events
- ✅ Implement VoiceSystem in classes.py

**Phase PD.2 – Game Server Integration**
- Integrate VoiceSystem into WorldEngine
- Add movement hooks to update proximity
- Send voice_init on connect

**Phase PD.3 – Voice Server Deployment**
- Deploy Janus/Livekit instance
- Implement session token generation
- Implement proximity routing logic

**Phase PD.4 – Client Voice UI**
- WebRTC PeerConnection setup
- Microphone permission handling
- Spatial audio visualization
- Ambient audio cross-fade

**Phase PD.5 – Ambient Audio Zones**
- YAML definitions for zones
- CDN stream URLs
- Client-side zone detection and playback

---

## Key Design Decisions

| Decision | Rationale | Trade-offs |
|----------|-----------|-----------|
| **SFU (not mesh)** | Scales better; CPU moved to server instead of client | Requires dedicated voice infrastructure; can't work peer-to-peer |
| **Ephemeral tokens** | Revoke access on disconnect; prevents token replay | Adds token generation latency on connect; requires voice server call |
| **Spatial processing on client** | Reduces voice server load; client GPU/CPU handles panning | Requires Web Audio API support; older browsers may have issues |
| **Game server tracks proximity** | Game server already knows positions; voice server stays stateless | Voice server can't do its own spatial validation; trust game state |
| **Separate voice service** | Decouples concerns; voice server can be scaled/upgraded independently | Added operational complexity; two systems to monitor |
| **Ambient audio via CDN** | No real-time audio burden; just streaming + client-side spatial effects | CDN cost; pre-recorded only (no dynamic mixing) |

---

## Critical Questions for Phase PD.1

Before implementing, resolve:

1. **Fallback behavior**: What happens if voice server is unavailable?
   - Option A: Graceful degrade (text chat only, log warning)
   - Option B: Block voice feature entirely, continue game normally
   - Recommendation: A (voice is optional luxury feature)

2. **Room-based vs. position-based proximity**:
   - Current design: Same room = always in range
   - Alternative: Real 2D/3D coordinates within rooms for fine-grained falloff
   - Recommendation: Start with room-based, add coordinates in Phase PD.4

3. **NPC voice representation**:
   - Option A: NPCs never have voice (no audio stream)
   - Option B: Pre-recorded NPC audio triggered on dialogue/combat
   - Option C: Text-to-speech synthesis server-side
   - Recommendation: A for Phase PD (add B in Phase PD.5+)

4. **Bandwidth budget**:
   - Opus codec @ 16kbps = ~2KB/s per connection
   - 100 concurrent players = 200KB/s egress
   - Voice server cluster size planning
   - Recommendation: Test with Janus in Docker first, profile before production

5. **Recording & moderation**:
   - Should voice streams be recorded for abuse reports?
   - Storage cost & privacy implications
   - Recommendation: Defer entirely; add only if moderation demands it

---

## Implementation Notes

### VoiceSystem Gotchas

1. **Proximity recalculation is expensive**
   - Current design recalculates on every move
   - Optimize: Only update if proximity_radius away from boundary
   - Cache invalidation strategy needed

2. **Connection lifecycle**
   - Player connects → request voice session → race condition if disconnect during token generation
   - Add timeout + cleanup handler
   - Consider: Move voice init to first command, not immediate connect

3. **Voice server single points of failure**
   - If voice server down, game still works (graceful degrade)
   - But clients waiting for voice_init will see lag
   - Recommendation: Make voice_init optional; client retries periodically

### Testing Strategy

```python
# Mock VoiceServer for testing
class MockVoiceServer:
    """Stub for unit tests."""
    async def create_session(self, player_id: str):
        return VoiceSession(
            token=f"mock-token-{player_id}",
            sfu_url="wss://mock.local/sfu",
            ice_servers=[{"urls": ["stun:stun.l.google.com:19302"]}]
        )

# Unit test: proximity calculation
async def test_proximity_calculation():
    """Same room should include all players."""
    voice_system = VoiceSystem(mock_context, "http://mock")
    proximity = await voice_system.calculate_proximity_group("player-1")
    assert "player-2" in proximity  # Both in same room
```

---

## Alternative: Lightweight MVP

If Phase PD feels too heavy, consider **Phase PD-Lite**:

1. **No dedicated voice server** — use Twilio/Vonage WebRTC API
   - They handle SFU, TURN, scaling
   - Pay per minute (not per-month infrastructure)
   - Trade: Less control, higher per-user cost at scale

2. **Text-to-speech ambient only** (no voice chat initially)
   - Google Cloud TTS reads NPC dialogue
   - Synthesized ambient effects ("wind howling", etc.)
   - Trigger: Player enters room
   - Trade: Robotic voices, but zero infrastructure burden

3. **Discord integration** (interim solution)
   - Players join Discord server matching game area
   - Bot manages channels per room
   - Trade: Out-of-game dependency, not integrated, but works today

---

## Monitoring & Observability

Add metrics before Phase PD.2:

```python
# In VoiceSystem
self.metrics = {
    "voice_sessions_active": 0,
    "proximity_updates_total": 0,
    "voice_server_latency_ms": [],
    "session_creation_failures": 0,
}

async def initialize_player_voice(self, player_id: str):
    start = time.time()
    try:
        session = await self._create_voice_session(player_id)
        self.metrics["voice_server_latency_ms"].append(
            (time.time() - start) * 1000
        )
        self.metrics["voice_sessions_active"] += 1
    except Exception as e:
        self.metrics["session_creation_failures"] += 1
        raise
```

Log to structured logging (you already have this in Phase 8):
```python
logger.info("voice.session.created", player_id=player_id, latency_ms=123)
logger.error("voice.session.failed", player_id=player_id, reason=str(e))
```

---

## Post-Implementation: Moderation & Abuse

**Not for Phase PD, but document for Phase PD+1:**

- Voice muting (server-side packet drop)
- Transcript generation (speech-to-text) for reports
- Report flow: Player → Admin → Review voice clip
- Privacy: Audio deleted after 7 days unless reported
- Legal: TOS clause about recording disclosure

This keeps it optional & deferred. ✨

---

## Deferred to Later

- 3D positional audio (requires coordinate system within rooms)
- Voice effects/modulation (voice synthesizers, noise gates)
- Echo cancellation (relies on quality codec; defer to Janus config)
- Multi-language translation (way future)
- Cross-server federation (voice mesh across regions)
