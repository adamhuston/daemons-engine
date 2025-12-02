# backend/daemons/legacy_deprecation.py
"""
Legacy Endpoint Deprecation Module - Phase 16.6

This module handles the graceful deprecation of the legacy /ws/game endpoint.
It implements a sunset timeline with configurable phases:

Phase 1 (WARN): Warning messages sent on connect, normal operation
Phase 2 (THROTTLE): Heavy rate limiting on legacy endpoint
Phase 3 (DISABLED): Legacy auth completely disabled

Configuration is via environment variables for operational flexibility.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DeprecationPhase(Enum):
    """Deprecation sunset phases."""
    WARN = "warn"           # Send warnings, allow full usage
    THROTTLE = "throttle"   # Heavy rate limiting
    DISABLED = "disabled"   # Legacy endpoint completely disabled


@dataclass
class LegacyDeprecationConfig:
    """
    Configuration for legacy endpoint deprecation.

    All values can be overridden via environment variables.
    """

    # Master switch for legacy authentication
    legacy_auth_enabled: bool = field(default_factory=lambda:
        os.getenv("WS_LEGACY_AUTH_ENABLED", "true").lower() == "true"
    )

    # Current deprecation phase
    deprecation_phase: DeprecationPhase = field(default_factory=lambda:
        DeprecationPhase(os.getenv("WS_LEGACY_DEPRECATION_PHASE", "warn"))
    )

    # Deprecation message settings
    deprecation_message: str = field(default_factory=lambda: os.getenv(
        "WS_LEGACY_DEPRECATION_MESSAGE",
        "DEPRECATION WARNING: The /ws/game endpoint is deprecated. "
        "Please migrate to /ws/game/auth with token-based authentication. "
        "This endpoint will be removed in a future release."
    ))

    # Sunset date (informational, for messages)
    sunset_date: str = field(default_factory=lambda: os.getenv(
        "WS_LEGACY_SUNSET_DATE",
        "2025-06-01"
    ))

    # Rate limiting overrides for throttle phase
    throttle_commands_per_minute: int = field(default_factory=lambda: int(
        os.getenv("WS_LEGACY_THROTTLE_COMMANDS_PER_MINUTE", "10")  # 10 vs normal 60
    ))
    throttle_chats_per_minute: int = field(default_factory=lambda: int(
        os.getenv("WS_LEGACY_THROTTLE_CHATS_PER_MINUTE", "5")  # 5 vs normal 30
    ))

    # Max connections for legacy endpoint (stricter than authenticated)
    legacy_max_connections_per_ip: int = field(default_factory=lambda: int(
        os.getenv("WS_LEGACY_MAX_CONNECTIONS_PER_IP", "3")  # 3 vs normal 10
    ))

    # Logging options
    log_legacy_connections: bool = field(default_factory=lambda:
        os.getenv("WS_LOG_LEGACY_CONNECTIONS", "true").lower() == "true"
    )


class LegacyDeprecationManager:
    """
    Manages the deprecation of the legacy /ws/game endpoint.

    Handles:
    - Connection validation based on current deprecation phase
    - Deprecation warning messages
    - Metrics tracking for legacy usage
    - Rate limit adjustments for throttle phase
    """

    def __init__(self, config: LegacyDeprecationConfig | None = None):
        """Initialize the deprecation manager."""
        self.config = config or LegacyDeprecationConfig()

        # Track legacy connection metrics
        self._legacy_connections_total = 0
        self._legacy_connections_active = 0
        self._connections_by_ip: dict[str, int] = {}
        self._last_reset = time.time()

    @property
    def is_enabled(self) -> bool:
        """Check if legacy authentication is enabled."""
        return self.config.legacy_auth_enabled

    @property
    def phase(self) -> DeprecationPhase:
        """Get current deprecation phase."""
        return self.config.deprecation_phase

    def validate_connection(self, client_ip: str) -> tuple[bool, str | None]:
        """
        Validate if a legacy connection should be allowed.

        Returns:
            Tuple of (allowed, error_message).
            If allowed is False, error_message contains the reason.
        """
        # Phase: DISABLED - reject all legacy connections
        if self.config.deprecation_phase == DeprecationPhase.DISABLED:
            return False, (
                "Legacy authentication is disabled. "
                "Please use /ws/game/auth with token-based authentication."
            )

        # Master switch check
        if not self.config.legacy_auth_enabled:
            return False, (
                "Legacy authentication is disabled. "
                "Please use /ws/game/auth with token-based authentication."
            )

        # Check IP connection limit (stricter for legacy)
        current_connections = self._connections_by_ip.get(client_ip, 0)
        if current_connections >= self.config.legacy_max_connections_per_ip:
            return False, (
                f"Too many legacy connections from this IP. "
                f"Maximum {self.config.legacy_max_connections_per_ip} allowed."
            )

        return True, None

    def register_connection(self, client_ip: str, player_id: str) -> None:
        """
        Register a new legacy connection.

        Tracks metrics and logs the connection if enabled.
        """
        self._legacy_connections_total += 1
        self._legacy_connections_active += 1
        self._connections_by_ip[client_ip] = self._connections_by_ip.get(client_ip, 0) + 1

        if self.config.log_legacy_connections:
            logger.warning(
                "Legacy WebSocket connection established - "
                "player_id=%s, ip=%s, phase=%s, total=%d, active=%d",
                player_id,
                client_ip,
                self.config.deprecation_phase.value,
                self._legacy_connections_total,
                self._legacy_connections_active,
            )

    def unregister_connection(self, client_ip: str, player_id: str) -> None:
        """Unregister a legacy connection."""
        self._legacy_connections_active = max(0, self._legacy_connections_active - 1)
        if client_ip in self._connections_by_ip:
            self._connections_by_ip[client_ip] = max(
                0, self._connections_by_ip[client_ip] - 1
            )
            if self._connections_by_ip[client_ip] == 0:
                del self._connections_by_ip[client_ip]

    def get_deprecation_message(self) -> dict[str, Any]:
        """
        Get the deprecation warning message to send to clients.

        Returns a JSON-serializable dict suitable for WebSocket send.
        """
        return {
            "type": "deprecation_warning",
            "message": self.config.deprecation_message,
            "sunset_date": self.config.sunset_date,
            "migration_url": "/ws/game/auth",
            "phase": self.config.deprecation_phase.value,
        }

    def get_rate_limits(self) -> tuple[int, int]:
        """
        Get rate limits based on current deprecation phase.

        Returns:
            Tuple of (commands_per_minute, chats_per_minute)
        """
        if self.config.deprecation_phase == DeprecationPhase.THROTTLE:
            return (
                self.config.throttle_commands_per_minute,
                self.config.throttle_chats_per_minute,
            )
        # Default/WARN phase - use normal limits (handled by ws_rate_limiter)
        return (60, 30)

    def should_send_warning(self) -> bool:
        """Check if a deprecation warning should be sent on connect."""
        # Always send warning in WARN and THROTTLE phases
        return self.config.deprecation_phase in (
            DeprecationPhase.WARN,
            DeprecationPhase.THROTTLE,
        )

    def get_metrics(self) -> dict[str, Any]:
        """Get current deprecation metrics."""
        return {
            "legacy_auth_enabled": self.config.legacy_auth_enabled,
            "deprecation_phase": self.config.deprecation_phase.value,
            "total_legacy_connections": self._legacy_connections_total,
            "active_legacy_connections": self._legacy_connections_active,
            "connections_by_ip_count": len(self._connections_by_ip),
        }

    def reset_metrics(self) -> None:
        """Reset connection metrics (for testing)."""
        self._legacy_connections_total = 0
        self._legacy_connections_active = 0
        self._connections_by_ip.clear()
        self._last_reset = time.time()


# Global instance
legacy_deprecation_config = LegacyDeprecationConfig()
legacy_deprecation_manager = LegacyDeprecationManager(legacy_deprecation_config)
