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


# ============================================================================
# Global Logger Instances
# ============================================================================

# Create global instances for convenient access
admin_audit = AdminAuditLogger()
game_events = GameEventLogger()
performance = PerformanceLogger()


# Configure logging on module import (can be reconfigured later)
configure_logging(development=True, log_level="INFO")
