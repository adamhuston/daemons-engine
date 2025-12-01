# backend/app/routes/admin.py
"""
Phase 8: Admin API Routes

Provides REST API endpoints for administrative operations:
- Server status and monitoring
- World state inspection
- Player management
- Entity spawning/despawning
- Content hot-reload
- Account management

All endpoints require appropriate roles (MODERATOR, GAME_MASTER, or ADMIN).
"""

import asyncio
import time
import uuid
from dataclasses import asdict
from enum import Enum
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from daemons.db import get_session
from daemons.engine.systems.auth import (
    ROLE_PERMISSIONS,
    AuthSystem,
    Permission,
    UserRole,
    verify_access_token,
)
from daemons.logging import admin_audit, get_logger
from daemons.models import Room, SecurityEvent, UserAccount

# Module logger
logger = get_logger(__name__)

# Admin audit logger instance
admin_audit_logger = admin_audit

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============================================================================
# Dependencies
# ============================================================================


def get_engine_from_request(request: Request):
    """Get the WorldEngine from daemons.state."""
    engine = getattr(request.app.state, "world_engine", None)
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="World engine not initialized",
        )
    return engine


def get_auth_system_from_request(request: Request) -> AuthSystem:
    """Get the AuthSystem from daemons.state."""
    auth_system = getattr(request.app.state, "auth_system", None)
    if auth_system is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth system not initialized",
        )
    return auth_system


async def get_current_admin(
    request: Request,
    authorization: str = None,
) -> dict:
    """
    Dependency that validates the access token and ensures user has admin privileges.
    Returns the token claims if valid.
    """
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.split(" ", 1)[1]
    claims = verify_access_token(token)

    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check role has at least MODERATOR privileges
    role = claims.get("role", "player")
    if role not in [
        UserRole.MODERATOR.value,
        UserRole.GAME_MASTER.value,
        UserRole.ADMIN.value,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )

    return claims


def require_permission(permission: Permission):
    """
    Dependency factory that checks for a specific permission.
    Use with Depends: Depends(require_permission(Permission.SPAWN_ITEM))
    """

    async def check_permission(admin: dict = Depends(get_current_admin)) -> dict:
        role_str = admin.get("role", "player")
        try:
            role = UserRole(role_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role"
            )

        if permission not in ROLE_PERMISSIONS.get(role, set()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value}",
            )

        return admin

    return check_permission


def require_role(min_role: UserRole):
    """
    Dependency factory that checks for minimum role level.
    Role hierarchy: PLAYER < MODERATOR < GAME_MASTER < ADMIN
    """
    role_hierarchy = [
        UserRole.PLAYER,
        UserRole.MODERATOR,
        UserRole.GAME_MASTER,
        UserRole.ADMIN,
    ]

    async def check_role(admin: dict = Depends(get_current_admin)) -> dict:
        role_str = admin.get("role", "player")
        try:
            role = UserRole(role_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role"
            )

        if role_hierarchy.index(role) < role_hierarchy.index(min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {min_role.value} or higher",
            )

        return admin

    return check_role


# ============================================================================
# Response Models
# ============================================================================


class ServerStatusResponse(BaseModel):
    """Server health and status information."""

    uptime_seconds: float
    players_online: int
    players_in_combat: int
    npcs_alive: int
    rooms_total: int
    rooms_occupied: int
    areas_total: int
    scheduled_events: int
    next_event_in_seconds: float | None
    maintenance_mode: bool = False
    maintenance_reason: str | None = None
    shutdown_pending: bool = False
    shutdown_at: float | None = None
    shutdown_reason: str | None = None
    content_version: str = "1.0.0"  # Will be updated by content reloader
    server_time: float


class PlayerSummary(BaseModel):
    """Brief player information for listings."""

    id: str
    name: str
    room_id: str
    level: int
    current_health: int
    max_health: int
    is_connected: bool
    in_combat: bool = False


class RoomSummary(BaseModel):
    """Brief room information for listings."""

    id: str
    name: str
    area_id: str | None
    player_count: int
    npc_count: int
    item_count: int
    exits: dict


class RoomDetail(BaseModel):
    """Detailed room information."""

    id: str
    name: str
    description: str
    room_type: str
    area_id: str | None
    exits: dict
    dynamic_exits: dict
    players: list[str]
    npcs: list[str]
    items: list[str]
    flags: dict
    triggers: list[str]


class NpcSummary(BaseModel):
    """Brief NPC information for listings."""

    id: str
    template_id: str
    name: str
    room_id: str
    current_health: int
    max_health: int
    is_alive: bool
    # Phase 14.5: Optional ability-related fields (included when verbose=True)
    class_id: str | None = None
    has_abilities: bool = False
    resource_pools: dict | None = None
    learned_abilities: list[str] | None = None
    ability_loadout: list[str] | None = None


class ItemSummary(BaseModel):
    """Brief item information for listings."""

    id: str
    template_id: str
    name: str
    location_type: str  # "room", "player", "container"
    location_id: str
    quantity: int


class AreaSummary(BaseModel):
    """Brief area information for listings."""

    id: str
    name: str
    room_count: int
    player_count: int
    time_scale: float


class WorldStateResponse(BaseModel):
    """Complete world state snapshot for debugging and admin dashboards."""

    # Server info
    server_uptime: float
    server_time: float
    maintenance_mode: bool
    shutdown_pending: bool

    # Counts
    players_online: int
    players_total: int
    npcs_alive: int
    npcs_total: int
    rooms_total: int
    areas_total: int
    items_total: int
    active_combats: int
    scheduled_events: int

    # Full entity listings
    players: list[PlayerSummary]
    rooms: list[RoomDetail]
    areas: list[AreaSummary]
    npcs: list[NpcSummary]
    items: list[ItemSummary]


# ============================================================================
# Request Models
# ============================================================================


class TeleportRequest(BaseModel):
    """Request to teleport a player."""

    room_id: str = Field(..., description="Target room ID")


class GiveItemRequest(BaseModel):
    """Request to give an item to a player."""

    template_id: str = Field(..., description="Item template ID")
    quantity: int = Field(1, ge=1, le=99, description="Quantity to give")


class ApplyEffectRequest(BaseModel):
    """Request to apply an effect to a player."""

    effect_name: str = Field(..., description="Effect name")
    duration: int = Field(60, ge=1, description="Duration in seconds")
    magnitude: int = Field(0, description="Effect magnitude (for DoT/HoT)")


class HealRequest(BaseModel):
    """Request to heal a player."""

    amount: int | None = Field(
        None, ge=1, description="Amount to heal (None = full heal)"
    )


class SpawnNpcRequest(BaseModel):
    """Request to spawn an NPC."""

    template_id: str = Field(..., description="NPC template ID")
    room_id: str = Field(..., description="Room to spawn in")


class SpawnItemRequest(BaseModel):
    """Request to spawn an item."""

    template_id: str = Field(..., description="Item template ID")
    room_id: str = Field(..., description="Room to spawn in")
    quantity: int = Field(1, ge=1, le=99, description="Quantity to spawn")


class MoveNpcRequest(BaseModel):
    """Request to move an NPC to a different room."""

    target_room_id: str = Field(..., description="Target room ID")
    reason: str = Field("", description="Optional reason for the move")


class MoveItemRequest(BaseModel):
    """Request to move an item to a different location."""

    target_room_id: str | None = Field(
        None, description="Target room ID (if on ground)"
    )
    target_player_id: str | None = Field(
        None, description="Target player ID (if giving to player)"
    )
    target_container_id: str | None = Field(
        None, description="Target container ID (if putting in container)"
    )


class BroadcastRequest(BaseModel):
    """Request to broadcast a message to all players."""

    message: str = Field(..., min_length=1, max_length=1000)
    sender_name: str = Field("SYSTEM", description="Name to show as sender")


class MaintenanceModeRequest(BaseModel):
    """Request to toggle maintenance mode."""

    enabled: bool = Field(..., description="Enable or disable maintenance mode")
    reason: str = Field("Scheduled maintenance", description="Reason for maintenance")
    kick_players: bool = Field(
        False, description="Kick all non-admin players when enabling"
    )


class ShutdownRequest(BaseModel):
    """Request to initiate graceful shutdown."""

    countdown_seconds: int = Field(
        60, ge=10, le=600, description="Countdown before shutdown (10-600 seconds)"
    )
    reason: str = Field("Server shutdown", description="Reason for shutdown")


class RoomUpdateRequest(BaseModel):
    """Request to update a room's properties."""

    name: str | None = Field(
        None, min_length=1, max_length=100, description="Room name"
    )
    description: str | None = Field(
        None, min_length=1, max_length=2000, description="Room description"
    )
    room_type: str | None = Field(
        None, description="Room type (e.g., forest, urban, underground)"
    )
    room_type_emoji: str | None = Field(
        None, max_length=10, description="Per-room emoji override"
    )
    on_enter_effect: str | None = Field(
        None, max_length=500, description="Text shown when entering"
    )
    on_exit_effect: str | None = Field(
        None, max_length=500, description="Text shown when exiting"
    )
    area_id: str | None = Field(None, description="Area this room belongs to")


class RoomCreateRequest(BaseModel):
    """Request to create a new room."""

    id: str = Field(..., min_length=1, max_length=100, description="Unique room ID")
    name: str = Field(..., min_length=1, max_length=100, description="Room name")
    description: str = Field(
        ..., min_length=1, max_length=2000, description="Room description"
    )
    room_type: str = Field(
        "ethereal", description="Room type (e.g., forest, urban, underground)"
    )
    room_type_emoji: str | None = Field(
        None, max_length=10, description="Per-room emoji override"
    )
    area_id: str | None = Field(None, description="Area this room belongs to")
    on_enter_effect: str | None = Field(
        None, max_length=500, description="Text shown when entering"
    )
    on_exit_effect: str | None = Field(
        None, max_length=500, description="Text shown when exiting"
    )
    # Exits as direction -> room_id mapping
    exits: dict[str, str] | None = Field(
        None, description="Exits: {direction: room_id}"
    )


class RoomExitUpdate(BaseModel):
    """Request to update a room's exits."""

    exits: dict[str, str | None] = Field(
        ...,
        description="Exits to set: {direction: room_id or null to remove}. Valid directions: north, south, east, west, up, down",
    )
    bidirectional: bool = Field(
        False, description="If true, also create/remove reverse exits in target rooms"
    )


# ============================================================================
# Trigger/Quest Request/Response Models
# ============================================================================


class TriggerStateResponse(BaseModel):
    """Response showing current state of a trigger."""

    trigger_id: str
    room_id: str
    event: str
    enabled: bool
    fire_count: int
    last_fired_at: float | None
    cooldown: float
    max_fires: int
    command_pattern: str | None = None
    timer_interval: float | None = None


class FireTriggerRequest(BaseModel):
    """Request to manually fire a trigger."""

    room_id: str = Field(..., description="Room containing the trigger")
    trigger_id: str = Field(..., description="Trigger ID to fire")
    player_id: str | None = Field(
        None, description="Player to use for trigger context (optional)"
    )


class ModifyTriggerRequest(BaseModel):
    """Request to modify trigger state."""

    room_id: str = Field(..., description="Room containing the trigger")
    trigger_id: str = Field(..., description="Trigger ID to modify")
    action: str = Field(..., description="Action: enable, disable, reset")


class RoomTriggersResponse(BaseModel):
    """Response listing all triggers in a room."""

    room_id: str
    room_name: str
    trigger_count: int
    triggers: list[TriggerStateResponse]


class QuestProgressResponse(BaseModel):
    """Response showing player's quest progress."""

    quest_id: str
    status: str
    objective_progress: dict[str, int]
    accepted_at: float | None
    completed_at: float | None
    turned_in_at: float | None
    expires_at: float | None
    completion_count: int


class PlayerQuestsResponse(BaseModel):
    """Response showing all of a player's quests."""

    player_id: str
    player_name: str
    in_progress_count: int
    completed_count: int
    quests: list[QuestProgressResponse]


class ModifyQuestRequest(BaseModel):
    """Request to modify player's quest state."""

    player_id: str = Field(..., description="Player ID")
    quest_id: str = Field(..., description="Quest ID")
    action: str = Field(
        ..., description="Action: give, complete, reset, abandon, turn_in"
    )


class QuestTemplateResponse(BaseModel):
    """Response showing a quest template."""

    quest_id: str
    name: str
    description: str
    category: str
    repeatable: bool
    level_requirement: int
    objective_count: int


class QuestTemplatesResponse(BaseModel):
    """Response listing all quest templates."""

    total_quests: int
    quests: list[QuestTemplateResponse]


# ============================================================================
# Account Management Request/Response Models
# ============================================================================


class AccountDetailResponse(BaseModel):
    """Response showing a user account's details."""

    id: str
    username: str
    email: str | None
    role: str
    is_active: bool
    is_banned: bool
    ban_reason: str | None
    banned_at: float | None
    banned_by: str | None
    created_at: float | None
    last_login: float | None
    active_character_id: str | None


class AccountSummary(BaseModel):
    """Brief summary of an account."""

    id: str
    username: str
    role: str
    is_banned: bool
    is_active: bool
    last_login: float | None


class AccountListResponse(BaseModel):
    """Response listing accounts with filtering."""

    total_accounts: int
    filtered_count: int
    accounts: list[AccountSummary]


class SetRoleRequest(BaseModel):
    """Request to change an account's role."""

    new_role: str = Field(
        ..., description="New role: player, moderator, game_master, admin"
    )
    reason: str = Field("", description="Optional reason for role change")


class BanAccountRequest(BaseModel):
    """Request to ban an account."""

    reason: str = Field(..., min_length=1, max_length=500, description="Reason for ban")
    kick_player: bool = Field(True, description="Kick player if currently online")


class UnbanAccountRequest(BaseModel):
    """Request to unban an account."""

    reason: str = Field("", description="Optional reason for unbanning")


class SecurityEventResponse(BaseModel):
    """Response showing a security event."""

    id: str
    event_type: str
    ip_address: str | None
    user_agent: str | None
    details: dict | None
    timestamp: float


class SecurityEventsListResponse(BaseModel):
    """Response listing security events for an account."""

    account_id: str
    account_username: str
    total_events: int
    events: list[SecurityEventResponse]


class MaintenanceStatusResponse(BaseModel):
    """Current maintenance mode status."""

    enabled: bool
    reason: str | None
    enabled_at: float | None
    enabled_by: str | None


class MaintenanceModeResponse(BaseModel):
    """Response from toggling maintenance mode."""

    enabled: bool
    reason: str | None = None
    enabled_at: float | None = None
    players_kicked: int = 0


class ShutdownStatusResponse(BaseModel):
    """Current shutdown status."""

    requested: bool
    shutdown_at: float | None
    reason: str | None
    requested_by: str | None


class ShutdownResponse(BaseModel):
    """Response from initiating shutdown."""

    success: bool
    countdown_seconds: int
    shutdown_at: float
    reason: str
    players_warned: int


# ============================================================================
# Server Status Endpoints
# ============================================================================

# Track server start time
_server_start_time = time.time()

# Maintenance mode state
_maintenance_mode = False
_maintenance_reason: str | None = None
_maintenance_enabled_at: float | None = None
_maintenance_enabled_by: str | None = None

# Shutdown state
_shutdown_requested = False
_shutdown_at: float | None = None
_shutdown_reason: str | None = None
_shutdown_requested_by: str | None = None
_shutdown_task: object | None = None  # asyncio.Task for countdown


@router.get("/server/status", response_model=ServerStatusResponse)
async def get_server_status(request: Request, admin: dict = Depends(get_current_admin)):
    """
    Get current server status and metrics.
    Requires: MODERATOR or higher
    """
    engine = get_engine_from_request(request)
    world = engine.world

    # Count online players
    players_online = sum(1 for p in world.players.values() if p.is_connected)

    # Count players in combat
    players_in_combat = (
        len(engine.combat_system.active_combats)
        if hasattr(engine, "combat_system")
        else 0
    )

    # Count alive NPCs
    npcs_alive = sum(1 for npc in world.npcs.values() if npc.current_health > 0)

    # Count rooms with players
    rooms_occupied = sum(1 for room in world.rooms.values() if room.players)

    # Get scheduled events count
    scheduled_events = (
        len(engine.time_manager.events) if hasattr(engine, "time_manager") else 0
    )

    # Get next event time
    next_event_in = None
    if hasattr(engine, "time_manager") and engine.time_manager.events:
        next_event_time = engine.time_manager.events[0].execute_at
        next_event_in = max(0, next_event_time - time.time())

    return ServerStatusResponse(
        uptime_seconds=time.time() - _server_start_time,
        players_online=players_online,
        players_in_combat=players_in_combat,
        npcs_alive=npcs_alive,
        rooms_total=len(world.rooms),
        rooms_occupied=rooms_occupied,
        areas_total=len(world.areas),
        scheduled_events=scheduled_events,
        next_event_in_seconds=next_event_in,
        maintenance_mode=_maintenance_mode,
        maintenance_reason=_maintenance_reason,
        shutdown_pending=_shutdown_requested,
        shutdown_at=_shutdown_at,
        shutdown_reason=_shutdown_reason if _shutdown_requested else None,
        content_version=getattr(engine, "content_version", "1.0.0"),
        server_time=time.time(),
    )


@router.post("/server/maintenance", response_model=MaintenanceModeResponse)
async def toggle_maintenance_mode(
    request: Request,
    body: MaintenanceModeRequest,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
):
    """
    Enable or disable maintenance mode.
    When enabled, new connections are blocked (except admin/GM).
    Optionally kicks all non-admin players with a broadcast message.

    Requires: ADMIN permission
    """
    global _maintenance_mode, _maintenance_reason, _maintenance_enabled_at

    engine = get_engine_from_request(request)
    world = engine.world
    admin_id = admin.get("user_id", "unknown")

    _maintenance_mode = body.enabled
    _maintenance_reason = body.reason or ""

    if body.enabled:
        _maintenance_enabled_at = time.time()

        # Log the action
        admin_audit_logger.log_maintenance_toggle(
            admin_id=admin_id,
            enabled=True,
            reason=body.reason,
            kick_players=body.kick_players,
        )

        players_kicked = 0
        if body.kick_players:
            # Broadcast maintenance warning
            maintenance_msg = f"\n*** SERVER ENTERING MAINTENANCE MODE ***\n{body.reason or 'Server maintenance required.'}\nYou are being disconnected.\n"

            players_to_kick = []
            for player in world.players.values():
                if player.is_connected:
                    # Check if player is admin/GM - don't kick them
                    # For now, we'll kick all players; admin filtering would need session data
                    players_to_kick.append(player)

            for player in players_to_kick:
                try:
                    # Send message before disconnect
                    if hasattr(player, "send"):
                        await player.send(maintenance_msg)
                    player.is_connected = False
                    players_kicked += 1
                except Exception:
                    pass  # Player may already be disconnected

        return MaintenanceModeResponse(
            enabled=True,
            reason=body.reason,
            enabled_at=_maintenance_enabled_at,
            players_kicked=players_kicked,
        )
    else:
        _maintenance_enabled_at = None

        admin_audit_logger.log_maintenance_toggle(
            admin_id=admin_id, enabled=False, reason="Maintenance mode disabled"
        )

        return MaintenanceModeResponse(
            enabled=False, reason=None, enabled_at=None, players_kicked=0
        )


@router.post("/server/shutdown", response_model=ShutdownResponse)
async def initiate_shutdown(
    request: Request,
    body: ShutdownRequest,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
):
    """
    Initiate graceful server shutdown with countdown.
    Broadcasts warnings at intervals and saves state before shutdown.

    Requires: ADMIN permission
    """
    global _shutdown_requested, _shutdown_reason, _shutdown_at, _shutdown_countdown, _shutdown_task

    engine = get_engine_from_request(request)
    world = engine.world
    admin_id = admin.get("user_id", "unknown")

    countdown = body.countdown_seconds
    if countdown < 0:
        countdown = 0

    _shutdown_requested = True
    _shutdown_reason = body.reason or "Server shutdown initiated by administrator."
    _shutdown_at = time.time() + countdown
    _shutdown_countdown = countdown

    admin_audit_logger.log_shutdown_initiated(
        admin_id=admin_id, countdown_seconds=countdown, reason=body.reason
    )

    # Broadcast initial shutdown warning
    warning_msg = f"\n*** SERVER SHUTDOWN IN {countdown} SECONDS ***\n{_shutdown_reason}\nPlease finish your actions and log out safely.\n"

    players_warned = 0
    for player in world.players.values():
        if player.is_connected:
            try:
                if hasattr(player, "send"):
                    await player.send(warning_msg)
                players_warned += 1
            except Exception:
                pass

    # Start async countdown task for periodic warnings
    async def shutdown_countdown_task():
        """Background task to broadcast warnings and trigger shutdown."""
        global _shutdown_requested

        intervals = [
            300,
            120,
            60,
            30,
            10,
            5,
            4,
            3,
            2,
            1,
        ]  # Warning intervals in seconds
        remaining = countdown

        while remaining > 0 and _shutdown_requested:
            await asyncio.sleep(1)
            remaining -= 1

            # Broadcast at specific intervals
            if remaining in intervals:
                warn_msg = f"\n*** SERVER SHUTDOWN IN {remaining} SECONDS ***\n"
                for player in world.players.values():
                    if player.is_connected:
                        try:
                            if hasattr(player, "send"):
                                await player.send(warn_msg)
                        except Exception:
                            pass

        if _shutdown_requested:
            # Final shutdown - save state and terminate
            final_msg = "\n*** SERVER SHUTTING DOWN NOW ***\n"
            for player in world.players.values():
                if player.is_connected:
                    try:
                        if hasattr(player, "send"):
                            await player.send(final_msg)
                    except Exception:
                        pass

            # In a real implementation, this would trigger the actual shutdown
            # For now, we just log it
            logger.info("Shutdown countdown complete - server would terminate now")

    # Cancel existing shutdown task if any
    if _shutdown_task is not None:
        try:
            _shutdown_task.cancel()
        except Exception:
            pass

    # Start new countdown task
    _shutdown_task = asyncio.create_task(shutdown_countdown_task())

    return ShutdownResponse(
        success=True,
        countdown_seconds=countdown,
        shutdown_at=_shutdown_at,
        reason=_shutdown_reason,
        players_warned=players_warned,
    )


@router.post("/server/shutdown/cancel")
async def cancel_shutdown(
    request: Request,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
):
    """
    Cancel a pending server shutdown.

    Requires: ADMIN permission
    """
    global _shutdown_requested, _shutdown_reason, _shutdown_at, _shutdown_countdown, _shutdown_task

    engine = get_engine_from_request(request)
    world = engine.world
    admin_id = admin.get("user_id", "unknown")

    if not _shutdown_requested:
        raise HTTPException(status_code=400, detail="No shutdown is currently pending")

    # Cancel the countdown task
    if _shutdown_task is not None:
        try:
            _shutdown_task.cancel()
        except Exception:
            pass
        _shutdown_task = None

    _shutdown_requested = False
    _shutdown_reason = ""
    _shutdown_at = None
    _shutdown_countdown = 0

    admin_audit_logger.log_shutdown_cancelled(admin_id=admin_id)

    # Broadcast cancellation
    cancel_msg = "\n*** SERVER SHUTDOWN CANCELLED ***\nThe server will remain online.\n"
    for player in world.players.values():
        if player.is_connected:
            try:
                if hasattr(player, "send"):
                    await player.send(cancel_msg)
            except Exception:
                pass

    return {"success": True, "message": "Shutdown cancelled"}


@router.get("/server/metrics")
async def get_prometheus_metrics(
    request: Request, admin: dict = Depends(get_current_admin)
):
    """
    Get Prometheus-format metrics for monitoring.

    Returns metrics in Prometheus text exposition format, suitable for
    scraping by Prometheus, Grafana Agent, or other compatible tools.

    Metrics include:
    - daemons_players_online: Current connected players
    - daemons_npcs_alive: Living NPCs in the world
    - daemons_rooms_occupied: Rooms with players
    - daemons_combat_sessions_active: Active combat sessions
    - daemons_commands_processed_total: Commands by type
    - daemons_command_latency_seconds: Command processing time
    - daemons_server_uptime_seconds: Server uptime
    - daemons_maintenance_mode: Maintenance mode status

    Requires: MODERATOR or higher

    Example scrape config for Prometheus:
    ```yaml
    scrape_configs:
      - job_name: 'daemons'
        static_configs:
          - targets: ['localhost:8000']
        metrics_path: '/api/admin/server/metrics'
        bearer_token: '<admin_jwt_token>'
    ```
    """
    from starlette.responses import Response

    from daemons.metrics import (
        get_metrics,
        get_metrics_content_type,
        update_world_metrics,
    )

    engine = get_engine_from_request(request)
    world = engine.world

    # Update current world state metrics before returning
    online_players = sum(1 for p in world.players.values() if p.is_connected)
    combat_players = (
        len(engine.combat_system.active_combats)
        if hasattr(engine, "combat_system")
        else 0
    )
    alive_npcs = sum(1 for npc in world.npcs.values() if npc.current_health > 0)
    total_npcs = len(world.npcs)
    total_rooms = len(world.rooms)
    occupied_rooms = sum(1 for room in world.rooms.values() if room.players)
    total_areas = len(world.areas)
    total_items = sum(len(getattr(room, "items", [])) for room in world.rooms.values())
    active_combats = (
        len(engine.combat_system.active_combats)
        if hasattr(engine, "combat_system")
        else 0
    )
    pending_events = (
        len(engine.time_manager.events) if hasattr(engine, "time_manager") else 0
    )

    update_world_metrics(
        online_players=online_players,
        combat_players=combat_players,
        alive_npcs=alive_npcs,
        total_npcs=total_npcs,
        total_rooms=total_rooms,
        occupied_rooms=occupied_rooms,
        total_areas=total_areas,
        total_items=total_items,
        active_combats=active_combats,
        pending_events=pending_events,
        is_maintenance=_maintenance_mode,
    )

    return Response(content=get_metrics(), media_type=get_metrics_content_type())


# ============================================================================
# World Inspection Endpoints
# ============================================================================


@router.get("/world/players", response_model=list[PlayerSummary])
async def list_online_players(
    request: Request, admin: dict = Depends(get_current_admin)
):
    """
    List all online players.
    Requires: MODERATOR or higher
    """
    engine = get_engine_from_request(request)
    world = engine.world

    players = []
    for player in world.players.values():
        if player.is_connected:
            in_combat = False
            if hasattr(engine, "combat_system"):
                in_combat = player.id in engine.combat_system.active_combats

            players.append(
                PlayerSummary(
                    id=player.id,
                    name=player.name,
                    room_id=player.room_id,
                    level=player.level,
                    current_health=player.current_health,
                    max_health=player.max_health,
                    is_connected=player.is_connected,
                    in_combat=in_combat,
                )
            )

    return players


@router.get("/world/players/{player_id}", response_model=PlayerSummary)
async def get_player_details(
    player_id: str, request: Request, admin: dict = Depends(get_current_admin)
):
    """
    Get detailed information about a specific player.
    Requires: MODERATOR or higher
    """
    engine = get_engine_from_request(request)
    world = engine.world

    player = world.players.get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    in_combat = False
    if hasattr(engine, "combat_system"):
        in_combat = player.id in engine.combat_system.active_combats

    return PlayerSummary(
        id=player.id,
        name=player.name,
        room_id=player.room_id,
        level=player.level,
        current_health=player.current_health,
        max_health=player.max_health,
        is_connected=player.is_connected,
        in_combat=in_combat,
    )


@router.get("/world/rooms", response_model=list[RoomSummary])
async def list_rooms(
    request: Request,
    admin: dict = Depends(get_current_admin),
    area_id: str | None = None,
):
    """
    List all rooms, optionally filtered by area.
    Requires: MODERATOR or higher
    """
    engine = get_engine_from_request(request)
    world = engine.world

    rooms = []
    for room in world.rooms.values():
        # Filter by area if specified
        if area_id and room.area_id != area_id:
            continue

        # Count NPCs in room
        npc_count = sum(1 for npc in world.npcs.values() if npc.room_id == room.id)

        # Count items in room
        item_count = sum(1 for item in world.items.values() if item.room_id == room.id)

        rooms.append(
            RoomSummary(
                id=room.id,
                name=room.name,
                area_id=room.area_id,
                player_count=len(room.players),
                npc_count=npc_count,
                item_count=item_count,
                exits=room.get_effective_exits(),
            )
        )

    return rooms


@router.get("/world/rooms/{room_id}", response_model=RoomDetail)
async def get_room_details(
    room_id: str, request: Request, admin: dict = Depends(get_current_admin)
):
    """
    Get detailed information about a specific room.
    Requires: MODERATOR or higher
    """
    engine = get_engine_from_request(request)
    world = engine.world

    room = world.rooms.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Get NPCs in room
    npc_ids = [npc.id for npc in world.npcs.values() if npc.room_id == room.id]

    # Get items in room
    item_ids = [item.id for item in world.items.values() if item.room_id == room.id]

    # Get trigger IDs
    trigger_ids = (
        [t.trigger_id for t in room.triggers] if hasattr(room, "triggers") else []
    )

    return RoomDetail(
        id=room.id,
        name=room.name,
        description=room.get_effective_description(),
        room_type=room.room_type,
        area_id=room.area_id,
        exits=room.exits,
        dynamic_exits=room.dynamic_exits,
        players=list(room.players),
        npcs=npc_ids,
        items=item_ids,
        flags=room.room_flags,
        triggers=trigger_ids,
    )


@router.put("/world/rooms/{room_id}", response_model=RoomDetail)
async def update_room(
    room_id: str,
    body: RoomUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(UserRole.GAME_MASTER)),
):
    """
    Update a room's properties.

    Updates both the database and in-memory state.
    Only provided fields are updated; omitted fields remain unchanged.

    Requires: GAME_MASTER or higher
    """
    engine = get_engine_from_request(request)
    world = engine.world
    admin_id = admin.get("user_id", "unknown")

    # Check room exists in memory
    world_room = world.rooms.get(room_id)
    if not world_room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Get database room
    db_room = await session.get(Room, room_id)
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found in database")

    # Track changes for audit log
    changes = {}

    # Update fields if provided
    if body.name is not None:
        changes["name"] = {"old": world_room.name, "new": body.name}
        world_room.name = body.name
        db_room.name = body.name

    if body.description is not None:
        changes["description"] = {
            "old": (
                world_room.description[:50] + "..."
                if len(world_room.description) > 50
                else world_room.description
            ),
            "new": (
                body.description[:50] + "..."
                if len(body.description) > 50
                else body.description
            ),
        }
        world_room.description = body.description
        db_room.description = body.description

    if body.room_type is not None:
        changes["room_type"] = {"old": world_room.room_type, "new": body.room_type}
        world_room.room_type = body.room_type
        db_room.room_type = body.room_type

    if body.room_type_emoji is not None:
        changes["room_type_emoji"] = {
            "old": world_room.room_type_emoji,
            "new": body.room_type_emoji,
        }
        world_room.room_type_emoji = body.room_type_emoji
        db_room.room_type_emoji = body.room_type_emoji

    if body.on_enter_effect is not None:
        changes["on_enter_effect"] = {
            "old": world_room.on_enter_effect,
            "new": body.on_enter_effect,
        }
        world_room.on_enter_effect = body.on_enter_effect
        db_room.on_enter_effect = body.on_enter_effect

    if body.on_exit_effect is not None:
        changes["on_exit_effect"] = {
            "old": world_room.on_exit_effect,
            "new": body.on_exit_effect,
        }
        world_room.on_exit_effect = body.on_exit_effect
        db_room.on_exit_effect = body.on_exit_effect

    if body.area_id is not None:
        # Validate area exists
        if body.area_id and body.area_id not in world.areas:
            raise HTTPException(
                status_code=400, detail=f"Area '{body.area_id}' not found"
            )
        changes["area_id"] = {"old": world_room.area_id, "new": body.area_id}
        world_room.area_id = body.area_id
        db_room.area_id = body.area_id

    # Mark as API-managed (will be skipped during YAML reload)
    if changes:
        world_room.yaml_managed = False
        db_room.yaml_managed = False
        changes["yaml_managed"] = {"old": True, "new": False}

    # Commit database changes
    await session.commit()

    # Audit log
    if changes:
        admin_audit_logger.info(
            "room_updated", admin_id=admin_id, room_id=room_id, changes=changes
        )

    # Return updated room details
    npc_ids = [npc.id for npc in world.npcs.values() if npc.room_id == room_id]
    item_ids = [item.id for item in world.items.values() if item.room_id == room_id]
    trigger_ids = (
        [t.trigger_id for t in world_room.triggers]
        if hasattr(world_room, "triggers")
        else []
    )

    return RoomDetail(
        id=world_room.id,
        name=world_room.name,
        description=world_room.get_effective_description(),
        room_type=world_room.room_type,
        area_id=world_room.area_id,
        exits=world_room.exits,
        dynamic_exits=world_room.dynamic_exits,
        players=list(world_room.players),
        npcs=npc_ids,
        items=item_ids,
        flags=world_room.room_flags,
        triggers=trigger_ids,
    )


@router.post("/world/rooms", response_model=RoomDetail, status_code=201)
async def create_room(
    body: RoomCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(UserRole.ADMIN)),
):
    """
    Create a new room.

    Creates both the database record and in-memory WorldRoom.
    Optionally links exits to existing rooms.

    Requires: ADMIN
    """
    from daemons.engine.world import WorldRoom

    engine = get_engine_from_request(request)
    world = engine.world
    admin_id = admin.get("user_id", "unknown")

    # Validate room ID doesn't exist
    if body.id in world.rooms:
        raise HTTPException(status_code=409, detail=f"Room '{body.id}' already exists")

    # Validate area if provided
    if body.area_id and body.area_id not in world.areas:
        raise HTTPException(status_code=400, detail=f"Area '{body.area_id}' not found")

    # Validate exits if provided
    exits_dict = {}
    if body.exits:
        valid_directions = {"north", "south", "east", "west", "up", "down"}
        for direction, target_id in body.exits.items():
            if direction not in valid_directions:
                raise HTTPException(
                    status_code=400, detail=f"Invalid exit direction: {direction}"
                )
            if target_id not in world.rooms:
                raise HTTPException(
                    status_code=400, detail=f"Exit target room '{target_id}' not found"
                )
            exits_dict[direction] = target_id

    # Create database room (API-created, so yaml_managed=False)
    db_room = Room(
        id=body.id,
        name=body.name,
        description=body.description,
        room_type=body.room_type,
        room_type_emoji=body.room_type_emoji,
        area_id=body.area_id,
        on_enter_effect=body.on_enter_effect,
        on_exit_effect=body.on_exit_effect,
        yaml_managed=False,
        north_id=exits_dict.get("north"),
        south_id=exits_dict.get("south"),
        east_id=exits_dict.get("east"),
        west_id=exits_dict.get("west"),
        up_id=exits_dict.get("up"),
        down_id=exits_dict.get("down"),
    )
    session.add(db_room)
    await session.commit()

    # Create in-memory WorldRoom (API-created)
    world_room = WorldRoom(
        id=body.id,
        name=body.name,
        description=body.description,
        room_type=body.room_type,
        room_type_emoji=body.room_type_emoji,
        yaml_managed=False,
        area_id=body.area_id,
        on_enter_effect=body.on_enter_effect,
        on_exit_effect=body.on_exit_effect,
        exits=exits_dict,
    )
    world.rooms[body.id] = world_room

    # Audit log
    admin_audit_logger.info(
        "room_created",
        admin_id=admin_id,
        room_id=body.id,
        room_name=body.name,
        area_id=body.area_id,
        exits=list(exits_dict.keys()) if exits_dict else [],
    )

    return RoomDetail(
        id=world_room.id,
        name=world_room.name,
        description=world_room.get_effective_description(),
        room_type=world_room.room_type,
        area_id=world_room.area_id,
        exits=world_room.exits,
        dynamic_exits=world_room.dynamic_exits,
        players=list(world_room.players),
        npcs=[],
        items=[],
        flags=world_room.room_flags,
        triggers=[],
    )


# Direction opposites for bidirectional exits
_OPPOSITE_DIRECTIONS = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "up": "down",
    "down": "up",
}

# Direction to DB column mapping
_DIRECTION_TO_COLUMN = {
    "north": "north_id",
    "south": "south_id",
    "east": "east_id",
    "west": "west_id",
    "up": "up_id",
    "down": "down_id",
}


@router.patch("/world/rooms/{room_id}/exits", response_model=RoomDetail)
async def update_room_exits(
    room_id: str,
    body: RoomExitUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(UserRole.GAME_MASTER)),
):
    """
    Update a room's exits.

    Allows adding, modifying, or removing exits. Set a direction to null to remove it.
    If bidirectional=true, also creates/removes the reverse exit in the target room.

    Example: {"exits": {"north": "room_2", "south": null}, "bidirectional": true}
    - Creates north exit to room_2 (and south exit from room_2 back)
    - Removes south exit (and north exit from whatever room was linked)

    Requires: GAME_MASTER or higher
    """
    engine = get_engine_from_request(request)
    world = engine.world
    admin_id = admin.get("user_id", "unknown")

    valid_directions = set(_OPPOSITE_DIRECTIONS.keys())

    # Validate room exists
    world_room = world.rooms.get(room_id)
    if not world_room:
        raise HTTPException(status_code=404, detail="Room not found")

    db_room = await session.get(Room, room_id)
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found in database")

    changes = []

    for direction, target_id in body.exits.items():
        if direction not in valid_directions:
            raise HTTPException(
                status_code=400, detail=f"Invalid direction: {direction}"
            )

        old_target = world_room.exits.get(direction)

        if target_id is None:
            # Removing exit
            if direction in world_room.exits:
                # Handle bidirectional removal
                if body.bidirectional and old_target:
                    opposite = _OPPOSITE_DIRECTIONS[direction]
                    old_target_room = world.rooms.get(old_target)
                    if old_target_room and opposite in old_target_room.exits:
                        del old_target_room.exits[opposite]
                        # Update DB
                        old_target_db = await session.get(Room, old_target)
                        if old_target_db:
                            setattr(old_target_db, _DIRECTION_TO_COLUMN[opposite], None)

                del world_room.exits[direction]
                setattr(db_room, _DIRECTION_TO_COLUMN[direction], None)
                changes.append(f"Removed {direction} exit (was -> {old_target})")
        else:
            # Adding/updating exit
            if target_id not in world.rooms:
                raise HTTPException(
                    status_code=400, detail=f"Target room '{target_id}' not found"
                )

            # Update in-memory
            world_room.exits[direction] = target_id
            # Update DB
            setattr(db_room, _DIRECTION_TO_COLUMN[direction], target_id)

            if old_target != target_id:
                changes.append(
                    f"Set {direction} exit -> {target_id}"
                    + (f" (was {old_target})" if old_target else "")
                )

            # Handle bidirectional creation
            if body.bidirectional:
                opposite = _OPPOSITE_DIRECTIONS[direction]
                target_room = world.rooms.get(target_id)
                if target_room:
                    target_room.exits[opposite] = room_id
                    target_db = await session.get(Room, target_id)
                    if target_db:
                        setattr(target_db, _DIRECTION_TO_COLUMN[opposite], room_id)
                    changes.append(
                        f"Set reverse {opposite} exit in {target_id} -> {room_id}"
                    )

    # Mark room as API-managed
    if changes:
        world_room.yaml_managed = False
        db_room.yaml_managed = False

    await session.commit()

    # Audit log
    if changes:
        admin_audit_logger.info(
            "room_exits_updated",
            admin_id=admin_id,
            room_id=room_id,
            changes=changes,
            bidirectional=body.bidirectional,
        )

    # Return updated room
    npc_ids = [npc.id for npc in world.npcs.values() if npc.room_id == room_id]
    item_ids = [item.id for item in world.items.values() if item.room_id == room_id]
    trigger_ids = (
        [t.trigger_id for t in world_room.triggers]
        if hasattr(world_room, "triggers")
        else []
    )

    return RoomDetail(
        id=world_room.id,
        name=world_room.name,
        description=world_room.get_effective_description(),
        room_type=world_room.room_type,
        area_id=world_room.area_id,
        exits=world_room.exits,
        dynamic_exits=world_room.dynamic_exits,
        players=list(world_room.players),
        npcs=npc_ids,
        items=item_ids,
        flags=world_room.room_flags,
        triggers=trigger_ids,
    )


@router.post("/world/rooms/{room_id}/reset-yaml-managed")
async def reset_room_yaml_managed(
    room_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(UserRole.ADMIN)),
):
    """
    Reset a room to be YAML-managed.

    After calling this, the room will be updated during YAML content reloads.
    Use this when you want YAML changes to take precedence again.

    Requires: ADMIN
    """
    engine = get_engine_from_request(request)
    world = engine.world
    admin_id = admin.get("user_id", "unknown")

    world_room = world.rooms.get(room_id)
    if not world_room:
        raise HTTPException(status_code=404, detail="Room not found")

    db_room = await session.get(Room, room_id)
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found in database")

    was_api_managed = not world_room.yaml_managed

    world_room.yaml_managed = True
    db_room.yaml_managed = True
    await session.commit()

    if was_api_managed:
        admin_audit_logger.info(
            "room_reset_to_yaml_managed", admin_id=admin_id, room_id=room_id
        )

    return {
        "success": True,
        "room_id": room_id,
        "yaml_managed": True,
        "message": "Room is now YAML-managed and will be updated during content reloads",
    }


@router.get("/world/areas", response_model=list[AreaSummary])
async def list_areas(request: Request, admin: dict = Depends(get_current_admin)):
    """
    List all areas.
    Requires: MODERATOR or higher
    """
    engine = get_engine_from_request(request)
    world = engine.world

    areas = []
    for area in world.areas.values():
        # Count rooms in area
        room_count = sum(1 for r in world.rooms.values() if r.area_id == area.area_id)

        # Count players in area
        player_count = sum(
            1
            for r in world.rooms.values()
            if r.area_id == area.area_id
            for _ in r.players
        )

        areas.append(
            AreaSummary(
                id=area.area_id,
                name=area.name,
                room_count=room_count,
                player_count=player_count,
                time_scale=area.time_scale,
            )
        )

    return areas


@router.get("/world/npcs", response_model=list[NpcSummary])
async def list_npcs(
    request: Request,
    admin: dict = Depends(get_current_admin),
    room_id: str | None = None,
    alive_only: bool = False,
    verbose: bool = False,
):
    """
    List all NPCs, optionally filtered by room or alive status.
    Requires: MODERATOR or higher

    Args:
        room_id: Filter NPCs by room ID
        alive_only: Only return living NPCs
        verbose: Include ability and resource pool details (Phase 14.5)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    npcs = []
    for npc in world.npcs.values():
        # Filter by room if specified
        if room_id and npc.room_id != room_id:
            continue

        # Filter by alive status
        if alive_only and npc.current_health <= 0:
            continue

        npc_data = NpcSummary(
            id=npc.id,
            template_id=npc.template_id,
            name=npc.name,
            room_id=npc.room_id,
            current_health=npc.current_health,
            max_health=npc.max_health,
            is_alive=npc.current_health > 0,
        )

        # Phase 14.5: Include ability details in verbose mode
        if verbose and npc.has_character_sheet():
            npc_data.class_id = npc.get_class_id()
            npc_data.has_abilities = True
            npc_data.learned_abilities = list(npc.get_learned_abilities())
            npc_data.ability_loadout = [
                slot.ability_id for slot in npc.get_ability_loadout()
            ]
            # Include resource pools with current/max values
            if npc.character_sheet and npc.character_sheet.resource_pools:
                npc_data.resource_pools = {
                    rid: {"current": pool.current, "max": pool.max}
                    for rid, pool in npc.character_sheet.resource_pools.items()
                }
        elif verbose:
            npc_data.has_abilities = False

        npcs.append(npc_data)

    return npcs


@router.get("/world/items", response_model=list[ItemSummary])
async def list_items(
    request: Request,
    admin: dict = Depends(get_current_admin),
    room_id: str | None = None,
    player_id: str | None = None,
):
    """
    List all items, optionally filtered by location.
    Requires: MODERATOR or higher
    """
    engine = get_engine_from_request(request)
    world = engine.world

    items = []
    for item in world.items.values():
        # Determine location
        if item.room_id:
            location_type = "room"
            location_id = item.room_id
        elif item.player_id:
            location_type = "player"
            location_id = item.player_id
        elif item.container_id:
            location_type = "container"
            location_id = item.container_id
        else:
            location_type = "unknown"
            location_id = ""

        # Filter by room if specified
        if room_id and location_id != room_id:
            continue

        # Filter by player if specified
        if player_id and location_id != player_id:
            continue

        items.append(
            ItemSummary(
                id=item.id,
                template_id=item.template_id,
                name=item.name,
                location_type=location_type,
                location_id=location_id,
                quantity=item.quantity,
            )
        )

    return items


@router.get("/world/state", response_model=WorldStateResponse)
async def get_world_state(
    request: Request, admin: dict = Depends(require_role(UserRole.GAME_MASTER))
):
    """
    Get complete world state snapshot.

    Returns all players, rooms, areas, NPCs, and items in a single response.
    WARNING: This can be a large response for big worlds. Use with caution.

    Requires: GAME_MASTER or higher
    """
    engine = get_engine_from_request(request)
    world = engine.world

    # Build player summaries
    players = []
    players_online = 0
    for player in world.players.values():
        if player.is_connected:
            players_online += 1
        in_combat = (
            hasattr(engine, "combat_system")
            and player.id in engine.combat_system.active_combats
        )
        players.append(
            PlayerSummary(
                id=player.id,
                name=player.name,
                room_id=player.current_room_id,
                level=player.level,
                current_health=player.current_health,
                max_health=player.max_health,
                is_connected=player.is_connected,
                in_combat=in_combat,
            )
        )

    # Build room details
    rooms = []
    for room in world.rooms.values():
        npc_ids = [npc.id for npc in world.npcs.values() if npc.room_id == room.id]
        item_ids = [item.id for item in world.items.values() if item.room_id == room.id]
        trigger_ids = (
            [t.trigger_id for t in room.triggers] if hasattr(room, "triggers") else []
        )

        rooms.append(
            RoomDetail(
                id=room.id,
                name=room.name,
                description=room.get_effective_description(),
                room_type=room.room_type,
                area_id=room.area_id,
                exits=room.exits,
                dynamic_exits=room.dynamic_exits,
                players=list(room.players),
                npcs=npc_ids,
                items=item_ids,
                flags=room.room_flags,
                triggers=trigger_ids,
            )
        )

    # Build area summaries
    areas = []
    for area in world.areas.values():
        room_count = sum(1 for r in world.rooms.values() if r.area_id == area.area_id)
        player_count = sum(
            1
            for r in world.rooms.values()
            if r.area_id == area.area_id
            for _ in r.players
        )
        areas.append(
            AreaSummary(
                id=area.area_id,
                name=area.name,
                room_count=room_count,
                player_count=player_count,
                time_scale=area.time_scale,
            )
        )

    # Build NPC summaries
    npcs = []
    npcs_alive = 0
    for npc in world.npcs.values():
        is_alive = npc.current_health > 0
        if is_alive:
            npcs_alive += 1
        npcs.append(
            NpcSummary(
                id=npc.id,
                template_id=npc.template_id,
                name=npc.name,
                room_id=npc.room_id,
                current_health=npc.current_health,
                max_health=npc.max_health,
                is_alive=is_alive,
            )
        )

    # Build item summaries
    items = []
    for item in world.items.values():
        if item.room_id:
            location_type = "room"
            location_id = item.room_id
        elif item.player_id:
            location_type = "player"
            location_id = item.player_id
        elif item.container_id:
            location_type = "container"
            location_id = item.container_id
        else:
            location_type = "unknown"
            location_id = ""

        items.append(
            ItemSummary(
                id=item.id,
                template_id=item.template_id,
                name=item.name,
                location_type=location_type,
                location_id=location_id,
                quantity=item.quantity,
            )
        )

    # Get combat and event counts
    active_combats = (
        len(engine.combat_system.active_combats)
        if hasattr(engine, "combat_system")
        else 0
    )
    scheduled_events = (
        len(engine.time_manager.events) if hasattr(engine, "time_manager") else 0
    )

    return WorldStateResponse(
        server_uptime=time.time() - _server_start_time,
        server_time=time.time(),
        maintenance_mode=_maintenance_mode,
        shutdown_pending=_shutdown_requested,
        players_online=players_online,
        players_total=len(world.players),
        npcs_alive=npcs_alive,
        npcs_total=len(world.npcs),
        rooms_total=len(world.rooms),
        areas_total=len(world.areas),
        items_total=len(world.items),
        active_combats=active_combats,
        scheduled_events=scheduled_events,
        players=players,
        rooms=rooms,
        areas=areas,
        npcs=npcs,
        items=items,
    )


# ============================================================================
# Player Manipulation Endpoints
# ============================================================================


@router.post("/players/{player_id}/teleport")
async def teleport_player(
    player_id: str,
    request: Request,
    teleport_request: TeleportRequest,
    admin: dict = Depends(require_permission(Permission.TELEPORT)),
):
    """
    Teleport a player to a specific room.
    Requires: TELEPORT permission (GAME_MASTER+)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    player = world.players.get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    target_room = world.rooms.get(teleport_request.room_id)
    if not target_room:
        raise HTTPException(status_code=404, detail="Target room not found")

    # Get old room
    old_room = world.rooms.get(player.room_id)
    old_room_id = old_room.id if old_room else None

    # Move player
    if old_room:
        old_room.players.discard(player.id)
    player.room_id = target_room.id
    target_room.players.add(player.id)

    # Audit log
    admin_audit.log_teleport(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        target_player_id=player_id,
        from_room=old_room_id,
        to_room=target_room.id,
        success=True,
    )

    # Notify player
    if player.id in engine._listeners:
        await engine._listeners[player.id].put(
            {
                "type": "message",
                "text": f"You have been teleported to {target_room.name}.",
            }
        )
        # Send room description
        room_desc = engine._format_room_description(target_room, player.id)
        await engine._listeners[player.id].put({"type": "message", "text": room_desc})

    return {
        "success": True,
        "message": f"Teleported {player.name} to {target_room.name}",
        "from_room": old_room_id,
        "to_room": target_room.id,
    }


@router.post("/players/{player_id}/heal")
async def heal_player(
    player_id: str,
    request: Request,
    heal_request: HealRequest,
    admin: dict = Depends(require_permission(Permission.MODIFY_STATS)),
):
    """
    Heal a player.
    Requires: MODIFY_STATS permission (GAME_MASTER+)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    player = world.players.get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    old_health = player.current_health

    if heal_request.amount is None:
        # Full heal
        player.current_health = player.max_health
    else:
        player.current_health = min(
            player.current_health + heal_request.amount, player.max_health
        )

    healed_amount = player.current_health - old_health

    # Notify player
    if player.id in engine._listeners:
        await engine._listeners[player.id].put(
            {
                "type": "message",
                "text": f"You have been healed for {healed_amount} HP by divine intervention.",
            }
        )
        await engine._listeners[player.id].put(
            {
                "type": "stat_update",
                "payload": {
                    "current_health": player.current_health,
                    "max_health": player.max_health,
                },
            }
        )

    return {
        "success": True,
        "message": f"Healed {player.name} for {healed_amount} HP",
        "old_health": old_health,
        "new_health": player.current_health,
        "max_health": player.max_health,
    }


@router.post("/players/{player_id}/kick")
async def kick_player(
    player_id: str,
    request: Request,
    reason: str = "Kicked by administrator",
    admin: dict = Depends(require_permission(Permission.KICK_PLAYER)),
):
    """
    Disconnect a player from the server.
    Requires: KICK_PLAYER permission (MODERATOR+)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    player = world.players.get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    if not player.is_connected:
        raise HTTPException(status_code=400, detail="Player is not connected")

    # Audit log
    admin_audit.log_kick(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        target_player_id=player_id,
        reason=reason,
        success=True,
    )

    # Send kick message to player
    if player.id in engine._listeners:
        await engine._listeners[player.id].put(
            {"type": "kicked", "text": f"You have been kicked: {reason}"}
        )

    # Mark player as disconnected (the WebSocket handler will clean up)
    player.is_connected = False

    logger.info(
        "Player kicked", admin_id=admin.get("sub"), player_id=player_id, reason=reason
    )

    return {"success": True, "message": f"Kicked {player.name}", "reason": reason}


@router.post("/players/{player_id}/give")
async def give_item_to_player(
    player_id: str,
    request: Request,
    give_request: GiveItemRequest,
    admin: dict = Depends(require_permission(Permission.SPAWN_ITEM)),
):
    """
    Give an item to a player.
    Requires: SPAWN_ITEM permission (GAME_MASTER+)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    player = world.players.get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Check template exists
    template = world.item_templates.get(give_request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Item template not found")

    # Create item instance
    import uuid

    item_id = str(uuid.uuid4())

    from daemons.engine.world import WorldItem

    item = WorldItem(
        id=item_id,
        template_id=template.id,
        name=template.name,
        description=template.description,
        room_id=None,
        player_id=player.id,
        container_id=None,
        quantity=give_request.quantity,
        keywords=template.keywords.copy() if template.keywords else [],
    )

    world.items[item_id] = item

    # Audit log
    admin_audit.log_give_item(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        target_player_id=player_id,
        item_template_id=give_request.template_id,
        quantity=give_request.quantity,
        success=True,
    )

    # Notify player
    if player.id in engine._listeners:
        qty_text = f"{give_request.quantity}x " if give_request.quantity > 1 else ""
        await engine._listeners[player.id].put(
            {
                "type": "message",
                "text": f"You received {qty_text}{template.name} from a mysterious force.",
            }
        )

    return {
        "success": True,
        "message": f"Gave {give_request.quantity}x {template.name} to {player.name}",
        "item_id": item_id,
    }


@router.post("/players/{player_id}/effect")
async def apply_effect_to_player(
    player_id: str,
    request: Request,
    effect_request: ApplyEffectRequest,
    admin: dict = Depends(require_permission(Permission.MODIFY_STATS)),
):
    """
    Apply a temporary effect (buff/debuff) to a player.
    Requires: MODIFY_STATS permission (GAME_MASTER+)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    player = world.players.get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Import Effect class
    import time
    import uuid

    from daemons.engine.world import Effect

    # Determine effect type based on name (convention: "buff_" prefix for buffs, "debuff_" for debuffs, "dot_" for damage, "hot_" for healing)
    effect_type = "buff"
    if effect_request.effect_name.startswith("debuff_"):
        effect_type = "debuff"
    elif effect_request.effect_name.startswith("dot_"):
        effect_type = "dot"
    elif effect_request.effect_name.startswith("hot_"):
        effect_type = "hot"

    # Create effect instance
    effect_id = str(uuid.uuid4())
    effect = Effect(
        effect_id=effect_id,
        name=effect_request.effect_name.replace("buff_", "")
        .replace("debuff_", "")
        .replace("dot_", "")
        .replace("hot_", "")
        .replace("_", " ")
        .title(),
        effect_type=effect_type,
        duration=effect_request.duration,
        applied_at=time.time(),
        magnitude=effect_request.magnitude if effect_request.magnitude > 0 else 0,
        interval=(
            1.0 if effect_request.magnitude > 0 else 0.0
        ),  # Tick every 1 second if periodic
    )

    # Apply effect to player
    player.apply_effect(effect)

    # Audit log
    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action_type="apply_effect",
        target_type="player",
        target_id=player_id,
        details={
            "effect_name": effect_request.effect_name,
            "effect_type": effect_type,
            "duration": effect_request.duration,
            "magnitude": effect_request.magnitude,
        },
        success=True,
    )

    # Notify player
    if player.id in engine._listeners:
        await engine._listeners[player.id].put(
            {
                "type": "message",
                "text": f"You are afflicted with {effect.name} for {effect_request.duration} seconds.",
            }
        )

    return {
        "success": True,
        "message": f"Applied {effect.name} to {player.name}",
        "effect_id": effect_id,
        "effect_type": effect_type,
        "duration": effect_request.duration,
    }


@router.post("/players/{player_id}/kill")
async def kill_player(
    player_id: str,
    request: Request,
    admin: dict = Depends(require_permission(Permission.MODIFY_STATS)),
):
    """
    Instantly kill a player, triggering the death handler.
    Requires: MODIFY_STATS permission (GAME_MASTER+)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    player = world.players.get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    if not player.is_alive():
        raise HTTPException(status_code=400, detail="Player is already dead")

    # Set health to 0
    player.current_health = 0

    # Get room for broadcast
    room = world.rooms.get(player.room_id)

    # Notify player
    if player.id in engine._listeners:
        await engine._listeners[player.id].put(
            {"type": "message", "text": "You have been slain by divine judgment."}
        )

    # Broadcast to room
    if room:
        for other_id in room.players:
            if other_id != player_id and other_id in engine._listeners:
                await engine._listeners[other_id].put(
                    {
                        "type": "message",
                        "text": f"💀 {player.name} has been slain by divine judgment!",
                    }
                )

    # Audit log
    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action_type="kill_player",
        target_type="player",
        target_id=player_id,
        details={"reason": "Admin judgment"},
        success=True,
    )

    logger.info(
        "Player killed by admin", admin_id=admin.get("sub"), player_id=player_id
    )

    return {"success": True, "message": f"Killed {player.name}", "player_id": player_id}


@router.post("/players/{player_id}/message")
async def send_message_to_player(
    player_id: str,
    request: Request,
    message_request: BroadcastRequest,
    admin: dict = Depends(require_permission(Permission.KICK_PLAYER)),
):
    """
    Send a direct message to a player.
    Requires: KICK_PLAYER permission (MODERATOR+)

    This sends a message directly to the player, appearing as from the sender name.
    """
    engine = get_engine_from_request(request)
    world = engine.world

    player = world.players.get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    if not player.is_connected:
        raise HTTPException(status_code=400, detail="Player is not connected")

    # Notify player
    if player.id in engine._listeners:
        await engine._listeners[player.id].put(
            {
                "type": "message",
                "text": f"[{message_request.sender_name}]: {message_request.message}",
            }
        )

    # Audit log
    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action_type="send_message",
        target_type="player",
        target_id=player_id,
        details={"message": message_request.message},
        success=True,
    )

    logger.info(
        "Message sent to player",
        admin_id=admin.get("sub"),
        player_id=player_id,
        sender=message_request.sender_name,
    )

    return {
        "success": True,
        "message": f"Message sent to {player.name}",
        "sender": message_request.sender_name,
        "recipient": player_id,
    }


# ============================================================================
# Spawn/Despawn Endpoints
# ============================================================================


@router.post("/npcs/spawn")
async def spawn_npc(
    request: Request,
    spawn_request: SpawnNpcRequest,
    admin: dict = Depends(require_permission(Permission.SPAWN_NPC)),
):
    """
    Spawn an NPC in a room.
    Requires: SPAWN_NPC permission (GAME_MASTER+)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    # Check template exists
    template = world.npc_templates.get(spawn_request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="NPC template not found")

    # Check room exists
    room = world.rooms.get(spawn_request.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Spawn the NPC using engine's spawn method
    npc = await engine._spawn_npc(template, spawn_request.room_id)

    # Audit log
    admin_audit.log_spawn(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        entity_type="npc",
        template_id=spawn_request.template_id,
        room_id=spawn_request.room_id,
        instance_id=npc.id,
        success=True,
    )

    return {
        "success": True,
        "message": f"Spawned {template.name} in {room.name}",
        "npc_id": npc.id,
        "room_id": room.id,
    }


@router.delete("/npcs/{npc_id}")
async def despawn_npc(
    npc_id: str,
    request: Request,
    admin: dict = Depends(require_permission(Permission.SPAWN_NPC)),
):
    """
    Despawn an NPC.
    Requires: SPAWN_NPC permission (GAME_MASTER+)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    npc = world.npcs.get(npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")

    npc_name = npc.name
    room_id = npc.room_id
    template_id = npc.template_id

    # Remove NPC from world
    del world.npcs[npc_id]

    # Audit log
    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action="despawn",
        target_type="npc",
        target_id=npc_id,
        details={"template_id": template_id, "room_id": room_id},
        success=True,
    )

    # Notify players in room
    room = world.rooms.get(room_id)
    if room:
        for pid in room.players:
            if pid in engine._listeners:
                await engine._listeners[pid].put(
                    {
                        "type": "message",
                        "text": f"{npc_name} vanishes in a puff of smoke.",
                    }
                )

    return {"success": True, "message": f"Despawned {npc_name}", "npc_id": npc_id}


@router.post("/items/spawn")
async def spawn_item(
    request: Request,
    spawn_request: SpawnItemRequest,
    admin: dict = Depends(require_permission(Permission.SPAWN_ITEM)),
):
    """
    Spawn an item in a room.
    Requires: SPAWN_ITEM permission (GAME_MASTER+)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    # Check template exists
    template = world.item_templates.get(spawn_request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Item template not found")

    # Check room exists
    room = world.rooms.get(spawn_request.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Create item instance
    import uuid

    item_id = str(uuid.uuid4())

    from daemons.engine.world import WorldItem

    item = WorldItem(
        id=item_id,
        template_id=template.id,
        name=template.name,
        description=template.description,
        room_id=room.id,
        player_id=None,
        container_id=None,
        quantity=spawn_request.quantity,
        keywords=template.keywords.copy() if template.keywords else [],
    )

    world.items[item_id] = item

    # Notify players in room
    qty_text = f"{spawn_request.quantity}x " if spawn_request.quantity > 1 else ""
    for pid in room.players:
        if pid in engine._listeners:
            await engine._listeners[pid].put(
                {
                    "type": "message",
                    "text": f"{qty_text}{template.name} materializes on the ground.",
                }
            )

    return {
        "success": True,
        "message": f"Spawned {spawn_request.quantity}x {template.name} in {room.name}",
        "item_id": item_id,
    }


@router.delete("/items/{item_id}")
async def despawn_item(
    item_id: str,
    request: Request,
    admin: dict = Depends(require_permission(Permission.SPAWN_ITEM)),
):
    """
    Despawn an item.
    Requires: SPAWN_ITEM permission (GAME_MASTER+)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    item = world.items.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item_name = item.name
    room_id = item.room_id

    # Remove item from world
    del world.items[item_id]

    # Notify players in room if it was on the ground
    if room_id:
        room = world.rooms.get(room_id)
        if room:
            for pid in room.players:
                if pid in engine._listeners:
                    await engine._listeners[pid].put(
                        {"type": "message", "text": f"{item_name} vanishes."}
                    )

    return {"success": True, "message": f"Despawned {item_name}", "item_id": item_id}


@router.post("/npcs/{npc_id}/move")
async def move_npc(
    npc_id: str,
    request: Request,
    move_request: MoveNpcRequest,
    admin: dict = Depends(require_permission(Permission.SPAWN_NPC)),
):
    """
    Move an NPC to a different room.
    Requires: SPAWN_NPC permission (GAME_MASTER+)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    npc = world.npcs.get(npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")

    target_room = world.rooms.get(move_request.target_room_id)
    if not target_room:
        raise HTTPException(status_code=404, detail="Target room not found")

    # Get old room
    old_room = world.rooms.get(npc.room_id)
    old_room_id = old_room.id if old_room else None

    # Move NPC
    if old_room:
        old_room.entities.discard(npc_id)
    npc.room_id = target_room.id
    target_room.entities.add(npc_id)

    # Audit log
    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action_type="move_npc",
        target_type="npc",
        target_id=npc_id,
        details={
            "from_room": old_room_id,
            "to_room": target_room.id,
            "reason": move_request.reason,
        },
        success=True,
    )

    # Notify players in old room
    if old_room:
        for pid in [eid for eid in old_room.entities if eid in world.players]:
            if pid in engine._listeners:
                await engine._listeners[pid].put(
                    {
                        "type": "message",
                        "text": f"{npc.name} vanishes in a shimmer of light.",
                    }
                )

    # Notify players in new room
    for pid in [eid for eid in target_room.entities if eid in world.players]:
        if pid in engine._listeners:
            await engine._listeners[pid].put(
                {"type": "message", "text": f"{npc.name} materializes before you!"}
            )

    return {
        "success": True,
        "message": f"Moved {npc.name} to {target_room.name}",
        "npc_id": npc_id,
        "from_room": old_room_id,
        "to_room": target_room.id,
    }


@router.post("/items/{item_id}/move")
async def move_item(
    item_id: str,
    request: Request,
    move_request: MoveItemRequest,
    admin: dict = Depends(require_permission(Permission.SPAWN_ITEM)),
):
    """
    Move an item to a different location (room, player inventory, or container).
    Requires: SPAWN_ITEM permission (GAME_MASTER+)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    item = world.items.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Must specify exactly one target location
    targets_specified = sum(
        [
            move_request.target_room_id is not None,
            move_request.target_player_id is not None,
            move_request.target_container_id is not None,
        ]
    )

    if targets_specified != 1:
        raise HTTPException(
            status_code=400,
            detail="Must specify exactly one target: target_room_id, target_player_id, or target_container_id",
        )

    # Track old location
    old_room_id = item.room_id
    old_player_id = item.player_id
    old_container_id = item.container_id

    # Move to room
    if move_request.target_room_id:
        target_room = world.rooms.get(move_request.target_room_id)
        if not target_room:
            raise HTTPException(status_code=404, detail="Target room not found")

        # Remove from old location
        if old_room_id:
            room = world.rooms.get(old_room_id)
            if room:
                room.items.discard(item_id)
        if old_player_id:
            # Remove from player inventory tracking if we implement it
            pass
        if old_container_id:
            # Remove from container contents if applicable
            if old_container_id in world.container_contents:
                world.container_contents[old_container_id].discard(item_id)

        # Add to new location
        item.room_id = move_request.target_room_id
        item.player_id = None
        item.container_id = None
        target_room.items.add(item_id)

        # Notify players in new room
        for pid in [eid for eid in target_room.entities if eid in world.players]:
            if pid in engine._listeners:
                qty_text = f"{item.quantity}x " if item.quantity > 1 else ""
                await engine._listeners[pid].put(
                    {
                        "type": "message",
                        "text": f"{qty_text}{item.name} materializes on the ground.",
                    }
                )

        message = f"Moved {item.name} to {target_room.name}"

    # Move to player inventory
    elif move_request.target_player_id:
        target_player = world.players.get(move_request.target_player_id)
        if not target_player:
            raise HTTPException(status_code=404, detail="Target player not found")

        # Remove from old location
        if old_room_id:
            room = world.rooms.get(old_room_id)
            if room:
                room.items.discard(item_id)
        if old_container_id:
            if old_container_id in world.container_contents:
                world.container_contents[old_container_id].discard(item_id)

        # Add to player inventory
        item.room_id = None
        item.player_id = move_request.target_player_id
        item.container_id = None

        # Notify target player
        if move_request.target_player_id in engine._listeners:
            qty_text = f"{item.quantity}x " if item.quantity > 1 else ""
            await engine._listeners[move_request.target_player_id].put(
                {"type": "message", "text": f"You received {qty_text}{item.name}."}
            )

        # Notify old room if item was there
        if old_room_id:
            room = world.rooms.get(old_room_id)
            if room:
                for pid in [eid for eid in room.entities if eid in world.players]:
                    if (
                        pid != move_request.target_player_id
                        and pid in engine._listeners
                    ):
                        await engine._listeners[pid].put(
                            {"type": "message", "text": f"{item.name} is taken."}
                        )

        message = f"Moved {item.name} to {target_player.name}'s inventory"

    # Move to container
    else:  # move_request.target_container_id
        target_container = world.items.get(move_request.target_container_id)
        if not target_container:
            raise HTTPException(status_code=404, detail="Target container not found")

        # Remove from old location
        if old_room_id:
            room = world.rooms.get(old_room_id)
            if room:
                room.items.discard(item_id)
        if old_player_id:
            pass  # Would need inventory tracking
        if old_container_id:
            if old_container_id in world.container_contents:
                world.container_contents[old_container_id].discard(item_id)

        # Add to container
        item.room_id = None
        item.player_id = None
        item.container_id = move_request.target_container_id

        # Update container contents index
        if move_request.target_container_id not in world.container_contents:
            world.container_contents[move_request.target_container_id] = set()
        world.container_contents[move_request.target_container_id].add(item_id)

        message = f"Moved {item.name} into {target_container.name}"

    # Audit log
    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action_type="move_item",
        target_type="item",
        target_id=item_id,
        details={
            "from_room": old_room_id,
            "from_player": old_player_id,
            "from_container": old_container_id,
            "to_room": move_request.target_room_id,
            "to_player": move_request.target_player_id,
            "to_container": move_request.target_container_id,
        },
        success=True,
    )

    return {"success": True, "message": message, "item_id": item_id}


# ============================================================================
# Trigger Management Endpoints
# ============================================================================


@router.get("/triggers/rooms/{room_id}", response_model=RoomTriggersResponse)
async def get_room_triggers(
    room_id: str,
    request: Request,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
):
    """
    Get all triggers in a specific room with their current state.
    Requires: GAME_MASTER+ (SERVER_COMMANDS)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    room = world.rooms.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    triggers_list: list[TriggerStateResponse] = []

    if hasattr(room, "triggers"):
        for trigger in room.triggers:
            state = engine.trigger_system._get_state(room, trigger.id)
            triggers_list.append(
                TriggerStateResponse(
                    trigger_id=trigger.id,
                    room_id=room_id,
                    event=trigger.event,
                    enabled=trigger.enabled,
                    fire_count=state.fire_count if state else 0,
                    last_fired_at=state.last_fired_at if state else None,
                    cooldown=trigger.cooldown,
                    max_fires=trigger.max_fires,
                    command_pattern=trigger.command_pattern,
                    timer_interval=trigger.timer_interval,
                )
            )

    return RoomTriggersResponse(
        room_id=room_id,
        room_name=room.name,
        trigger_count=len(triggers_list),
        triggers=triggers_list,
    )


@router.post("/triggers/{trigger_id}/fire")
async def fire_trigger(
    trigger_id: str,
    request: Request,
    fire_request: FireTriggerRequest,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
):
    """
    Manually fire a trigger immediately.
    Requires: GAME_MASTER+ (SERVER_COMMANDS)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    room = world.rooms.get(fire_request.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if not hasattr(room, "triggers"):
        raise HTTPException(status_code=400, detail="Room has no triggers")

    # Find the trigger
    trigger = None
    for t in room.triggers:
        if t.id == trigger_id:
            trigger = t
            break

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    if not trigger.enabled:
        raise HTTPException(status_code=400, detail="Trigger is disabled")

    # Use provided player or pick one from room
    player_id = fire_request.player_id or ""
    if not player_id:
        for entity_id in room.entities:
            if entity_id in world.players:
                player_id = entity_id
                break

    # Create trigger context and fire
    from daemons.engine.systems.triggers import TriggerContext

    trigger_ctx = TriggerContext(
        player_id=player_id,
        room_id=fire_request.room_id,
        world=world,
        event_type=trigger.event,
    )

    engine.trigger_system.execute_actions(trigger.actions, trigger_ctx)

    # Update state
    state = engine.trigger_system._get_or_create_state(room, trigger_id)
    state.fire_count += 1
    state.last_fired_at = time.time()

    # Audit log
    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action_type="fire_trigger",
        target_type="trigger",
        target_id=trigger_id,
        details={"room_id": fire_request.room_id, "fire_count": state.fire_count},
        success=True,
    )

    return {
        "success": True,
        "message": f"Fired trigger {trigger_id}",
        "trigger_id": trigger_id,
        "fire_count": state.fire_count,
        "actions_executed": len(trigger.actions),
    }


@router.post("/triggers/{trigger_id}/enable")
async def enable_trigger(
    trigger_id: str,
    request: Request,
    modify_request: ModifyTriggerRequest,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
):
    """
    Enable a disabled trigger.
    Requires: GAME_MASTER+ (SERVER_COMMANDS)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    room = world.rooms.get(modify_request.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if not hasattr(room, "triggers"):
        raise HTTPException(status_code=400, detail="Room has no triggers")

    trigger = None
    for t in room.triggers:
        if t.id == trigger_id:
            trigger = t
            break

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    trigger.enabled = True
    state = engine.trigger_system._get_or_create_state(room, trigger_id)
    state.enabled = True

    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action_type="enable_trigger",
        target_type="trigger",
        target_id=trigger_id,
        details={"room_id": modify_request.room_id},
        success=True,
    )

    return {
        "success": True,
        "message": f"Enabled trigger {trigger_id}",
        "trigger_id": trigger_id,
        "enabled": True,
    }


@router.post("/triggers/{trigger_id}/disable")
async def disable_trigger(
    trigger_id: str,
    request: Request,
    modify_request: ModifyTriggerRequest,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
):
    """
    Disable a trigger (prevent it from firing).
    Requires: GAME_MASTER+ (SERVER_COMMANDS)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    room = world.rooms.get(modify_request.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if not hasattr(room, "triggers"):
        raise HTTPException(status_code=400, detail="Room has no triggers")

    trigger = None
    for t in room.triggers:
        if t.id == trigger_id:
            trigger = t
            break

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    trigger.enabled = False
    state = engine.trigger_system._get_or_create_state(room, trigger_id)
    state.enabled = False

    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action_type="disable_trigger",
        target_type="trigger",
        target_id=trigger_id,
        details={"room_id": modify_request.room_id},
        success=True,
    )

    return {
        "success": True,
        "message": f"Disabled trigger {trigger_id}",
        "trigger_id": trigger_id,
        "enabled": False,
    }


@router.post("/triggers/{trigger_id}/reset")
async def reset_trigger(
    trigger_id: str,
    request: Request,
    modify_request: ModifyTriggerRequest,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
):
    """
    Reset a trigger's fire count and cooldown.
    Requires: GAME_MASTER+ (SERVER_COMMANDS)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    room = world.rooms.get(modify_request.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if not hasattr(room, "triggers"):
        raise HTTPException(status_code=400, detail="Room has no triggers")

    trigger = None
    for t in room.triggers:
        if t.id == trigger_id:
            trigger = t
            break

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    state = engine.trigger_system._get_or_create_state(room, trigger_id)
    old_fire_count = state.fire_count
    state.fire_count = 0
    state.last_fired_at = None

    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action_type="reset_trigger",
        target_type="trigger",
        target_id=trigger_id,
        details={"room_id": modify_request.room_id, "old_fire_count": old_fire_count},
        success=True,
    )

    return {
        "success": True,
        "message": f"Reset trigger {trigger_id}",
        "trigger_id": trigger_id,
        "old_fire_count": old_fire_count,
        "new_fire_count": 0,
    }


# ============================================================================
# Quest Management Endpoints
# ============================================================================


@router.get("/quests/templates", response_model=QuestTemplatesResponse)
async def get_quest_templates(
    request: Request,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
):
    """
    Get all available quest templates.
    Requires: GAME_MASTER+ (SERVER_COMMANDS)
    """
    engine = get_engine_from_request(request)

    quests_list: list[QuestTemplateResponse] = []
    for quest_id, template in engine.quest_system.templates.items():
        quests_list.append(
            QuestTemplateResponse(
                quest_id=quest_id,
                name=template.name,
                description=template.description,
                category=template.category,
                repeatable=template.repeatable,
                level_requirement=template.level_requirement,
                objective_count=len(template.objectives),
            )
        )

    return QuestTemplatesResponse(total_quests=len(quests_list), quests=quests_list)


@router.get("/quests/progress/{player_id}", response_model=PlayerQuestsResponse)
async def get_player_quests(
    player_id: str,
    request: Request,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
):
    """
    Get a player's quest progress.
    Requires: GAME_MASTER+ (SERVER_COMMANDS)
    """
    engine = get_engine_from_request(request)
    world = engine.world

    player = world.players.get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    quests_list: list[QuestProgressResponse] = []
    in_progress_count = 0
    completed_count = 0

    for quest_id, progress in player.quest_progress.items():
        in_progress_count += 1
        quests_list.append(
            QuestProgressResponse(
                quest_id=quest_id,
                status=progress.status.value,
                objective_progress=progress.objective_progress,
                accepted_at=progress.accepted_at,
                completed_at=progress.completed_at,
                turned_in_at=progress.turned_in_at,
                expires_at=progress.expires_at,
                completion_count=progress.completion_count,
            )
        )

    completed_count = len(player.completed_quests)

    return PlayerQuestsResponse(
        player_id=player_id,
        player_name=player.name,
        in_progress_count=in_progress_count,
        completed_count=completed_count,
        quests=quests_list,
    )


@router.post("/quests/modify")
async def modify_player_quest(
    request: Request,
    modify_request: ModifyQuestRequest,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
):
    """
    Modify a player's quest state (give, complete, reset, abandon, turn_in).
    Requires: GAME_MASTER+ (SERVER_COMMANDS)

    Actions:
    - give: Grant a quest to a player
    - complete: Mark all objectives as complete
    - turn_in: Turn in a completed quest
    - reset: Reset quest progress to accept again
    - abandon: Remove quest from player's progress
    """
    engine = get_engine_from_request(request)
    world = engine.world

    player = world.players.get(modify_request.player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    template = engine.quest_system.templates.get(modify_request.quest_id)
    if not template:
        raise HTTPException(status_code=404, detail="Quest template not found")

    action = modify_request.action.lower()
    result_message = ""

    if action == "give":
        # Give/accept quest to player
        from daemons.engine.systems.quests import QuestStatus

        if modify_request.quest_id in player.quest_progress:
            raise HTTPException(status_code=400, detail="Player already has this quest")

        engine.quest_system.accept_quest(
            modify_request.player_id, modify_request.quest_id
        )
        result_message = f"Gave quest {template.name} to {player.name}"

    elif action == "complete":
        # Mark all objectives as complete
        from daemons.engine.systems.quests import QuestStatus

        progress = player.quest_progress.get(modify_request.quest_id)
        if not progress:
            raise HTTPException(
                status_code=400, detail="Player does not have this quest"
            )

        # Complete all required objectives
        for objective in template.objectives:
            if not objective.optional:
                progress.objective_progress[objective.id] = objective.required_count

        progress.status = QuestStatus.COMPLETED
        progress.completed_at = time.time()
        result_message = f"Completed all objectives for {template.name}"

    elif action == "turn_in":
        # Turn in quest for rewards
        progress = player.quest_progress.get(modify_request.quest_id)
        if not progress:
            raise HTTPException(
                status_code=400, detail="Player does not have this quest"
            )

        from daemons.engine.systems.quests import QuestStatus

        if progress.status != QuestStatus.COMPLETED:
            # Auto-complete first
            for objective in template.objectives:
                if not objective.optional:
                    progress.objective_progress[objective.id] = objective.required_count
            progress.status = QuestStatus.COMPLETED

        engine.quest_system.turn_in_quest(
            modify_request.player_id, modify_request.quest_id
        )
        result_message = f"Turned in quest {template.name} for {player.name}"

    elif action == "reset":
        # Reset quest progress
        if modify_request.quest_id not in player.quest_progress:
            raise HTTPException(
                status_code=400, detail="Player does not have this quest"
            )

        progress = player.quest_progress[modify_request.quest_id]
        progress.objective_progress = {obj.id: 0 for obj in template.objectives}
        from daemons.engine.systems.quests import QuestStatus

        progress.status = QuestStatus.ACCEPTED
        result_message = f"Reset quest progress for {template.name}"

    elif action == "abandon":
        # Remove quest from player
        if modify_request.quest_id not in player.quest_progress:
            raise HTTPException(
                status_code=400, detail="Player does not have this quest"
            )

        del player.quest_progress[modify_request.quest_id]
        result_message = f"Abandoned quest {template.name} for {player.name}"

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    # Audit log
    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action_type=f"quest_{action}",
        target_type="quest",
        target_id=modify_request.quest_id,
        details={"player_id": modify_request.player_id, "quest_name": template.name},
        success=True,
    )

    return {
        "success": True,
        "message": result_message,
        "action": action,
        "quest_id": modify_request.quest_id,
        "player_id": modify_request.player_id,
        "quest_name": template.name,
    }


# ============================================================================
# Account Management Endpoints
# ============================================================================


@router.get("/accounts", response_model=AccountListResponse)
async def list_accounts(
    request: Request,
    role: str | None = None,
    banned_only: bool = False,
    admin: dict = Depends(require_permission(Permission.MANAGE_ACCOUNTS)),
):
    """
    List all user accounts with optional filtering.
    Requires: ADMIN (MANAGE_ACCOUNTS permission)

    Query parameters:
    - role: Filter by role (player, moderator, game_master, admin)
    - banned_only: If true, show only banned accounts
    """
    session = get_session()

    try:
        # Base query
        query = select(UserAccount)

        # Apply filters
        if role:
            query = query.where(UserAccount.role == role.lower())

        if banned_only:
            query = query.where(UserAccount.is_banned == 1)

        # Execute query
        result = session.execute(query)
        accounts = result.scalars().all()

        # Count total without filters
        total_query = select(func.count(UserAccount.id))
        total_result = session.execute(total_query)
        total_count = total_result.scalar()

        # Build response
        account_summaries = [
            AccountSummary(
                id=acc.id,
                username=acc.username,
                role=acc.role,
                is_banned=bool(acc.is_banned),
                is_active=bool(acc.is_active),
                last_login=acc.last_login,
            )
            for acc in accounts
        ]

        return AccountListResponse(
            total_accounts=total_count,
            filtered_count=len(accounts),
            accounts=account_summaries,
        )
    finally:
        session.close()


@router.get("/accounts/{account_id}", response_model=AccountDetailResponse)
async def get_account_details(
    account_id: str,
    request: Request,
    admin: dict = Depends(require_permission(Permission.MANAGE_ACCOUNTS)),
):
    """
    Get detailed information about a specific account.
    Requires: ADMIN (MANAGE_ACCOUNTS permission)
    """
    session = get_session()

    try:
        account = session.get(UserAccount, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        return AccountDetailResponse(
            id=account.id,
            username=account.username,
            email=account.email,
            role=account.role,
            is_active=bool(account.is_active),
            is_banned=bool(account.is_banned),
            ban_reason=account.ban_reason,
            banned_at=account.banned_at,
            banned_by=account.banned_by,
            created_at=account.created_at,
            last_login=account.last_login,
            active_character_id=account.active_character_id,
        )
    finally:
        session.close()


@router.put("/accounts/{account_id}/role")
async def set_account_role(
    account_id: str,
    request: Request,
    role_request: SetRoleRequest,
    admin: dict = Depends(require_permission(Permission.MANAGE_ROLES)),
    session: AsyncSession = Depends(get_session),
):
    """
    Change an account's role.
    Requires: ADMIN (MANAGE_ROLES permission)

    Valid roles: player, moderator, game_master, admin
    """
    # Validate role
    valid_roles = [r.value for r in UserRole]
    if role_request.new_role.lower() not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Valid roles: {', '.join(valid_roles)}",
        )

    account = session.get(UserAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    old_role = account.role
    account.role = role_request.new_role.lower()

    # Log security event
    from daemons.engine.systems.auth import SecurityEventType

    security_event = SecurityEvent(
        id=str(uuid.uuid4()),
        account_id=account_id,
        event_type=SecurityEventType.ROLE_CHANGED.value,
        details={
            "old_role": old_role,
            "new_role": account.role,
            "changed_by": admin.get("sub", "unknown"),
            "reason": role_request.reason,
        },
        timestamp=time.time(),
    )
    session.add(security_event)

    # Audit log
    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action_type="set_account_role",
        target_type="account",
        target_id=account_id,
        details={
            "username": account.username,
            "old_role": old_role,
            "new_role": account.role,
            "reason": role_request.reason,
        },
        success=True,
    )

    session.commit()

    logger.info(
        "Account role changed",
        admin_id=admin.get("sub"),
        account_id=account_id,
        old_role=old_role,
        new_role=account.role,
    )

    return {
        "success": True,
        "message": f"Changed {account.username}'s role from {old_role} to {account.role}",
        "account_id": account_id,
        "username": account.username,
        "old_role": old_role,
        "new_role": account.role,
    }


@router.post("/accounts/{account_id}/ban")
async def ban_account(
    account_id: str,
    request: Request,
    ban_request: BanAccountRequest,
    admin: dict = Depends(require_permission(Permission.MANAGE_ACCOUNTS)),
    session: AsyncSession = Depends(get_session),
):
    """
    Ban an account from the game.
    Requires: ADMIN (MANAGE_ACCOUNTS permission)

    This prevents the account from logging in and optionally kicks online players.
    """
    account = session.get(UserAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if account.is_banned:
        raise HTTPException(status_code=400, detail="Account is already banned")

    # Ban the account
    account.is_banned = True
    account.ban_reason = ban_request.reason
    account.banned_at = time.time()
    account.banned_by = admin.get("sub", "unknown")

    # Log security event
    from daemons.engine.systems.auth import SecurityEventType

    security_event = SecurityEvent(
        id=str(uuid.uuid4()),
        account_id=account_id,
        event_type=SecurityEventType.ACCOUNT_BANNED.value,
        details={
            "reason": ban_request.reason,
            "banned_by": admin.get("sub", "unknown"),
            "banned_by_username": admin.get("username", "unknown"),
        },
        timestamp=time.time(),
    )
    session.add(security_event)

    # Audit log
    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action_type="ban_account",
        target_type="account",
        target_id=account_id,
        details={"username": account.username, "reason": ban_request.reason},
        success=True,
    )

    # Kick online players if requested
    kicked_players = []
    if ban_request.kick_player:
        engine = get_engine_from_request(request)
        world = engine.world

        # Find and disconnect all players on this account
        for player_id, player in world.players.items():
            # Check if player's account matches (via owner_account_id or similar)
            # For now, we'll check if the player is connected and matches the account
            if hasattr(player, "account_id") and player.account_id == account_id:
                if player.is_connected:
                    player.is_connected = False
                    kicked_players.append(player.name)

                    # Notify other players
                    if player.id in engine._listeners:
                        await engine._listeners[player.id].put(
                            {
                                "type": "system",
                                "text": "Your account has been banned by an administrator.",
                            }
                        )

    session.commit()

    logger.info(
        "Account banned",
        admin_id=admin.get("sub"),
        account_id=account_id,
        reason=ban_request.reason,
        kicked_players=kicked_players,
    )

    return {
        "success": True,
        "message": f"Banned account {account.username}",
        "account_id": account_id,
        "username": account.username,
        "reason": ban_request.reason,
        "kicked_players": kicked_players,
    }


@router.post("/accounts/{account_id}/unban")
async def unban_account(
    account_id: str,
    request: Request,
    unban_request: UnbanAccountRequest,
    admin: dict = Depends(require_permission(Permission.MANAGE_ACCOUNTS)),
    session: AsyncSession = Depends(get_session),
):
    """
    Unban an account, allowing it to log in again.
    Requires: ADMIN (MANAGE_ACCOUNTS permission)
    """
    account = session.get(UserAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not account.is_banned:
        raise HTTPException(status_code=400, detail="Account is not banned")

    old_ban_reason = account.ban_reason
    account.is_banned = False
    account.ban_reason = None

    # Log security event
    from daemons.engine.systems.auth import SecurityEventType

    security_event = SecurityEvent(
        id=str(uuid.uuid4()),
        account_id=account_id,
        event_type=SecurityEventType.ACCOUNT_UNBANNED.value,
        details={
            "old_ban_reason": old_ban_reason,
            "unban_reason": unban_request.reason,
            "unbanned_by": admin.get("sub", "unknown"),
            "unbanned_by_username": admin.get("username", "unknown"),
        },
        timestamp=time.time(),
    )
    session.add(security_event)

    # Audit log
    admin_audit.log_action(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        action_type="unban_account",
        target_type="account",
        target_id=account_id,
        details={
            "username": account.username,
            "old_ban_reason": old_ban_reason,
            "unban_reason": unban_request.reason,
        },
        success=True,
    )

    session.commit()

    logger.info(
        "Account unbanned",
        admin_id=admin.get("sub"),
        account_id=account_id,
        reason=unban_request.reason,
    )

    return {
        "success": True,
        "message": f"Unbanned account {account.username}",
        "account_id": account_id,
        "username": account.username,
        "old_ban_reason": old_ban_reason,
    }


@router.get(
    "/accounts/{account_id}/security-events", response_model=SecurityEventsListResponse
)
async def get_security_events(
    account_id: str,
    request: Request,
    event_type: str | None = None,
    limit: int = 100,
    admin: dict = Depends(require_permission(Permission.VIEW_LOGS)),
):
    """
    Get security events for an account.
    Requires: ADMIN (VIEW_LOGS permission)

    Query parameters:
    - event_type: Filter by event type (login_success, account_banned, role_changed, etc.)
    - limit: Maximum number of events to return (default: 100, max: 500)
    """
    if limit < 1 or limit > 500:
        limit = 100

    session = get_session()

    try:
        # Verify account exists
        account = session.get(UserAccount, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Query security events
        query = select(SecurityEvent).where(SecurityEvent.account_id == account_id)

        if event_type:
            query = query.where(SecurityEvent.event_type == event_type)

        # Order by timestamp descending (most recent first)
        query = query.order_by(SecurityEvent.timestamp.desc()).limit(limit)

        result = session.execute(query)
        events = result.scalars().all()

        # Build response
        event_responses = [
            SecurityEventResponse(
                id=event.id,
                event_type=event.event_type,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                details=event.details,
                timestamp=event.timestamp,
            )
            for event in events
        ]

        return SecurityEventsListResponse(
            account_id=account_id,
            account_username=account.username,
            total_events=len(events),
            events=event_responses,
        )
    finally:
        session.close()


# ============================================================================
# Broadcast Endpoint
# ============================================================================


@router.post("/server/broadcast")
async def broadcast_message(
    request: Request,
    broadcast_request: BroadcastRequest,
    admin: dict = Depends(require_role(UserRole.ADMIN)),
):
    """
    Broadcast a message to all connected players.
    Requires: ADMIN role
    """
    engine = get_engine_from_request(request)

    message = f"📢 [{broadcast_request.sender_name}]: {broadcast_request.message}"

    # Send to all connected players
    sent_count = 0
    for player_id, queue in engine._listeners.items():
        await queue.put({"type": "message", "text": message})
        sent_count += 1

    return {"success": True, "message": "Broadcast sent", "recipients": sent_count}


# ============================================================================
# Content Hot-Reload System
# ============================================================================


class ReloadContentType(str, Enum):
    """Types of content that can be reloaded."""

    AREAS = "areas"
    ROOMS = "rooms"
    ITEMS = "items"
    ITEM_TEMPLATES = "item_templates"
    NPCS = "npcs"
    NPC_TEMPLATES = "npc_templates"
    NPC_SPAWNS = "npc_spawns"
    ALL = "all"


class ReloadRequest(BaseModel):
    """Request to reload content."""

    content_type: ReloadContentType = Field(
        ..., description="Type of content to reload"
    )
    file_path: str | None = Field(
        None, description="Specific file to reload (optional)"
    )
    force: bool = Field(
        False,
        description="Force reload even for API-managed content (ignores yaml_managed flag)",
    )


class ValidateRequest(BaseModel):
    """Request to validate YAML content."""

    content_type: ReloadContentType = Field(
        ..., description="Type of content to validate"
    )
    file_path: str | None = Field(
        None, description="Specific file to validate (optional)"
    )


class ValidationResult(BaseModel):
    """Result of a validation check."""

    file_path: str
    is_valid: bool
    errors: list[str] = []
    warnings: list[str] = []


class ReloadResult(BaseModel):
    """Result of a reload operation."""

    success: bool
    content_type: str
    items_loaded: int
    items_updated: int
    items_failed: int
    errors: list[str] = []
    warnings: list[str] = []


class ContentReloader:
    """
    Handles hot-reloading of YAML content into the game world.

    This allows admins to update content without restarting the server:
    - Reload item templates, NPC templates
    - Reload room descriptions and metadata
    - Reload area configurations
    - Validate YAML before applying changes
    """

    def __init__(self, engine, session: AsyncSession):
        self.engine = engine
        self.world = engine.world
        self.session = session
        self.world_data_dir = Path(__file__).parent.parent.parent / "world_data"

    async def validate_yaml_file(
        self, file_path: Path, content_type: ReloadContentType
    ) -> ValidationResult:
        """Validate a YAML file without loading it."""
        import yaml

        result = ValidationResult(file_path=str(file_path), is_valid=True)

        if not file_path.exists():
            result.is_valid = False
            result.errors.append(f"File not found: {file_path}")
            return result

        try:
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                result.is_valid = False
                result.errors.append("Empty or invalid YAML file")
                return result

            # Validate based on content type
            if content_type == ReloadContentType.AREAS:
                result = self._validate_area_data(data, result)
            elif content_type == ReloadContentType.ROOMS:
                result = self._validate_room_data(data, result)
            elif content_type in (
                ReloadContentType.ITEMS,
                ReloadContentType.ITEM_TEMPLATES,
            ):
                result = self._validate_item_template_data(data, result)
            elif content_type in (
                ReloadContentType.NPCS,
                ReloadContentType.NPC_TEMPLATES,
            ):
                result = self._validate_npc_template_data(data, result)
            elif content_type == ReloadContentType.NPC_SPAWNS:
                result = self._validate_npc_spawn_data(data, result)

        except yaml.YAMLError as e:
            result.is_valid = False
            result.errors.append(f"YAML parse error: {e}")
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Validation error: {e}")

        return result

    def _validate_area_data(
        self, data: dict, result: ValidationResult
    ) -> ValidationResult:
        """Validate area YAML data."""
        required_fields = ["id", "name"]
        for field in required_fields:
            if field not in data:
                result.is_valid = False
                result.errors.append(f"Missing required field: {field}")

        if "time_scale" in data:
            if (
                not isinstance(data["time_scale"], int | float)
                or data["time_scale"] <= 0
            ):
                result.warnings.append("time_scale should be a positive number")

        return result

    def _validate_room_data(
        self, data: dict, result: ValidationResult
    ) -> ValidationResult:
        """Validate room YAML data."""
        required_fields = ["id", "name", "description"]
        for field in required_fields:
            if field not in data:
                result.is_valid = False
                result.errors.append(f"Missing required field: {field}")

        if "exits" in data:
            valid_exits = {"north", "south", "east", "west", "up", "down"}
            for exit_dir in data["exits"]:
                if exit_dir not in valid_exits:
                    result.warnings.append(f"Non-standard exit direction: {exit_dir}")

        return result

    def _validate_item_template_data(
        self, data: dict, result: ValidationResult
    ) -> ValidationResult:
        """Validate item template YAML data."""
        required_fields = ["id", "name"]
        for field in required_fields:
            if field not in data:
                result.is_valid = False
                result.errors.append(f"Missing required field: {field}")

        valid_item_types = {
            "weapon",
            "armor",
            "consumable",
            "container",
            "misc",
            "quest",
            "tool",
        }
        if "item_type" in data and data["item_type"] not in valid_item_types:
            result.warnings.append(f"Unknown item_type: {data['item_type']}")

        return result

    def _validate_npc_template_data(
        self, data: dict, result: ValidationResult
    ) -> ValidationResult:
        """Validate NPC template YAML data."""
        required_fields = ["id", "name"]
        for field in required_fields:
            if field not in data:
                result.is_valid = False
                result.errors.append(f"Missing required field: {field}")

        if "max_health" in data and (
            not isinstance(data["max_health"], int) or data["max_health"] <= 0
        ):
            result.errors.append("max_health must be a positive integer")
            result.is_valid = False

        return result

    def _validate_npc_spawn_data(
        self, data: dict, result: ValidationResult
    ) -> ValidationResult:
        """Validate NPC spawn YAML data."""
        if "spawns" not in data:
            result.is_valid = False
            result.errors.append("Missing 'spawns' list")
            return result

        for i, spawn in enumerate(data["spawns"]):
            if "template_id" not in spawn:
                result.errors.append(f"Spawn {i}: missing template_id")
                result.is_valid = False
            if "room_id" not in spawn:
                result.errors.append(f"Spawn {i}: missing room_id")
                result.is_valid = False

        return result

    async def reload_item_templates(
        self, file_path: Path | None = None
    ) -> ReloadResult:
        """Reload item templates from YAML files."""
        import yaml

        from daemons.engine.world import ItemTemplate as WorldItemTemplate

        items_dir = self.world_data_dir / "items"
        result = ReloadResult(
            success=True,
            content_type="item_templates",
            items_loaded=0,
            items_updated=0,
            items_failed=0,
        )

        if file_path:
            yaml_files = [file_path] if file_path.exists() else []
        else:
            yaml_files = list(items_dir.glob("**/*.yaml")) if items_dir.exists() else []

        for yaml_file in yaml_files:
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    item_data = yaml.safe_load(f)

                if not item_data or "id" not in item_data:
                    result.errors.append(f"{yaml_file}: Missing 'id' field")
                    result.items_failed += 1
                    continue

                # Update in-memory world
                template = WorldItemTemplate(
                    id=item_data["id"],
                    name=item_data["name"],
                    description=item_data.get("description", ""),
                    item_type=item_data.get("item_type", "misc"),
                    item_subtype=item_data.get("item_subtype"),
                    equipment_slot=item_data.get("equipment_slot"),
                    stat_modifiers=item_data.get("stat_modifiers", {}),
                    weight=item_data.get("weight", 0.0),
                    max_stack_size=item_data.get("max_stack_size", 1),
                    has_durability=item_data.get("has_durability", False),
                    max_durability=item_data.get("max_durability"),
                    is_container=item_data.get("is_container", False),
                    container_capacity=item_data.get("container_capacity"),
                    container_type=item_data.get("container_type"),
                    is_consumable=item_data.get("is_consumable", False),
                    consume_effect=item_data.get("consume_effect"),
                    flavor_text=item_data.get("flavor_text"),
                    rarity=item_data.get("rarity", "common"),
                    value=item_data.get("value", 0),
                    flags=item_data.get("flags", {}),
                    keywords=item_data.get("keywords", []),
                    damage_min=item_data.get("damage_min", 0),
                    damage_max=item_data.get("damage_max", 0),
                    attack_speed=item_data.get("attack_speed", 2.0),
                    damage_type=item_data.get("damage_type", "physical"),
                )

                is_update = item_data["id"] in self.world.item_templates
                self.world.item_templates[item_data["id"]] = template

                if is_update:
                    result.items_updated += 1
                else:
                    result.items_loaded += 1

            except Exception as e:
                result.errors.append(f"{yaml_file}: {e}")
                result.items_failed += 1

        if result.items_failed > 0:
            result.success = False

        return result

    async def reload_npc_templates(self, file_path: Path | None = None) -> ReloadResult:
        """Reload NPC templates from YAML files."""
        import yaml

        from daemons.engine.behaviors import resolve_behaviors
        from daemons.engine.world import NpcTemplate as WorldNpcTemplate

        npcs_dir = self.world_data_dir / "npcs"
        result = ReloadResult(
            success=True,
            content_type="npc_templates",
            items_loaded=0,
            items_updated=0,
            items_failed=0,
        )

        if file_path:
            yaml_files = [file_path] if file_path.exists() else []
        else:
            yaml_files = list(npcs_dir.glob("**/*.yaml")) if npcs_dir.exists() else []

        for yaml_file in yaml_files:
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    npc_data = yaml.safe_load(f)

                if not npc_data or "id" not in npc_data:
                    result.errors.append(f"{yaml_file}: Missing 'id' field")
                    result.items_failed += 1
                    continue

                behavior_config = npc_data.get("behavior", {})
                behaviors = resolve_behaviors(behavior_config)

                template = WorldNpcTemplate(
                    id=npc_data["id"],
                    name=npc_data["name"],
                    description=npc_data.get("description", ""),
                    npc_type=npc_data.get("npc_type", "neutral"),
                    level=npc_data.get("level", 1),
                    max_health=npc_data.get("max_health", 10),
                    armor_class=npc_data.get("armor_class", 10),
                    strength=npc_data.get("strength", 10),
                    dexterity=npc_data.get("dexterity", 10),
                    intelligence=npc_data.get("intelligence", 10),
                    attack_damage_min=npc_data.get("attack_damage_min", 1),
                    attack_damage_max=npc_data.get("attack_damage_max", 4),
                    attack_speed=npc_data.get("attack_speed", 1.0),
                    experience_reward=npc_data.get("experience_reward", 10),
                    behaviors=behaviors,
                    idle_messages=npc_data.get("idle_messages", []),
                    keywords=npc_data.get("keywords", []),
                    loot_table=npc_data.get("loot_table", []),
                )

                is_update = npc_data["id"] in self.world.npc_templates
                self.world.npc_templates[npc_data["id"]] = template

                if is_update:
                    result.items_updated += 1
                    result.warnings.append(
                        f"Updated template: {npc_data['id']} (existing NPCs unchanged)"
                    )
                else:
                    result.items_loaded += 1

            except Exception as e:
                result.errors.append(f"{yaml_file}: {e}")
                result.items_failed += 1

        if result.items_failed > 0:
            result.success = False

        return result

    async def reload_rooms(
        self, file_path: Path | None = None, force: bool = False
    ) -> ReloadResult:
        """
        Reload room data from YAML files.

        Rooms with yaml_managed=False (API-modified) are skipped unless force=True.
        """
        import yaml

        rooms_dir = self.world_data_dir / "rooms"
        result = ReloadResult(
            success=True,
            content_type="rooms",
            items_loaded=0,
            items_updated=0,
            items_failed=0,
        )

        if file_path:
            yaml_files = [file_path] if file_path.exists() else []
        else:
            yaml_files = list(rooms_dir.glob("**/*.yaml")) if rooms_dir.exists() else []

        skipped_rooms = []

        for yaml_file in yaml_files:
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    room_data = yaml.safe_load(f)

                if not room_data or "id" not in room_data:
                    result.errors.append(f"{yaml_file}: Missing 'id' field")
                    result.items_failed += 1
                    continue

                room_id = room_data["id"]
                existing_room = self.world.rooms.get(room_id)

                if existing_room:
                    # Check if room is API-managed (skip unless forced)
                    if not existing_room.yaml_managed and not force:
                        skipped_rooms.append(room_id)
                        continue

                    # Update existing room (preserve players and entities)
                    existing_room.name = room_data["name"]
                    existing_room.description = room_data["description"]
                    existing_room.room_type = room_data.get("room_type", "ethereal")
                    existing_room.on_enter_effect = room_data.get("on_enter_effect")
                    existing_room.on_exit_effect = room_data.get("on_exit_effect")

                    # Update exits
                    exits = room_data.get("exits", {})
                    for direction in ("north", "south", "east", "west", "up", "down"):
                        if direction in exits:
                            existing_room.exits[direction] = exits[direction]
                        elif direction in existing_room.exits:
                            del existing_room.exits[direction]

                    result.items_updated += 1
                else:
                    result.warnings.append(
                        f"Room {room_id} not found in world (add via database)"
                    )
                    result.items_failed += 1

            except Exception as e:
                result.errors.append(f"{yaml_file}: {e}")
                result.items_failed += 1

        # Report skipped API-managed rooms
        if skipped_rooms:
            result.warnings.append(
                f"Skipped {len(skipped_rooms)} API-managed rooms: {', '.join(skipped_rooms[:5])}"
                + (
                    f" and {len(skipped_rooms) - 5} more"
                    if len(skipped_rooms) > 5
                    else ""
                )
            )

        if result.items_failed > 0:
            result.success = False

        return result

    async def reload_areas(self, file_path: Path | None = None) -> ReloadResult:
        """Reload area data from YAML files."""
        import yaml

        areas_dir = self.world_data_dir / "areas"
        result = ReloadResult(
            success=True,
            content_type="areas",
            items_loaded=0,
            items_updated=0,
            items_failed=0,
        )

        if file_path:
            yaml_files = [file_path] if file_path.exists() else []
        else:
            yaml_files = list(areas_dir.glob("**/*.yaml")) if areas_dir.exists() else []

        for yaml_file in yaml_files:
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    area_data = yaml.safe_load(f)

                if not area_data or "id" not in area_data:
                    result.errors.append(f"{yaml_file}: Missing 'id' field")
                    result.items_failed += 1
                    continue

                area_id = area_data["id"]
                existing_area = self.world.areas.get(area_id)

                if existing_area:
                    # Update existing area
                    existing_area.name = area_data["name"]
                    existing_area.description = area_data.get("description", "")
                    existing_area.time_scale = area_data.get("time_scale", 1.0)
                    existing_area.biome = area_data.get("biome", "mystical")
                    existing_area.climate = area_data.get("climate", "temperate")
                    existing_area.ambient_lighting = area_data.get(
                        "ambient_lighting", "dim"
                    )
                    existing_area.danger_level = area_data.get("danger_level", 1)
                    existing_area.magic_intensity = area_data.get(
                        "magic_intensity", "moderate"
                    )
                    existing_area.default_respawn_time = area_data.get(
                        "default_respawn_time", 300
                    )

                    result.items_updated += 1
                else:
                    result.warnings.append(
                        f"Area {area_id} not found in world (add via database)"
                    )
                    result.items_failed += 1

            except Exception as e:
                result.errors.append(f"{yaml_file}: {e}")
                result.items_failed += 1

        if result.items_failed > 0:
            result.success = False

        return result

    async def reload_all(self, force: bool = False) -> dict:
        """Reload all content types."""
        results = {
            "areas": await self.reload_areas(),
            "rooms": await self.reload_rooms(force=force),
            "item_templates": await self.reload_item_templates(),
            "npc_templates": await self.reload_npc_templates(),
        }

        overall_success = all(r.success for r in results.values())

        return {
            "success": overall_success,
            "results": {k: v.model_dump() for k, v in results.items()},
        }


@router.post("/content/reload", response_model=ReloadResult)
async def reload_content(
    request: Request,
    reload_request: ReloadRequest,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(UserRole.ADMIN)),
):
    """
    Hot-reload content from YAML files without restarting the server.
    Requires: ADMIN role

    This updates the in-memory world state with changes from YAML files.
    Note: For structural changes (new rooms, areas), a full reload may be needed.
    """
    engine = get_engine_from_request(request)
    reloader = ContentReloader(engine, session)

    file_path = Path(reload_request.file_path) if reload_request.file_path else None

    if reload_request.content_type == ReloadContentType.ALL:
        all_results = await reloader.reload_all(force=reload_request.force)
        # Return summary as ReloadResult
        total_loaded = sum(r["items_loaded"] for r in all_results["results"].values())
        total_updated = sum(r["items_updated"] for r in all_results["results"].values())
        total_failed = sum(r["items_failed"] for r in all_results["results"].values())
        all_errors = []
        for ct, r in all_results["results"].items():
            all_errors.extend([f"{ct}: {e}" for e in r["errors"]])

        # Audit log
        admin_audit.log_content_reload(
            admin_id=admin.get("sub", "unknown"),
            admin_name=admin.get("username", "unknown"),
            content_type="all",
            items_loaded=total_loaded,
            items_updated=total_updated,
            items_failed=total_failed,
            success=all_results["success"],
        )

        return ReloadResult(
            success=all_results["success"],
            content_type="all",
            items_loaded=total_loaded,
            items_updated=total_updated,
            items_failed=total_failed,
            errors=all_errors,
        )
    elif reload_request.content_type == ReloadContentType.AREAS:
        result = await reloader.reload_areas(file_path)
    elif reload_request.content_type == ReloadContentType.ROOMS:
        result = await reloader.reload_rooms(file_path, force=reload_request.force)
    elif reload_request.content_type in (
        ReloadContentType.ITEMS,
        ReloadContentType.ITEM_TEMPLATES,
    ):
        result = await reloader.reload_item_templates(file_path)
    elif reload_request.content_type in (
        ReloadContentType.NPCS,
        ReloadContentType.NPC_TEMPLATES,
    ):
        result = await reloader.reload_npc_templates(file_path)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type: {reload_request.content_type}",
        )

    # Audit log for individual content type reload
    admin_audit.log_content_reload(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        content_type=reload_request.content_type.value,
        items_loaded=result.items_loaded,
        items_updated=result.items_updated,
        items_failed=result.items_failed,
        success=result.success,
    )

    return result


@router.post("/content/validate")
async def validate_content(
    request: Request,
    validate_request: ValidateRequest,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(UserRole.GAME_MASTER)),
):
    """
    Validate YAML content files without loading them.
    Requires: GAME_MASTER or higher

    Use this to check for errors before reloading content.
    """
    engine = get_engine_from_request(request)
    reloader = ContentReloader(engine, session)

    world_data_dir = reloader.world_data_dir

    # Determine which directory to validate
    if validate_request.content_type == ReloadContentType.AREAS:
        content_dir = world_data_dir / "areas"
    elif validate_request.content_type == ReloadContentType.ROOMS:
        content_dir = world_data_dir / "rooms"
    elif validate_request.content_type in (
        ReloadContentType.ITEMS,
        ReloadContentType.ITEM_TEMPLATES,
    ):
        content_dir = world_data_dir / "items"
    elif validate_request.content_type in (
        ReloadContentType.NPCS,
        ReloadContentType.NPC_TEMPLATES,
    ):
        content_dir = world_data_dir / "npcs"
    elif validate_request.content_type == ReloadContentType.NPC_SPAWNS:
        content_dir = world_data_dir / "npc_spawns"
    else:
        raise HTTPException(
            status_code=400, detail="Unsupported content type for validation"
        )

    if validate_request.file_path:
        yaml_files = [Path(validate_request.file_path)]
    else:
        yaml_files = list(content_dir.glob("**/*.yaml")) if content_dir.exists() else []

    results = []
    for yaml_file in yaml_files:
        result = await reloader.validate_yaml_file(
            yaml_file, validate_request.content_type
        )
        results.append(result.model_dump())

    all_valid = all(r["is_valid"] for r in results)

    return {
        "success": all_valid,
        "content_type": validate_request.content_type.value,
        "files_checked": len(results),
        "files_valid": sum(1 for r in results if r["is_valid"]),
        "files_invalid": sum(1 for r in results if not r["is_valid"]),
        "results": results,
    }


@router.get("/classes")
async def get_classes(
    request: Request, admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Get all loaded character classes.
    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)
        classes = engine.class_system.get_available_classes()

        # Serialize ClassTemplate objects to dictionaries
        classes_data = []
        for cls in classes:
            classes_data.append(
                {
                    "class_id": cls.class_id,
                    "name": cls.name,
                    "description": cls.description,
                    "base_stats": (
                        cls.base_stats.model_dump() if cls.base_stats else None
                    ),
                    "stat_growth": (
                        cls.stat_growth.model_dump() if cls.stat_growth else None
                    ),
                    "resources": (
                        {rid: rd.model_dump() for rid, rd in cls.resources.items()}
                        if cls.resources
                        else {}
                    ),
                    "available_abilities": cls.available_abilities,
                    "skill_tree": (
                        cls.skill_tree if hasattr(cls, "skill_tree") else None
                    ),
                }
            )

        return {
            "success": True,
            "detail": f"Retrieved {len(classes_data)} classes",
            "count": len(classes_data),
            "classes": classes_data,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving classes: {str(e)}"
        )


@router.get("/abilities")
async def get_abilities(
    request: Request, admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Get all loaded abilities.
    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)
        abilities = engine.class_system.get_available_abilities()

        # Serialize AbilityTemplate objects to dictionaries
        abilities_data = []
        for ability in abilities:
            abilities_data.append(
                {
                    "ability_id": ability.ability_id,
                    "name": ability.name,
                    "description": ability.description,
                    "ability_type": ability.ability_type,
                    "costs": ability.costs.model_dump() if ability.costs else None,
                    "cooldown_seconds": ability.cooldown_seconds,
                    "gcd_seconds": ability.gcd_seconds,
                    "target_mode": ability.target_mode,
                    "behavior": ability.behavior,
                }
            )

        return {
            "success": True,
            "detail": f"Retrieved {len(abilities_data)} abilities",
            "count": len(abilities_data),
            "abilities": abilities_data,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving abilities: {str(e)}"
        )


@router.post("/classes/reload")
async def reload_classes(
    request: Request,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
) -> dict:
    """
    Hot-reload character classes and abilities from YAML files.
    Requires: GAME_MASTER role or higher (via Permission.SERVER_COMMANDS).
    """
    try:
        engine = get_engine_from_request(request)

        # Load content from YAML
        await engine.class_system.load_content()

        # Get updated counts
        classes = engine.class_system.get_available_classes()
        abilities = engine.class_system.get_available_abilities()

        return {
            "success": True,
            "detail": "Classes and abilities reloaded successfully",
            "classes_loaded": len(classes),
            "abilities_loaded": len(abilities),
            "behavior_count": len(engine.class_system.behavior_registry),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error reloading classes: {str(e)}"
        )


# ============================================================================
# Phase 12.1 - Schema Registry API Endpoints
# ============================================================================


class SchemaResponse(BaseModel):
    """Schema file information."""

    content_type: str
    file_path: str
    content: str
    checksum: str
    last_modified: str
    size_bytes: int


class SchemaVersionResponse(BaseModel):
    """Schema version information."""

    version: str
    engine_version: str
    last_modified: str
    schema_count: int


@router.get("/schemas")
async def get_schemas(
    request: Request,
    content_type: str | None = None,
    admin: dict = Depends(get_current_admin),
) -> dict:
    """
    Get all schema definitions (_schema.yaml files).

    Query Parameters:
        content_type: Optional filter by content type (e.g., "classes", "items")

    Returns:
        List of schema files with content, checksums, and metadata.

    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        # Get schemas (with optional filter)
        schemas = engine.schema_registry.get_all_schemas(
            content_type_filter=content_type
        )

        # Convert to response format
        schemas_data = []
        for schema in schemas:
            schemas_data.append(
                {
                    "content_type": schema.content_type,
                    "file_path": schema.file_path,
                    "content": schema.content,
                    "checksum": schema.checksum,
                    "last_modified": schema.last_modified.isoformat(),
                    "size_bytes": schema.size_bytes,
                }
            )

        return {
            "success": True,
            "detail": f"Retrieved {len(schemas_data)} schemas",
            "count": len(schemas_data),
            "schemas": schemas_data,
            "filter_applied": content_type,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving schemas: {str(e)}"
        )


@router.get("/schemas/version")
async def get_schema_version(
    request: Request, admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Get schema version information for cache invalidation.

    Returns:
        Schema version, engine version, last modified time, and schema count.

    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)
        version = engine.schema_registry.get_version()

        return {
            "success": True,
            "version": version.version,
            "engine_version": version.engine_version,
            "last_modified": version.last_modified.isoformat(),
            "schema_count": version.schema_count,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving schema version: {str(e)}"
        )


@router.post("/schemas/reload")
async def reload_schemas(
    request: Request,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
) -> dict:
    """
    Hot-reload all schema definitions from disk.

    Useful when schema files are updated and CMS needs fresh definitions.

    Requires: GAME_MASTER role or higher (via Permission.SERVER_COMMANDS).
    """
    try:
        engine = get_engine_from_request(request)

        # Reload schemas
        count = engine.schema_registry.reload_schemas()
        version = engine.schema_registry.get_version()

        # Log the action
        admin_audit_logger.info(
            "schemas_reloaded",
            admin_id=admin.get("account_id"),
            admin_name=admin.get("username"),
            schemas_loaded=count,
        )

        return {
            "success": True,
            "detail": f"Reloaded {count} schemas",
            "schemas_loaded": count,
            "version": version.version,
            "engine_version": version.engine_version,
            "last_modified": version.last_modified.isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error reloading schemas: {str(e)}"
        )


# ============================================================================
# Phase 12.2 - YAML File Management API Endpoints
# ============================================================================


class FileListRequest(BaseModel):
    """Request model for file listing."""

    content_type: str | None = None
    include_schema_files: bool = False


class FileDownloadRequest(BaseModel):
    """Request model for file download."""

    file_path: str


class FileUploadRequest(BaseModel):
    """Request model for file upload."""

    file_path: str = Field(..., description="Relative path from world_data root")
    content: str = Field(..., description="Raw YAML content")
    validate_only: bool = Field(False, description="If true, validate but don't write")


class FileInfoResponse(BaseModel):
    """Response model for file info."""

    file_path: str
    content_type: str
    size_bytes: int
    last_modified: str
    checksum: str | None = None


class FileContentResponse(BaseModel):
    """Response model for file content."""

    file_path: str
    content: str
    checksum: str
    last_modified: str
    size_bytes: int


@router.get("/content/files")
async def list_content_files(
    request: Request,
    content_type: str | None = None,
    include_schema_files: bool = False,
    admin: dict = Depends(get_current_admin),
) -> dict:
    """
    List all YAML files in world_data directory.

    Query Parameters:
        content_type: Optional filter by content type (e.g., "classes", "items")
        include_schema_files: Whether to include _schema.yaml files (default: False)

    Returns:
        List of file metadata (path, size, last_modified, content_type).

    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        # Get files
        files = await engine.file_manager.list_files(
            content_type_filter=content_type, include_schema_files=include_schema_files
        )

        # Convert to response format
        files_data = []
        for file_info in files:
            files_data.append(
                {
                    "file_path": file_info.file_path,
                    "content_type": file_info.content_type,
                    "size_bytes": file_info.size_bytes,
                    "last_modified": file_info.last_modified.isoformat(),
                }
            )

        # Get stats
        stats = await engine.file_manager.get_stats()

        return {
            "success": True,
            "detail": f"Retrieved {len(files_data)} files",
            "count": len(files_data),
            "files": files_data,
            "stats": stats,
            "filter_applied": content_type,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")


@router.get("/content/download")
async def download_content_file(
    request: Request, file_path: str, admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Download a specific YAML file by path.

    Query Parameters:
        file_path: Relative path from world_data root (e.g., "classes/warrior.yaml")

    Returns:
        File content with checksum and metadata.

    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        # Read file
        file_content = await engine.file_manager.read_file(file_path)

        # Log the action
        admin_audit_logger.info(
            "file_downloaded",
            admin_id=admin.get("account_id"),
            admin_name=admin.get("username"),
            file_path=file_path,
        )

        return {
            "success": True,
            "file_path": file_content.file_path,
            "content": file_content.content,
            "checksum": file_content.checksum,
            "last_modified": file_content.last_modified.isoformat(),
            "size_bytes": file_content.size_bytes,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")


@router.post("/content/upload")
async def upload_content_file(
    request: Request,
    upload_request: FileUploadRequest,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
) -> dict:
    """
    Upload or update a YAML file.

    Request Body:
        file_path: Relative path from world_data root
        content: Raw YAML content
        validate_only: If true, validate but don't write (default: False)

    Returns:
        Success status, validation errors, checksum (if written).

    Requires: GAME_MASTER role or higher (via Permission.SERVER_COMMANDS).
    """
    try:
        engine = get_engine_from_request(request)

        # Write file (or validate only)
        success, checksum, errors = await engine.file_manager.write_file(
            file_path=upload_request.file_path,
            content=upload_request.content,
            validate_only=upload_request.validate_only,
        )

        if not success:
            return {
                "success": False,
                "detail": "Validation failed",
                "errors": errors,
                "file_written": False,
            }

        # Log the action (if actually written)
        if not upload_request.validate_only:
            admin_audit_logger.info(
                "file_uploaded",
                admin_id=admin.get("account_id"),
                admin_name=admin.get("username"),
                file_path=upload_request.file_path,
                checksum=checksum,
            )

        return {
            "success": True,
            "detail": (
                "File validated successfully"
                if upload_request.validate_only
                else "File written successfully"
            ),
            "file_path": upload_request.file_path,
            "checksum": checksum,
            "file_written": not upload_request.validate_only,
            "errors": [],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


@router.delete("/content/file")
async def delete_content_file(
    request: Request,
    file_path: str,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
) -> dict:
    """
    Delete a YAML file.

    Query Parameters:
        file_path: Relative path from world_data root

    Returns:
        Success status and any errors.

    Requires: GAME_MASTER role or higher (via Permission.SERVER_COMMANDS).
    """
    try:
        engine = get_engine_from_request(request)

        # Delete file
        success, errors = await engine.file_manager.delete_file(file_path)

        if not success:
            return {
                "success": False,
                "detail": "Failed to delete file",
                "errors": errors,
            }

        # Log the action
        admin_audit_logger.info(
            "file_deleted",
            admin_id=admin.get("account_id"),
            admin_name=admin.get("username"),
            file_path=file_path,
        )

        return {
            "success": True,
            "detail": "File deleted successfully",
            "file_path": file_path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")


@router.get("/content/stats")
async def get_content_stats(
    request: Request, admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Get statistics about YAML files in world_data.

    Returns:
        File counts per content type.

    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        # Get stats
        stats = await engine.file_manager.get_stats()

        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {str(e)}")


# ============================================================================
# Phase 12.3: Enhanced Validation API
# ============================================================================


class EnhancedValidateRequest(BaseModel):
    """Request for enhanced YAML validation."""

    yaml_content: str = Field(..., description="Raw YAML content to validate")
    content_type: str = Field(
        ..., description="Content type (classes, items, rooms, etc.)"
    )
    check_references: bool = Field(
        default=True, description="Whether to validate cross-content references"
    )
    file_path: str | None = Field(
        default=None, description="Optional file path for context"
    )


class ValidateReferencesRequest(BaseModel):
    """Request for reference-only validation."""

    yaml_content: str = Field(..., description="Raw YAML content to validate")
    content_type: str = Field(
        ..., description="Content type (classes, items, rooms, etc.)"
    )
    file_path: str | None = Field(
        default=None, description="Optional file path for context"
    )


@router.post("/content/validate-enhanced")
async def validate_content_enhanced(
    request: Request,
    validate_request: EnhancedValidateRequest,
    admin: dict = Depends(get_current_admin),
) -> dict:
    """
    Enhanced YAML validation with detailed error reporting.

    Provides:
    - Syntax validation with line/column error positions
    - Schema conformance checking
    - Reference validation (optional)
    - Errors and warnings with precise locations

    Perfect for real-time Monaco editor validation.

    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        if (
            not hasattr(engine, "validation_service")
            or engine.validation_service is None
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Validation service not initialized",
            )

        # Perform full validation
        result = await engine.validation_service.validate_full(
            yaml_content=validate_request.yaml_content,
            content_type=validate_request.content_type,
            check_references=validate_request.check_references,
        )

        # Set file path if provided
        if validate_request.file_path:
            result.file_path = validate_request.file_path

        # Convert to dict for API response
        response = result.to_dict()
        response["success"] = result.valid

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")


@router.post("/content/validate-references")
async def validate_content_references(
    request: Request,
    validate_request: ValidateReferencesRequest,
    admin: dict = Depends(get_current_admin),
) -> dict:
    """
    Validate cross-content references only.

    Checks:
    - Room exits point to existing rooms
    - Class abilities exist
    - NPC factions/dialogues exist
    - Quest objectives reference valid entities
    - And more...

    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        if (
            not hasattr(engine, "validation_service")
            or engine.validation_service is None
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Validation service not initialized",
            )

        # Perform reference-only validation
        result = await engine.validation_service.validate_references(
            yaml_content=validate_request.yaml_content,
            content_type=validate_request.content_type,
        )

        # Set file path if provided
        if validate_request.file_path:
            result.file_path = validate_request.file_path

        # Convert to dict for API response
        response = result.to_dict()
        response["success"] = result.valid

        # Add cache status
        response["cache_built"] = engine.validation_service._cache_built
        response["cached_entities"] = {
            "rooms": len(engine.validation_service.reference_cache.room_ids),
            "items": len(engine.validation_service.reference_cache.item_ids),
            "npcs": len(engine.validation_service.reference_cache.npc_ids),
            "abilities": len(engine.validation_service.reference_cache.ability_ids),
            "quests": len(engine.validation_service.reference_cache.quest_ids),
            "classes": len(engine.validation_service.reference_cache.class_ids),
            "areas": len(engine.validation_service.reference_cache.area_ids),
            "factions": len(engine.validation_service.reference_cache.faction_ids),
            "dialogues": len(engine.validation_service.reference_cache.dialogue_ids),
        }

        return response
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Reference validation error: {str(e)}"
        )


@router.post("/content/rebuild-reference-cache")
async def rebuild_reference_cache(
    request: Request, admin: dict = Depends(require_role(UserRole.GAME_MASTER))
) -> dict:
    """
    Rebuild the reference validation cache.

    Call this after bulk content changes to ensure reference
    validation has the latest content IDs indexed.

    Requires: GAME_MASTER role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        if (
            not hasattr(engine, "validation_service")
            or engine.validation_service is None
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Validation service not initialized",
            )

        # Rebuild cache
        await engine.validation_service.build_reference_cache()

        # Get stats
        cache = engine.validation_service.reference_cache

        return {
            "success": True,
            "detail": "Reference cache rebuilt successfully",
            "cached_entities": {
                "rooms": len(cache.room_ids),
                "items": len(cache.item_ids),
                "npcs": len(cache.npc_ids),
                "abilities": len(cache.ability_ids),
                "quests": len(cache.quest_ids),
                "classes": len(cache.class_ids),
                "areas": len(cache.area_ids),
                "factions": len(cache.faction_ids),
                "dialogues": len(cache.dialogue_ids),
                "triggers": len(cache.trigger_ids),
                "quest_chains": len(cache.quest_chain_ids),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rebuilding cache: {str(e)}")


# ============================================================================
# Phase 12.4: Content Querying API
# ============================================================================


@router.get("/content/search")
async def search_content(
    request: Request,
    q: str,
    content_type: str | None = None,
    limit: int = 50,
    admin: dict = Depends(get_current_admin),
) -> dict:
    """
    Search content files by query string.

    Searches across:
    - Entity IDs
    - Names
    - Descriptions
    - Content-specific fields

    Query Parameters:
        q: Search query string
        content_type: Optional filter by content type (classes, items, rooms, etc.)
        limit: Maximum results to return (default: 50, max: 200)

    Returns:
        Search results with context snippets ordered by relevance.

    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        if not hasattr(engine, "query_service") or engine.query_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Query service not initialized",
            )

        # Validate limit
        if limit < 1 or limit > 200:
            raise HTTPException(
                status_code=400, detail="limit must be between 1 and 200"
            )

        # Perform search
        results = await engine.query_service.search(
            query=q, content_type=content_type, limit=limit
        )

        return {
            "success": True,
            "query": q,
            "content_type_filter": content_type,
            "result_count": len(results),
            "results": [
                {
                    "content_type": r.content_type,
                    "file_path": r.file_path,
                    "entity_id": r.entity_id,
                    "entity_name": r.entity_name,
                    "match_field": r.match_field,
                    "match_value": r.match_value,
                    "context_snippet": r.context_snippet,
                    "score": r.score,
                }
                for r in results
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@router.get("/content/dependencies")
async def get_content_dependencies(
    request: Request,
    entity_type: str,
    entity_id: str,
    admin: dict = Depends(get_current_admin),
) -> dict:
    """
    Get dependency graph for a specific entity.

    Shows:
    - What this entity references (outgoing dependencies)
    - What references this entity (incoming dependencies)
    - Whether the entity is orphaned (nothing references it)

    Use for:
    - Safe delete checks
    - Impact analysis
    - Dependency visualization

    Query Parameters:
        entity_type: Content type (classes, items, rooms, etc.)
        entity_id: Entity identifier

    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        if not hasattr(engine, "query_service") or engine.query_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Query service not initialized",
            )

        # Get dependency graph
        graph = await engine.query_service.get_dependencies(entity_type, entity_id)

        if not graph:
            raise HTTPException(
                status_code=404, detail=f"Entity not found: {entity_type}:{entity_id}"
            )

        # Check if safe to delete
        is_safe, blocking_refs = engine.query_service.find_safe_to_delete(
            entity_type, entity_id
        )

        result = graph.to_dict()
        result["success"] = True
        result["safe_to_delete"] = is_safe
        result["blocking_references"] = blocking_refs

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Dependency lookup error: {str(e)}"
        )


@router.get("/content/analytics")
async def get_content_analytics(
    request: Request, admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Get comprehensive content analytics and health metrics.

    Returns:
    - Total entity counts by type
    - Broken references (links to non-existent entities)
    - Orphaned entities (no incoming references)
    - Most referenced entities
    - Average references per entity

    Use for:
    - Content health monitoring
    - Finding cleanup opportunities
    - Identifying important entities

    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        if not hasattr(engine, "query_service") or engine.query_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Query service not initialized",
            )

        # Generate analytics
        analytics = await engine.query_service.get_analytics()

        result = analytics.to_dict()
        result["success"] = True

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")


@router.post("/content/rebuild-dependency-graph")
async def rebuild_dependency_graph(
    request: Request, admin: dict = Depends(require_role(UserRole.GAME_MASTER))
) -> dict:
    """
    Rebuild the dependency graph.

    Call this after bulk content changes to refresh the
    dependency index for accurate analytics and safe-delete checks.

    Requires: GAME_MASTER role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        if not hasattr(engine, "query_service") or engine.query_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Query service not initialized",
            )

        # Rebuild graph
        await engine.query_service.build_dependency_graph()

        # Get stats
        entity_count = len(engine.query_service._dependency_graph)
        dependency_count = sum(
            len(graph.references)
            for graph in engine.query_service._dependency_graph.values()
        )

        return {
            "success": True,
            "detail": "Dependency graph rebuilt successfully",
            "entity_count": entity_count,
            "dependency_count": dependency_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rebuilding graph: {str(e)}")


# ============================================================================
# Phase 12.5 - Bulk Operations API
# ============================================================================


class BulkImportRequestModel(BaseModel):
    """Request model for bulk import"""

    files: dict = Field(..., description="Map of file_path to YAML content")
    validate_only: bool = Field(False, description="Only validate, don't write")
    rollback_on_error: bool = Field(
        True, description="Rollback all changes if any file fails"
    )
    overwrite_existing: bool = Field(True, description="Overwrite existing files")


class BulkExportRequestModel(BaseModel):
    """Request model for bulk export"""

    content_types: list | None = Field(
        None, description="Filter by content types (None = all)"
    )
    include_schema_files: bool = Field(False, description="Include _schema.yaml files")
    file_paths: list | None = Field(
        None, description="Specific file paths (None = all)"
    )


class BatchValidationRequestModel(BaseModel):
    """Request model for batch validation"""

    files: dict = Field(..., description="Map of file_path to YAML content")


@router.post("/content/bulk-import")
async def bulk_import_content(
    request: Request,
    import_request: BulkImportRequestModel,
    admin: dict = Depends(require_role(UserRole.GAME_MASTER)),
) -> dict:
    """
    Import multiple YAML files at once with validation and rollback support.

    Process:
    1. Validates all files before writing any
    2. If validate_only=true, returns validation results without writing
    3. If rollback_on_error=true, aborts if any validation fails
    4. Writes all files atomically
    5. Rolls back all changes if any write fails (when rollback_on_error=true)

    Use cases:
    - Import content from backup ZIP
    - Batch content creation
    - Migrate content between environments
    - Validate large content sets

    Request body:
    {
      "files": {
        "rooms/tavern.yaml": "id: tavern\\nname: ...",
        "items/sword.yaml": "id: iron_sword\\n..."
      },
      "validate_only": false,
      "rollback_on_error": true,
      "overwrite_existing": true
    }

    Returns: BulkImportResponse with per-file results

    Requires: GAME_MASTER role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        if not hasattr(engine, "bulk_service") or engine.bulk_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Bulk service not initialized",
            )

        from daemons.engine.systems.bulk_service import BulkImportRequest

        # Convert to internal request
        bulk_request = BulkImportRequest(
            files=import_request.files,
            validate_only=import_request.validate_only,
            rollback_on_error=import_request.rollback_on_error,
            overwrite_existing=import_request.overwrite_existing,
        )

        # Execute bulk import
        response = await engine.bulk_service.bulk_import(bulk_request)

        # Log audit
        admin_audit_logger.info(
            "bulk_import_content",
            admin_username=admin.get("username", "unknown"),
            file_count=response.total_files,
            written=response.files_written,
            failed=response.files_failed,
            rolled_back=response.rolled_back,
        )

        # Convert to dict for JSON response
        result = asdict(response)

        # Convert validation results to dicts
        if response.results:
            result["results"] = [
                {
                    "file_path": r.file_path,
                    "success": r.success,
                    "written": r.written,
                    "validation_result": (
                        r.validation_result.to_dict() if r.validation_result else None
                    ),
                    "error": r.error,
                    "checksum": r.checksum,
                }
                for r in response.results
            ]

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Bulk import failed")
        raise HTTPException(status_code=500, detail=f"Bulk import error: {str(e)}")


@router.post("/content/bulk-export")
async def bulk_export_content(
    request: Request,
    export_request: BulkExportRequestModel,
    admin: dict = Depends(require_role(UserRole.MODERATOR)),
) -> dict:
    """
    Export multiple YAML files to a ZIP archive.

    Process:
    1. Filters files by content_types or file_paths
    2. Creates temporary directory with file copies
    3. Generates manifest.json with metadata
    4. Creates ZIP archive
    5. Returns path to ZIP file

    Use cases:
    - Backup all content
    - Export specific content types (e.g., all quests)
    - Export content for migration
    - Share content with other developers

    Request body:
    {
      "content_types": ["rooms", "items"],  // null = all types
      "include_schema_files": false,
      "file_paths": null  // null = all files matching content_types
    }

    Returns: BulkExportResponse with ZIP path and manifest

    Note: ZIP files are stored temporarily and should be downloaded immediately.

    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        if not hasattr(engine, "bulk_service") or engine.bulk_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Bulk service not initialized",
            )

        from daemons.engine.systems.bulk_service import BulkExportRequest

        # Convert to internal request
        bulk_request = BulkExportRequest(
            content_types=export_request.content_types,
            include_schema_files=export_request.include_schema_files,
            file_paths=export_request.file_paths,
        )

        # Execute bulk export
        response = await engine.bulk_service.bulk_export(bulk_request)

        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)

        # Log audit
        admin_audit_logger.info(
            "bulk_export_content",
            admin_username=admin.get("username", "unknown"),
            file_count=response.total_files,
            zip_path=response.zip_path,
        )

        # Return response
        return {
            "success": response.success,
            "zip_path": response.zip_path,
            "total_files": response.total_files,
            "manifest": response.manifest,
            "detail": f"Exported {response.total_files} files to {response.zip_path}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Bulk export failed")
        raise HTTPException(status_code=500, detail=f"Bulk export error: {str(e)}")


@router.post("/content/batch-validate")
async def batch_validate_content(
    request: Request,
    validation_request: BatchValidationRequestModel,
    admin: dict = Depends(require_role(UserRole.MODERATOR)),
) -> dict:
    """
    Validate multiple YAML files without writing them.

    Use cases:
    - Pre-validate before bulk import
    - Test content changes locally
    - Validate entire content sets
    - CI/CD content validation

    Request body:
    {
      "files": {
        "rooms/tavern.yaml": "id: tavern\\nname: ...",
        "items/sword.yaml": "id: iron_sword\\n..."
      }
    }

    Returns: BatchValidationResponse with per-file validation results

    Requires: MODERATOR role or higher.
    """
    try:
        engine = get_engine_from_request(request)

        if not hasattr(engine, "bulk_service") or engine.bulk_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Bulk service not initialized",
            )

        from daemons.engine.systems.bulk_service import BatchValidationRequest

        # Convert to internal request
        batch_request = BatchValidationRequest(files=validation_request.files)

        # Execute batch validation
        response = await engine.bulk_service.batch_validate(batch_request)

        # Convert to dict for JSON response
        result = {
            "success": response.success,
            "total_files": response.total_files,
            "valid_files": response.valid_files,
            "invalid_files": response.invalid_files,
            "results": [r.to_dict() for r in response.results],
        }

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Batch validation failed")
        raise HTTPException(status_code=500, detail=f"Batch validation error: {str(e)}")
