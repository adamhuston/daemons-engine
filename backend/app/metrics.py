# backend/app/metrics.py
"""
Phase 8: Prometheus Metrics for Daemons MUD Engine

Provides Prometheus-compatible metrics for monitoring:
- Player counts and session metrics
- Game world statistics (NPCs, rooms, items)
- Combat and event processing
- System performance (command latency, tick timing)
- Content reload tracking

Metrics are exposed via GET /api/admin/server/metrics endpoint.
"""

import time
from typing import Optional

from prometheus_client import (CONTENT_TYPE_LATEST, CollectorRegistry, Counter,
                               Gauge, Histogram, Info, generate_latest)

# ============================================================================
# Custom Registry
# ============================================================================

# Use a custom registry to avoid polluting the default one
METRICS_REGISTRY = CollectorRegistry()


# ============================================================================
# Server Info
# ============================================================================

server_info = Info(
    "daemons_server", "Daemons MUD Engine server information", registry=METRICS_REGISTRY
)


# ============================================================================
# Player Metrics
# ============================================================================

players_online = Gauge(
    "daemons_players_online",
    "Number of players currently connected",
    registry=METRICS_REGISTRY,
)

players_total = Counter(
    "daemons_players_total",
    "Total number of player connections since server start",
    registry=METRICS_REGISTRY,
)

players_in_combat = Gauge(
    "daemons_players_in_combat",
    "Number of players currently in combat",
    registry=METRICS_REGISTRY,
)

player_session_duration = Histogram(
    "daemons_player_session_duration_seconds",
    "Duration of player sessions in seconds",
    buckets=[60, 300, 600, 1800, 3600, 7200, 14400, 28800],  # 1min to 8hr
    registry=METRICS_REGISTRY,
)


# ============================================================================
# World State Metrics
# ============================================================================

npcs_alive = Gauge(
    "daemons_npcs_alive",
    "Number of living NPCs in the world",
    registry=METRICS_REGISTRY,
)

npcs_total = Gauge(
    "daemons_npcs_total",
    "Total number of NPCs in the world (alive + dead)",
    registry=METRICS_REGISTRY,
)

rooms_total = Gauge(
    "daemons_rooms_total",
    "Total number of rooms in the world",
    registry=METRICS_REGISTRY,
)

rooms_occupied = Gauge(
    "daemons_rooms_occupied",
    "Number of rooms with at least one player",
    registry=METRICS_REGISTRY,
)

areas_total = Gauge(
    "daemons_areas_total",
    "Total number of areas in the world",
    registry=METRICS_REGISTRY,
)

items_total = Gauge(
    "daemons_items_total",
    "Total number of item instances in the world",
    registry=METRICS_REGISTRY,
)


# ============================================================================
# Combat Metrics
# ============================================================================

combat_sessions_active = Gauge(
    "daemons_combat_sessions_active",
    "Number of active combat sessions",
    registry=METRICS_REGISTRY,
)

combat_sessions_total = Counter(
    "daemons_combat_sessions_total",
    "Total combat sessions since server start",
    registry=METRICS_REGISTRY,
)

combat_damage_dealt = Counter(
    "daemons_combat_damage_dealt_total",
    "Total damage dealt in combat",
    ["attacker_type"],  # player, npc
    registry=METRICS_REGISTRY,
)

npc_deaths = Counter(
    "daemons_npc_deaths_total",
    "Total NPC deaths since server start",
    registry=METRICS_REGISTRY,
)

player_deaths = Counter(
    "daemons_player_deaths_total",
    "Total player deaths since server start",
    registry=METRICS_REGISTRY,
)


# ============================================================================
# Event & Command Processing Metrics
# ============================================================================

commands_processed = Counter(
    "daemons_commands_processed_total",
    "Total commands processed by type",
    ["command"],
    registry=METRICS_REGISTRY,
)

command_latency = Histogram(
    "daemons_command_latency_seconds",
    "Command processing latency in seconds",
    ["command"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    registry=METRICS_REGISTRY,
)

scheduled_events = Gauge(
    "daemons_scheduled_events",
    "Number of events scheduled in the time manager",
    registry=METRICS_REGISTRY,
)

events_processed = Counter(
    "daemons_events_processed_total",
    "Total events processed by type",
    ["event_type"],
    registry=METRICS_REGISTRY,
)


# ============================================================================
# System Performance Metrics
# ============================================================================

tick_duration = Histogram(
    "daemons_tick_duration_seconds",
    "Game tick processing duration in seconds",
    ["tick_type"],  # npc_ai, respawn, combat, etc.
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
    registry=METRICS_REGISTRY,
)

websocket_messages_sent = Counter(
    "daemons_websocket_messages_sent_total",
    "Total WebSocket messages sent to clients",
    registry=METRICS_REGISTRY,
)

websocket_messages_received = Counter(
    "daemons_websocket_messages_received_total",
    "Total WebSocket messages received from clients",
    registry=METRICS_REGISTRY,
)

db_query_duration = Histogram(
    "daemons_db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],  # select, insert, update, delete
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
    registry=METRICS_REGISTRY,
)


# ============================================================================
# Content Reload Metrics
# ============================================================================

content_reloads = Counter(
    "daemons_content_reloads_total",
    "Total content reload operations by type",
    ["content_type"],  # areas, rooms, items, npcs, npc_spawns
    registry=METRICS_REGISTRY,
)

content_reload_errors = Counter(
    "daemons_content_reload_errors_total",
    "Total content reload errors by type",
    ["content_type"],
    registry=METRICS_REGISTRY,
)


# ============================================================================
# Server State Metrics
# ============================================================================

server_uptime = Gauge(
    "daemons_server_uptime_seconds",
    "Server uptime in seconds",
    registry=METRICS_REGISTRY,
)

maintenance_mode = Gauge(
    "daemons_maintenance_mode",
    "1 if maintenance mode is enabled, 0 otherwise",
    registry=METRICS_REGISTRY,
)


# ============================================================================
# Helper Functions
# ============================================================================

_server_start_time: Optional[float] = None


def init_metrics(version: str = "unknown", environment: str = "development") -> None:
    """Initialize metrics with server information."""
    global _server_start_time
    _server_start_time = time.time()

    server_info.info(
        {
            "version": version,
            "environment": environment,
            "engine": "daemons",
            "started_at": str(_server_start_time),
        }
    )


def update_server_uptime() -> None:
    """Update the server uptime gauge."""
    if _server_start_time:
        server_uptime.set(time.time() - _server_start_time)


def update_world_metrics(
    online_players: int,
    combat_players: int,
    alive_npcs: int,
    total_npcs: int,
    total_rooms: int,
    occupied_rooms: int,
    total_areas: int,
    total_items: int,
    active_combats: int,
    pending_events: int,
    is_maintenance: bool,
) -> None:
    """Update all world state metrics at once."""
    players_online.set(online_players)
    players_in_combat.set(combat_players)
    npcs_alive.set(alive_npcs)
    npcs_total.set(total_npcs)
    rooms_total.set(total_rooms)
    rooms_occupied.set(occupied_rooms)
    areas_total.set(total_areas)
    items_total.set(total_items)
    combat_sessions_active.set(active_combats)
    scheduled_events.set(pending_events)
    maintenance_mode.set(1 if is_maintenance else 0)
    update_server_uptime()


def record_command(command: str, duration_seconds: float) -> None:
    """Record a command execution with timing."""
    commands_processed.labels(command=command).inc()
    command_latency.labels(command=command).observe(duration_seconds)


def record_tick(tick_type: str, duration_seconds: float) -> None:
    """Record a game tick execution with timing."""
    tick_duration.labels(tick_type=tick_type).observe(duration_seconds)


def record_event(event_type: str) -> None:
    """Record an event being processed."""
    events_processed.labels(event_type=event_type).inc()


def record_content_reload(content_type: str, success: bool = True) -> None:
    """Record a content reload operation."""
    content_reloads.labels(content_type=content_type).inc()
    if not success:
        content_reload_errors.labels(content_type=content_type).inc()


def record_player_connect() -> None:
    """Record a player connection."""
    players_total.inc()


def record_player_disconnect(session_duration_seconds: float) -> None:
    """Record a player disconnection with session duration."""
    player_session_duration.observe(session_duration_seconds)


def record_combat_start() -> None:
    """Record a combat session starting."""
    combat_sessions_total.inc()


def record_damage(attacker_type: str, amount: float) -> None:
    """Record damage dealt in combat."""
    combat_damage_dealt.labels(attacker_type=attacker_type).inc(amount)


def record_npc_death() -> None:
    """Record an NPC death."""
    npc_deaths.inc()


def record_player_death() -> None:
    """Record a player death."""
    player_deaths.inc()


def record_websocket_sent() -> None:
    """Record a WebSocket message sent."""
    websocket_messages_sent.inc()


def record_websocket_received() -> None:
    """Record a WebSocket message received."""
    websocket_messages_received.inc()


def record_db_query(operation: str, duration_seconds: float) -> None:
    """Record a database query with timing."""
    db_query_duration.labels(operation=operation).observe(duration_seconds)


def get_metrics() -> bytes:
    """
    Generate Prometheus-format metrics output.

    Returns:
        bytes: Prometheus text format metrics
    """
    return generate_latest(METRICS_REGISTRY)


def get_metrics_content_type() -> str:
    """Get the content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST
