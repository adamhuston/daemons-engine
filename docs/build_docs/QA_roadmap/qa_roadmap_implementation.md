# QA Roadmap Implementation Plan

This document provides detailed implementation guidance for the debugging infrastructure proposed in [qa_roadmap.md](qa_roadmap.md). It is intended to serve as a comprehensive context document for LLM agents or developers implementing this solution.

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Phase 1: Enhanced Backend Instrumentation](#phase-1-enhanced-backend-instrumentation)
4. [Phase 2: Debugging Client Implementation](#phase-2-debugging-client-implementation)
5. [Phase 3: External Monitoring Integration](#phase-3-external-monitoring-integration)
6. [Software Requirements](#software-requirements)
7. [File Structure](#file-structure)
8. [Implementation Tasks](#implementation-tasks)

---

## Executive Summary

The Daemons engine has comprehensive test coverage but experiences runtime bugs due to gaps in property-based testing, load testing, and race condition detection. This implementation plan describes a **hybrid debugging approach** that:

1. **Extends existing backend infrastructure** (structlog, Prometheus metrics, Admin API)
2. **Creates a concurrent debugging client** that monitors real-time events and errors
3. **Integrates external error tracking** for pattern analysis and alerting

---

## Architecture Overview

### Existing Infrastructure (Leverage Points)

| Component | Location | Description |
|-----------|----------|-------------|
| **Structured Logging** | `backend/daemons/logging.py` | structlog-based with AdminAuditLogger, GameEventLogger, PerformanceLogger |
| **Prometheus Metrics** | `backend/daemons/metrics.py` | Comprehensive game metrics with custom registry |
| **Admin REST API** | `backend/daemons/routes/admin.py` | `/api/admin/*` endpoints for server inspection |
| **WebSocket Protocol** | `backend/daemons/main.py` | Event-driven messaging with per-player queues |
| **Event Dispatcher** | `backend/daemons/engine/systems/events.py` | Scoped event routing (player, room, group, tell) |
| **WebSocket Security** | `backend/daemons/websocket_security.py` | Connection limits, message validation, origin checks |

### Key Dependencies (Already Installed)

```
structlog>=25.3.0          # Structured logging
prometheus-client>=0.22.1  # Metrics collection
fastapi>=0.122.0           # Web framework
websockets>=15.0.1         # WebSocket support
httpx>=0.28.1              # HTTP client
flet>=0.21.0               # GUI framework (optional, for debugging client)
```

---

## Phase 1: Enhanced Backend Instrumentation

### 1.1 Debug Event Logger ✅ COMPLETE

**Purpose**: Create a specialized logger for debugging events that can be streamed to debugging clients.

**File**: `backend/daemons/logging.py`

**Status**: Implemented on 2026-02-18

**Implementation Notes**:
- Added `DebugEventLogger` class with circular buffer (1000 events default)
- Subscription mechanism via `asyncio.Queue` for real-time streaming
- Event types: `error`, `warning`, `performance`, `race_condition`, `connection`, `state_conflict`
- Severity levels: `debug`, `info`, `warning`, `error`, `critical`
- Global instance `debug_events` available for import
- Helper methods for common use cases:
  - `record_error()` - General error recording with exception capture
  - `record_warning()` - Warning events
  - `record_performance_anomaly()` - Latency threshold monitoring
  - `record_race_condition_indicator()` - Race condition detection
  - `record_connection_event()` - WebSocket connection events
  - `record_state_conflict()` - State consistency issues
  - `record_ability_error()` - Ability execution failures
  - `record_command_error()` - Command processing failures
  - `record_websocket_error()` - WebSocket-specific errors
- API for debugging clients:
  - `subscribe(subscriber_id)` - Get async queue for real-time events
  - `unsubscribe(subscriber_id)` - Remove subscription
  - `get_recent_events()` - Query buffered events with filters
  - `get_event_counts()` - Get event statistics by type/severity

**Reference Implementation** (see actual code in `logging.py`):

```python
class DebugEventLogger:
    """
    Specialized logger for debug events that can be streamed to debugging clients.

    Captures:
    - Errors and exceptions with full context
    - Performance anomalies (slow commands, high latency)
    - Race condition indicators (out-of-order events, state conflicts)
    - WebSocket connection issues
    """

    def __init__(self):
        self.logger = get_logger("daemons.debug.events")
        self._event_buffer: collections.deque = collections.deque(maxlen=1000)
        self._subscribers: set[asyncio.Queue] = set()

    def log_error(
        self,
        error_type: str,
        error_message: str,
        *,
        player_id: str = None,
        room_id: str = None,
        command: str = None,
        stack_trace: str = None,
        context: dict = None,
    ) -> None:
        """Log an error event and notify subscribers."""
        event = {
            "type": "debug_error",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error_type": error_type,
            "error_message": error_message,
            "player_id": player_id,
            "room_id": room_id,
            "command": command,
            "stack_trace": stack_trace,
            "context": context or {},
        }
        self._event_buffer.append(event)
        self._notify_subscribers(event)
        self.logger.error("Debug error", **event)

    def log_performance_anomaly(
        self,
        metric_name: str,
        expected_ms: float,
        actual_ms: float,
        *,
        player_id: str = None,
        context: dict = None,
    ) -> None:
        """Log performance anomaly (e.g., slow command execution)."""
        event = {
            "type": "debug_performance",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metric_name": metric_name,
            "expected_ms": expected_ms,
            "actual_ms": actual_ms,
            "deviation_pct": ((actual_ms - expected_ms) / expected_ms) * 100,
            "player_id": player_id,
            "context": context or {},
        }
        self._event_buffer.append(event)
        self._notify_subscribers(event)
        self.logger.warning("Performance anomaly", **event)

    def log_race_condition_indicator(
        self,
        indicator_type: str,
        description: str,
        *,
        entities_involved: list[str] = None,
        context: dict = None,
    ) -> None:
        """Log potential race condition indicators."""
        event = {
            "type": "debug_race_condition",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "indicator_type": indicator_type,
            "description": description,
            "entities_involved": entities_involved or [],
            "context": context or {},
        }
        self._event_buffer.append(event)
        self._notify_subscribers(event)
        self.logger.warning("Race condition indicator", **event)

    def subscribe(self, queue: asyncio.Queue) -> None:
        """Subscribe to debug events."""
        self._subscribers.add(queue)

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from debug events."""
        self._subscribers.discard(queue)

    def get_recent_events(self, count: int = 100) -> list[dict]:
        """Get recent debug events from buffer."""
        return list(self._event_buffer)[-count:]

    def _notify_subscribers(self, event: dict) -> None:
        """Push event to all subscribers."""
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Don't block on slow subscribers

# Global instance
debug_events = DebugEventLogger()
```

### 1.2 Debug Metrics Extension

**Purpose**: Add new Prometheus metrics specifically for debugging and anomaly detection.

**File**: `backend/daemons/metrics.py`

**Add these metrics**:

```python
# ============================================================================
# Debug & Anomaly Detection Metrics
# ============================================================================

errors_total = Counter(
    "daemons_errors_total",
    "Total errors by type and severity",
    ["error_type", "severity"],
    registry=METRICS_REGISTRY,
)

race_condition_indicators = Counter(
    "daemons_race_condition_indicators_total",
    "Potential race condition indicators detected",
    ["indicator_type"],
    registry=METRICS_REGISTRY,
)

websocket_connection_errors = Counter(
    "daemons_websocket_connection_errors_total",
    "WebSocket connection errors by type",
    ["error_type"],
    registry=METRICS_REGISTRY,
)

ability_execution_errors = Counter(
    "daemons_ability_execution_errors_total",
    "Ability execution failures by ability and error type",
    ["ability_id", "error_type"],
    registry=METRICS_REGISTRY,
)

command_errors = Counter(
    "daemons_command_errors_total",
    "Command processing errors by command type",
    ["command"],
    registry=METRICS_REGISTRY,
)

state_conflicts = Counter(
    "daemons_state_conflicts_total",
    "State conflict incidents (potential race conditions)",
    ["conflict_type"],
    registry=METRICS_REGISTRY,
)

# Latency percentiles for anomaly detection
command_latency_summary = Summary(
    "daemons_command_latency_summary",
    "Command latency summary with percentiles",
    ["command"],
    registry=METRICS_REGISTRY,
)

# Helper functions for debug metrics
def record_error(error_type: str, severity: str = "error") -> None:
    """Record an error occurrence."""
    errors_total.labels(error_type=error_type, severity=severity).inc()

def record_race_condition_indicator(indicator_type: str) -> None:
    """Record a potential race condition indicator."""
    race_condition_indicators.labels(indicator_type=indicator_type).inc()

def record_ability_error(ability_id: str, error_type: str) -> None:
    """Record an ability execution error."""
    ability_execution_errors.labels(ability_id=ability_id, error_type=error_type).inc()

def record_websocket_error(error_type: str) -> None:
    """Record a WebSocket connection error."""
    websocket_connection_errors.labels(error_type=error_type).inc()
```

### 1.3 Debug Admin API Endpoints

**Purpose**: Expose debugging information via REST API for the debugging client.

**File**: `backend/daemons/routes/admin.py`

**Add these endpoints**:

```python
# ============================================================================
# Debug Endpoints (Phase QA)
# ============================================================================

class DebugEventFilter(BaseModel):
    """Filter criteria for debug events."""
    event_types: list[str] | None = Field(None, description="Filter by event types")
    player_id: str | None = Field(None, description="Filter by player ID")
    since_timestamp: str | None = Field(None, description="Events since ISO timestamp")
    limit: int = Field(100, ge=1, le=1000, description="Max events to return")


@router.get("/debug/events")
async def get_debug_events(
    event_type: str | None = None,
    player_id: str | None = None,
    limit: int = 100,
    admin: dict = Depends(get_current_admin),
) -> dict:
    """
    Get recent debug events from the buffer.

    Requires: MODERATOR+
    """
    from daemons.logging import debug_events

    events = debug_events.get_recent_events(limit)

    # Apply filters
    if event_type:
        events = [e for e in events if e.get("type") == event_type]
    if player_id:
        events = [e for e in events if e.get("player_id") == player_id]

    return {
        "success": True,
        "events": events,
        "total_count": len(events),
    }


@router.get("/debug/error-summary")
async def get_error_summary(
    hours: int = 24,
    admin: dict = Depends(get_current_admin),
) -> dict:
    """
    Get a summary of errors over the specified time period.

    Requires: MODERATOR+
    """
    from daemons.logging import debug_events
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat() + "Z"

    events = debug_events.get_recent_events(1000)
    recent_errors = [
        e for e in events
        if e.get("type") == "debug_error"
        and e.get("timestamp", "") >= cutoff_str
    ]

    # Aggregate by error type
    error_counts: dict[str, int] = {}
    for e in recent_errors:
        error_type = e.get("error_type", "unknown")
        error_counts[error_type] = error_counts.get(error_type, 0) + 1

    return {
        "success": True,
        "period_hours": hours,
        "total_errors": len(recent_errors),
        "errors_by_type": error_counts,
        "recent_errors": recent_errors[:10],  # Last 10 for preview
    }


@router.get("/debug/performance-anomalies")
async def get_performance_anomalies(
    threshold_pct: float = 200.0,  # 200% = 3x expected
    limit: int = 50,
    admin: dict = Depends(get_current_admin),
) -> dict:
    """
    Get recent performance anomalies exceeding threshold.

    Requires: MODERATOR+
    """
    from daemons.logging import debug_events

    events = debug_events.get_recent_events(500)
    anomalies = [
        e for e in events
        if e.get("type") == "debug_performance"
        and e.get("deviation_pct", 0) >= threshold_pct
    ]

    return {
        "success": True,
        "threshold_pct": threshold_pct,
        "anomalies": anomalies[:limit],
        "total_count": len(anomalies),
    }


@router.get("/debug/connection-stats")
async def get_connection_stats(
    admin: dict = Depends(get_current_admin),
) -> dict:
    """
    Get WebSocket connection statistics.

    Requires: MODERATOR+
    """
    from daemons.websocket_security import ws_security_manager

    limiter = ws_security_manager.connection_limiter

    return {
        "success": True,
        "connections_by_ip": {
            ip: len(conns)
            for ip, conns in limiter._ip_connections.items()
        },
        "connections_by_account": {
            acc: len(conns)
            for acc, conns in limiter._account_connections.items()
        },
        "total_active_connections": len(limiter._connection_info),
        "config": {
            "max_per_ip": limiter.max_per_ip,
            "max_per_account": limiter.max_per_account,
        },
    }


class LoadTestConfig(BaseModel):
    """Configuration for load testing."""
    num_connections: int = Field(10, ge=1, le=100, description="Number of concurrent connections")
    commands_per_connection: int = Field(10, ge=1, le=100, description="Commands per connection")
    delay_between_commands_ms: int = Field(100, ge=0, le=5000, description="Delay between commands")


@router.post("/debug/load-test")
async def trigger_load_test(
    config: LoadTestConfig,
    admin: dict = Depends(require_permission(Permission.SERVER_COMMANDS)),
) -> dict:
    """
    Trigger a controlled load test (ADMIN only).

    This endpoint is intentionally limited to prevent abuse.
    """
    # This would integrate with the debugging client for load testing
    # For now, return configuration acknowledgment
    return {
        "success": True,
        "message": "Load test configuration accepted",
        "config": config.model_dump(),
        "note": "Execute load test via debugging client with this configuration",
    }
```

### 1.4 Debug WebSocket Endpoint

**Purpose**: Provide a dedicated WebSocket endpoint for real-time debug event streaming.

**File**: `backend/daemons/main.py`

**Add this endpoint**:

```python
@app.websocket("/ws/debug")
async def debug_ws(
    websocket: WebSocket,
    token: str | None = Query(None),
) -> None:
    """
    Debug WebSocket endpoint for real-time event monitoring.

    Requires MODERATOR+ role.

    Streams:
    - All debug events (errors, performance anomalies, race conditions)
    - Optionally: All game events (for debugging client monitoring)
    """
    # Extract and verify token
    ws_protocols = websocket.headers.get("sec-websocket-protocol", "")
    header_token = None
    subprotocol = None

    if ws_protocols:
        protocols = [p.strip() for p in ws_protocols.split(",")]
        if len(protocols) >= 2 and protocols[0] == "access_token":
            header_token = protocols[1]
            subprotocol = "access_token"

    effective_token = header_token or token

    if not effective_token:
        await websocket.close(code=4001, reason="No token provided")
        return

    claims = verify_access_token(effective_token)
    if not claims:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # Check for admin privileges
    role = claims.get("role", "player")
    if role not in [UserRole.MODERATOR.value, UserRole.GAME_MASTER.value, UserRole.ADMIN.value]:
        await websocket.close(code=4003, reason="Admin privileges required")
        return

    # Accept connection
    if subprotocol:
        await websocket.accept(subprotocol=subprotocol)
    else:
        await websocket.accept()

    logger.info("Debug WebSocket connected for user %s (role: %s)", claims["user_id"], role)

    # Create event queue and subscribe
    from daemons.logging import debug_events
    event_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    debug_events.subscribe(event_queue)

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "debug_connected",
            "user_id": claims["user_id"],
            "role": role,
        })

        # Stream events
        while True:
            event = await event_queue.get()
            await websocket.send_json(event)

    except WebSocketDisconnect:
        logger.info("Debug WebSocket disconnected")
    finally:
        debug_events.unsubscribe(event_queue)
```

---

## Phase 2: Debugging Client Implementation

### 2.1 Client Architecture

The debugging client is a standalone Python application that connects to the Daemons backend via:

1. **Debug WebSocket** (`/ws/debug`) - Real-time debug event stream
2. **Admin REST API** (`/api/admin/*`) - Server state inspection and control
3. **Game WebSocket** (`/ws/game/auth`) - Optional: Monitor actual game events

### 2.2 Core Client Structure

**File**: `tools/debug_client/debug_client.py`

```python
#!/usr/bin/env python3
"""
Daemons Debugging Client

A concurrent debugging client that monitors the Daemons engine for:
- Real-time errors and exceptions
- Performance anomalies
- Race condition indicators
- WebSocket connection stability
- Load testing capabilities

Usage:
    python debug_client.py --server http://localhost:8000 --token <admin_token>
"""

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import httpx
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class DebugClientConfig:
    """Configuration for the debugging client."""
    server_url: str
    access_token: str
    enable_game_monitor: bool = False
    log_file: str | None = None
    error_threshold: int = 10  # Alert after N errors in window
    performance_threshold_pct: float = 200.0  # Alert on 200%+ deviation
    reconnect_delay: float = 5.0


@dataclass
class DebugStats:
    """Accumulated debugging statistics."""
    errors_by_type: dict[str, int] = field(default_factory=dict)
    performance_anomalies: int = 0
    race_condition_indicators: int = 0
    connection_drops: int = 0
    total_events: int = 0
    session_start: datetime = field(default_factory=datetime.utcnow)

    def record_error(self, error_type: str) -> None:
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
        self.total_events += 1

    def record_performance_anomaly(self) -> None:
        self.performance_anomalies += 1
        self.total_events += 1

    def record_race_condition(self) -> None:
        self.race_condition_indicators += 1
        self.total_events += 1

    def summary(self) -> dict:
        duration = (datetime.utcnow() - self.session_start).total_seconds()
        return {
            "session_duration_seconds": duration,
            "total_events": self.total_events,
            "errors_by_type": self.errors_by_type,
            "performance_anomalies": self.performance_anomalies,
            "race_condition_indicators": self.race_condition_indicators,
            "connection_drops": self.connection_drops,
        }


class DebugClient:
    """
    Main debugging client that connects to Daemons backend.
    """

    def __init__(self, config: DebugClientConfig):
        self.config = config
        self.stats = DebugStats()
        self._running = False
        self._log_file = None
        self._event_handlers: list[Callable] = []

    async def connect(self) -> None:
        """
        Establish connections to the backend.
        """
        self._running = True

        if self.config.log_file:
            self._log_file = open(self.config.log_file, "a")
            logger.info(f"Logging to file: {self.config.log_file}")

        # Run debug monitor (and optionally game monitor) concurrently
        tasks = [self._debug_monitor()]

        if self.config.enable_game_monitor:
            tasks.append(self._game_monitor())

        try:
            await asyncio.gather(*tasks)
        finally:
            if self._log_file:
                self._log_file.close()

    async def _debug_monitor(self) -> None:
        """
        Monitor the debug WebSocket for real-time events.
        """
        ws_url = self.config.server_url.replace("http://", "ws://").replace("https://", "wss://")
        debug_url = f"{ws_url}/ws/debug"

        while self._running:
            try:
                logger.info(f"Connecting to debug WebSocket: {debug_url}")

                async with websockets.connect(
                    debug_url,
                    additional_headers={"Authorization": f"Bearer {self.config.access_token}"},
                    subprotocols=["access_token", self.config.access_token],
                ) as ws:
                    logger.info("Debug WebSocket connected")

                    async for message in ws:
                        event = json.loads(message)
                        await self._handle_debug_event(event)

            except websockets.ConnectionClosed as e:
                logger.warning(f"Debug WebSocket closed: {e}")
                self.stats.connection_drops += 1
            except Exception as e:
                logger.error(f"Debug WebSocket error: {e}")
                self.stats.connection_drops += 1

            if self._running:
                logger.info(f"Reconnecting in {self.config.reconnect_delay}s...")
                await asyncio.sleep(self.config.reconnect_delay)

    async def _handle_debug_event(self, event: dict) -> None:
        """
        Process a debug event.
        """
        event_type = event.get("type", "unknown")

        # Log to file
        if self._log_file:
            self._log_file.write(json.dumps(event) + "\n")
            self._log_file.flush()

        # Update stats
        if event_type == "debug_error":
            error_type = event.get("error_type", "unknown")
            self.stats.record_error(error_type)
            logger.error(f"🔴 ERROR [{error_type}]: {event.get('error_message')}")

        elif event_type == "debug_performance":
            self.stats.record_performance_anomaly()
            deviation = event.get("deviation_pct", 0)
            if deviation >= self.config.performance_threshold_pct:
                logger.warning(
                    f"⚡ SLOW: {event.get('metric_name')} took {event.get('actual_ms'):.1f}ms "
                    f"(expected {event.get('expected_ms'):.1f}ms, +{deviation:.0f}%)"
                )

        elif event_type == "debug_race_condition":
            self.stats.record_race_condition()
            logger.warning(f"⚠️ RACE: {event.get('indicator_type')} - {event.get('description')}")

        elif event_type == "debug_connected":
            logger.info(f"✅ Debug session established (role: {event.get('role')})")

        # Notify registered handlers
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    def add_event_handler(self, handler: Callable) -> None:
        """Register a callback for debug events."""
        self._event_handlers.append(handler)

    async def fetch_server_status(self) -> dict | None:
        """Fetch current server status via Admin API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.config.server_url}/api/admin/server/status",
                    headers={"Authorization": f"Bearer {self.config.access_token}"},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch server status: {e}")
            return None

    async def fetch_error_summary(self, hours: int = 24) -> dict | None:
        """Fetch error summary via Admin API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.config.server_url}/api/admin/debug/error-summary",
                    params={"hours": hours},
                    headers={"Authorization": f"Bearer {self.config.access_token}"},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch error summary: {e}")
            return None

    def print_stats(self) -> None:
        """Print current session statistics."""
        summary = self.stats.summary()
        logger.info("=" * 50)
        logger.info("DEBUG SESSION STATISTICS")
        logger.info("=" * 50)
        logger.info(f"Duration: {summary['session_duration_seconds']:.0f}s")
        logger.info(f"Total Events: {summary['total_events']}")
        logger.info(f"Performance Anomalies: {summary['performance_anomalies']}")
        logger.info(f"Race Condition Indicators: {summary['race_condition_indicators']}")
        logger.info(f"Connection Drops: {summary['connection_drops']}")
        logger.info("Errors by Type:")
        for error_type, count in summary['errors_by_type'].items():
            logger.info(f"  - {error_type}: {count}")
        logger.info("=" * 50)

    def stop(self) -> None:
        """Stop the client gracefully."""
        self._running = False


async def main():
    parser = argparse.ArgumentParser(description="Daemons Debugging Client")
    parser.add_argument("--server", required=True, help="Server URL (e.g., http://localhost:8000)")
    parser.add_argument("--token", required=True, help="Admin access token")
    parser.add_argument("--log-file", help="Path to log file for debug events")
    parser.add_argument("--game-monitor", action="store_true", help="Also monitor game events")

    args = parser.parse_args()

    config = DebugClientConfig(
        server_url=args.server,
        access_token=args.token,
        log_file=args.log_file,
        enable_game_monitor=args.game_monitor,
    )

    client = DebugClient(config)

    try:
        await client.connect()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        client.stop()
        client.print_stats()


if __name__ == "__main__":
    asyncio.run(main())
```

### 2.3 Load Testing Module

**File**: `tools/debug_client/load_tester.py`

```python
"""
Load Testing Module for Daemons Engine

Provides controlled load testing capabilities:
- Concurrent WebSocket connections
- Automated command sequences
- Latency measurement
- Stress testing patterns
"""

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, field

import websockets
import httpx

logger = logging.getLogger(__name__)


@dataclass
class LoadTestConfig:
    """Configuration for load testing."""
    server_url: str
    num_connections: int = 10
    commands_per_connection: int = 20
    delay_between_commands_ms: int = 100
    command_pool: list[str] = field(default_factory=lambda: [
        "look", "stats", "north", "south", "east", "west",
        "inventory", "effects", "time", "weather",
    ])


@dataclass
class LoadTestResult:
    """Results from a load test run."""
    total_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    total_commands: int = 0
    successful_commands: int = 0
    failed_commands: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return sum(self.latencies_ms) / len(self.latencies_ms)

    @property
    def p95_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def p99_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]


class LoadTester:
    """
    Executes load tests against the Daemons server.
    """

    def __init__(self, config: LoadTestConfig, access_tokens: list[str]):
        self.config = config
        self.access_tokens = access_tokens
        self.result = LoadTestResult()

    async def run(self) -> LoadTestResult:
        """
        Execute the load test.
        """
        start_time = time.time()

        # Create connection tasks
        tasks = []
        for i in range(self.config.num_connections):
            token = self.access_tokens[i % len(self.access_tokens)]
            tasks.append(self._run_connection(i, token))

        # Run all connections concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        self.result.duration_seconds = time.time() - start_time
        return self.result

    async def _run_connection(self, conn_id: int, token: str) -> None:
        """
        Run a single test connection.
        """
        self.result.total_connections += 1
        ws_url = self.config.server_url.replace("http://", "ws://").replace("https://", "wss://")
        game_url = f"{ws_url}/ws/game/auth"

        try:
            async with websockets.connect(
                game_url,
                subprotocols=["access_token", token],
            ) as ws:
                self.result.successful_connections += 1
                logger.debug(f"Connection {conn_id} established")

                # Execute command sequence
                for _ in range(self.config.commands_per_connection):
                    command = random.choice(self.config.command_pool)

                    try:
                        start = time.time()
                        await ws.send(json.dumps({"type": "command", "text": command}))

                        # Wait for response (with timeout)
                        response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        latency = (time.time() - start) * 1000

                        self.result.latencies_ms.append(latency)
                        self.result.total_commands += 1
                        self.result.successful_commands += 1

                    except asyncio.TimeoutError:
                        self.result.total_commands += 1
                        self.result.failed_commands += 1
                        self.result.errors.append(f"Conn {conn_id}: Command timeout")
                    except Exception as e:
                        self.result.total_commands += 1
                        self.result.failed_commands += 1
                        self.result.errors.append(f"Conn {conn_id}: {e}")

                    # Delay between commands
                    if self.config.delay_between_commands_ms > 0:
                        await asyncio.sleep(self.config.delay_between_commands_ms / 1000)

        except Exception as e:
            self.result.failed_connections += 1
            self.result.errors.append(f"Connection {conn_id} failed: {e}")
            logger.error(f"Connection {conn_id} failed: {e}")

    def print_results(self) -> None:
        """Print load test results."""
        r = self.result
        logger.info("=" * 60)
        logger.info("LOAD TEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"Duration: {r.duration_seconds:.2f}s")
        logger.info(f"Connections: {r.successful_connections}/{r.total_connections} successful")
        logger.info(f"Commands: {r.successful_commands}/{r.total_commands} successful")
        logger.info(f"Latency (avg): {r.avg_latency_ms:.1f}ms")
        logger.info(f"Latency (p95): {r.p95_latency_ms:.1f}ms")
        logger.info(f"Latency (p99): {r.p99_latency_ms:.1f}ms")
        if r.errors:
            logger.info(f"Errors: {len(r.errors)}")
            for error in r.errors[:10]:
                logger.info(f"  - {error}")
        logger.info("=" * 60)
```

---

## Phase 3: External Monitoring Integration

### 3.1 Sentry Integration

**Purpose**: Integrate Sentry for automated error tracking and alerting.

**New File**: `backend/daemons/integrations/sentry.py`

```python
"""
Sentry Integration for Daemons Engine

Provides:
- Automatic exception capture
- Performance monitoring
- Context enrichment (player, room, command)
- Release tracking
"""

import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Optional import - Sentry is not required
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    HAS_SENTRY = True
except ImportError:
    HAS_SENTRY = False
    logger.info("Sentry SDK not installed - error tracking disabled")


def init_sentry(
    dsn: str | None = None,
    environment: str = "development",
    release: str | None = None,
    sample_rate: float = 1.0,
    traces_sample_rate: float = 0.1,
) -> bool:
    """
    Initialize Sentry SDK for error tracking.

    Args:
        dsn: Sentry DSN (or SENTRY_DSN env var)
        environment: Environment name (development, staging, production)
        release: Release version (defaults to daemons-engine version)
        sample_rate: Error sample rate (0.0-1.0)
        traces_sample_rate: Performance trace sample rate (0.0-1.0)

    Returns:
        True if Sentry was initialized, False otherwise
    """
    if not HAS_SENTRY:
        return False

    dsn = dsn or os.getenv("SENTRY_DSN")
    if not dsn:
        logger.info("No Sentry DSN configured - error tracking disabled")
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release or "daemons-engine@0.18.1",
        sample_rate=sample_rate,
        traces_sample_rate=traces_sample_rate,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
            LoggingIntegration(level=logging.ERROR, event_level=logging.ERROR),
        ],
        # Scrub sensitive data
        send_default_pii=False,
        before_send=_before_send,
    )

    logger.info(f"Sentry initialized (environment: {environment})")
    return True


def _before_send(event: dict, hint: dict) -> dict | None:
    """
    Process events before sending to Sentry.

    - Scrub sensitive data (tokens, passwords)
    - Add custom context
    """
    # Scrub any token/password data that slipped through
    if "request" in event:
        headers = event["request"].get("headers", {})
        if "authorization" in headers:
            headers["authorization"] = "[REDACTED]"

    return event


def set_player_context(player_id: str, player_name: str, room_id: str) -> None:
    """Set player context for Sentry events."""
    if not HAS_SENTRY:
        return

    sentry_sdk.set_user({"id": player_id, "username": player_name})
    sentry_sdk.set_context("game", {
        "player_id": player_id,
        "player_name": player_name,
        "room_id": room_id,
    })


def capture_game_error(
    error: Exception,
    *,
    player_id: str | None = None,
    command: str | None = None,
    extra: dict | None = None,
) -> None:
    """Capture a game error with context."""
    if not HAS_SENTRY:
        return

    with sentry_sdk.push_scope() as scope:
        if player_id:
            scope.set_tag("player_id", player_id)
        if command:
            scope.set_tag("command", command)
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)

        sentry_sdk.capture_exception(error)
```

### 3.2 Optional Dependencies

**Update**: `pyproject.toml`

```toml
[project.optional-dependencies]
# ... existing ...
monitoring = [
    "sentry-sdk[fastapi]>=1.40.0",
]
```

---

## Software Requirements

### Required (Already Installed)

| Package | Version | Purpose |
|---------|---------|---------|
| `structlog` | >=25.3.0 | Structured logging |
| `prometheus-client` | >=0.22.1 | Metrics collection |
| `fastapi` | >=0.122.0 | REST API framework |
| `websockets` | >=15.0.1 | WebSocket client |
| `httpx` | >=0.28.1 | HTTP client |

### Optional (For Enhanced Features)

| Package | Version | Purpose |
|---------|---------|---------|
| `sentry-sdk[fastapi]` | >=1.40.0 | Error tracking integration |
| `flet` | >=0.21.0 | GUI debugging client (alternative) |

### Python Version

- **Minimum**: Python 3.11
- **Recommended**: Python 3.12+

---

## File Structure

```
backend/
└── daemons/
    ├── logging.py              # ADD: DebugEventLogger class
    ├── metrics.py              # ADD: Debug metrics
    ├── main.py                 # ADD: /ws/debug endpoint
    ├── routes/
    │   └── admin.py            # ADD: /api/admin/debug/* endpoints
    └── integrations/           # NEW DIRECTORY
        ├── __init__.py
        └── sentry.py           # Sentry integration

tools/                          # NEW DIRECTORY
└── debug_client/
    ├── __init__.py
    ├── debug_client.py         # Main debugging client
    ├── load_tester.py          # Load testing module
    └── requirements.txt        # Client-specific deps

docs/
└── build_docs/
    └── QA_roadmap/
        ├── qa_roadmap.md                 # Strategy document
        └── qa_roadmap_implementation.md  # This document
```

---

## Implementation Tasks

### Phase 1 Tasks (Backend Instrumentation)

| # | Task | File | Priority | Estimate | Status |
|---|------|------|----------|----------|--------|
| 1.1 | Add `DebugEventLogger` class | `logging.py` | High | 2h | ✅ Complete |
| 1.2 | Add debug metrics to Prometheus | `metrics.py` | High | 1h | Not Started |
| 1.3 | Integrate debug logging into engine | `engine/engine.py` | High | 2h | Not Started |
| 1.4 | Add `/api/admin/debug/*` endpoints | `routes/admin.py` | High | 2h | Not Started |
| 1.5 | Add `/ws/debug` WebSocket endpoint | `main.py` | High | 1h | Not Started |
| 1.6 | Update WebSocket handlers to log errors | `main.py` | Medium | 1h | Not Started |
| 1.7 | Add performance timing to commands | `engine/engine.py` | Medium | 2h | Not Started |
| 1.8 | Write unit tests for debug logging | `tests/unit/test_debug_logging.py` | Medium | 2h | Not Started |

### Phase 2 Tasks (Debugging Client)

| # | Task | File | Priority | Estimate |
|---|------|------|----------|----------|
| 2.1 | Create debug_client directory structure | `tools/debug_client/` | High | 0.5h |
| 2.2 | Implement core `DebugClient` class | `debug_client.py` | High | 3h |
| 2.3 | Implement WebSocket event monitoring | `debug_client.py` | High | 2h |
| 2.4 | Implement Admin API integration | `debug_client.py` | Medium | 1h |
| 2.5 | Implement `LoadTester` class | `load_tester.py` | Medium | 3h |
| 2.6 | Add CLI interface | `debug_client.py` | Medium | 1h |
| 2.7 | Write documentation | `README.md` | Low | 1h |

### Phase 3 Tasks (External Integration)

| # | Task | File | Priority | Estimate |
|---|------|------|----------|----------|
| 3.1 | Create integrations directory | `integrations/__init__.py` | Low | 0.5h |
| 3.2 | Implement Sentry integration | `integrations/sentry.py` | Low | 2h |
| 3.3 | Update `pyproject.toml` dependencies | `pyproject.toml` | Low | 0.5h |
| 3.4 | Integrate Sentry in main.py | `main.py` | Low | 1h |
| 3.5 | Document Sentry setup | `docs/` | Low | 1h |

---

## Testing Strategy

### Unit Tests

- Test `DebugEventLogger` subscription and event buffering
- Test debug metrics collection
- Test debug endpoint authentication

### Integration Tests

- Test `/ws/debug` WebSocket connection and event streaming
- Test `/api/admin/debug/*` endpoints
- Test load tester against local server

### Manual Testing

1. Start server with debug logging enabled
2. Connect debugging client
3. Trigger various error conditions
4. Verify event capture and streaming
5. Run load test and verify metrics

---

## Success Criteria

1. **Real-time Error Visibility**: Debug events stream to connected clients within 100ms
2. **Performance Monitoring**: Command latency exceeding thresholds triggers alerts
3. **Load Testing**: Client can sustain 100+ concurrent connections for stress testing
4. **Error Aggregation**: Errors are categorized and countable for pattern detection
5. **Zero Production Impact**: Debug infrastructure has negligible overhead when no clients connected

---

## Notes for LLM Agents

When implementing this plan:

1. **Start with Phase 1.1-1.5** - These are the foundational backend changes
2. **Test incrementally** - Each component should be testable in isolation
3. **Preserve existing patterns** - Follow the structlog and Prometheus patterns already in use
4. **Use existing auth** - The Admin API auth pattern (`get_current_admin`) is well-established
5. **Queue-based architecture** - The event dispatcher pattern uses `asyncio.Queue` - follow this
6. **Error handling** - Use the existing `try/except` patterns and log appropriately
