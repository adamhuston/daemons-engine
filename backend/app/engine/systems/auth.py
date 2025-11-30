"""
Phase 7: Authentication System

Provides user authentication, authorization, and session management.
Implements JWT-based tokens with refresh token rotation.
"""

import hashlib
import os
import time
import uuid
from enum import Enum
from functools import wraps
from typing import Callable

from app.models import Player, RefreshToken, SecurityEvent, UserAccount
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

# ============================================================================
# Configuration
# ============================================================================

# Secret key for JWT signing (should be set via environment variable in production)
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"

# Token expiration times (user requested 1hr access tokens)
ACCESS_TOKEN_EXPIRE_SECONDS = 60 * 60  # 1 hour
REFRESH_TOKEN_EXPIRE_SECONDS = 60 * 60 * 24 * 7  # 7 days


# ============================================================================
# Enums and Types
# ============================================================================


class UserRole(str, Enum):
    """User permission levels."""

    PLAYER = "player"  # Normal player
    MODERATOR = "moderator"  # Can mute, kick, view reports
    GAME_MASTER = "game_master"  # Can spawn items, teleport, edit world
    ADMIN = "admin"  # Full access, user management


class Permission(str, Enum):
    """Granular permissions for commands and actions."""

    # Player permissions (default)
    PLAY = "play"  # Basic gameplay
    CHAT = "chat"  # Send messages
    TRADE = "trade"  # Trade with players

    # Moderator permissions
    MUTE_PLAYER = "mute_player"  # Mute chat
    KICK_PLAYER = "kick_player"  # Disconnect player
    VIEW_REPORTS = "view_reports"  # See player reports
    WARN_PLAYER = "warn_player"  # Issue warnings

    # Game Master permissions
    TELEPORT = "teleport"  # Teleport self/others
    SPAWN_ITEM = "spawn_item"  # Create items
    SPAWN_NPC = "spawn_npc"  # Spawn NPCs
    MODIFY_STATS = "modify_stats"  # Edit player stats (heal, hurt, bless, etc.)
    INVISIBLE = "invisible"  # Go invisible
    INVULNERABLE = "invulnerable"  # God mode

    # Admin permissions
    MANAGE_ACCOUNTS = "manage_accounts"  # Ban, unban, verify
    MANAGE_ROLES = "manage_roles"  # Assign roles
    VIEW_LOGS = "view_logs"  # Security event logs
    SERVER_COMMANDS = "server_commands"  # Restart, maintenance


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


class SecurityEventType(str, Enum):
    """Types of security events for audit logging."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REVOKED = "token_revoked"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_BANNED = "account_banned"
    ACCOUNT_UNBANNED = "account_unbanned"
    ROLE_CHANGED = "role_changed"
    CHARACTER_CREATED = "character_created"
    CHARACTER_DELETED = "character_deleted"


# ============================================================================
# Password Hashing
# ============================================================================

# Use Argon2 for password hashing (recommended by OWASP)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_token(token: str) -> str:
    """Hash a refresh token for storage (SHA256)."""
    return hashlib.sha256(token.encode()).hexdigest()


# ============================================================================
# JWT Token Functions
# ============================================================================


def create_access_token(
    user_id: str, role: str, expires_delta: int | None = None
) -> str:
    """
    Create a JWT access token.

    Claims:
      - sub: user account ID
      - role: user's role
      - type: "access"
      - exp: expiration timestamp
      - iat: issued at timestamp
    """
    now = time.time()
    expire = now + (expires_delta or ACCESS_TOKEN_EXPIRE_SECONDS)

    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """
    Create a refresh token.

    Returns: (token_id, raw_token)

    The raw_token is given to the client.
    The hash of raw_token is stored in the database.
    """
    token_id = str(uuid.uuid4())
    raw_token = f"{token_id}:{uuid.uuid4().hex}{uuid.uuid4().hex}"
    return token_id, raw_token


def verify_access_token(token: str) -> dict | None:
    """
    Verify a JWT access token and extract claims.

    Returns: {"user_id": str, "role": str, "exp": float} or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check it's an access token
        if payload.get("type") != "access":
            return None

        # Check expiration
        if payload.get("exp", 0) < time.time():
            return None

        return {
            "user_id": payload.get("sub"),
            "role": payload.get("role"),
            "exp": payload.get("exp"),
        }
    except JWTError:
        return None


# ============================================================================
# AuthSystem Class
# ============================================================================


class AuthSystem:
    """
    Handles authentication, authorization, and session management.

    Responsibilities:
    - Account registration and login
    - JWT token generation and verification
    - Refresh token rotation
    - Permission checking
    - Security event logging
    """

    def __init__(self, db_session_factory: Callable[[], AsyncSession]):
        """
        Initialize the auth system.

        Args:
            db_session_factory: Callable that returns an async database session
        """
        self.db_session_factory = db_session_factory

    # ========================================================================
    # Account Management
    # ========================================================================

    async def create_account(
        self,
        username: str,
        password: str,
        email: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[UserAccount | None, str]:
        """
        Create a new user account.

        Returns: (UserAccount, error_message)
            - If successful: (account, "")
            - If failed: (None, error_message)
        """
        async with self.db_session_factory() as session:
            # Check if username already exists
            result = await session.execute(
                select(UserAccount).where(UserAccount.username == username)
            )
            if result.scalar_one_or_none():
                return None, "Username already taken"

            # Check if email already exists (if provided)
            if email:
                result = await session.execute(
                    select(UserAccount).where(UserAccount.email == email)
                )
                if result.scalar_one_or_none():
                    return None, "Email already registered"

            # Create account
            account_id = str(uuid.uuid4())
            now = time.time()

            account = UserAccount(
                id=account_id,
                username=username,
                email=email,
                password_hash=hash_password(password),
                role=UserRole.PLAYER.value,
                is_active=True,
                created_at=now,
                last_login=None,
                active_character_id=None,
            )

            session.add(account)

            # Log security event
            await self._log_event_internal(
                session,
                SecurityEventType.ACCOUNT_CREATED,
                account_id,
                ip_address,
                None,
                {"username": username},
            )

            await session.commit()

            return account, ""

    async def get_account_by_id(self, account_id: str) -> UserAccount | None:
        """Get an account by its ID."""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(UserAccount).where(UserAccount.id == account_id)
            )
            return result.scalar_one_or_none()

    async def get_account_by_username(self, username: str) -> UserAccount | None:
        """Get an account by username."""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(UserAccount).where(UserAccount.username == username)
            )
            return result.scalar_one_or_none()

    # ========================================================================
    # Authentication
    # ========================================================================

    async def login(
        self,
        username: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str, UserAccount] | tuple[None, None, str]:
        """
        Authenticate user and return tokens.

        Returns:
            - If successful: (access_token, refresh_token, account)
            - If failed: (None, None, error_message)
        """
        async with self.db_session_factory() as session:
            # Find account by username
            result = await session.execute(
                select(UserAccount).where(UserAccount.username == username)
            )
            account = result.scalar_one_or_none()

            # Check account exists and password is correct
            if not account or not verify_password(password, account.password_hash):
                # Log failed login
                await self._log_event_internal(
                    session,
                    SecurityEventType.LOGIN_FAILURE,
                    account.id if account else None,
                    ip_address,
                    user_agent,
                    {"username": username},
                )
                await session.commit()
                return None, None, "Invalid username or password"

            # Check account is active
            if not account.is_active:
                await self._log_event_internal(
                    session,
                    SecurityEventType.LOGIN_FAILURE,
                    account.id,
                    ip_address,
                    user_agent,
                    {"reason": "account_inactive"},
                )
                await session.commit()
                return None, None, "Account is inactive"

            # Create tokens
            access_token = create_access_token(account.id, account.role)
            token_id, refresh_token = create_refresh_token(account.id)

            # Store refresh token
            now = time.time()
            db_token = RefreshToken(
                id=token_id,
                account_id=account.id,
                token_hash=hash_token(refresh_token),
                expires_at=now + REFRESH_TOKEN_EXPIRE_SECONDS,
                created_at=now,
                revoked=False,
                device_info=user_agent,
            )
            session.add(db_token)

            # Update last login
            await session.execute(
                update(UserAccount)
                .where(UserAccount.id == account.id)
                .values(last_login=now)
            )

            # Log successful login
            await self._log_event_internal(
                session,
                SecurityEventType.LOGIN_SUCCESS,
                account.id,
                ip_address,
                user_agent,
                {},
            )

            await session.commit()

            return access_token, refresh_token, account

    async def refresh_access_token(
        self,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str] | tuple[None, str]:
        """
        Use refresh token to get new access token.
        Implements token rotation (old refresh token invalidated).

        Returns:
            - If successful: (new_access_token, new_refresh_token)
            - If failed: (None, error_message)
        """
        # Parse token to get ID
        try:
            token_id = refresh_token.split(":")[0]
        except (ValueError, IndexError):
            return None, "Invalid token format"

        async with self.db_session_factory() as session:
            # Find token
            result = await session.execute(
                select(RefreshToken).where(RefreshToken.id == token_id)
            )
            db_token = result.scalar_one_or_none()

            if not db_token:
                return None, "Token not found"

            # Verify token hash
            if db_token.token_hash != hash_token(refresh_token):
                # Possible token theft - revoke all tokens for this user
                await self._revoke_all_tokens_for_user(session, db_token.account_id)
                await session.commit()
                return None, "Invalid token"

            # Check if revoked
            if db_token.revoked:
                # Token reuse detected - possible theft
                await self._revoke_all_tokens_for_user(session, db_token.account_id)
                await session.commit()
                return None, "Token revoked"

            # Check expiration
            if db_token.expires_at < time.time():
                return None, "Token expired"

            # Get user account
            result = await session.execute(
                select(UserAccount).where(UserAccount.id == db_token.account_id)
            )
            account = result.scalar_one_or_none()

            if not account or not account.is_active:
                return None, "Account not found or inactive"

            # Revoke old token
            await session.execute(
                update(RefreshToken)
                .where(RefreshToken.id == token_id)
                .values(revoked=True)
            )

            # Create new tokens
            new_access_token = create_access_token(account.id, account.role)
            new_token_id, new_refresh_token = create_refresh_token(account.id)

            # Store new refresh token
            now = time.time()
            new_db_token = RefreshToken(
                id=new_token_id,
                account_id=account.id,
                token_hash=hash_token(new_refresh_token),
                expires_at=now + REFRESH_TOKEN_EXPIRE_SECONDS,
                created_at=now,
                revoked=False,
                device_info=user_agent,
            )
            session.add(new_db_token)

            # Log refresh
            await self._log_event_internal(
                session,
                SecurityEventType.TOKEN_REFRESH,
                account.id,
                ip_address,
                user_agent,
                {},
            )

            await session.commit()

            return new_access_token, new_refresh_token

    async def logout(
        self,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> bool:
        """Revoke a refresh token (logout from one device)."""
        try:
            token_id = refresh_token.split(":")[0]
        except (ValueError, IndexError):
            return False

        async with self.db_session_factory() as session:
            result = await session.execute(
                select(RefreshToken).where(RefreshToken.id == token_id)
            )
            db_token = result.scalar_one_or_none()

            if not db_token:
                return False

            # Revoke token
            await session.execute(
                update(RefreshToken)
                .where(RefreshToken.id == token_id)
                .values(revoked=True)
            )

            # Log logout
            await self._log_event_internal(
                session,
                SecurityEventType.LOGOUT,
                db_token.account_id,
                ip_address,
                user_agent,
                {},
            )

            await session.commit()
            return True

    async def logout_all_sessions(self, account_id: str) -> int:
        """Revoke all refresh tokens for a user. Returns count revoked."""
        async with self.db_session_factory() as session:
            count = await self._revoke_all_tokens_for_user(session, account_id)
            await session.commit()
            return count

    async def _revoke_all_tokens_for_user(
        self, session: AsyncSession, account_id: str
    ) -> int:
        """Internal: revoke all tokens for a user within an existing session."""
        result = await session.execute(
            update(RefreshToken)
            .where(RefreshToken.account_id == account_id)
            .where(not RefreshToken.revoked)
            .values(revoked=True)
        )
        return result.rowcount

    def verify_token(self, token: str) -> dict | None:
        """
        Verify an access token and extract claims.

        Returns: {"user_id": str, "role": str, "exp": float} or None
        """
        return verify_access_token(token)

    # ========================================================================
    # Authorization
    # ========================================================================

    def has_role(self, account: UserAccount, role: UserRole) -> bool:
        """Check if user has at least the specified role."""
        role_hierarchy = {
            UserRole.PLAYER: 0,
            UserRole.MODERATOR: 1,
            UserRole.GAME_MASTER: 2,
            UserRole.ADMIN: 3,
        }

        try:
            user_role = UserRole(account.role)
        except ValueError:
            user_role = UserRole.PLAYER

        return role_hierarchy.get(user_role, 0) >= role_hierarchy.get(role, 0)

    def has_permission(self, account: UserAccount, permission: Permission) -> bool:
        """Check if user has a specific permission based on their role."""
        try:
            user_role = UserRole(account.role)
        except ValueError:
            user_role = UserRole.PLAYER

        role_perms = ROLE_PERMISSIONS.get(user_role, set())
        return permission in role_perms

    def has_permission_by_role(self, role: str, permission: Permission) -> bool:
        """Check if a role string has a specific permission."""
        try:
            user_role = UserRole(role)
        except ValueError:
            user_role = UserRole.PLAYER

        role_perms = ROLE_PERMISSIONS.get(user_role, set())
        return permission in role_perms

    # ========================================================================
    # Character Management
    # ========================================================================

    async def get_characters_for_account(self, account_id: str) -> list[Player]:
        """Get all characters belonging to an account."""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(Player).where(Player.account_id == account_id)
            )
            return list(result.scalars().all())

    async def set_active_character(self, account_id: str, character_id: str) -> bool:
        """Set the active character for an account."""
        async with self.db_session_factory() as session:
            # Verify character belongs to account
            result = await session.execute(
                select(Player)
                .where(Player.id == character_id)
                .where(Player.account_id == account_id)
            )
            if not result.scalar_one_or_none():
                return False

            # Update active character
            await session.execute(
                update(UserAccount)
                .where(UserAccount.id == account_id)
                .values(active_character_id=character_id)
            )

            await session.commit()
            return True

    async def clear_active_character(self, account_id: str) -> bool:
        """Clear the active character for an account (used when returning to char select)."""
        async with self.db_session_factory() as session:
            await session.execute(
                update(UserAccount)
                .where(UserAccount.id == account_id)
                .values(active_character_id=None)
            )
            await session.commit()
            return True

    async def get_active_character(self, account_id: str) -> Player | None:
        """Get the active character for an account."""
        async with self.db_session_factory() as session:
            # Get account
            result = await session.execute(
                select(UserAccount).where(UserAccount.id == account_id)
            )
            account = result.scalar_one_or_none()

            if not account or not account.active_character_id:
                return None

            # Get character
            result = await session.execute(
                select(Player).where(Player.id == account.active_character_id)
            )
            return result.scalar_one_or_none()

    # ========================================================================
    # Security Event Logging
    # ========================================================================

    async def log_event(
        self,
        event_type: SecurityEventType | str,
        account_id: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Log a security event."""
        async with self.db_session_factory() as session:
            await self._log_event_internal(
                session, event_type, account_id, ip_address, user_agent, details
            )
            await session.commit()

    async def _log_event_internal(
        self,
        session: AsyncSession,
        event_type: SecurityEventType | str,
        account_id: str | None,
        ip_address: str | None,
        user_agent: str | None,
        details: dict | None,
    ) -> None:
        """Internal: log event within existing session."""
        event = SecurityEvent(
            id=str(uuid.uuid4()),
            account_id=account_id,
            event_type=(
                event_type.value
                if isinstance(event_type, SecurityEventType)
                else event_type
            ),
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            timestamp=time.time(),
        )
        session.add(event)

    async def get_recent_events(
        self, account_id: str, limit: int = 10
    ) -> list[SecurityEvent]:
        """Get recent security events for an account."""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(SecurityEvent)
                .where(SecurityEvent.account_id == account_id)
                .order_by(SecurityEvent.timestamp.desc())
                .limit(limit)
            )
            return list(result.scalars().all())


# ============================================================================
# Decorator for Permission Checks
# ============================================================================


def requires_role(role: UserRole):
    """
    Decorator to require a minimum role for a command handler.

    Usage:
        @requires_role(UserRole.GAME_MASTER)
        async def do_spawn(ctx, player_id, args):
            ...

    Note: The decorated function's ctx must have auth_system and the player
    must have an associated account.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(ctx, player_id: str, args: list[str], *more_args, **kwargs):
            # Get player
            player = ctx.world.players.get(player_id)
            if not player:
                return [ctx.events.error(player_id, "Player not found.")]

            # Get account
            if not hasattr(player, "account") or not player.account:
                # Check if we have auth info in context
                if hasattr(ctx, "auth_info") and ctx.auth_info:
                    account_role = ctx.auth_info.get("role", "player")
                else:
                    return [
                        ctx.events.error(
                            player_id, "You must be logged in to use this command."
                        )
                    ]
            else:
                account_role = player.account.role

            # Check role permission
            if not ctx.auth_system.has_permission_by_role(
                account_role,
                (
                    list(ROLE_PERMISSIONS.get(role, set()))[0]
                    if ROLE_PERMISSIONS.get(role)
                    else Permission.PLAY
                ),
            ):
                return [
                    ctx.events.error(
                        player_id, "You don't have permission to use this command."
                    )
                ]

            return await func(ctx, player_id, args, *more_args, **kwargs)

        # Mark the function as requiring a role for introspection
        wrapper.required_role = role
        return wrapper

    return decorator


def requires_permission(permission: Permission):
    """
    Decorator to require a specific permission for a command handler.

    Usage:
        @requires_permission(Permission.MODIFY_STATS)
        async def do_heal(ctx, player_id, args):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(ctx, player_id: str, args: list[str], *more_args, **kwargs):
            # Get player
            player = ctx.world.players.get(player_id)
            if not player:
                return [ctx.events.error(player_id, "Player not found.")]

            # Get account role from context auth info
            if hasattr(ctx, "auth_info") and ctx.auth_info:
                account_role = ctx.auth_info.get("role", "player")
            elif hasattr(player, "account") and player.account:
                account_role = player.account.role
            else:
                return [
                    ctx.events.error(
                        player_id, "You must be logged in to use this command."
                    )
                ]

            # Check permission
            if not ctx.auth_system.has_permission_by_role(account_role, permission):
                return [
                    ctx.events.error(
                        player_id,
                        f"You don't have permission to use this command. Requires: {permission.value}",
                    )
                ]

            return await func(ctx, player_id, args, *more_args, **kwargs)

        # Mark the function as requiring a permission for introspection
        wrapper.required_permission = permission
        return wrapper

    return decorator
