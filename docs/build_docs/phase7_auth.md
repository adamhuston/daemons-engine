# Phase 7 Design Document: Accounts, Authentication, and Security

## Executive Summary

Phase 7 transforms our MUD from a simple player_id-based system into a full account-based architecture with authentication, authorization, and security controls. This phase introduces user accounts separate from player characters (enabling multiple characters per account), JWT-based authentication for both HTTP and WebSocket connections, and role-based permissions for administrative commands. Building on the persistence infrastructure from Phase 6, we ensure secure credential storage, session management, and audit logging.

---

## Current State Analysis

### What We Already Have

**Player Identification** - Simple UUID-based system:
```python
# Current: player_id passed directly in WebSocket URL
ws://localhost:8000/ws/game?player_id=abc-123-def

# No verification that the client owns this player_id
# Anyone who knows a player_id can connect as that player
```

**Database Models** - Player tied directly to game state:
```python
class Player(Base):
    id: Mapped[str]  # UUID string
    name: Mapped[str]
    current_room_id: Mapped[str]
    # ... game stats ...
    # No password, no account reference
```

**WebSocket Connection** - No authentication:
```python
@app.websocket("/ws/game")
async def websocket_game(ws: WebSocket, player_id: str = Query(...)):
    # player_id is trusted without verification
    await ws.accept()
    engine.register_player(player_id, ws)
```

**Admin Commands** - Available to everyone:
```python
@cmd("heal")
def do_heal(ctx, args):
    # Any player can heal any other player
    # No permission check
```

### The Gap

| Current State | Required State |
|---------------|----------------|
| player_id in URL | Authenticated token |
| Anyone can impersonate | Cryptographic identity verification |
| One player per "account" | Multiple characters per account |
| No passwords | Secure credential storage |
| No admin roles | Role-based permissions |
| No session management | Token refresh, revocation |
| No audit trail | Security event logging |

---

## Design Philosophy

### Principle 1: Accounts ≠ Characters

A **UserAccount** represents a real person with credentials. A **Player** (character) is a game entity owned by an account. This separation enables:

- Multiple characters per account
- Account-level bans without losing character data
- Shared account settings across characters
- Future: character transfers between accounts

```
UserAccount (1) ──────< (N) Player/Character
     │
     ├── email
     ├── password_hash
     ├── roles
     └── settings
```

### Principle 2: Stateless Authentication with JWT

JSON Web Tokens provide:
- **Stateless verification**: No session database lookup per request
- **Embedded claims**: User ID, roles, expiration in the token
- **Cross-service compatibility**: Future microservice architecture
- **Standard tooling**: Well-tested libraries, debuggable tokens

Token flow:
```
1. Client → POST /auth/login (email, password)
2. Server → { access_token, refresh_token }
3. Client → WS /ws/game?token=<access_token>
4. Server verifies token signature, extracts user_id
5. Server looks up user's active character
```

### Principle 3: Defense in Depth

Security is layered:

| Layer | Protection |
|-------|------------|
| **Transport** | HTTPS/WSS in production |
| **Authentication** | JWT with short expiry |
| **Authorization** | Role-based command permissions |
| **Input validation** | Schema validation, sanitization |
| **Rate limiting** | Per-IP and per-account limits |
| **Audit logging** | Security-relevant event trail |

### Principle 4: Minimal Trust, Maximum Verification

- Never trust client-provided player_id
- Always verify token signatures
- Re-validate permissions on each command
- Log security-relevant events
- Fail closed (deny by default)

---

## Proposed Architecture

### Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Authentication Flow                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────┐     ┌─────────────┐     ┌─────────────┐     ┌───────────────┐   │
│  │ Client │────▶│ POST /login │────▶│ Verify Creds│────▶│ Generate JWT  │   │
│  └────────┘     └─────────────┘     └─────────────┘     └───────────────┘   │
│       │                                                         │            │
│       │              ┌──────────────────────────────────────────┘            │
│       │              ▼                                                       │
│       │         { access_token (15min), refresh_token (7d) }                │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ WS /ws/game?token=<access_token>                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────┐    │
│  │ Verify JWT  │────▶│ Extract     │────▶│ Load User + Active Character│    │
│  │ Signature   │     │ user_id     │     │ Register with WorldEngine   │    │
│  └─────────────┘     └─────────────┘     └─────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Token Refresh Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Token Refresh Flow                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Access token expires after 15 minutes                                       │
│  Refresh token valid for 7 days (stored securely by client)                │
│                                                                              │
│  ┌────────┐     ┌──────────────────┐     ┌─────────────┐                    │
│  │ Client │────▶│ POST /auth/refresh│────▶│ Verify      │                    │
│  └────────┘     │ { refresh_token } │     │ Refresh JWT │                    │
│       ▲         └──────────────────┘     └─────────────┘                    │
│       │                                         │                            │
│       │         ┌───────────────────────────────┘                            │
│       │         ▼                                                            │
│       │    ┌─────────────────────────────────────────────────┐              │
│       └────│ { new_access_token (15min), new_refresh_token } │              │
│            └─────────────────────────────────────────────────┘              │
│                                                                              │
│  Refresh token rotation: old refresh token invalidated on use               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Core Data Structures

```python
class UserRole(str, Enum):
    """User permission levels."""
    PLAYER = "player"           # Normal player
    MODERATOR = "moderator"     # Can mute, kick, view reports
    GAME_MASTER = "game_master" # Can spawn items, teleport, edit world
    ADMIN = "admin"             # Full access, user management

@dataclass
class UserAccount:
    """A registered user account."""
    id: str                     # UUID
    email: str                  # Unique, for login and recovery
    username: str               # Display name, unique
    password_hash: str          # Argon2id hash

    # Roles and permissions
    roles: set[UserRole] = field(default_factory=lambda: {UserRole.PLAYER})

    # Account state
    is_active: bool = True      # Can login
    is_verified: bool = False   # Email verified
    is_banned: bool = False     # Account suspended
    ban_reason: str | None = None
    ban_expires_at: float | None = None

    # Timestamps
    created_at: float = field(default_factory=time.time)
    last_login_at: float | None = None

    # Settings
    preferences: dict[str, Any] = field(default_factory=dict)

    # Characters
    character_ids: list[str] = field(default_factory=list)
    active_character_id: str | None = None
    max_characters: int = 3     # Configurable per account

@dataclass
class RefreshToken:
    """A refresh token for session management."""
    id: str                     # UUID, stored in token
    user_id: str                # Owner account
    token_hash: str             # SHA256 of actual token (we store hash, not token)

    created_at: float
    expires_at: float

    # Security metadata
    ip_address: str | None = None
    user_agent: str | None = None

    # State
    is_revoked: bool = False
    revoked_at: float | None = None
    replaced_by: str | None = None  # ID of token that replaced this one

@dataclass
class SecurityEvent:
    """An auditable security event."""
    id: str
    timestamp: float
    event_type: str             # login_success, login_failure, token_refresh, etc.
    user_id: str | None
    ip_address: str
    user_agent: str | None
    details: dict[str, Any] = field(default_factory=dict)
```

### Database Schema Extensions

```python
class UserAccount(Base):
    """User account for authentication."""
    __tablename__ = "user_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    # Roles stored as JSON array
    roles: Mapped[list] = mapped_column(JSON, default=["player"])

    # Account state
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    ban_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ban_expires_at: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timestamps
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    last_login_at: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Settings
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)

    # Character management
    active_character_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("players.id"), nullable=True
    )
    max_characters: Mapped[int] = mapped_column(Integer, default=3)

    # Relationships
    characters: Mapped[list["Player"]] = relationship(
        back_populates="account",
        foreign_keys="Player.account_id"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user"
    )

class RefreshToken(Base):
    """Refresh tokens for session management."""
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_accounts.id"))
    token_hash: Mapped[str] = mapped_column(String(64), index=True)  # SHA256

    created_at: Mapped[float] = mapped_column(Float)
    expires_at: Mapped[float] = mapped_column(Float, index=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    replaced_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Relationship
    user: Mapped["UserAccount"] = relationship(back_populates="refresh_tokens")

class SecurityEvent(Base):
    """Audit log for security events."""
    __tablename__ = "security_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[float] = mapped_column(Float, index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    ip_address: Mapped[str] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)

# Extend Player model
class Player(Base):
    # ... existing fields ...

    # Link to account
    account_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user_accounts.id"), nullable=True
    )

    # Relationship
    account: Mapped["UserAccount | None"] = relationship(
        back_populates="characters",
        foreign_keys=[account_id]
    )
```

### AuthSystem Class

```python
class AuthSystem:
    """Handles authentication, authorization, and session management."""

    def __init__(
        self,
        db_session_factory: Callable[[], AsyncSession],
        secret_key: str,
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 7
    ):
        self.db_session_factory = db_session_factory
        self.secret_key = secret_key
        self.access_token_expire = timedelta(minutes=access_token_expire_minutes)
        self.refresh_token_expire = timedelta(days=refresh_token_expire_days)
        self.password_hasher = PasswordHasher()  # Argon2

    # === Account Management ===

    async def create_account(
        self,
        email: str,
        username: str,
        password: str,
        ip_address: str
    ) -> tuple[UserAccount, list[Event]]:
        """Create a new user account."""
        ...

    async def verify_email(self, token: str) -> bool:
        """Verify email address with token."""
        ...

    async def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> bool:
        """Change account password."""
        ...

    async def reset_password_request(self, email: str) -> bool:
        """Initiate password reset flow."""
        ...

    # === Authentication ===

    async def login(
        self,
        email_or_username: str,
        password: str,
        ip_address: str,
        user_agent: str | None
    ) -> tuple[str, str, UserAccount] | None:
        """
        Authenticate user and return tokens.
        Returns: (access_token, refresh_token, user) or None if failed.
        """
        ...

    async def refresh_access_token(
        self,
        refresh_token: str,
        ip_address: str,
        user_agent: str | None
    ) -> tuple[str, str] | None:
        """
        Use refresh token to get new access token.
        Implements token rotation (old refresh token invalidated).
        Returns: (new_access_token, new_refresh_token) or None.
        """
        ...

    async def logout(self, refresh_token: str) -> bool:
        """Revoke refresh token."""
        ...

    async def logout_all_sessions(self, user_id: str) -> int:
        """Revoke all refresh tokens for user. Returns count revoked."""
        ...

    def verify_access_token(self, token: str) -> dict | None:
        """
        Verify JWT and extract claims.
        Returns: {"user_id": ..., "roles": [...], "exp": ...} or None.
        """
        ...

    # === Authorization ===

    def has_role(self, user: UserAccount, role: UserRole) -> bool:
        """Check if user has a specific role."""
        return role in user.roles or UserRole.ADMIN in user.roles

    def has_permission(self, user: UserAccount, permission: str) -> bool:
        """Check if user has a specific permission."""
        ...

    # === Character Management ===

    async def create_character(
        self,
        user_id: str,
        character_name: str,
        character_class: str
    ) -> Player | None:
        """Create a new character for an account."""
        ...

    async def delete_character(
        self,
        user_id: str,
        character_id: str,
        password: str  # Require password for destructive action
    ) -> bool:
        """Delete a character (with confirmation)."""
        ...

    async def switch_character(
        self,
        user_id: str,
        character_id: str
    ) -> Player | None:
        """Switch active character."""
        ...

    # === Security Events ===

    async def log_event(
        self,
        event_type: str,
        user_id: str | None,
        ip_address: str,
        user_agent: str | None = None,
        details: dict | None = None
    ) -> None:
        """Log a security event."""
        ...

    async def get_recent_events(
        self,
        user_id: str,
        limit: int = 10
    ) -> list[SecurityEvent]:
        """Get recent security events for a user."""
        ...
```

### Permission System

```python
class Permission(str, Enum):
    """Granular permissions for commands and actions."""

    # Player permissions (default)
    PLAY = "play"                       # Basic gameplay
    CHAT = "chat"                       # Send messages
    TRADE = "trade"                     # Trade with players

    # Moderator permissions
    MUTE_PLAYER = "mute_player"         # Mute chat
    KICK_PLAYER = "kick_player"         # Disconnect player
    VIEW_REPORTS = "view_reports"       # See player reports
    WARN_PLAYER = "warn_player"         # Issue warnings

    # Game Master permissions
    TELEPORT = "teleport"               # Teleport self/others
    SPAWN_ITEM = "spawn_item"           # Create items
    SPAWN_NPC = "spawn_npc"             # Spawn NPCs
    MODIFY_STATS = "modify_stats"       # Edit player stats
    INVISIBLE = "invisible"             # Go invisible
    INVULNERABLE = "invulnerable"       # God mode

    # Admin permissions
    MANAGE_ACCOUNTS = "manage_accounts" # Ban, unban, verify
    MANAGE_ROLES = "manage_roles"       # Assign roles
    VIEW_LOGS = "view_logs"             # Security event logs
    SERVER_COMMANDS = "server_commands" # Restart, maintenance

# Role to permission mapping
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.PLAYER: {
        Permission.PLAY,
        Permission.CHAT,
        Permission.TRADE,
    },
    UserRole.MODERATOR: {
        Permission.PLAY,
        Permission.CHAT,
        Permission.TRADE,
        Permission.MUTE_PLAYER,
        Permission.KICK_PLAYER,
        Permission.VIEW_REPORTS,
        Permission.WARN_PLAYER,
    },
    UserRole.GAME_MASTER: {
        Permission.PLAY,
        Permission.CHAT,
        Permission.TRADE,
        Permission.MUTE_PLAYER,
        Permission.KICK_PLAYER,
        Permission.VIEW_REPORTS,
        Permission.WARN_PLAYER,
        Permission.TELEPORT,
        Permission.SPAWN_ITEM,
        Permission.SPAWN_NPC,
        Permission.MODIFY_STATS,
        Permission.INVISIBLE,
        Permission.INVULNERABLE,
    },
    UserRole.ADMIN: set(Permission),  # All permissions
}

def requires_permission(permission: Permission):
    """Decorator to require a permission for a command handler."""
    def decorator(func):
        @wraps(func)
        async def wrapper(ctx: GameContext, player_id: str, args: list[str]):
            player = ctx.world.players.get(player_id)
            if not player or not player.account:
                return [ctx.events.error(player_id, "You must be logged in.")]

            if not ctx.auth.has_permission(player.account, permission):
                return [ctx.events.error(player_id, "You don't have permission to do that.")]

            return await func(ctx, player_id, args)
        return wrapper
    return decorator
```

---

## API Endpoints

### Authentication Endpoints

```python
# POST /auth/register
class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str

class RegisterResponse(BaseModel):
    user_id: str
    message: str  # "Check your email to verify your account"

# POST /auth/login
class LoginRequest(BaseModel):
    email_or_username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires
    user: UserInfo

class UserInfo(BaseModel):
    id: str
    username: str
    email: str
    roles: list[str]
    active_character: CharacterInfo | None
    characters: list[CharacterInfo]

# POST /auth/refresh
class RefreshRequest(BaseModel):
    refresh_token: str

class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int

# POST /auth/logout
class LogoutRequest(BaseModel):
    refresh_token: str

# POST /auth/logout-all
# (Requires authentication via access token)

# POST /auth/change-password
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

# POST /auth/forgot-password
class ForgotPasswordRequest(BaseModel):
    email: str

# POST /auth/reset-password
class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
```

### Character Management Endpoints

```python
# GET /characters
# Returns list of user's characters

# POST /characters
class CreateCharacterRequest(BaseModel):
    name: str
    character_class: str

# DELETE /characters/{character_id}
class DeleteCharacterRequest(BaseModel):
    password: str  # Confirmation

# POST /characters/{character_id}/activate
# Switch active character
```

### WebSocket Authentication

```python
@app.websocket("/ws/game")
async def websocket_game(
    ws: WebSocket,
    token: str = Query(...)  # Changed from player_id to token
):
    # Verify JWT
    claims = auth_system.verify_access_token(token)
    if not claims:
        await ws.close(code=4001, reason="Invalid or expired token")
        return

    user_id = claims["user_id"]

    # Get user and active character
    async with db_session() as session:
        user = await session.get(UserAccount, user_id)
        if not user or not user.is_active or user.is_banned:
            await ws.close(code=4003, reason="Account unavailable")
            return

        if not user.active_character_id:
            await ws.close(code=4004, reason="No active character")
            return

        player = await session.get(Player, user.active_character_id)

    # Proceed with connection
    await ws.accept()
    engine.register_player(player.id, ws, user=user)
```

---

## Security Considerations

### Password Requirements

```python
class PasswordPolicy:
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = False  # Optional for usability

    COMMON_PASSWORDS_FILE = "data/common_passwords.txt"

    @classmethod
    def validate(cls, password: str) -> tuple[bool, str | None]:
        """Validate password against policy. Returns (is_valid, error_message)."""
        if len(password) < cls.MIN_LENGTH:
            return False, f"Password must be at least {cls.MIN_LENGTH} characters"
        if len(password) > cls.MAX_LENGTH:
            return False, f"Password must be at most {cls.MAX_LENGTH} characters"
        if cls.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            return False, "Password must contain an uppercase letter"
        if cls.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            return False, "Password must contain a lowercase letter"
        if cls.REQUIRE_DIGIT and not any(c.isdigit() for c in password):
            return False, "Password must contain a digit"
        if cls._is_common_password(password):
            return False, "Password is too common"
        return True, None
```

### Rate Limiting

```python
class RateLimiter:
    """Rate limiting for security-sensitive operations."""

    # Limits per IP address
    LOGIN_ATTEMPTS_PER_MINUTE = 5
    LOGIN_ATTEMPTS_PER_HOUR = 20
    REGISTRATION_PER_HOUR = 3
    PASSWORD_RESET_PER_HOUR = 3

    # Limits per account
    FAILED_LOGINS_BEFORE_LOCKOUT = 5
    LOCKOUT_DURATION_MINUTES = 15

    async def check_login_rate(self, ip: str, email: str) -> tuple[bool, str | None]:
        """Check if login attempt is allowed."""
        ...

    async def record_failed_login(self, ip: str, email: str) -> None:
        """Record a failed login attempt."""
        ...

    async def record_successful_login(self, ip: str, email: str) -> None:
        """Clear failed login counter on success."""
        ...
```

### Token Security

```python
# Access token payload
{
    "sub": "user-uuid",           # Subject (user ID)
    "roles": ["player"],          # User roles
    "char": "character-uuid",     # Active character (optional)
    "iat": 1234567890,            # Issued at
    "exp": 1234568790,            # Expires at (15 min from iat)
    "jti": "token-uuid"           # Unique token ID
}

# Refresh token payload
{
    "sub": "user-uuid",
    "type": "refresh",
    "jti": "refresh-token-uuid",
    "iat": 1234567890,
    "exp": 1235172690             # Expires at (7 days from iat)
}

# Security measures:
# - Short access token lifetime (15 minutes)
# - Refresh token rotation (new token on each refresh)
# - Refresh token stored as hash in database
# - IP and user-agent binding for refresh tokens
# - Ability to revoke all sessions
```

### Audit Events

| Event Type | When Logged | Details |
|------------|-------------|---------|
| `register` | Account created | email, username |
| `login_success` | Successful login | user_id |
| `login_failure` | Failed login | email_or_username, reason |
| `logout` | Token revoked | user_id |
| `token_refresh` | Tokens refreshed | user_id |
| `password_change` | Password changed | user_id |
| `password_reset_request` | Reset requested | email |
| `password_reset_complete` | Reset completed | user_id |
| `account_locked` | Too many failures | user_id, duration |
| `account_banned` | Account banned | user_id, reason, admin_id |
| `account_unbanned` | Ban lifted | user_id, admin_id |
| `character_created` | New character | user_id, character_id |
| `character_deleted` | Character deleted | user_id, character_id |
| `role_changed` | Role modified | user_id, old_roles, new_roles, admin_id |
| `admin_command` | Admin action | user_id, command, target |

---

## Command Integration

### Admin Commands

```python
@cmd("ban", aliases=["banuser"])
@requires_permission(Permission.MANAGE_ACCOUNTS)
async def do_ban(ctx: GameContext, player_id: str, args: list[str]):
    """Ban a user account. Usage: ban <username> <duration> <reason>"""
    if len(args) < 3:
        return [ctx.events.error(player_id, "Usage: ban <username> <duration> <reason>")]

    username, duration, *reason_parts = args
    reason = " ".join(reason_parts)

    # Parse duration: "1h", "1d", "1w", "perm"
    expires_at = parse_duration(duration)

    async with ctx.db_session() as session:
        user = await session.execute(
            select(UserAccount).where(UserAccount.username == username)
        )
        user = user.scalar_one_or_none()

        if not user:
            return [ctx.events.error(player_id, f"User '{username}' not found.")]

        user.is_banned = True
        user.ban_reason = reason
        user.ban_expires_at = expires_at
        await session.commit()

        # Disconnect if online
        if user.active_character_id:
            await ctx.engine.disconnect_player(
                user.active_character_id,
                reason=f"Banned: {reason}"
            )

        # Log event
        admin = ctx.world.players.get(player_id)
        await ctx.auth.log_event(
            "account_banned",
            user_id=user.id,
            ip_address="server",
            details={"admin": admin.name, "reason": reason, "expires": expires_at}
        )

    return [ctx.events.message(player_id, f"User '{username}' has been banned.")]

@cmd("teleport", aliases=["tp", "goto"])
@requires_permission(Permission.TELEPORT)
async def do_teleport(ctx: GameContext, player_id: str, args: list[str]):
    """Teleport to a room or player. Usage: teleport <room_id|player_name>"""
    ...

@cmd("spawn", aliases=["create"])
@requires_permission(Permission.SPAWN_ITEM)
async def do_spawn(ctx: GameContext, player_id: str, args: list[str]):
    """Spawn an item. Usage: spawn <item_template_id> [quantity]"""
    ...

@cmd("godmode", aliases=["god"])
@requires_permission(Permission.INVULNERABLE)
async def do_godmode(ctx: GameContext, player_id: str, args: list[str]):
    """Toggle invulnerability."""
    player = ctx.world.players.get(player_id)
    player.is_invulnerable = not player.is_invulnerable
    status = "enabled" if player.is_invulnerable else "disabled"
    return [ctx.events.message(player_id, f"God mode {status}.")]
```

---

## Migration Path

### Phase 7.1: Database and Models

1. Create database migration for new tables
2. Add UserAccount, RefreshToken, SecurityEvent models
3. Add account_id FK to Player model
4. Create migration script for existing players (optional auto-account creation)

### Phase 7.2: Authentication System

1. Implement AuthSystem class
2. Password hashing with Argon2
3. JWT generation and validation
4. Refresh token rotation

### Phase 7.3: API Endpoints

1. Registration endpoint with email validation
2. Login endpoint with rate limiting
3. Token refresh endpoint
4. Password change/reset endpoints
5. Character management endpoints

### Phase 7.4: WebSocket Integration

1. Update WebSocket endpoint to require token
2. Token validation on connection
3. Re-authentication on token expiry (client-side)
4. Graceful disconnection on ban

### Phase 7.5: Permission System

1. Define permissions and role mappings
2. Add @requires_permission decorator
3. Update existing admin commands
4. Add new admin commands

### Phase 7.6: Security Hardening

1. Rate limiting implementation
2. Audit logging integration
3. Security event monitoring
4. Ban management commands

---

## Configuration

```python
# config.py or environment variables

class AuthConfig:
    # JWT
    SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Password
    MIN_PASSWORD_LENGTH: int = 8
    REQUIRE_EMAIL_VERIFICATION: bool = True

    # Rate limiting
    LOGIN_ATTEMPTS_PER_MINUTE: int = 5
    LOCKOUT_AFTER_FAILURES: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    # Sessions
    MAX_SESSIONS_PER_USER: int = 5  # Max concurrent refresh tokens

    # Characters
    DEFAULT_MAX_CHARACTERS: int = 3
```

---

## Future Considerations

### OAuth/Social Login

```python
# Future: Support login via Discord, Google, etc.
class OAuthProvider(str, Enum):
    DISCORD = "discord"
    GOOGLE = "google"
    TWITCH = "twitch"

class LinkedAccount(Base):
    __tablename__ = "linked_accounts"

    id: Mapped[str]
    user_id: Mapped[str]  # FK to UserAccount
    provider: Mapped[str]
    provider_user_id: Mapped[str]
    access_token: Mapped[str]  # Encrypted
    refresh_token: Mapped[str | None]
```

### Two-Factor Authentication

```python
# Future: TOTP-based 2FA
class TwoFactorAuth(Base):
    __tablename__ = "two_factor_auth"

    user_id: Mapped[str]
    secret: Mapped[str]  # Encrypted TOTP secret
    backup_codes: Mapped[list]  # Encrypted list
    enabled_at: Mapped[float]
```

### API Keys for Bots

```python
# Future: Long-lived API keys for automation
class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str]
    user_id: Mapped[str]
    key_hash: Mapped[str]
    name: Mapped[str]  # "My Discord Bot"
    permissions: Mapped[list]  # Subset of user's permissions
    expires_at: Mapped[float | None]
    last_used_at: Mapped[float | None]
```

---

## Conclusion

Phase 7 establishes a robust authentication and authorization foundation that:

1. **Separates identity from gameplay** - Accounts are distinct from characters
2. **Secures all connections** - JWT-based auth for HTTP and WebSocket
3. **Enables administration** - Role-based permissions for moderation and GM commands
4. **Provides auditability** - Security event logging for accountability
5. **Supports growth** - Extensible for OAuth, 2FA, and API keys

By building on our existing architecture patterns (systems with GameContext, database models, configuration), Phase 7 integrates cleanly while adding the security layer necessary for a production MUD environment.
