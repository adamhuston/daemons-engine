# backend/app/logging.py
"""
Phase 8: Structured Logging Configuration

Provides structured logging using structlog for better observability:
- JSON output for production (machine-parseable)
- Pretty console output for development
- Request/response logging
- Admin action audit logging
- Performance metrics

All log entries include contextual information like player_id, room_id, etc.
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import Any

import structlog
from structlog.typing import EventDict, WrappedLogger

# ============================================================================
# Custom Processors
# ============================================================================


def add_timestamp(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add ISO timestamp to all log entries."""
    event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return event_dict


def add_service_name(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add service name for log aggregation."""
    event_dict["service"] = "daemons"
    return event_dict


def sanitize_sensitive_data(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Remove or mask sensitive fields from logs."""
    sensitive_keys = {"password", "token", "secret", "api_key", "authorization"}

    for key in list(event_dict.keys()):
        if any(s in key.lower() for s in sensitive_keys):
            event_dict[key] = "[REDACTED]"

    return event_dict


# ============================================================================
# Logger Configuration
# ============================================================================


def configure_logging(
    development: bool = True, log_level: str = "INFO", json_output: bool = False
) -> None:
    """
    Configure structured logging for the application.

    Args:
        development: If True, use pretty console output. If False, use JSON.
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Force JSON output regardless of development mode
    """
    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # Shared processors for all environments
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        add_timestamp,
        add_service_name,
        sanitize_sensitive_data,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if development and not json_output:
        # Pretty console output for development
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]
    else:
        # JSON output for production
        processors = shared_processors + [structlog.processors.JSONRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "daemons") -> structlog.stdlib.BoundLogger:
    """
    Get a configured structured logger.

    Usage:
        logger = get_logger(__name__)
        logger.info("Player connected", player_id="abc123", room_id="room1")
    """
    return structlog.get_logger(name)


# ============================================================================
# Context Managers for Request/Session Logging
# ============================================================================


def bind_player_context(player_id: str, player_name: str = None) -> None:
    """Bind player context to all subsequent log entries in this request."""
    structlog.contextvars.bind_contextvars(player_id=player_id, player_name=player_name)


def bind_request_context(request_id: str, endpoint: str = None) -> None:
    """Bind request context to all subsequent log entries."""
    structlog.contextvars.bind_contextvars(request_id=request_id, endpoint=endpoint)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()


# ============================================================================
# Specialized Loggers
# ============================================================================


class AdminAuditLogger:
    """
    Specialized logger for admin actions that should be audited.

    All admin actions are logged with:
    - Admin user ID and name
    - Action type
    - Target entity (player, NPC, room, etc.)
    - Timestamp
    - Success/failure status
    """

    def __init__(self):
        self.logger = get_logger("daemons.admin.audit")

    def log_action(
        self,
        admin_id: str,
        admin_name: str,
        action: str,
        target_type: str = None,
        target_id: str = None,
        details: dict = None,
        success: bool = True,
    ) -> None:
        """
        Log an admin action for audit purposes.

        Args:
            admin_id: UUID of the admin user
            admin_name: Display name of the admin
            action: Action performed (teleport, spawn, kick, etc.)
            target_type: Type of target (player, npc, item, room)
            target_id: ID of the target entity
            details: Additional action-specific details
            success: Whether the action succeeded
        """
        log_data = {
            "admin_id": admin_id,
            "admin_name": admin_name,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "success": success,
            "audit": True,  # Flag for log aggregation filtering
        }

        if details:
            log_data["details"] = details

        if success:
            self.logger.info("Admin action performed", **log_data)
        else:
            self.logger.warning("Admin action failed", **log_data)

    def log_teleport(
        self,
        admin_id: str,
        admin_name: str,
        target_player_id: str,
        from_room: str,
        to_room: str,
        success: bool = True,
    ) -> None:
        """Log a teleport action."""
        self.log_action(
            admin_id=admin_id,
            admin_name=admin_name,
            action="teleport",
            target_type="player",
            target_id=target_player_id,
            details={"from_room": from_room, "to_room": to_room},
            success=success,
        )

    def log_spawn(
        self,
        admin_id: str,
        admin_name: str,
        entity_type: str,
        template_id: str,
        room_id: str,
        instance_id: str = None,
        success: bool = True,
    ) -> None:
        """Log a spawn action."""
        self.log_action(
            admin_id=admin_id,
            admin_name=admin_name,
            action="spawn",
            target_type=entity_type,
            target_id=instance_id,
            details={"template_id": template_id, "room_id": room_id},
            success=success,
        )

    def log_kick(
        self,
        admin_id: str,
        admin_name: str,
        target_player_id: str,
        reason: str,
        success: bool = True,
    ) -> None:
        """Log a kick action."""
        self.log_action(
            admin_id=admin_id,
            admin_name=admin_name,
            action="kick",
            target_type="player",
            target_id=target_player_id,
            details={"reason": reason},
            success=success,
        )

    def log_give_item(
        self,
        admin_id: str,
        admin_name: str,
        target_player_id: str,
        item_template_id: str,
        quantity: int,
        success: bool = True,
    ) -> None:
        """Log a give item action."""
        self.log_action(
            admin_id=admin_id,
            admin_name=admin_name,
            action="give_item",
            target_type="player",
            target_id=target_player_id,
            details={"item_template_id": item_template_id, "quantity": quantity},
            success=success,
        )

    def log_modify_stat(
        self,
        admin_id: str,
        admin_name: str,
        target_player_id: str,
        stat_name: str,
        old_value: Any,
        new_value: Any,
        success: bool = True,
    ) -> None:
        """Log a stat modification action."""
        self.log_action(
            admin_id=admin_id,
            admin_name=admin_name,
            action="modify_stat",
            target_type="player",
            target_id=target_player_id,
            details={
                "stat_name": stat_name,
                "old_value": old_value,
                "new_value": new_value,
            },
            success=success,
        )

    def log_content_reload(
        self,
        admin_id: str,
        admin_name: str,
        content_type: str,
        items_loaded: int,
        items_updated: int,
        items_failed: int,
        success: bool = True,
    ) -> None:
        """Log a content reload action."""
        self.log_action(
            admin_id=admin_id,
            admin_name=admin_name,
            action="content_reload",
            target_type="content",
            target_id=content_type,
            details={
                "items_loaded": items_loaded,
                "items_updated": items_updated,
                "items_failed": items_failed,
            },
            success=success,
        )

    def log_maintenance_toggle(
        self,
        admin_id: str,
        enabled: bool,
        reason: str = None,
        kick_players: bool = False,
        success: bool = True,
    ) -> None:
        """Log maintenance mode toggle."""
        self.log_action(
            admin_id=admin_id,
            admin_name="admin",  # Name not always available in this context
            action="maintenance_toggle",
            target_type="server",
            target_id="maintenance_mode",
            details={
                "enabled": enabled,
                "reason": reason,
                "kick_players": kick_players,
            },
            success=success,
        )

    def log_shutdown_initiated(
        self,
        admin_id: str,
        countdown_seconds: int,
        reason: str = None,
        success: bool = True,
    ) -> None:
        """Log server shutdown initiation."""
        self.log_action(
            admin_id=admin_id,
            admin_name="admin",
            action="shutdown_initiated",
            target_type="server",
            target_id="shutdown",
            details={"countdown_seconds": countdown_seconds, "reason": reason},
            success=success,
        )

    def log_shutdown_cancelled(self, admin_id: str, success: bool = True) -> None:
        """Log server shutdown cancellation."""
        self.log_action(
            admin_id=admin_id,
            admin_name="admin",
            action="shutdown_cancelled",
            target_type="server",
            target_id="shutdown",
            details={},
            success=success,
        )


class GameEventLogger:
    """
    Specialized logger for game events.

    Logs significant game events for analytics and debugging:
    - Combat events
    - Player actions
    - NPC behavior
    - System events
    """

    def __init__(self):
        self.logger = get_logger("daemons.game.events")

    def log_player_connect(
        self, player_id: str, player_name: str, room_id: str
    ) -> None:
        """Log player connection."""
        self.logger.info(
            "Player connected",
            player_id=player_id,
            player_name=player_name,
            room_id=room_id,
            event_type="player_connect",
        )

    def log_player_disconnect(
        self, player_id: str, player_name: str, session_duration: float = None
    ) -> None:
        """Log player disconnection."""
        self.logger.info(
            "Player disconnected",
            player_id=player_id,
            player_name=player_name,
            session_duration_seconds=session_duration,
            event_type="player_disconnect",
        )

    def log_combat_start(
        self,
        attacker_id: str,
        attacker_type: str,
        defender_id: str,
        defender_type: str,
        room_id: str,
    ) -> None:
        """Log combat initiation."""
        self.logger.info(
            "Combat started",
            attacker_id=attacker_id,
            attacker_type=attacker_type,
            defender_id=defender_id,
            defender_type=defender_type,
            room_id=room_id,
            event_type="combat_start",
        )

    def log_combat_end(
        self, winner_id: str, loser_id: str, cause: str, room_id: str
    ) -> None:
        """Log combat conclusion."""
        self.logger.info(
            "Combat ended",
            winner_id=winner_id,
            loser_id=loser_id,
            cause=cause,
            room_id=room_id,
            event_type="combat_end",
        )

    def log_player_death(
        self,
        player_id: str,
        player_name: str,
        cause: str,
        killer_id: str = None,
        room_id: str = None,
    ) -> None:
        """Log player death."""
        self.logger.warning(
            "Player died",
            player_id=player_id,
            player_name=player_name,
            cause=cause,
            killer_id=killer_id,
            room_id=room_id,
            event_type="player_death",
        )

    def log_npc_spawn(self, npc_id: str, template_id: str, room_id: str) -> None:
        """Log NPC spawn."""
        self.logger.debug(
            "NPC spawned",
            npc_id=npc_id,
            template_id=template_id,
            room_id=room_id,
            event_type="npc_spawn",
        )

    def log_npc_death(
        self, npc_id: str, template_id: str, killer_id: str, room_id: str
    ) -> None:
        """Log NPC death."""
        self.logger.debug(
            "NPC died",
            npc_id=npc_id,
            template_id=template_id,
            killer_id=killer_id,
            room_id=room_id,
            event_type="npc_death",
        )

    def log_item_pickup(
        self, player_id: str, item_id: str, item_name: str, room_id: str
    ) -> None:
        """Log item pickup."""
        self.logger.debug(
            "Item picked up",
            player_id=player_id,
            item_id=item_id,
            item_name=item_name,
            room_id=room_id,
            event_type="item_pickup",
        )

    def log_item_drop(
        self, player_id: str, item_id: str, item_name: str, room_id: str
    ) -> None:
        """Log item drop."""
        self.logger.debug(
            "Item dropped",
            player_id=player_id,
            item_id=item_id,
            item_name=item_name,
            room_id=room_id,
            event_type="item_drop",
        )


class PerformanceLogger:
    """
    Specialized logger for performance metrics.

    Logs timing and performance data for:
    - Command processing time
    - Database query time
    - WebSocket message latency
    - Tick processing time
    """

    def __init__(self):
        self.logger = get_logger("daemons.performance")

    def log_command_timing(
        self, command: str, player_id: str, duration_ms: float, success: bool = True
    ) -> None:
        """Log command processing time."""
        level = "debug" if duration_ms < 100 else "warning"
        getattr(self.logger, level)(
            "Command processed",
            command=command,
            player_id=player_id,
            duration_ms=round(duration_ms, 2),
            success=success,
            metric_type="command_timing",
        )

    def log_tick_timing(
        self, tick_type: str, duration_ms: float, entities_processed: int = 0
    ) -> None:
        """Log game tick processing time."""
        self.logger.debug(
            "Tick processed",
            tick_type=tick_type,
            duration_ms=round(duration_ms, 2),
            entities_processed=entities_processed,
            metric_type="tick_timing",
        )

    def log_db_query(
        self, query_type: str, table: str, duration_ms: float, rows_affected: int = 0
    ) -> None:
        """Log database query timing."""
        level = "debug" if duration_ms < 50 else "warning"
        getattr(self.logger, level)(
            "Database query",
            query_type=query_type,
            table=table,
            duration_ms=round(duration_ms, 2),
            rows_affected=rows_affected,
            metric_type="db_query",
        )


class DebugEventLogger:
    """
    Specialized logger for debug events that can be streamed to debugging clients.

    Captures:
    - Errors and exceptions with full context
    - Performance anomalies (commands exceeding latency thresholds)
    - Race condition indicators
    - WebSocket connection issues
    - Ability execution failures
    - State conflicts

    Provides:
    - Subscription mechanism for real-time event streaming
    - Circular buffer for recent event retrieval
    - Event categorization and severity levels

    Usage:
        # Record an error
        debug_events.record_error(
            error_type="ability_execution",
            message="Failed to cast fireball",
            context={"player_id": "abc123", "ability_id": "fireball"},
            exception=e
        )

        # Subscribe to events (for debugging client)
        queue = debug_events.subscribe("client_123")
        try:
            while True:
                event = await queue.get()
                # Process event...
        finally:
            debug_events.unsubscribe("client_123")
    """

    # Event types for categorization
    EVENT_TYPE_ERROR = "error"
    EVENT_TYPE_WARNING = "warning"
    EVENT_TYPE_PERFORMANCE = "performance"
    EVENT_TYPE_RACE_CONDITION = "race_condition"
    EVENT_TYPE_CONNECTION = "connection"
    EVENT_TYPE_STATE_CONFLICT = "state_conflict"

    # Severity levels
    SEVERITY_DEBUG = "debug"
    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_ERROR = "error"
    SEVERITY_CRITICAL = "critical"

    def __init__(self, buffer_size: int = 1000):
        """
        Initialize the debug event logger.

        Args:
            buffer_size: Maximum number of events to keep in the circular buffer
        """
        self.logger = get_logger("daemons.debug")
        self._buffer_size = buffer_size
        self._event_buffer: list[dict[str, Any]] = []
        self._subscribers: dict[str, "asyncio.Queue[dict[str, Any]]"] = {}
        self._event_counter = 0

    def _create_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        context: dict[str, Any] | None = None,
        exception: Exception | None = None,
    ) -> dict[str, Any]:
        """Create a structured debug event."""
        import traceback

        self._event_counter += 1
        event = {
            "id": self._event_counter,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": event_type,
            "severity": severity,
            "message": message,
            "context": context or {},
        }

        if exception:
            event["exception"] = {
                "type": type(exception).__name__,
                "message": str(exception),
                "traceback": traceback.format_exc(),
            }

        return event

    def _emit_event(self, event: dict[str, Any]) -> None:
        """Add event to buffer and notify subscribers."""
        import asyncio

        # Add to circular buffer
        self._event_buffer.append(event)
        if len(self._event_buffer) > self._buffer_size:
            self._event_buffer.pop(0)

        # Notify all subscribers (non-blocking)
        for subscriber_id, queue in list(self._subscribers.items()):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest event if queue is full
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    def subscribe(self, subscriber_id: str, queue_size: int = 100) -> "asyncio.Queue[dict[str, Any]]":
        """
        Subscribe to real-time debug events.

        Args:
            subscriber_id: Unique identifier for the subscriber
            queue_size: Maximum events to buffer per subscriber

        Returns:
            asyncio.Queue that will receive debug events
        """
        import asyncio

        if subscriber_id in self._subscribers:
            return self._subscribers[subscriber_id]

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=queue_size)
        self._subscribers[subscriber_id] = queue
        self.logger.info(
            "Debug subscriber added",
            subscriber_id=subscriber_id,
            total_subscribers=len(self._subscribers),
        )
        return queue

    def unsubscribe(self, subscriber_id: str) -> bool:
        """
        Unsubscribe from debug events.

        Args:
            subscriber_id: Unique identifier for the subscriber

        Returns:
            True if subscriber was found and removed
        """
        if subscriber_id in self._subscribers:
            del self._subscribers[subscriber_id]
            self.logger.info(
                "Debug subscriber removed",
                subscriber_id=subscriber_id,
                total_subscribers=len(self._subscribers),
            )
            return True
        return False

    def get_recent_events(
        self,
        count: int = 100,
        event_type: str | None = None,
        severity: str | None = None,
        since_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get recent events from the buffer.

        Args:
            count: Maximum number of events to return
            event_type: Filter by event type
            severity: Filter by severity level
            since_id: Only return events with ID greater than this

        Returns:
            List of matching events (most recent last)
        """
        events = self._event_buffer

        if since_id is not None:
            events = [e for e in events if e["id"] > since_id]

        if event_type is not None:
            events = [e for e in events if e["type"] == event_type]

        if severity is not None:
            events = [e for e in events if e["severity"] == severity]

        return events[-count:]

    def get_event_counts(self) -> dict[str, dict[str, int]]:
        """Get counts of events by type and severity."""
        counts: dict[str, dict[str, int]] = {}

        for event in self._event_buffer:
            event_type = event["type"]
            severity = event["severity"]

            if event_type not in counts:
                counts[event_type] = {}

            counts[event_type][severity] = counts[event_type].get(severity, 0) + 1

        return counts

    def clear_buffer(self) -> int:
        """Clear the event buffer. Returns number of events cleared."""
        count = len(self._event_buffer)
        self._event_buffer.clear()
        return count

    # ========================================================================
    # Convenience Methods for Common Event Types
    # ========================================================================

    def record_error(
        self,
        error_type: str,
        message: str,
        context: dict[str, Any] | None = None,
        exception: Exception | None = None,
        severity: str = SEVERITY_ERROR,
    ) -> None:
        """
        Record an error event.

        Args:
            error_type: Category of error (ability_execution, command, websocket, etc.)
            message: Human-readable error description
            context: Additional context (player_id, room_id, ability_id, etc.)
            exception: The exception object if available
            severity: Error severity level
        """
        ctx = context or {}
        ctx["error_type"] = error_type

        event = self._create_event(
            event_type=self.EVENT_TYPE_ERROR,
            severity=severity,
            message=message,
            context=ctx,
            exception=exception,
        )

        self._emit_event(event)
        log_method = getattr(self.logger, severity, self.logger.error)
        log_method(
            message,
            debug_event_id=event["id"],
            **ctx,
        )

    def record_warning(
        self,
        warning_type: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record a warning event."""
        ctx = context or {}
        ctx["warning_type"] = warning_type

        event = self._create_event(
            event_type=self.EVENT_TYPE_WARNING,
            severity=self.SEVERITY_WARNING,
            message=message,
            context=ctx,
        )

        self._emit_event(event)
        self.logger.warning(message, debug_event_id=event["id"], **ctx)

    def record_performance_anomaly(
        self,
        operation: str,
        duration_ms: float,
        threshold_ms: float,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Record a performance anomaly (operation exceeded expected duration).

        Args:
            operation: Name of the operation (command, query, tick, etc.)
            duration_ms: Actual duration in milliseconds
            threshold_ms: Expected maximum duration
            context: Additional context
        """
        ctx = context or {}
        ctx["operation"] = operation
        ctx["duration_ms"] = round(duration_ms, 2)
        ctx["threshold_ms"] = round(threshold_ms, 2)
        ctx["exceeded_by_pct"] = round((duration_ms / threshold_ms - 1) * 100, 1)

        event = self._create_event(
            event_type=self.EVENT_TYPE_PERFORMANCE,
            severity=self.SEVERITY_WARNING,
            message=f"Performance anomaly: {operation} took {duration_ms:.1f}ms (threshold: {threshold_ms:.1f}ms)",
            context=ctx,
        )

        self._emit_event(event)
        self.logger.warning(
            "Performance anomaly detected",
            debug_event_id=event["id"],
            **ctx,
        )

    def record_race_condition_indicator(
        self,
        indicator_type: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Record a potential race condition indicator.

        Args:
            indicator_type: Type of indicator (state_mismatch, concurrent_modification, etc.)
            message: Description of the indicator
            context: Additional context
        """
        ctx = context or {}
        ctx["indicator_type"] = indicator_type

        event = self._create_event(
            event_type=self.EVENT_TYPE_RACE_CONDITION,
            severity=self.SEVERITY_WARNING,
            message=message,
            context=ctx,
        )

        self._emit_event(event)
        self.logger.warning(
            "Race condition indicator",
            debug_event_id=event["id"],
            **ctx,
        )

    def record_connection_event(
        self,
        event_subtype: str,
        message: str,
        context: dict[str, Any] | None = None,
        severity: str = SEVERITY_INFO,
    ) -> None:
        """
        Record a WebSocket connection event.

        Args:
            event_subtype: Type of connection event (connect, disconnect, error, timeout)
            message: Description
            context: Additional context (player_id, connection_id, etc.)
            severity: Event severity
        """
        ctx = context or {}
        ctx["connection_event"] = event_subtype

        event = self._create_event(
            event_type=self.EVENT_TYPE_CONNECTION,
            severity=severity,
            message=message,
            context=ctx,
        )

        self._emit_event(event)
        log_method = getattr(self.logger, severity, self.logger.info)
        log_method(message, debug_event_id=event["id"], **ctx)

    def record_state_conflict(
        self,
        entity_type: str,
        entity_id: str,
        field: str,
        expected_value: Any,
        actual_value: Any,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Record a state conflict (unexpected value detected).

        Args:
            entity_type: Type of entity (player, npc, room)
            entity_id: ID of the entity
            field: Field with conflict
            expected_value: Expected value
            actual_value: Actual value found
            context: Additional context
        """
        ctx = context or {}
        ctx["entity_type"] = entity_type
        ctx["entity_id"] = entity_id
        ctx["field"] = field
        ctx["expected_value"] = str(expected_value)
        ctx["actual_value"] = str(actual_value)

        event = self._create_event(
            event_type=self.EVENT_TYPE_STATE_CONFLICT,
            severity=self.SEVERITY_WARNING,
            message=f"State conflict: {entity_type}:{entity_id}.{field} expected {expected_value}, got {actual_value}",
            context=ctx,
        )

        self._emit_event(event)
        self.logger.warning(
            "State conflict detected",
            debug_event_id=event["id"],
            **ctx,
        )

    def record_ability_error(
        self,
        ability_id: str,
        error_type: str,
        message: str,
        player_id: str | None = None,
        target_id: str | None = None,
        exception: Exception | None = None,
    ) -> None:
        """
        Record an ability execution error.

        Args:
            ability_id: ID of the ability
            error_type: Type of error (validation, execution, effect, etc.)
            message: Error description
            player_id: ID of the player using the ability
            target_id: ID of the target (if applicable)
            exception: The exception object if available
        """
        context = {
            "ability_id": ability_id,
            "error_type": error_type,
        }
        if player_id:
            context["player_id"] = player_id
        if target_id:
            context["target_id"] = target_id

        self.record_error(
            error_type=f"ability_{error_type}",
            message=message,
            context=context,
            exception=exception,
        )

    def record_command_error(
        self,
        command: str,
        error_type: str,
        message: str,
        player_id: str | None = None,
        exception: Exception | None = None,
    ) -> None:
        """
        Record a command execution error.

        Args:
            command: The command that failed
            error_type: Type of error (parse, validation, execution, etc.)
            message: Error description
            player_id: ID of the player who issued the command
            exception: The exception object if available
        """
        context = {
            "command": command,
            "error_type": error_type,
        }
        if player_id:
            context["player_id"] = player_id

        self.record_error(
            error_type=f"command_{error_type}",
            message=message,
            context=context,
            exception=exception,
        )

    def record_websocket_error(
        self,
        error_type: str,
        message: str,
        player_id: str | None = None,
        connection_id: str | None = None,
        exception: Exception | None = None,
    ) -> None:
        """
        Record a WebSocket error.

        Args:
            error_type: Type of error (connection, message, protocol, etc.)
            message: Error description
            player_id: ID of the affected player (if known)
            connection_id: ID of the connection (if known)
            exception: The exception object if available
        """
        context = {"websocket_error_type": error_type}
        if player_id:
            context["player_id"] = player_id
        if connection_id:
            context["connection_id"] = connection_id

        self.record_error(
            error_type=f"websocket_{error_type}",
            message=message,
            context=context,
            exception=exception,
            severity=self.SEVERITY_WARNING,
        )

    @property
    def subscriber_count(self) -> int:
        """Get the number of active subscribers."""
        return len(self._subscribers)

    @property
    def buffer_count(self) -> int:
        """Get the number of events in the buffer."""
        return len(self._event_buffer)


# ============================================================================
# Global Logger Instances
# ============================================================================

# Create global instances for convenient access
admin_audit = AdminAuditLogger()
game_events = GameEventLogger()
performance = PerformanceLogger()
debug_events = DebugEventLogger()


# Configure logging on module import (can be reconfigured later)
configure_logging(development=True, log_level="INFO")
