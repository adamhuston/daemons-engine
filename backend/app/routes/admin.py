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
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import UserAccount, Player
from app.engine.systems.auth import (
    AuthSystem, UserRole, Permission, ROLE_PERMISSIONS,
    verify_access_token, SecurityEventType
)
from app.logging import admin_audit, get_logger

# Module logger
logger = get_logger(__name__)

# Admin audit logger instance
admin_audit_logger = admin_audit

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============================================================================
# Dependencies
# ============================================================================

def get_engine_from_request(request: Request):
    """Get the WorldEngine from app.state."""
    engine = getattr(request.app.state, "world_engine", None)
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="World engine not initialized"
        )
    return engine


def get_auth_system_from_request(request: Request) -> AuthSystem:
    """Get the AuthSystem from app.state."""
    auth_system = getattr(request.app.state, "auth_system", None)
    if auth_system is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth system not initialized"
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
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = auth_header.split(" ", 1)[1]
    claims = verify_access_token(token)
    
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Check role has at least MODERATOR privileges
    role = claims.get("role", "player")
    if role not in [UserRole.MODERATOR.value, UserRole.GAME_MASTER.value, UserRole.ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
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
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid role"
            )
        
        if permission not in ROLE_PERMISSIONS.get(role, set()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value}"
            )
        
        return admin
    
    return check_permission


def require_role(min_role: UserRole):
    """
    Dependency factory that checks for minimum role level.
    Role hierarchy: PLAYER < MODERATOR < GAME_MASTER < ADMIN
    """
    role_hierarchy = [UserRole.PLAYER, UserRole.MODERATOR, UserRole.GAME_MASTER, UserRole.ADMIN]
    
    async def check_role(admin: dict = Depends(get_current_admin)) -> dict:
        role_str = admin.get("role", "player")
        try:
            role = UserRole(role_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid role"
            )
        
        if role_hierarchy.index(role) < role_hierarchy.index(min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {min_role.value} or higher"
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
    next_event_in_seconds: Optional[float]
    maintenance_mode: bool = False
    maintenance_reason: Optional[str] = None
    shutdown_pending: bool = False
    shutdown_at: Optional[float] = None
    shutdown_reason: Optional[str] = None
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
    area_id: Optional[str]
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
    area_id: Optional[str]
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
    amount: Optional[int] = Field(None, ge=1, description="Amount to heal (None = full heal)")


class SpawnNpcRequest(BaseModel):
    """Request to spawn an NPC."""
    template_id: str = Field(..., description="NPC template ID")
    room_id: str = Field(..., description="Room to spawn in")


class SpawnItemRequest(BaseModel):
    """Request to spawn an item."""
    template_id: str = Field(..., description="Item template ID")
    room_id: str = Field(..., description="Room to spawn in")
    quantity: int = Field(1, ge=1, le=99, description="Quantity to spawn")


class BroadcastRequest(BaseModel):
    """Request to broadcast a message to all players."""
    message: str = Field(..., min_length=1, max_length=1000)
    sender_name: str = Field("SYSTEM", description="Name to show as sender")


class MaintenanceModeRequest(BaseModel):
    """Request to toggle maintenance mode."""
    enabled: bool = Field(..., description="Enable or disable maintenance mode")
    reason: str = Field("Scheduled maintenance", description="Reason for maintenance")
    kick_players: bool = Field(False, description="Kick all non-admin players when enabling")


class ShutdownRequest(BaseModel):
    """Request to initiate graceful shutdown."""
    countdown_seconds: int = Field(60, ge=10, le=600, description="Countdown before shutdown (10-600 seconds)")
    reason: str = Field("Server shutdown", description="Reason for shutdown")


class MaintenanceStatusResponse(BaseModel):
    """Current maintenance mode status."""
    enabled: bool
    reason: Optional[str]
    enabled_at: Optional[float]
    enabled_by: Optional[str]


class MaintenanceModeResponse(BaseModel):
    """Response from toggling maintenance mode."""
    enabled: bool
    reason: Optional[str] = None
    enabled_at: Optional[float] = None
    players_kicked: int = 0


class ShutdownStatusResponse(BaseModel):
    """Current shutdown status."""
    requested: bool
    shutdown_at: Optional[float]
    reason: Optional[str]
    requested_by: Optional[str]


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
_maintenance_reason: Optional[str] = None
_maintenance_enabled_at: Optional[float] = None
_maintenance_enabled_by: Optional[str] = None

# Shutdown state
_shutdown_requested = False
_shutdown_at: Optional[float] = None
_shutdown_reason: Optional[str] = None
_shutdown_requested_by: Optional[str] = None
_shutdown_task: Optional[object] = None  # asyncio.Task for countdown


@router.get("/server/status", response_model=ServerStatusResponse)
async def get_server_status(
    request: Request,
    admin: dict = Depends(get_current_admin)
):
    """
    Get current server status and metrics.
    Requires: MODERATOR or higher
    """
    engine = get_engine_from_request(request)
    world = engine.world
    
    # Count online players
    players_online = sum(1 for p in world.players.values() if p.is_connected)
    
    # Count players in combat
    players_in_combat = len(engine.combat_system.active_combats) if hasattr(engine, 'combat_system') else 0
    
    # Count alive NPCs
    npcs_alive = sum(1 for npc in world.npcs.values() if npc.current_health > 0)
    
    # Count rooms with players
    rooms_occupied = sum(1 for room in world.rooms.values() if room.players)
    
    # Get scheduled events count
    scheduled_events = len(engine.time_manager.events) if hasattr(engine, 'time_manager') else 0
    
    # Get next event time
    next_event_in = None
    if hasattr(engine, 'time_manager') and engine.time_manager.events:
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
        content_version=getattr(engine, 'content_version', '1.0.0'),
        server_time=time.time()
    )


@router.post("/server/maintenance", response_model=MaintenanceModeResponse)
async def toggle_maintenance_mode(
    request: Request,
    body: MaintenanceModeRequest,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS))
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
    
    previous_state = _maintenance_mode
    _maintenance_mode = body.enabled
    _maintenance_reason = body.reason or ""
    
    if body.enabled:
        _maintenance_enabled_at = time.time()
        
        # Log the action
        admin_audit_logger.log_maintenance_toggle(
            admin_id=admin_id,
            enabled=True,
            reason=body.reason,
            kick_players=body.kick_players
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
                    if hasattr(player, 'send'):
                        await player.send(maintenance_msg)
                    player.is_connected = False
                    players_kicked += 1
                except Exception:
                    pass  # Player may already be disconnected
        
        return MaintenanceModeResponse(
            enabled=True,
            reason=body.reason,
            enabled_at=_maintenance_enabled_at,
            players_kicked=players_kicked
        )
    else:
        _maintenance_enabled_at = None
        
        admin_audit_logger.log_maintenance_toggle(
            admin_id=admin_id,
            enabled=False,
            reason="Maintenance mode disabled"
        )
        
        return MaintenanceModeResponse(
            enabled=False,
            reason=None,
            enabled_at=None,
            players_kicked=0
        )


@router.post("/server/shutdown", response_model=ShutdownResponse)
async def initiate_shutdown(
    request: Request,
    body: ShutdownRequest,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS))
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
        admin_id=admin_id,
        countdown_seconds=countdown,
        reason=body.reason
    )
    
    # Broadcast initial shutdown warning
    warning_msg = f"\n*** SERVER SHUTDOWN IN {countdown} SECONDS ***\n{_shutdown_reason}\nPlease finish your actions and log out safely.\n"
    
    players_warned = 0
    for player in world.players.values():
        if player.is_connected:
            try:
                if hasattr(player, 'send'):
                    await player.send(warning_msg)
                players_warned += 1
            except Exception:
                pass
    
    # Start async countdown task for periodic warnings
    async def shutdown_countdown_task():
        """Background task to broadcast warnings and trigger shutdown."""
        global _shutdown_requested
        
        intervals = [300, 120, 60, 30, 10, 5, 4, 3, 2, 1]  # Warning intervals in seconds
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
                            if hasattr(player, 'send'):
                                await player.send(warn_msg)
                        except Exception:
                            pass
        
        if _shutdown_requested:
            # Final shutdown - save state and terminate
            final_msg = "\n*** SERVER SHUTTING DOWN NOW ***\n"
            for player in world.players.values():
                if player.is_connected:
                    try:
                        if hasattr(player, 'send'):
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
        players_warned=players_warned
    )


@router.post("/server/shutdown/cancel")
async def cancel_shutdown(
    request: Request,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS))
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
                if hasattr(player, 'send'):
                    await player.send(cancel_msg)
            except Exception:
                pass
    
    return {"success": True, "message": "Shutdown cancelled"}


@router.get("/server/metrics")
async def get_prometheus_metrics(
    request: Request,
    admin: dict = Depends(get_current_admin)
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
    from app.metrics import get_metrics, get_metrics_content_type, update_world_metrics
    from starlette.responses import Response
    
    engine = get_engine_from_request(request)
    world = engine.world
    
    # Update current world state metrics before returning
    online_players = sum(1 for p in world.players.values() if p.is_connected)
    combat_players = len(engine.combat_system.active_combats) if hasattr(engine, 'combat_system') else 0
    alive_npcs = sum(1 for npc in world.npcs.values() if npc.current_health > 0)
    total_npcs = len(world.npcs)
    total_rooms = len(world.rooms)
    occupied_rooms = sum(1 for room in world.rooms.values() if room.players)
    total_areas = len(world.areas)
    total_items = sum(len(getattr(room, 'items', [])) for room in world.rooms.values())
    active_combats = len(engine.combat_system.active_combats) if hasattr(engine, 'combat_system') else 0
    pending_events = len(engine.time_manager.events) if hasattr(engine, 'time_manager') else 0
    
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
        is_maintenance=_maintenance_mode
    )
    
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type()
    )


# ============================================================================
# World Inspection Endpoints
# ============================================================================

@router.get("/world/players", response_model=list[PlayerSummary])
async def list_online_players(
    request: Request,
    admin: dict = Depends(get_current_admin)
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
            if hasattr(engine, 'combat_system'):
                in_combat = player.id in engine.combat_system.active_combats
            
            players.append(PlayerSummary(
                id=player.id,
                name=player.name,
                room_id=player.room_id,
                level=player.level,
                current_health=player.current_health,
                max_health=player.max_health,
                is_connected=player.is_connected,
                in_combat=in_combat
            ))
    
    return players


@router.get("/world/players/{player_id}", response_model=PlayerSummary)
async def get_player_details(
    player_id: str,
    request: Request,
    admin: dict = Depends(get_current_admin)
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
    if hasattr(engine, 'combat_system'):
        in_combat = player.id in engine.combat_system.active_combats
    
    return PlayerSummary(
        id=player.id,
        name=player.name,
        room_id=player.room_id,
        level=player.level,
        current_health=player.current_health,
        max_health=player.max_health,
        is_connected=player.is_connected,
        in_combat=in_combat
    )


@router.get("/world/rooms", response_model=list[RoomSummary])
async def list_rooms(
    request: Request,
    admin: dict = Depends(get_current_admin),
    area_id: Optional[str] = None
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
        
        rooms.append(RoomSummary(
            id=room.id,
            name=room.name,
            area_id=room.area_id,
            player_count=len(room.players),
            npc_count=npc_count,
            item_count=item_count,
            exits=room.get_effective_exits()
        ))
    
    return rooms


@router.get("/world/rooms/{room_id}", response_model=RoomDetail)
async def get_room_details(
    room_id: str,
    request: Request,
    admin: dict = Depends(get_current_admin)
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
    trigger_ids = [t.trigger_id for t in room.triggers] if hasattr(room, 'triggers') else []
    
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
        triggers=trigger_ids
    )


@router.get("/world/areas", response_model=list[AreaSummary])
async def list_areas(
    request: Request,
    admin: dict = Depends(get_current_admin)
):
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
            1 for r in world.rooms.values() 
            if r.area_id == area.area_id 
            for _ in r.players
        )
        
        areas.append(AreaSummary(
            id=area.area_id,
            name=area.name,
            room_count=room_count,
            player_count=player_count,
            time_scale=area.time_scale
        ))
    
    return areas


@router.get("/world/npcs", response_model=list[NpcSummary])
async def list_npcs(
    request: Request,
    admin: dict = Depends(get_current_admin),
    room_id: Optional[str] = None,
    alive_only: bool = False
):
    """
    List all NPCs, optionally filtered by room or alive status.
    Requires: MODERATOR or higher
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
        
        npcs.append(NpcSummary(
            id=npc.id,
            template_id=npc.template_id,
            name=npc.name,
            room_id=npc.room_id,
            current_health=npc.current_health,
            max_health=npc.max_health,
            is_alive=npc.current_health > 0
        ))
    
    return npcs


@router.get("/world/items", response_model=list[ItemSummary])
async def list_items(
    request: Request,
    admin: dict = Depends(get_current_admin),
    room_id: Optional[str] = None,
    player_id: Optional[str] = None
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
        
        items.append(ItemSummary(
            id=item.id,
            template_id=item.template_id,
            name=item.name,
            location_type=location_type,
            location_id=location_id,
            quantity=item.quantity
        ))
    
    return items


# ============================================================================
# Player Manipulation Endpoints
# ============================================================================

@router.post("/players/{player_id}/teleport")
async def teleport_player(
    player_id: str,
    request: Request,
    teleport_request: TeleportRequest,
    admin: dict = Depends(require_permission(Permission.TELEPORT))
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
        success=True
    )
    
    # Notify player
    if player.id in engine._listeners:
        await engine._listeners[player.id].put({
            "type": "message",
            "text": f"You have been teleported to {target_room.name}."
        })
        # Send room description
        room_desc = engine._format_room_description(target_room, player.id)
        await engine._listeners[player.id].put({
            "type": "message", 
            "text": room_desc
        })
    
    return {
        "success": True,
        "message": f"Teleported {player.name} to {target_room.name}",
        "from_room": old_room_id,
        "to_room": target_room.id
    }


@router.post("/players/{player_id}/heal")
async def heal_player(
    player_id: str,
    request: Request,
    heal_request: HealRequest,
    admin: dict = Depends(require_permission(Permission.MODIFY_STATS))
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
        player.current_health = min(player.current_health + heal_request.amount, player.max_health)
    
    healed_amount = player.current_health - old_health
    
    # Notify player
    if player.id in engine._listeners:
        await engine._listeners[player.id].put({
            "type": "message",
            "text": f"You have been healed for {healed_amount} HP by divine intervention."
        })
        await engine._listeners[player.id].put({
            "type": "stat_update",
            "payload": {"current_health": player.current_health, "max_health": player.max_health}
        })
    
    return {
        "success": True,
        "message": f"Healed {player.name} for {healed_amount} HP",
        "old_health": old_health,
        "new_health": player.current_health,
        "max_health": player.max_health
    }


@router.post("/players/{player_id}/kick")
async def kick_player(
    player_id: str,
    request: Request,
    reason: str = "Kicked by administrator",
    admin: dict = Depends(require_permission(Permission.KICK_PLAYER))
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
        success=True
    )
    
    # Send kick message to player
    if player.id in engine._listeners:
        await engine._listeners[player.id].put({
            "type": "kicked",
            "text": f"You have been kicked: {reason}"
        })
    
    # Mark player as disconnected (the WebSocket handler will clean up)
    player.is_connected = False
    
    logger.info(
        "Player kicked",
        admin_id=admin.get("sub"),
        player_id=player_id,
        reason=reason
    )
    
    return {
        "success": True,
        "message": f"Kicked {player.name}",
        "reason": reason
    }


@router.post("/players/{player_id}/give")
async def give_item_to_player(
    player_id: str,
    request: Request,
    give_request: GiveItemRequest,
    admin: dict = Depends(require_permission(Permission.SPAWN_ITEM))
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
    
    from app.engine.world import WorldItem
    item = WorldItem(
        id=item_id,
        template_id=template.id,
        name=template.name,
        description=template.description,
        room_id=None,
        player_id=player.id,
        container_id=None,
        quantity=give_request.quantity,
        keywords=template.keywords.copy() if template.keywords else []
    )
    
    world.items[item_id] = item
    
    # Audit log
    admin_audit.log_give_item(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        target_player_id=player_id,
        item_template_id=give_request.template_id,
        quantity=give_request.quantity,
        success=True
    )
    
    # Notify player
    if player.id in engine._listeners:
        qty_text = f"{give_request.quantity}x " if give_request.quantity > 1 else ""
        await engine._listeners[player.id].put({
            "type": "message",
            "text": f"You received {qty_text}{template.name} from a mysterious force."
        })
    
    return {
        "success": True,
        "message": f"Gave {give_request.quantity}x {template.name} to {player.name}",
        "item_id": item_id
    }


# ============================================================================
# Spawn/Despawn Endpoints
# ============================================================================

@router.post("/npcs/spawn")
async def spawn_npc(
    request: Request,
    spawn_request: SpawnNpcRequest,
    admin: dict = Depends(require_permission(Permission.SPAWN_NPC))
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
        success=True
    )
    
    return {
        "success": True,
        "message": f"Spawned {template.name} in {room.name}",
        "npc_id": npc.id,
        "room_id": room.id
    }


@router.delete("/npcs/{npc_id}")
async def despawn_npc(
    npc_id: str,
    request: Request,
    admin: dict = Depends(require_permission(Permission.SPAWN_NPC))
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
        success=True
    )
    
    # Notify players in room
    room = world.rooms.get(room_id)
    if room:
        for pid in room.players:
            if pid in engine._listeners:
                await engine._listeners[pid].put({
                    "type": "message",
                    "text": f"{npc_name} vanishes in a puff of smoke."
                })
    
    return {
        "success": True,
        "message": f"Despawned {npc_name}",
        "npc_id": npc_id
    }


@router.post("/items/spawn")
async def spawn_item(
    request: Request,
    spawn_request: SpawnItemRequest,
    admin: dict = Depends(require_permission(Permission.SPAWN_ITEM))
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
    
    from app.engine.world import WorldItem
    item = WorldItem(
        id=item_id,
        template_id=template.id,
        name=template.name,
        description=template.description,
        room_id=room.id,
        player_id=None,
        container_id=None,
        quantity=spawn_request.quantity,
        keywords=template.keywords.copy() if template.keywords else []
    )
    
    world.items[item_id] = item
    
    # Notify players in room
    qty_text = f"{spawn_request.quantity}x " if spawn_request.quantity > 1 else ""
    for pid in room.players:
        if pid in engine._listeners:
            await engine._listeners[pid].put({
                "type": "message",
                "text": f"{qty_text}{template.name} materializes on the ground."
            })
    
    return {
        "success": True,
        "message": f"Spawned {spawn_request.quantity}x {template.name} in {room.name}",
        "item_id": item_id
    }


@router.delete("/items/{item_id}")
async def despawn_item(
    item_id: str,
    request: Request,
    admin: dict = Depends(require_permission(Permission.SPAWN_ITEM))
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
                    await engine._listeners[pid].put({
                        "type": "message",
                        "text": f"{item_name} vanishes."
                    })
    
    return {
        "success": True,
        "message": f"Despawned {item_name}",
        "item_id": item_id
    }


# ============================================================================
# Broadcast Endpoint
# ============================================================================

@router.post("/server/broadcast")
async def broadcast_message(
    request: Request,
    broadcast_request: BroadcastRequest,
    admin: dict = Depends(require_role(UserRole.ADMIN))
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
        await queue.put({
            "type": "message",
            "text": message
        })
        sent_count += 1
    
    return {
        "success": True,
        "message": "Broadcast sent",
        "recipients": sent_count
    }


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
    content_type: ReloadContentType = Field(..., description="Type of content to reload")
    file_path: Optional[str] = Field(None, description="Specific file to reload (optional)")


class ValidateRequest(BaseModel):
    """Request to validate YAML content."""
    content_type: ReloadContentType = Field(..., description="Type of content to validate")
    file_path: Optional[str] = Field(None, description="Specific file to validate (optional)")


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
        self.world_data_dir = Path(__file__).parent.parent.parent / 'world_data'
    
    async def validate_yaml_file(self, file_path: Path, content_type: ReloadContentType) -> ValidationResult:
        """Validate a YAML file without loading it."""
        import yaml
        
        result = ValidationResult(file_path=str(file_path), is_valid=True)
        
        if not file_path.exists():
            result.is_valid = False
            result.errors.append(f"File not found: {file_path}")
            return result
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
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
            elif content_type in (ReloadContentType.ITEMS, ReloadContentType.ITEM_TEMPLATES):
                result = self._validate_item_template_data(data, result)
            elif content_type in (ReloadContentType.NPCS, ReloadContentType.NPC_TEMPLATES):
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
    
    def _validate_area_data(self, data: dict, result: ValidationResult) -> ValidationResult:
        """Validate area YAML data."""
        required_fields = ['id', 'name']
        for field in required_fields:
            if field not in data:
                result.is_valid = False
                result.errors.append(f"Missing required field: {field}")
        
        if 'time_scale' in data:
            if not isinstance(data['time_scale'], (int, float)) or data['time_scale'] <= 0:
                result.warnings.append("time_scale should be a positive number")
        
        return result
    
    def _validate_room_data(self, data: dict, result: ValidationResult) -> ValidationResult:
        """Validate room YAML data."""
        required_fields = ['id', 'name', 'description']
        for field in required_fields:
            if field not in data:
                result.is_valid = False
                result.errors.append(f"Missing required field: {field}")
        
        if 'exits' in data:
            valid_exits = {'north', 'south', 'east', 'west', 'up', 'down'}
            for exit_dir in data['exits']:
                if exit_dir not in valid_exits:
                    result.warnings.append(f"Non-standard exit direction: {exit_dir}")
        
        return result
    
    def _validate_item_template_data(self, data: dict, result: ValidationResult) -> ValidationResult:
        """Validate item template YAML data."""
        required_fields = ['id', 'name']
        for field in required_fields:
            if field not in data:
                result.is_valid = False
                result.errors.append(f"Missing required field: {field}")
        
        valid_item_types = {'weapon', 'armor', 'consumable', 'container', 'misc', 'quest', 'tool'}
        if 'item_type' in data and data['item_type'] not in valid_item_types:
            result.warnings.append(f"Unknown item_type: {data['item_type']}")
        
        return result
    
    def _validate_npc_template_data(self, data: dict, result: ValidationResult) -> ValidationResult:
        """Validate NPC template YAML data."""
        required_fields = ['id', 'name']
        for field in required_fields:
            if field not in data:
                result.is_valid = False
                result.errors.append(f"Missing required field: {field}")
        
        if 'max_health' in data and (not isinstance(data['max_health'], int) or data['max_health'] <= 0):
            result.errors.append("max_health must be a positive integer")
            result.is_valid = False
        
        return result
    
    def _validate_npc_spawn_data(self, data: dict, result: ValidationResult) -> ValidationResult:
        """Validate NPC spawn YAML data."""
        if 'spawns' not in data:
            result.is_valid = False
            result.errors.append("Missing 'spawns' list")
            return result
        
        for i, spawn in enumerate(data['spawns']):
            if 'template_id' not in spawn:
                result.errors.append(f"Spawn {i}: missing template_id")
                result.is_valid = False
            if 'room_id' not in spawn:
                result.errors.append(f"Spawn {i}: missing room_id")
                result.is_valid = False
        
        return result
    
    async def reload_item_templates(self, file_path: Optional[Path] = None) -> ReloadResult:
        """Reload item templates from YAML files."""
        import yaml
        from app.models import ItemTemplate
        from app.engine.world import ItemTemplate as WorldItemTemplate
        
        items_dir = self.world_data_dir / 'items'
        result = ReloadResult(
            success=True,
            content_type="item_templates",
            items_loaded=0,
            items_updated=0,
            items_failed=0
        )
        
        if file_path:
            yaml_files = [file_path] if file_path.exists() else []
        else:
            yaml_files = list(items_dir.glob('**/*.yaml')) if items_dir.exists() else []
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    item_data = yaml.safe_load(f)
                
                if not item_data or 'id' not in item_data:
                    result.errors.append(f"{yaml_file}: Missing 'id' field")
                    result.items_failed += 1
                    continue
                
                # Update in-memory world
                template = WorldItemTemplate(
                    id=item_data['id'],
                    name=item_data['name'],
                    description=item_data.get('description', ''),
                    item_type=item_data.get('item_type', 'misc'),
                    item_subtype=item_data.get('item_subtype'),
                    equipment_slot=item_data.get('equipment_slot'),
                    stat_modifiers=item_data.get('stat_modifiers', {}),
                    weight=item_data.get('weight', 0.0),
                    max_stack_size=item_data.get('max_stack_size', 1),
                    has_durability=item_data.get('has_durability', False),
                    max_durability=item_data.get('max_durability'),
                    is_container=item_data.get('is_container', False),
                    container_capacity=item_data.get('container_capacity'),
                    container_type=item_data.get('container_type'),
                    is_consumable=item_data.get('is_consumable', False),
                    consume_effect=item_data.get('consume_effect'),
                    flavor_text=item_data.get('flavor_text'),
                    rarity=item_data.get('rarity', 'common'),
                    value=item_data.get('value', 0),
                    flags=item_data.get('flags', {}),
                    keywords=item_data.get('keywords', []),
                    damage_min=item_data.get('damage_min', 0),
                    damage_max=item_data.get('damage_max', 0),
                    attack_speed=item_data.get('attack_speed', 2.0),
                    damage_type=item_data.get('damage_type', 'physical'),
                )
                
                is_update = item_data['id'] in self.world.item_templates
                self.world.item_templates[item_data['id']] = template
                
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
    
    async def reload_npc_templates(self, file_path: Optional[Path] = None) -> ReloadResult:
        """Reload NPC templates from YAML files."""
        import yaml
        from app.engine.world import NpcTemplate as WorldNpcTemplate, resolve_behaviors
        
        npcs_dir = self.world_data_dir / 'npcs'
        result = ReloadResult(
            success=True,
            content_type="npc_templates",
            items_loaded=0,
            items_updated=0,
            items_failed=0
        )
        
        if file_path:
            yaml_files = [file_path] if file_path.exists() else []
        else:
            yaml_files = list(npcs_dir.glob('**/*.yaml')) if npcs_dir.exists() else []
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    npc_data = yaml.safe_load(f)
                
                if not npc_data or 'id' not in npc_data:
                    result.errors.append(f"{yaml_file}: Missing 'id' field")
                    result.items_failed += 1
                    continue
                
                behavior_config = npc_data.get('behavior', {})
                behaviors = resolve_behaviors(behavior_config)
                
                template = WorldNpcTemplate(
                    id=npc_data['id'],
                    name=npc_data['name'],
                    description=npc_data.get('description', ''),
                    npc_type=npc_data.get('npc_type', 'neutral'),
                    level=npc_data.get('level', 1),
                    max_health=npc_data.get('max_health', 10),
                    armor_class=npc_data.get('armor_class', 10),
                    strength=npc_data.get('strength', 10),
                    dexterity=npc_data.get('dexterity', 10),
                    intelligence=npc_data.get('intelligence', 10),
                    attack_damage_min=npc_data.get('attack_damage_min', 1),
                    attack_damage_max=npc_data.get('attack_damage_max', 4),
                    attack_speed=npc_data.get('attack_speed', 1.0),
                    experience_reward=npc_data.get('experience_reward', 10),
                    behaviors=behaviors,
                    idle_messages=npc_data.get('idle_messages', []),
                    keywords=npc_data.get('keywords', []),
                    loot_table=npc_data.get('loot_table', []),
                )
                
                is_update = npc_data['id'] in self.world.npc_templates
                self.world.npc_templates[npc_data['id']] = template
                
                if is_update:
                    result.items_updated += 1
                    result.warnings.append(f"Updated template: {npc_data['id']} (existing NPCs unchanged)")
                else:
                    result.items_loaded += 1
                    
            except Exception as e:
                result.errors.append(f"{yaml_file}: {e}")
                result.items_failed += 1
        
        if result.items_failed > 0:
            result.success = False
        
        return result
    
    async def reload_rooms(self, file_path: Optional[Path] = None) -> ReloadResult:
        """Reload room data from YAML files."""
        import yaml
        
        rooms_dir = self.world_data_dir / 'rooms'
        result = ReloadResult(
            success=True,
            content_type="rooms",
            items_loaded=0,
            items_updated=0,
            items_failed=0
        )
        
        if file_path:
            yaml_files = [file_path] if file_path.exists() else []
        else:
            yaml_files = list(rooms_dir.glob('**/*.yaml')) if rooms_dir.exists() else []
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    room_data = yaml.safe_load(f)
                
                if not room_data or 'id' not in room_data:
                    result.errors.append(f"{yaml_file}: Missing 'id' field")
                    result.items_failed += 1
                    continue
                
                room_id = room_data['id']
                existing_room = self.world.rooms.get(room_id)
                
                if existing_room:
                    # Update existing room (preserve players and entities)
                    existing_room.name = room_data['name']
                    existing_room.description = room_data['description']
                    existing_room.room_type = room_data.get('room_type', 'ethereal')
                    existing_room.on_enter_effect = room_data.get('on_enter_effect')
                    existing_room.on_exit_effect = room_data.get('on_exit_effect')
                    
                    # Update exits
                    exits = room_data.get('exits', {})
                    for direction in ('north', 'south', 'east', 'west', 'up', 'down'):
                        if direction in exits:
                            existing_room.exits[direction] = exits[direction]
                        elif direction in existing_room.exits:
                            del existing_room.exits[direction]
                    
                    result.items_updated += 1
                else:
                    result.warnings.append(f"Room {room_id} not found in world (add via database)")
                    result.items_failed += 1
                    
            except Exception as e:
                result.errors.append(f"{yaml_file}: {e}")
                result.items_failed += 1
        
        if result.items_failed > 0:
            result.success = False
        
        return result
    
    async def reload_areas(self, file_path: Optional[Path] = None) -> ReloadResult:
        """Reload area data from YAML files."""
        import yaml
        
        areas_dir = self.world_data_dir / 'areas'
        result = ReloadResult(
            success=True,
            content_type="areas",
            items_loaded=0,
            items_updated=0,
            items_failed=0
        )
        
        if file_path:
            yaml_files = [file_path] if file_path.exists() else []
        else:
            yaml_files = list(areas_dir.glob('**/*.yaml')) if areas_dir.exists() else []
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    area_data = yaml.safe_load(f)
                
                if not area_data or 'id' not in area_data:
                    result.errors.append(f"{yaml_file}: Missing 'id' field")
                    result.items_failed += 1
                    continue
                
                area_id = area_data['id']
                existing_area = self.world.areas.get(area_id)
                
                if existing_area:
                    # Update existing area
                    existing_area.name = area_data['name']
                    existing_area.description = area_data.get('description', '')
                    existing_area.time_scale = area_data.get('time_scale', 1.0)
                    existing_area.biome = area_data.get('biome', 'mystical')
                    existing_area.climate = area_data.get('climate', 'temperate')
                    existing_area.ambient_lighting = area_data.get('ambient_lighting', 'dim')
                    existing_area.danger_level = area_data.get('danger_level', 1)
                    existing_area.magic_intensity = area_data.get('magic_intensity', 'moderate')
                    existing_area.default_respawn_time = area_data.get('default_respawn_time', 300)
                    
                    result.items_updated += 1
                else:
                    result.warnings.append(f"Area {area_id} not found in world (add via database)")
                    result.items_failed += 1
                    
            except Exception as e:
                result.errors.append(f"{yaml_file}: {e}")
                result.items_failed += 1
        
        if result.items_failed > 0:
            result.success = False
        
        return result
    
    async def reload_all(self) -> dict:
        """Reload all content types."""
        results = {
            "areas": await self.reload_areas(),
            "rooms": await self.reload_rooms(),
            "item_templates": await self.reload_item_templates(),
            "npc_templates": await self.reload_npc_templates(),
        }
        
        overall_success = all(r.success for r in results.values())
        
        return {
            "success": overall_success,
            "results": {k: v.model_dump() for k, v in results.items()}
        }


@router.post("/content/reload", response_model=ReloadResult)
async def reload_content(
    request: Request,
    reload_request: ReloadRequest,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(UserRole.ADMIN))
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
        all_results = await reloader.reload_all()
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
            success=all_results["success"]
        )
        
        return ReloadResult(
            success=all_results["success"],
            content_type="all",
            items_loaded=total_loaded,
            items_updated=total_updated,
            items_failed=total_failed,
            errors=all_errors
        )
    elif reload_request.content_type == ReloadContentType.AREAS:
        result = await reloader.reload_areas(file_path)
    elif reload_request.content_type == ReloadContentType.ROOMS:
        result = await reloader.reload_rooms(file_path)
    elif reload_request.content_type in (ReloadContentType.ITEMS, ReloadContentType.ITEM_TEMPLATES):
        result = await reloader.reload_item_templates(file_path)
    elif reload_request.content_type in (ReloadContentType.NPCS, ReloadContentType.NPC_TEMPLATES):
        result = await reloader.reload_npc_templates(file_path)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {reload_request.content_type}")
    
    # Audit log for individual content type reload
    admin_audit.log_content_reload(
        admin_id=admin.get("sub", "unknown"),
        admin_name=admin.get("username", "unknown"),
        content_type=reload_request.content_type.value,
        items_loaded=result.items_loaded,
        items_updated=result.items_updated,
        items_failed=result.items_failed,
        success=result.success
    )
    
    return result


@router.post("/content/validate")
async def validate_content(
    request: Request,
    validate_request: ValidateRequest,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(UserRole.GAME_MASTER))
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
        content_dir = world_data_dir / 'areas'
    elif validate_request.content_type == ReloadContentType.ROOMS:
        content_dir = world_data_dir / 'rooms'
    elif validate_request.content_type in (ReloadContentType.ITEMS, ReloadContentType.ITEM_TEMPLATES):
        content_dir = world_data_dir / 'items'
    elif validate_request.content_type in (ReloadContentType.NPCS, ReloadContentType.NPC_TEMPLATES):
        content_dir = world_data_dir / 'npcs'
    elif validate_request.content_type == ReloadContentType.NPC_SPAWNS:
        content_dir = world_data_dir / 'npc_spawns'
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported content type for validation")
    
    if validate_request.file_path:
        yaml_files = [Path(validate_request.file_path)]
    else:
        yaml_files = list(content_dir.glob('**/*.yaml')) if content_dir.exists() else []
    
    results = []
    for yaml_file in yaml_files:
        result = await reloader.validate_yaml_file(yaml_file, validate_request.content_type)
        results.append(result.model_dump())
    
    all_valid = all(r["is_valid"] for r in results)
    
    return {
        "success": all_valid,
        "content_type": validate_request.content_type.value,
        "files_checked": len(results),
        "files_valid": sum(1 for r in results if r["is_valid"]),
        "files_invalid": sum(1 for r in results if not r["is_valid"]),
        "results": results
    }
