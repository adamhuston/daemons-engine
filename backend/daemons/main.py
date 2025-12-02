# backend/app/main.py
import asyncio
import contextlib
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import AsyncSessionLocal, engine, get_session
from .engine.engine import WorldEngine
from .engine.loader import (
    load_dialogues_into_system,
    load_quest_chains_into_system,
    load_quests_into_system,
    load_triggers_from_yaml,
    load_world,
    restore_player_quest_progress,
)
from .engine.systems.auth import AuthSystem, verify_access_token
from .input_sanitization import sanitize_player_name
from .legacy_deprecation import (
    legacy_deprecation_manager,
)
from .metrics import init_metrics
from .models import Base, Player, PlayerInventory
from .rate_limit import (
    RATE_LIMITS,
    is_chat_command,
    limiter,
    rate_limit_exceeded_handler,
    ws_rate_limiter,
)
from .routes.admin import router as admin_router
from .websocket_security import (
    get_client_ip_from_websocket,
    ws_security_manager,
)

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
    # 0) Initialize Prometheus metrics (Phase 8)
    init_metrics(version="1.0.0", environment="development")

    # 1) Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2) Seed players if empty (rooms/areas come from migrations)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Player).limit(1))
        if result.scalar_one_or_none() is None:
            await seed_world(session)

    # 3) Load world into memory
    async with AsyncSessionLocal() as session:
        world = await load_world(session)

    # 3b) Load triggers from YAML into world objects
    load_triggers_from_yaml(world)

    logger.info(
        "Loaded world: %d rooms, %d players", len(world.rooms), len(world.players)
    )
    if len(world.rooms) > 0:
        sample_rooms = list(world.rooms.keys())[:5]
        logger.info("Sample room IDs: %s", sample_rooms)

    # 4) Create engine and start game loop
    engine_instance = WorldEngine(world, db_session_factory=AsyncSessionLocal)
    app.state.world_engine = engine_instance
    app.state.engine_task = asyncio.create_task(engine_instance.game_loop())

    # 4a) Load class/ability content into ClassSystem (Phase 9c)
    from pathlib import Path

    class_dir = Path(__file__).parent / "world_data"
    await engine_instance.class_system.load_content(class_dir)
    logger.info("Loaded character classes and abilities from world_data")

    # 4a1) Initialize character sheets for all players now that classes are loaded
    from .engine.world import CharacterSheet, ResourcePool

    for player in engine_instance.world.players.values():
        if player.character_class and not player.character_sheet:
            # Get class template
            class_template = engine_instance.class_system.get_class(
                player.character_class
            )
            if class_template:
                # Initialize resource pools
                resource_pools = {}
                for resource_id, resource_def in class_template.resources.items():
                    resource_pools[resource_id] = ResourcePool(
                        resource_id=resource_id,
                        current=resource_def.max_amount,
                        max=resource_def.max_amount,
                        regen_per_second=resource_def.regen_rate,
                        last_regen_tick=0.0,
                    )

                # Get learned abilities from DB or default to first 3 available
                learned_abilities = set()
                if hasattr(player, "player_flags") and player.player_flags:
                    learned_abilities = set(
                        player.player_flags.get("learned_abilities", [])
                    )
                if not learned_abilities and class_template.available_abilities:
                    learned_abilities = set(class_template.available_abilities[:3])

                # Create character sheet
                player.character_sheet = CharacterSheet(
                    class_id=player.character_class,
                    level=player.level,
                    experience=player.experience,
                    learned_abilities=learned_abilities,
                    ability_loadout=[],
                    resource_pools=resource_pools,
                )
                logger.info(
                    f"Initialized character sheet for {player.name} ({player.character_class})"
                )

    # 4a1b) Initialize character sheets for NPCs with class_id (Phase 14.4)
    from .engine.loader import create_npc_character_sheet

    npc_sheet_count = 0
    for npc in engine_instance.world.npcs.values():
        template = engine_instance.world.npc_templates.get(npc.template_id)
        if template and template.class_id and not npc.character_sheet:
            npc.character_sheet = create_npc_character_sheet(
                template,
                engine_instance.class_system.class_templates,
            )
            if npc.character_sheet:
                npc_sheet_count += 1
    if npc_sheet_count > 0:
        logger.info(
            f"Initialized character sheets for {npc_sheet_count} NPCs with abilities"
        )

    # 4a2) Load clans from database into ClanSystem (Phase 10.2)
    await engine_instance.clan_system.load_clans_from_db()
    logger.info("Loaded clans from database into ClanSystem")

    # 4a3) Load factions from YAML into FactionSystem (Phase 10.3)
    from pathlib import Path

    factions_dir = Path(__file__).parent / "world_data" / "factions"
    await engine_instance.faction_system.load_factions_from_yaml(str(factions_dir))
    logger.info("Loaded factions from YAML into FactionSystem")

    # 4a4) Load schemas from YAML into SchemaRegistry (Phase 12.1)
    engine_instance.schema_registry.load_all_schemas()
    logger.info(
        f"Loaded {engine_instance.schema_registry.version.schema_count} schemas from world_data"
    )

    # 4b) Create auth system (Phase 7)
    auth_system = AuthSystem(db_session_factory=AsyncSessionLocal)
    app.state.auth_system = auth_system
    engine_instance.ctx.auth_system = auth_system

    # 4b) Load quests, dialogues, and quest chains into QuestSystem (Phase X)
    quest_count = load_quests_into_system(engine_instance.quest_system)
    dialogue_count = load_dialogues_into_system(engine_instance.quest_system)
    chain_count = load_quest_chains_into_system(engine_instance.quest_system)
    logger.info(
        "Loaded %d quests, %d dialogues, %d quest chains",
        quest_count,
        dialogue_count,
        chain_count,
    )

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
    world_engine: WorldEngine | None = getattr(app.state, "world_engine", None)
    if world_engine is not None:
        await world_engine.stop_time_system()

    # Cancel the background engine loop gracefully on application shutdown
    engine_task: asyncio.Task | None = getattr(app.state, "engine_task", None)
    if engine_task is not None:
        engine_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await engine_task

    logger.info("World engine stopped")


app = FastAPI(lifespan=lifespan)

# Register rate limiter and exception handler (Phase 16.1)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Register admin routes (Phase 8)
app.include_router(admin_router)


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
    logger.info(
        "Seeded 2 test players with inventories: %s, %s", player1_id, player2_id
    )


def get_world_engine() -> WorldEngine:
    """
    Helper to retrieve the global WorldEngine instance from daemons.state.
    """
    engine_instance: WorldEngine | None = getattr(app.state, "world_engine", None)
    if engine_instance is None:
        raise RuntimeError("World engine not initialized")
    return engine_instance


# ---------- HTTP Endpoints ----------


@app.get("/")
async def root():
    return {"message": "💀 Hello, Dungeon! 💀"}


@app.get("/metrics", include_in_schema=False)
async def public_metrics(request: Request):
    """
    Public Prometheus metrics endpoint for monitoring.

    Returns metrics in Prometheus text exposition format.
    No authentication required (metrics are generally non-sensitive).

    Metrics tracked:
    - Players online, total, in combat
    - NPCs alive and total
    - Rooms and occupied rooms
    - Combat statistics
    - Command processing
    - Server uptime
    """
    from starlette.responses import Response

    # Get engine instance if available
    engine_instance = getattr(request.app.state, "world_engine", None)
    if engine_instance:
        # Update metrics with current world state
        world = engine_instance.world
        online_players = sum(1 for p in world.players.values() if p.is_connected)
        alive_npcs = sum(1 for npc in world.npcs.values() if npc.current_health > 0)
        total_npcs = len(world.npcs)
        total_rooms = len(world.rooms)
        occupied_rooms = len([r for r in world.rooms.values() if r.entities])

        # Update the metrics
        from daemons.metrics import (
            areas_total,
            npcs_alive,
            npcs_total,
            players_online,
            rooms_occupied,
            rooms_total,
        )

        players_online.set(online_players)
        npcs_alive.set(alive_npcs)
        npcs_total.set(total_npcs)
        rooms_total.set(total_rooms)
        rooms_occupied.set(occupied_rooms)
        areas_total.set(len(world.areas))

    # Generate Prometheus exposition format
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    from prometheus_client import REGISTRY as prometheus_registry

    metrics_content = generate_latest(prometheus_registry)

    return Response(
        content=metrics_content,
        media_type=CONTENT_TYPE_LATEST,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


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
    """Helper to retrieve the global AuthSystem instance from daemons.state."""
    auth_system: AuthSystem | None = getattr(app.state, "auth_system", None)
    if auth_system is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth system not initialized",
        )
    return auth_system


class RegisterRequest(BaseModel):
    """Registration request body."""

    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)
    email: str | None = Field(None, max_length=255)


class RegisterResponse(BaseModel):
    """Registration response."""

    user_id: str
    username: str
    message: str


@app.post("/auth/register", response_model=RegisterResponse)
@limiter.limit(RATE_LIMITS["auth_register"])
async def register(
    request: RegisterRequest,
    req: Request,
    auth_system: AuthSystem = Depends(get_auth_system),
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
        ip_address=ip_address,
    )

    if not account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    return RegisterResponse(
        user_id=account.id,
        username=account.username,
        message="Account created successfully",
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
    active_character_id: str | None = None


@app.post("/auth/login", response_model=LoginResponse)
@limiter.limit(RATE_LIMITS["auth_login"])
async def login(
    request: LoginRequest,
    req: Request,
    user_agent: str | None = Header(None),
    auth_system: AuthSystem = Depends(get_auth_system),
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
        user_agent=user_agent,
    )

    if result[0] is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result[2],  # Error message
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, refresh_token, account = result

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user_id=account.id,
        username=account.username,
        role=account.role,
        active_character_id=account.active_character_id,
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
@limiter.limit(RATE_LIMITS["auth_refresh"])
async def refresh_token(
    request: RefreshRequest,
    req: Request,
    user_agent: str | None = Header(None),
    auth_system: AuthSystem = Depends(get_auth_system),
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
        user_agent=user_agent,
    )

    if result[0] is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result[1],  # Error message
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, new_refresh_token = result

    return RefreshResponse(
        access_token=access_token, refresh_token=new_refresh_token, token_type="bearer"
    )


class LogoutRequest(BaseModel):
    """Logout request body."""

    refresh_token: str


@app.post("/auth/logout")
@limiter.limit(RATE_LIMITS["auth_logout"])
async def logout(
    request: LogoutRequest,
    req: Request,
    user_agent: str | None = Header(None),
    auth_system: AuthSystem = Depends(get_auth_system),
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
        user_agent=user_agent,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired refresh token",
        )

    return {"message": "Logged out successfully"}


@app.get("/auth/me")
async def get_current_user(
    authorization: str = Header(..., description="Bearer <access_token>"),
    auth_system: AuthSystem = Depends(get_auth_system),
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
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    claims = verify_access_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get full account info
    account = await auth_system.get_account_by_id(claims["user_id"])
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
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
            {
                "id": c.id,
                "name": c.name,
                "level": c.level,
                "character_class": c.character_class,
            }
            for c in characters
        ],
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
    auth_system: AuthSystem = Depends(get_auth_system),
):
    """
    Create a new character for the authenticated account.

    The character starts in the default spawn room.
    Phase 16.5: Character names are sanitized and validated.
    """
    # Parse Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    token = authorization[7:]
    claims = verify_access_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    user_id = claims["user_id"]

    # Phase 16.5: Sanitize and validate character name
    sanitized_name, is_valid, error_msg = sanitize_player_name(request.name)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg or "Invalid character name",
        )

    # Check if name is already taken (using sanitized name)
    result = await session.execute(select(Player).where(Player.name == sanitized_name))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Character name already taken",
        )

    # Check character limit (max 3 per account)
    existing = await auth_system.get_characters_for_account(user_id)
    if len(existing) >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum number of characters reached (3)",
        )

    # Create new character (using sanitized name)
    start_room_id = "room_1_1_1"  # Default spawn location
    character_id = str(uuid.uuid4())

    character = Player(
        id=character_id,
        name=sanitized_name,
        current_room_id=start_room_id,
        character_class=request.character_class,
        account_id=user_id,
        data={},
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
        from .engine.world import PlayerInventory as WorldPlayerInventory
        from .engine.world import WorldPlayer

        world_player = WorldPlayer(
            id=character_id,
            name=request.name,
            room_id=start_room_id,
            character_class=request.character_class,
            max_health=100,
            current_health=100,
            data={},
            account_id=user_id,
            inventory_meta=WorldPlayerInventory(
                player_id=character_id,
                max_weight=100.0,
                max_slots=20,
                current_weight=0.0,
                current_slots=0,
            ),
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
        current_room_id=start_room_id,
    )


@app.get("/characters")
async def list_characters(
    authorization: str = Header(...), auth_system: AuthSystem = Depends(get_auth_system)
):
    """
    List all characters for the authenticated account.
    """
    # Parse Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    token = authorization[7:]
    claims = verify_access_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
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
                "is_active": account and account.active_character_id == c.id,
            }
            for c in characters
        ]
    }


@app.post("/characters/{character_id}/select")
async def select_character(
    character_id: str,
    authorization: str = Header(...),
    auth_system: AuthSystem = Depends(get_auth_system),
):
    """
    Set a character as the active character for the authenticated account.
    """
    # Parse Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    token = authorization[7:]
    claims = verify_access_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    user_id = claims["user_id"]

    # Verify character belongs to this account and set as active
    success = await auth_system.set_active_character(user_id, character_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found or doesn't belong to this account",
        )

    return {"message": "Character selected", "active_character_id": character_id}


@app.delete("/characters/{character_id}")
async def delete_character(
    character_id: str,
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_session),
    auth_system: AuthSystem = Depends(get_auth_system),
):
    """
    Delete a character.

    This is a permanent action and cannot be undone.
    """
    # Parse Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    token = authorization[7:]
    claims = verify_access_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
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
            detail="Character not found or doesn't belong to this account",
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


# ---------- Admin Endpoints (Phase 16.2) ----------


class UnlockAccountRequest(BaseModel):
    """Request to unlock a locked account."""

    account_id: str = Field(..., description="ID of the account to unlock")


@app.post("/admin/unlock-account")
async def unlock_account(
    request: UnlockAccountRequest,
    req: Request,
    authorization: str = Header(..., description="Bearer <access_token>"),
    auth_system: AuthSystem = Depends(get_auth_system),
):
    """
    Unlock a locked account (admin only).

    Requires admin role. Clears the lockout state and resets failed login attempts.
    """
    # Parse and verify admin token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]
    claims = verify_access_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check admin role
    if claims.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    ip_address = req.client.host if req.client else None
    admin_account_id = claims["user_id"]

    success, error = await auth_system.unlock_account(
        account_id=request.account_id,
        admin_account_id=admin_account_id,
        ip_address=ip_address,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    return {"message": "Account unlocked successfully", "account_id": request.account_id}


# ---------- Character Selection Mode Helper ----------


async def _build_character_menu(
    auth_system,
    user_id: str,
) -> tuple[str, list]:
    """Build the character selection menu text."""
    characters = await auth_system.get_characters_for_account(user_id)

    lines = [
        "=== Character Selection ===",
        "",
    ]

    if characters:
        lines.append("Your characters:")
        for i, char in enumerate(characters, 1):
            lines.append(
                f"  {i}. {char.name} (Level {char.level} {char.character_class})"
            )
        lines.append("")
        lines.append("Commands:")
        lines.append("  <number>        - Select a character to play")
        lines.append("  new             - Create a new character")
        lines.append("  delete <number> - Delete a character")
    else:
        lines.append("You have no characters yet.")
        lines.append("")
        lines.append("Commands:")
        lines.append("  new             - Create a new character")

    lines.append("")

    return "\n".join(lines), characters


async def _handle_character_selection(
    websocket,
    auth_system,
    engine,
    user_id: str,
):
    """
    Handle character selection/creation mode.

    Returns the selected Character object, or None if disconnected/error.
    """
    # State for character creation
    create_state = None  # None, "awaiting_name", "awaiting_class"
    pending_name = None

    # Available classes
    available_classes = ["warrior", "mage", "rogue", "cleric"]

    while True:
        # Send current menu
        menu_text, characters = await _build_character_menu(auth_system, user_id)

        if create_state == "awaiting_name":
            menu_text = "=== Create New Character ===\n\nEnter a name for your character (or 'cancel' to go back):\n"
        elif create_state == "awaiting_class":
            class_list = ", ".join(available_classes)
            menu_text = f"=== Create New Character ===\n\nChoose a class for {pending_name}:\n  {class_list}\n\n(or 'cancel' to go back):\n"

        await websocket.send_json(
            {
                "type": "character_menu",
                "text": menu_text,
            }
        )

        try:
            # Wait for input
            data = await websocket.receive_json()

            if data.get("type") != "command":
                continue

            cmd = data.get("text", "").strip().lower()

            # Handle creation states
            if create_state == "awaiting_name":
                if cmd == "cancel":
                    create_state = None
                    pending_name = None
                    continue

                # Validate name
                name = data.get("text", "").strip()  # Use original case
                if len(name) < 2:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "text": "Name must be at least 2 characters.",
                        }
                    )
                    continue
                if len(name) > 32:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "text": "Name must be 32 characters or less.",
                        }
                    )
                    continue

                pending_name = name
                create_state = "awaiting_class"
                continue

            elif create_state == "awaiting_class":
                if cmd == "cancel":
                    create_state = None
                    pending_name = None
                    continue

                if cmd not in available_classes:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "text": f"Invalid class. Choose from: {', '.join(available_classes)}",
                        }
                    )
                    continue

                # Create the character
                from daemons.db import get_session
                from daemons.models import Player

                async for session in get_session():
                    # Check if name is taken
                    from sqlalchemy import select

                    existing = await session.execute(
                        select(Player).where(Player.name == pending_name)
                    )
                    if existing.scalar():
                        await websocket.send_json(
                            {
                                "type": "error",
                                "text": f"The name '{pending_name}' is already taken.",
                            }
                        )
                        create_state = "awaiting_name"
                        pending_name = None
                        break

                    # Generate unique player ID
                    import uuid

                    player_id = str(uuid.uuid4())

                    # Get class template for initialization
                    class_template = engine.class_system.get_class(cmd)
                    if not class_template:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "text": f"Class '{cmd}' is not available.",
                            }
                        )
                        continue

                    # Initialize character data with class info
                    char_data = {
                        "class_id": cmd,
                        "learned_abilities": (
                            class_template.available_abilities[:3]
                            if class_template.available_abilities
                            else []
                        ),
                    }

                    # Create character
                    new_char = Player(
                        id=player_id,
                        account_id=user_id,
                        name=pending_name,
                        character_class=cmd,
                        level=1,
                        current_room_id="room_0_0_0",
                        strength=class_template.base_stats.get("strength", 10),
                        dexterity=class_template.base_stats.get("dexterity", 10),
                        intelligence=class_template.base_stats.get("intelligence", 10),
                        vitality=class_template.base_stats.get("vitality", 10),
                        data=char_data,
                    )
                    session.add(new_char)
                    await session.commit()
                    await session.refresh(new_char)

                    # Set as active
                    await auth_system.set_active_character(user_id, new_char.id)

                    await websocket.send_json(
                        {
                            "type": "message",
                            "text": f"Character '{pending_name}' created! Entering the world...",
                        }
                    )

                    create_state = None
                    pending_name = None

                    return new_char

                continue

            # Normal menu state
            if cmd == "new":
                create_state = "awaiting_name"
                continue

            elif cmd.startswith("delete "):
                try:
                    num = int(cmd.split()[1])
                    if 1 <= num <= len(characters):
                        char_to_delete = characters[num - 1]

                        from daemons.db import get_session

                        async for session in get_session():
                            # Remove from world if loaded
                            if char_to_delete.id in engine.world.players:
                                del engine.world.players[char_to_delete.id]

                            await session.delete(char_to_delete)
                            await session.commit()

                        await websocket.send_json(
                            {
                                "type": "message",
                                "text": f"Character '{char_to_delete.name}' deleted.",
                            }
                        )
                    else:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "text": f"Invalid character number. Enter 1-{len(characters)}.",
                            }
                        )
                except (ValueError, IndexError):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "text": "Usage: delete <number>",
                        }
                    )
                continue

            # Try to select by number
            try:
                num = int(cmd)
                if 1 <= num <= len(characters):
                    selected_char = characters[num - 1]
                    await auth_system.set_active_character(user_id, selected_char.id)

                    await websocket.send_json(
                        {
                            "type": "message",
                            "text": f"Selected {selected_char.name}. Entering the world...",
                        }
                    )

                    return selected_char
                else:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "text": f"Invalid character number. Enter 1-{len(characters)}.",
                        }
                    )
            except ValueError:
                if characters:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "text": "Unknown command. Enter a number to select a character, 'new' to create one, or 'delete <number>' to delete one.",
                        }
                    )
                else:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "text": "Unknown command. Enter 'new' to create a character.",
                        }
                    )

        except WebSocketDisconnect:
            logger.info("Client disconnected during character selection")
            return None
        except Exception as e:
            logger.error("Error during character selection: %s", e)
            await websocket.send_json(
                {
                    "type": "error",
                    "text": "An error occurred. Please try again.",
                }
            )


# ---------- WebSocket Endpoints ----------


@app.websocket("/ws/game/auth")
async def game_ws_auth(
    websocket: WebSocket,
    token: str | None = Query(None, description="Access token (deprecated, use Sec-WebSocket-Protocol header)"),
) -> None:
    """
    Authenticated WebSocket endpoint (Phase 7).

    Phase 16.3: Token should be passed via Sec-WebSocket-Protocol header:
    - Header format: Sec-WebSocket-Protocol: access_token, <your_token>
    - Query string still supported but deprecated: /ws/game/auth?token=<token>

    Phase 16.4: Security hardening:
    - Origin validation (configurable allowed origins)
    - Connection limits per IP and account
    - Message size limits (64KB default)
    - Message schema validation
    - Heartbeat/ping-pong for connection health

    - client sends: {"type": "command", "text": "look"}
    - server sends: events like {"type": "message", "player_id": "...", "text": "..."}

    The token is verified and the user's active character is loaded.
    Supports returning to character selection via the 'quit' command.
    """
    # Phase 16.4: Get client IP for connection limiting
    client_ip = get_client_ip_from_websocket(websocket)
    connection_id = str(uuid.uuid4())  # Unique ID for this connection

    # Phase 16.4: Validate connection before accepting (origin and IP limit)
    valid, error = await ws_security_manager.validate_connection(
        websocket, client_ip, account_id=None  # Account checked after auth
    )
    if not valid:
        logger.warning(f"WebSocket connection rejected: {error} (IP: {client_ip})")
        await websocket.close(code=4003, reason=error)
        return

    # Phase 16.3: Extract token from Sec-WebSocket-Protocol header first
    # Format: "access_token, <actual_token>"
    ws_protocols = websocket.headers.get("sec-websocket-protocol", "")
    header_token = None
    subprotocol = None

    if ws_protocols:
        protocols = [p.strip() for p in ws_protocols.split(",")]
        if len(protocols) >= 2 and protocols[0] == "access_token":
            header_token = protocols[1]
            subprotocol = "access_token"

    # Prefer header token, fall back to query string
    effective_token = header_token or token

    if not effective_token:
        await websocket.close(code=4001, reason="No token provided. Use Sec-WebSocket-Protocol header or token query param")
        return

    # Log deprecation warning if using query string
    if token and not header_token:
        logger.warning("WebSocket connection using deprecated query string token. Migrate to Sec-WebSocket-Protocol header.")

    # Verify token first (before accepting connection)
    claims = verify_access_token(effective_token)
    if not claims:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id = claims["user_id"]
    user_role = claims["role"]

    # Phase 16.4: Check account connection limit
    valid, error = ws_security_manager.connection_limiter.check_account_limit(user_id)
    if not valid:
        logger.warning(f"WebSocket connection rejected: {error} (user: {user_id})")
        await websocket.close(code=4003, reason=error)
        return

    # Accept connection with subprotocol if token was in header
    if subprotocol:
        await websocket.accept(subprotocol=subprotocol)
    else:
        await websocket.accept()

    # Phase 16.4: Register connection for tracking after acceptance
    ws_security_manager.register_connection(connection_id, client_ip, user_id)
    logger.info("Authenticated WebSocket connection for user %s (connection: %s)", user_id, connection_id)

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

    # Outer loop: Character Selection -> Play -> Character Selection (on quit)
    while True:
        # Get active character - if none, enter character selection mode
        character = await auth_system.get_active_character(user_id)

        if character is None:
            # Enter character selection mode
            character = await _handle_character_selection(
                websocket, auth_system, engine, user_id
            )
            if character is None:
                # User disconnected or error during character selection
                return

        player_id = character.id

        # Ensure player exists in the in-memory world
        if player_id not in engine.world.players:
            # Character exists in DB but not in memory - load it now
            logger.info("Loading character %s into memory from database", player_id)
            from .engine.world import (
                CharacterSheet,
                EntityType,
                ResourcePool,
                WorldPlayer,
            )

            # Load quest/flag data from DB
            quest_progress_data = (
                character.quest_progress if character.quest_progress else {}
            )
            completed_quests_data = (
                character.completed_quests if character.completed_quests else []
            )
            player_flags_data = character.player_flags if character.player_flags else {}

            # Initialize character sheet if they have a class
            character_sheet = None
            if character.character_class and character.data:
                class_id = character.data.get("class_id", character.character_class)
                learned_abilities = set(character.data.get("learned_abilities", []))

                # Get class template to initialize resource pools
                class_template = engine.class_system.get_class(class_id)
                resource_pools = {}
                if class_template and class_template.resources:
                    for resource_id, resource_def in class_template.resources.items():
                        resource_pools[resource_id] = ResourcePool(
                            resource_id=resource_id,
                            current=resource_def.max_amount,
                            max=resource_def.max_amount,
                            regen_per_second=resource_def.regen_rate,
                            last_regen_tick=0.0,
                        )

                character_sheet = CharacterSheet(
                    class_id=class_id,
                    level=character.level,
                    experience=character.experience,
                    learned_abilities=learned_abilities,
                    ability_loadout=[],
                    resource_pools=resource_pools,
                )

            world_player = WorldPlayer(
                id=character.id,
                entity_type=EntityType.PLAYER,
                name=character.name,
                room_id=character.current_room_id,
                character_class=character.character_class,
                level=character.level,
                max_health=character.max_health,
                current_health=character.current_health,
                strength=character.strength,
                dexterity=character.dexterity,
                intelligence=character.intelligence,
                vitality=character.vitality,
                armor_class=character.armor_class,
                max_energy=character.max_energy,
                current_energy=character.current_energy,
                experience=character.experience,
                on_move_effect=(
                    character.data.get("on_move_effect") if character.data else None
                ),
                quest_progress=quest_progress_data,
                completed_quests=set(completed_quests_data),
                player_flags=player_flags_data,
                character_sheet=character_sheet,
            )
            engine.world.players[player_id] = world_player

            # Make sure the room exists and add player to it
            if world_player.room_id in engine.world.rooms:
                engine.world.rooms[world_player.room_id].entities.add(player_id)

        # Store auth info in context for permission checks
        auth_info = {"user_id": user_id, "role": user_role}

        # Register this player with the engine
        event_queue = await engine.register_player(player_id)
        logger.info(
            "Player %s (user %s, role %s) connected via authenticated WebSocket",
            player_id,
            user_id,
            user_role,
        )

        # Send welcome message with auth info
        await websocket.send_json(
            {
                "type": "auth_success",
                "user_id": user_id,
                "player_id": player_id,
                "role": user_role,
            }
        )

        # Use a flag to track if player quit (vs disconnected)
        quit_flag = {"quit": False}

        send_task = asyncio.create_task(
            _ws_sender_with_quit(websocket, event_queue, quit_flag)
        )
        recv_task = asyncio.create_task(
            _ws_receiver_auth(websocket, engine, player_id, auth_info)
        )

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
            # Phase 16.4: Cleanup security tracking on disconnect
            ws_security_manager.cleanup_connection(connection_id)
            logger.info("Player %s disconnected (connection: %s)", player_id, connection_id)

        # If player used 'quit' command, loop back to character selection
        if quit_flag["quit"]:
            logger.info(
                "Player %s used quit, returning to character selection", player_id
            )
            # Clear active character so they go through selection again
            await auth_system.clear_active_character(user_id)
            # Re-register a new connection for the next character
            connection_id = str(uuid.uuid4())
            ws_security_manager.register_connection(connection_id, client_ip, user_id)
            continue
        else:
            # Real disconnect - exit the loop
            return


async def _ws_sender_with_quit(
    websocket: WebSocket,
    queue: asyncio.Queue,
    quit_flag: dict,
) -> None:
    """
    Sends events from the engine queue to the WebSocket.
    Detects quit events and sets the quit_flag to signal return to character selection.
    """
    try:
        while True:
            event = await queue.get()

            # Check if this is a quit event
            if event.get("type") == "quit":
                quit_flag["quit"] = True
                # Send the quit event to client first
                await websocket.send_json(event)
                # Then stop the sender (which will trigger return to char select)
                return

            await websocket.send_json(event)
    except Exception as e:
        logger.warning("Error in _ws_sender_with_quit: %s", e)


async def _ws_receiver_auth(
    websocket: WebSocket,
    engine: WorldEngine,
    player_id: str,
    auth_info: dict,
) -> None:
    """
    Receives messages from authenticated client and forwards commands.
    Sets auth_info on context for permission checks.
    Includes rate limiting for commands and chat (Phase 16.1).
    Phase 16.4: Adds message size and schema validation.
    """
    try:
        while True:
            # Phase 16.4: Receive raw text for size validation first
            raw_message = await websocket.receive_text()

            # Phase 16.4: Validate message (size, JSON, schema)
            valid, data, error = ws_security_manager.validate_message(raw_message)
            if not valid:
                logger.warning("Invalid message from player %s: %s", player_id, error)
                await websocket.send_json({
                    "type": "error",
                    "error": "invalid_message",
                    "message": error,
                })
                continue

            logger.info("Received WS message from player %s: %s", player_id, data)
            msg_type = data.get("type")

            # Phase 16.4: Handle ping messages for heartbeat
            if msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": data.get("timestamp"),
                })
                continue

            if msg_type == "command":
                text = data.get("text", "")

                # Rate limit check (Phase 16.1)
                # Check chat rate limit for chat commands, command rate limit otherwise
                if is_chat_command(text):
                    allowed, error_msg = ws_rate_limiter.check_chat_rate(player_id)
                else:
                    allowed, error_msg = ws_rate_limiter.check_command_rate(player_id)

                if not allowed:
                    # Send rate limit error to client
                    await websocket.send_json({
                        "type": "error",
                        "error": "rate_limit",
                        "message": error_msg,
                    })
                    continue

                # Set auth info on context before processing command
                engine.ctx.auth_info = auth_info
                await engine.submit_command(player_id, text)
            else:
                logger.debug("Ignoring unknown WS message type: %s", msg_type)
    except WebSocketDisconnect:
        logger.info("WebSocketDisconnect for player %s", player_id)
        ws_rate_limiter.disconnect(player_id)
    except Exception as exc:
        logger.exception("Error in _ws_receiver_auth for player %s: %s", player_id, exc)
        ws_rate_limiter.disconnect(player_id)


# Legacy WebSocket endpoint (deprecated - kept for backward compatibility)
@app.websocket("/ws/game")
async def game_ws(
    websocket: WebSocket,
    player_id: str = Query(
        ...,
        description="Player ID (from /players) - DEPRECATED: Use /ws/game/auth instead",
    ),
) -> None:
    """
    Legacy WebSocket endpoint (DEPRECATED).

    Use /ws/game/auth with a token instead for authenticated connections.

    Phase 16.4: Security hardening applied but with relaxed origin validation
    for backward compatibility.

    Phase 16.6: Added deprecation warnings and feature flag to disable legacy auth.
    - Sends deprecation warning on connect
    - Configurable via WS_LEGACY_AUTH_ENABLED environment variable
    - Supports sunset phases: warn, throttle, disabled

    - client connects: /ws/game?player_id=...
    - client sends: {"type": "command", "text": "look"}
    - server sends: events like {"type": "message", "player_id": "...", "text": "..."}

    This is single-process, multi-player: one WorldEngine shared by all connections.
    """
    # Phase 16.4: Get client IP for connection limiting
    client_ip = get_client_ip_from_websocket(websocket)
    connection_id = str(uuid.uuid4())

    # Phase 16.6: Check if legacy auth is enabled and validate connection
    valid, error = legacy_deprecation_manager.validate_connection(client_ip)
    if not valid:
        logger.warning(
            "Legacy WebSocket connection rejected (Phase 16.6): %s (IP: %s, player: %s)",
            error, client_ip, player_id
        )
        await websocket.close(code=4010, reason=error)
        return

    # Phase 16.4: Check IP connection limit only (no account for legacy)
    valid, error = ws_security_manager.connection_limiter.check_ip_limit(client_ip)
    if not valid:
        logger.warning(f"Legacy WebSocket connection rejected: {error} (IP: {client_ip})")
        await websocket.close(code=4003, reason=error)
        return

    await websocket.accept()

    # Phase 16.4: Register connection after acceptance
    ws_security_manager.register_connection(connection_id, client_ip)

    # Phase 16.6: Register with deprecation manager and log
    legacy_deprecation_manager.register_connection(client_ip, player_id)

    # Phase 16.6: Send deprecation warning to client
    if legacy_deprecation_manager.should_send_warning():
        try:
            await websocket.send_json(legacy_deprecation_manager.get_deprecation_message())
        except Exception as e:
            logger.warning("Failed to send deprecation warning: %s", e)

    # Ensure engine exists
    try:
        engine = get_world_engine()
        if engine is None:
            logger.error("World engine not initialized")
            ws_security_manager.cleanup_connection(connection_id)
            legacy_deprecation_manager.unregister_connection(client_ip, player_id)
            await websocket.close(
                code=1011, reason="Engine is None. World engine not ready"
            )
            return
    except RuntimeError:
        logger.error("World engine not initialized")
        ws_security_manager.cleanup_connection(connection_id)
        legacy_deprecation_manager.unregister_connection(client_ip, player_id)
        await websocket.close(code=1011, reason="Runtime Error: World engine not ready")
        return

    # Basic validation: ensure this player exists in the in-memory world
    if player_id not in engine.world.players:
        logger.info("WS connection rejected for unknown player %s", player_id)
        ws_security_manager.cleanup_connection(connection_id)
        legacy_deprecation_manager.unregister_connection(client_ip, player_id)
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
        # Phase 16.4: Cleanup security tracking
        ws_security_manager.cleanup_connection(connection_id)
        # Phase 16.6: Cleanup deprecation tracking
        legacy_deprecation_manager.unregister_connection(client_ip, player_id)
        logger.info("Player %s disconnected", player_id)


async def _ws_receiver(
    websocket: WebSocket,
    engine: WorldEngine,
    player_id: str,
) -> None:
    """
    Receives messages from the client and forwards commands to the engine.
    Includes rate limiting for commands and chat (Phase 16.1).
    Phase 16.4: Adds message validation.

    NOTE: This is the legacy endpoint handler. Use _ws_receiver_auth for new connections.
    """
    try:
        while True:
            # Phase 16.4: Receive raw text for validation
            raw_message = await websocket.receive_text()

            # Phase 16.4: Validate message
            valid, data, error = ws_security_manager.validate_message(raw_message)
            if not valid:
                logger.warning("Invalid message from player %s: %s", player_id, error)
                await websocket.send_json({
                    "type": "error",
                    "error": "invalid_message",
                    "message": error,
                })
                continue

            logger.info("Received WS message from player %s: %s", player_id, data)
            msg_type = data.get("type")

            # Phase 16.4: Handle ping messages
            if msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": data.get("timestamp"),
                })
                continue

            if msg_type == "command":
                text = data.get("text", "")

                # Rate limit check (Phase 16.1)
                # Check chat rate limit for chat commands, command rate limit otherwise
                if is_chat_command(text):
                    allowed, error_msg = ws_rate_limiter.check_chat_rate(player_id)
                else:
                    allowed, error_msg = ws_rate_limiter.check_command_rate(player_id)

                if not allowed:
                    # Send rate limit error to client
                    await websocket.send_json({
                        "type": "error",
                        "error": "rate_limit",
                        "message": error_msg,
                    })
                    continue

                await engine.submit_command(player_id, text)
            else:
                # Unknown message types can be ignored or handled later
                logger.debug("Ignoring unknown WS message type: %s", msg_type)
    except WebSocketDisconnect:
        # Normal disconnect; let game_ws handle cleanup
        logger.info("WebSocketDisconnect for player %s", player_id)
        ws_rate_limiter.disconnect(player_id)
    except Exception as exc:
        logger.exception("Error in _ws_receiver for player %s: %s", player_id, exc)
        ws_rate_limiter.disconnect(player_id)


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
