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
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import engine, get_session, AsyncSessionLocal
from .models import Base, Room, Player, PlayerInventory
from .engine.loader import load_world
from .engine.engine import WorldEngine

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
    
    logger.info("Loaded world: %d rooms, %d players", len(world.rooms), len(world.players))
    if len(world.rooms) > 0:
        sample_rooms = list(world.rooms.keys())[:5]
        logger.info("Sample room IDs: %s", sample_rooms)

    # 4) Create engine and start game loop
    engine_instance = WorldEngine(world, db_session_factory=AsyncSessionLocal)
    app.state.world_engine = engine_instance
    app.state.engine_task = asyncio.create_task(engine_instance.game_loop())
    
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


# ---------- WebSocket Endpoint ----------

@app.websocket("/ws/game")
async def game_ws(
    websocket: WebSocket,
    player_id: str = Query(..., description="Player ID (from /players)"),
) -> None:
    """
    Simple WebSocket endpoint:

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
