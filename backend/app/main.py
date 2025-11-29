# backend/app/main.py
import asyncio
import contextlib
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import (
    FastAPI,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    Query,
    HTTPException,
    status,
    Request,
    Header,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import engine, get_session, AsyncSessionLocal
from .models import Base, Room, Player, PlayerInventory
from .engine.loader import (
    load_world, load_triggers_from_yaml,
    load_quests_into_system, load_dialogues_into_system,
    load_quest_chains_into_system,
    restore_player_quest_progress
)
from .engine.engine import WorldEngine
from .engine.systems.auth import AuthSystem, verify_access_token

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    - Create tables (dev-time; later use migrations).
    - Seed a tiny world if the DB is empty.
    - Load the world into memory.
    - Start a single WorldEngine instance in the background.
    """
    # Startup
    # 1) Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2) Seed players if empty (rooms/areas come from migrations)
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Player).limit(1))
        if result.scalar_one_or_none() is None:
            await seed_world(session)

    # 3) Load world into memory
    async with AsyncSession(engine) as session:
        world = await load_world(session)
    
    # 3b) Load triggers from YAML into world objects
    load_triggers_from_yaml(world)
    
    logger.info("Loaded world: %d rooms, %d players", len(world.rooms), len(world.players))
    if len(world.rooms) > 0:
        sample_rooms = list(world.rooms.keys())[:5]
        logger.info("Sample room IDs: %s", sample_rooms)

    # 4) Create engine and start game loop
    engine_instance = WorldEngine(world, db_session_factory=AsyncSessionLocal)
    app.state.world_engine = engine_instance
    app.state.engine_task = asyncio.create_task(engine_instance.game_loop())
    
    # 4a) Create auth system (Phase 7)
    auth_system = AuthSystem(db_session_factory=AsyncSessionLocal)
    app.state.auth_system = auth_system
    engine_instance.ctx.auth_system = auth_system
    
    # 4b) Load quests, dialogues, and quest chains into QuestSystem (Phase X)
    quest_count = load_quests_into_system(engine_instance.quest_system)
    dialogue_count = load_dialogues_into_system(engine_instance.quest_system)
    chain_count = load_quest_chains_into_system(engine_instance.quest_system)
    logger.info("Loaded %d quests, %d dialogues, %d quest chains", quest_count, dialogue_count, chain_count)
    
    # 4c) Restore player quest progress from saved data
    for player in world.players.values():
        restore_player_quest_progress(engine_instance.quest_system, player)
    
    # 5) Start time event system (Phase 2)
    await engine_instance.start_time_system()

    logger.info(
        "World engine started with %d rooms, %d players",
        len(world.rooms),
        len(world.players),
    )

    yield

    # Shutdown
    # Stop time system first
    world_engine: Optional[WorldEngine] = getattr(app.state, "world_engine", None)
    if world_engine is not None:
        await world_engine.stop_time_system()
    
    # Cancel the background engine loop gracefully on application shutdown
    engine_task: Optional[asyncio.Task] = getattr(app.state, "engine_task", None)
    if engine_task is not None:
        engine_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await engine_task

    logger.info("World engine stopped")


app = FastAPI(lifespan=lifespan)


async def seed_world(session: AsyncSession) -> None:
    """
    Seed test players only. Rooms and areas are loaded from YAML via migrations.
    """
    # Start players in the center of the grid (1, 1, 1)
    start_room_id = "room_1_1_1"
    
    player1_id = str(uuid.uuid4())
    player2_id = str(uuid.uuid4())
    
    player1 = Player(
        id=player1_id,
        name="test_player",
        current_room_id=start_room_id,
        data={},
    )
    player2 = Player(
        id=player2_id,
        name="test_player_2",
        current_room_id=start_room_id,
        data={},
    )
    session.add_all([player1, player2])
    
    # Create inventory records for the new players (Phase 3)
    inventory1 = PlayerInventory(
        player_id=player1_id,
        max_weight=100.0,
        max_slots=20,
        current_weight=0.0,
        current_slots=0,
    )
    inventory2 = PlayerInventory(
        player_id=player2_id,
        max_weight=100.0,
        max_slots=20,
        current_weight=0.0,
        current_slots=0,
    )
    session.add_all([inventory1, inventory2])

    await session.commit()
    logger.info("Seeded 2 test players with inventories: %s, %s", player1_id, player2_id)


def get_world_engine() -> WorldEngine:
    """
    Helper to retrieve the global WorldEngine instance from app.state.
    """
    engine_instance: Optional[WorldEngine] = getattr(app.state, "world_engine", None)
    if engine_instance is None:
        raise RuntimeError("World engine not initialized")
    return engine_instance


# ---------- HTTP Endpoints ----------

@app.get("/")
async def root():
    return {"message": "💀 Hello, Dungeon! 💀"}


@app.get("/players")
async def list_players(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Player))
    players = result.scalars().all()
    return [
        {"id": p.id, "name": p.name, "current_room_id": p.current_room_id}
        for p in players
    ]


# ---------- Auth Endpoints (Phase 7) ----------

def get_auth_system() -> AuthSystem:
    """Helper to retrieve the global AuthSystem instance from app.state."""
    auth_system: Optional[AuthSystem] = getattr(app.state, "auth_system", None)
    if auth_system is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth system not initialized"
        )
    return auth_system


class RegisterRequest(BaseModel):
    """Registration request body."""
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)
    email: Optional[str] = Field(None, max_length=255)


class RegisterResponse(BaseModel):
    """Registration response."""
    user_id: str
    username: str
    message: str


@app.post("/auth/register", response_model=RegisterResponse)
async def register(
    request: RegisterRequest,
    req: Request,
    auth_system: AuthSystem = Depends(get_auth_system)
):
    """
    Register a new user account.
    
    Returns the user ID on success.
    """
    ip_address = req.client.host if req.client else None
    
    account, error = await auth_system.create_account(
        username=request.username,
        password=request.password,
        email=request.email,
        ip_address=ip_address
    )
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return RegisterResponse(
        user_id=account.id,
        username=account.username,
        message="Account created successfully"
    )


class LoginRequest(BaseModel):
    """Login request body."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response with tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    role: str
    active_character_id: Optional[str] = None


@app.post("/auth/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    req: Request,
    user_agent: Optional[str] = Header(None),
    auth_system: AuthSystem = Depends(get_auth_system)
):
    """
    Authenticate and get access/refresh tokens.
    
    Use the access_token to connect via WebSocket.
    Use the refresh_token to get new access tokens when expired.
    """
    ip_address = req.client.host if req.client else None
    
    result = await auth_system.login(
        username=request.username,
        password=request.password,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    if result[0] is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result[2],  # Error message
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    access_token, refresh_token, account = result
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user_id=account.id,
        username=account.username,
        role=account.role,
        active_character_id=account.active_character_id
    )


class RefreshRequest(BaseModel):
    """Token refresh request body."""
    refresh_token: str


class RefreshResponse(BaseModel):
    """Token refresh response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@app.post("/auth/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: RefreshRequest,
    req: Request,
    user_agent: Optional[str] = Header(None),
    auth_system: AuthSystem = Depends(get_auth_system)
):
    """
    Refresh access token using refresh token.
    
    This implements token rotation - the old refresh token is invalidated
    and a new one is returned.
    """
    ip_address = req.client.host if req.client else None
    
    result = await auth_system.refresh_access_token(
        refresh_token=request.refresh_token,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    if result[0] is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result[1],  # Error message
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    access_token, new_refresh_token = result
    
    return RefreshResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )


class LogoutRequest(BaseModel):
    """Logout request body."""
    refresh_token: str


@app.post("/auth/logout")
async def logout(
    request: LogoutRequest,
    req: Request,
    user_agent: Optional[str] = Header(None),
    auth_system: AuthSystem = Depends(get_auth_system)
):
    """
    Logout by revoking the refresh token.
    
    This invalidates the session for the device that sent the request.
    To logout from all devices, use /auth/logout-all.
    """
    ip_address = req.client.host if req.client else None
    
    success = await auth_system.logout(
        refresh_token=request.refresh_token,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired refresh token"
        )
    
    return {"message": "Logged out successfully"}


@app.get("/auth/me")
async def get_current_user(
    authorization: str = Header(..., description="Bearer <access_token>"),
    auth_system: AuthSystem = Depends(get_auth_system)
):
    """
    Get current user info from access token.
    
    Pass the access token in the Authorization header: `Bearer <token>`
    """
    # Parse Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    
    claims = verify_access_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Get full account info
    account = await auth_system.get_account_by_id(claims["user_id"])
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    
    # Get characters
    characters = await auth_system.get_characters_for_account(account.id)
    
    return {
        "user_id": account.id,
        "username": account.username,
        "email": account.email,
        "role": account.role,
        "is_active": account.is_active,
        "active_character_id": account.active_character_id,
        "characters": [
            {"id": c.id, "name": c.name, "level": c.level, "character_class": c.character_class}
            for c in characters
        ]
    }


# ---------- Character Management Endpoints (Phase 7) ----------

class CreateCharacterRequest(BaseModel):
    """Create character request body."""
    name: str = Field(..., min_length=2, max_length=32)
    character_class: str = Field(default="adventurer", max_length=32)


class CharacterResponse(BaseModel):
    """Character info response."""
    id: str
    name: str
    level: int
    character_class: str
    current_room_id: str


@app.post("/characters", response_model=CharacterResponse)
async def create_character(
    request: CreateCharacterRequest,
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_session),
    auth_system: AuthSystem = Depends(get_auth_system)
):
    """
    Create a new character for the authenticated account.
    
    The character starts in the default spawn room.
    """
    # Parse Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    token = authorization[7:]
    claims = verify_access_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = claims["user_id"]
    
    # Check if name is already taken
    result = await session.execute(
        select(Player).where(Player.name == request.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Character name already taken"
        )
    
    # Check character limit (max 3 per account)
    existing = await auth_system.get_characters_for_account(user_id)
    if len(existing) >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum number of characters reached (3)"
        )
    
    # Create new character
    start_room_id = "room_1_1_1"  # Default spawn location
    character_id = str(uuid.uuid4())
    
    character = Player(
        id=character_id,
        name=request.name,
        current_room_id=start_room_id,
        character_class=request.character_class,
        account_id=user_id,
        data={}
    )
    session.add(character)
    
    # Create inventory record
    inventory = PlayerInventory(
        player_id=character_id,
        max_weight=100.0,
        max_slots=20,
        current_weight=0.0,
        current_slots=0,
    )
    session.add(inventory)
    
    await session.commit()
    
    # Add to in-memory world if engine is running
    engine = getattr(app.state, "world_engine", None)
    if engine:
        from .engine.world import WorldPlayer
        world_player = WorldPlayer(
            id=character_id,
            name=request.name,
            room_id=start_room_id,
            character_class=request.character_class,
            max_health=100,
            current_health=100,
            data={},
            account_id=user_id
        )
        engine.world.players[character_id] = world_player
    
    # Set as active character if it's the first one
    if len(existing) == 0:
        await auth_system.set_active_character(user_id, character_id)
    
    return CharacterResponse(
        id=character_id,
        name=request.name,
        level=1,
        character_class=request.character_class,
        current_room_id=start_room_id
    )


@app.get("/characters")
async def list_characters(
    authorization: str = Header(...),
    auth_system: AuthSystem = Depends(get_auth_system)
):
    """
    List all characters for the authenticated account.
    """
    # Parse Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    token = authorization[7:]
    claims = verify_access_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = claims["user_id"]
    
    characters = await auth_system.get_characters_for_account(user_id)
    account = await auth_system.get_account_by_id(user_id)
    
    return {
        "characters": [
            {
                "id": c.id,
                "name": c.name,
                "level": c.level,
                "character_class": c.character_class,
                "current_room_id": c.current_room_id,
                "is_active": account and account.active_character_id == c.id
            }
            for c in characters
        ]
    }


@app.post("/characters/{character_id}/select")
async def select_character(
    character_id: str,
    authorization: str = Header(...),
    auth_system: AuthSystem = Depends(get_auth_system)
):
    """
    Set a character as the active character for the authenticated account.
    """
    # Parse Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    token = authorization[7:]
    claims = verify_access_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = claims["user_id"]
    
    # Verify character belongs to this account and set as active
    success = await auth_system.set_active_character(user_id, character_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found or doesn't belong to this account"
        )
    
    return {"message": "Character selected", "active_character_id": character_id}


@app.delete("/characters/{character_id}")
async def delete_character(
    character_id: str,
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_session),
    auth_system: AuthSystem = Depends(get_auth_system)
):
    """
    Delete a character.
    
    This is a permanent action and cannot be undone.
    """
    # Parse Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    token = authorization[7:]
    claims = verify_access_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = claims["user_id"]
    
    # Verify character belongs to this account
    result = await session.execute(
        select(Player)
        .where(Player.id == character_id)
        .where(Player.account_id == user_id)
    )
    character = result.scalar_one_or_none()
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found or doesn't belong to this account"
        )
    
    # Remove from in-memory world if engine is running
    engine = getattr(app.state, "world_engine", None)
    if engine and character_id in engine.world.players:
        del engine.world.players[character_id]
    
    # Delete from database
    await session.delete(character)
    
    # If this was the active character, clear the active_character_id
    account = await auth_system.get_account_by_id(user_id)
    if account and account.active_character_id == character_id:
        # Get remaining characters and set first one as active, or None
        remaining = await auth_system.get_characters_for_account(user_id)
        remaining = [c for c in remaining if c.id != character_id]
        if remaining:
            await auth_system.set_active_character(user_id, remaining[0].id)
    
    await session.commit()
    
    return {"message": "Character deleted", "character_id": character_id}


# ---------- WebSocket Endpoints ----------

@app.websocket("/ws/game/auth")
async def game_ws_auth(
    websocket: WebSocket,
    token: str = Query(..., description="Access token from /auth/login"),
) -> None:
    """
    Authenticated WebSocket endpoint (Phase 7).

    - client connects: /ws/game/auth?token=<access_token>
    - client sends: {"type": "command", "text": "look"}
    - server sends: events like {"type": "message", "player_id": "...", "text": "..."}

    The token is verified and the user's active character is loaded.
    """
    # Verify token first (before accepting connection)
    claims = verify_access_token(token)
    if not claims:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return
    
    user_id = claims["user_id"]
    user_role = claims["role"]
    
    await websocket.accept()
    logger.info("Authenticated WebSocket connection attempt for user %s", user_id)
    
    # Ensure engine exists
    try:
        engine = get_world_engine()
        if engine is None:
            logger.error("World engine not initialized")
            await websocket.close(code=1011, reason="World engine not ready")
            return
    except RuntimeError:
        logger.error("World engine not initialized")
        await websocket.close(code=1011, reason="World engine not ready")
        return
    
    # Get auth system and lookup user's active character
    auth_system = getattr(app.state, "auth_system", None)
    if auth_system is None:
        await websocket.close(code=1011, reason="Auth system not ready")
        return
    
    # Get active character
    character = await auth_system.get_active_character(user_id)
    if character is None:
        # No active character - tell client they need to select/create one
        await websocket.send_json({
            "type": "error",
            "code": "no_active_character",
            "text": "No active character. Please create or select a character first."
        })
        await websocket.close(code=4002, reason="No active character")
        return
    
    player_id = character.id
    
    # Ensure player exists in the in-memory world
    if player_id not in engine.world.players:
        logger.info("WS connection rejected for unknown player %s", player_id)
        await websocket.close(code=1008, reason="Character not loaded")
        return
    
    # Store auth info in context for permission checks
    auth_info = {"user_id": user_id, "role": user_role}
    
    # Register this player with the engine
    event_queue = await engine.register_player(player_id)
    logger.info("Player %s (user %s, role %s) connected via authenticated WebSocket", 
                player_id, user_id, user_role)
    
    # Send welcome message with auth info
    await websocket.send_json({
        "type": "auth_success",
        "user_id": user_id,
        "player_id": player_id,
        "role": user_role
    })

    send_task = asyncio.create_task(_ws_sender(websocket, event_queue))
    recv_task = asyncio.create_task(_ws_receiver_auth(websocket, engine, player_id, auth_info))

    try:
        done, pending = await asyncio.wait(
            {send_task, recv_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        # If either sender or receiver stops, cancel the other
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    finally:
        # Broadcast disconnect message to other players
        await engine.player_disconnect(player_id)
        engine.unregister_player(player_id)
        logger.info("Player %s disconnected", player_id)


async def _ws_receiver_auth(
    websocket: WebSocket,
    engine: WorldEngine,
    player_id: str,
    auth_info: dict,
) -> None:
    """
    Receives messages from authenticated client and forwards commands.
    Sets auth_info on context for permission checks.
    """
    try:
        while True:
            data = await websocket.receive_json()
            logger.info("Received WS message from player %s: %s", player_id, data)
            msg_type = data.get("type")
            if msg_type == "command":
                text = data.get("text", "")
                # Set auth info on context before processing command
                engine.ctx.auth_info = auth_info
                await engine.submit_command(player_id, text)
            else:
                logger.debug("Ignoring unknown WS message type: %s", msg_type)
    except WebSocketDisconnect:
        logger.info("WebSocketDisconnect for player %s", player_id)
        pass
    except Exception as exc:
        logger.exception("Error in _ws_receiver_auth for player %s: %s", player_id, exc)


# Legacy WebSocket endpoint (deprecated - kept for backward compatibility)
@app.websocket("/ws/game")
async def game_ws(
    websocket: WebSocket,
    player_id: str = Query(..., description="Player ID (from /players) - DEPRECATED: Use /ws/game/auth instead"),
) -> None:
    """
    Legacy WebSocket endpoint (DEPRECATED).
    
    Use /ws/game/auth with a token instead for authenticated connections.

    - client connects: /ws/game?player_id=...
    - client sends: {"type": "command", "text": "look"}
    - server sends: events like {"type": "message", "player_id": "...", "text": "..."}

    This is single-process, multi-player: one WorldEngine shared by all connections.
    """
    await websocket.accept()
    logger.info("WebSocket connection attempt for player %s", player_id)
    # Ensure engine exists
    try:
        engine = get_world_engine()
        if engine is None:
            logger.error("World engine not initialized")
            await websocket.close(code=1011, reason="Engine is None. World engine not ready")
            return
    except RuntimeError:
        logger.error("World engine not initialized")
        await websocket.close(code=1011, reason="Runtime Error: World engine not ready")
        return

    # Basic validation: ensure this player exists in the in-memory world
    if player_id not in engine.world.players:
        logger.info("WS connection rejected for unknown player %s", player_id)
        await websocket.close(code=1008, reason="Unknown player")
        return

    # Register this player with the engine
    event_queue = await engine.register_player(player_id)
    logger.info("Player %s connected via WebSocket", player_id)

    send_task = asyncio.create_task(_ws_sender(websocket, event_queue))
    recv_task = asyncio.create_task(_ws_receiver(websocket, engine, player_id))

    try:
        done, pending = await asyncio.wait(
            {send_task, recv_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        # If either sender or receiver stops, cancel the other
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    finally:
        # Broadcast disconnect message to other players
        await engine.player_disconnect(player_id)
        engine.unregister_player(player_id)
        logger.info("Player %s disconnected", player_id)


async def _ws_receiver(
    websocket: WebSocket,
    engine: WorldEngine,
    player_id: str,
) -> None:
    """
    Receives messages from the client and forwards commands to the engine.
    """
    try:
        while True:
            data = await websocket.receive_json()
            logger.info("Received WS message from player %s: %s", player_id, data)
            msg_type = data.get("type")
            if msg_type == "command":
                text = data.get("text", "")
                await engine.submit_command(player_id, text)
            else:
                # Unknown message types can be ignored or handled later
                logger.debug("Ignoring unknown WS message type: %s", msg_type)
    except WebSocketDisconnect:
        # Normal disconnect; let game_ws handle cleanup
        logger.info("WebSocketDisconnect for player %s", player_id)
        pass
    except Exception as exc:
        logger.exception("Error in _ws_receiver for player %s: %s", player_id, exc)


async def _ws_sender(
    websocket: WebSocket,
    event_queue: asyncio.Queue[dict],
) -> None:
    """
    Sends events from the engine to the client.
    """
    try:
        while True:
            ev = await event_queue.get()
            await websocket.send_json(ev)
    except WebSocketDisconnect:
        # Normal disconnect; let game_ws handle cleanup
        pass
    except Exception as exc:
        logger.exception("Error in _ws_sender: %s", exc)
