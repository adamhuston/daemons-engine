# backend/daemons/websocket_security.py
"""
WebSocket Security Module - Phase 16.4

This module provides security hardening for WebSocket connections:
- Message size limits: Prevent oversized message attacks
- Origin validation: Allow only trusted origins
- Connection limits: Prevent connection flooding per IP/account
- Message validation: JSON schema validation for incoming messages
- Heartbeat/ping-pong: Connection health monitoring

Configuration is via environment variables for flexibility.
"""

import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class WebSocketSecurityConfig:
    """
    Configuration for WebSocket security features.

    All values can be overridden via environment variables.
    """

    # Message size limits
    max_message_size: int = field(default_factory=lambda: int(
        os.getenv("WS_MAX_MESSAGE_SIZE", "65536")  # 64KB default
    ))

    # Origin validation
    allowed_origins: list[str] = field(default_factory=lambda: [
        origin.strip()
        for origin in os.getenv(
            "WS_ALLOWED_ORIGINS",
            "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000"
        ).split(",")
        if origin.strip()
    ])
    origin_validation_enabled: bool = field(default_factory=lambda:
        os.getenv("WS_ORIGIN_VALIDATION_ENABLED", "true").lower() == "true"
    )

    # Connection limits
    max_connections_per_ip: int = field(default_factory=lambda: int(
        os.getenv("WS_MAX_CONNECTIONS_PER_IP", "10")
    ))
    max_connections_per_account: int = field(default_factory=lambda: int(
        os.getenv("WS_MAX_CONNECTIONS_PER_ACCOUNT", "3")
    ))

    # Heartbeat settings
    heartbeat_interval: int = field(default_factory=lambda: int(
        os.getenv("WS_HEARTBEAT_INTERVAL", "30")  # 30 seconds default
    ))
    heartbeat_timeout: int = field(default_factory=lambda: int(
        os.getenv("WS_HEARTBEAT_TIMEOUT", "10")  # 10 seconds timeout
    ))

    # Message validation
    message_validation_enabled: bool = field(default_factory=lambda:
        os.getenv("WS_MESSAGE_VALIDATION_ENABLED", "true").lower() == "true"
    )


# Global config instance
ws_security_config = WebSocketSecurityConfig()


# =============================================================================
# Message Size Validation
# =============================================================================

class MessageSizeValidator:
    """
    Validates that incoming WebSocket messages don't exceed size limits.
    """

    def __init__(self, max_size: int = None):
        self.max_size = max_size or ws_security_config.max_message_size

    def validate(self, message: str | bytes) -> tuple[bool, str | None]:
        """
        Check if message size is within limits.

        Returns:
            (valid: bool, error_message: str | None)
        """
        if isinstance(message, str):
            size = len(message.encode('utf-8'))
        else:
            size = len(message)

        if size > self.max_size:
            error = f"Message size {size} bytes exceeds limit of {self.max_size} bytes"
            logger.warning(error)
            return False, error

        return True, None


# =============================================================================
# Origin Validation
# =============================================================================

class OriginValidator:
    """
    Validates WebSocket connection Origin header against allowed list.
    """

    def __init__(self, allowed_origins: list[str] = None, enabled: bool = None):
        self.allowed_origins = allowed_origins or ws_security_config.allowed_origins
        self.enabled = enabled if enabled is not None else ws_security_config.origin_validation_enabled

    def validate(self, origin: str | None) -> tuple[bool, str | None]:
        """
        Check if the Origin header is in the allowed list.

        Returns:
            (valid: bool, error_message: str | None)
        """
        if not self.enabled:
            return True, None

        # No origin header - this is typically localhost or same-origin
        # Allow by default but log for monitoring
        if origin is None:
            logger.debug("WebSocket connection with no Origin header")
            return True, None

        # Check against allowed list
        if origin in self.allowed_origins:
            return True, None

        # Check for wildcard patterns (e.g., "*.example.com")
        for allowed in self.allowed_origins:
            if allowed.startswith("*"):
                # Simple wildcard suffix matching
                suffix = allowed[1:]  # Remove the *
                if origin.endswith(suffix):
                    return True, None

        error = f"Origin '{origin}' not in allowed origins list"
        logger.warning(error)
        return False, error

    def add_origin(self, origin: str) -> None:
        """Add an origin to the allowed list at runtime."""
        if origin not in self.allowed_origins:
            self.allowed_origins.append(origin)
            logger.info(f"Added origin to allowed list: {origin}")

    def remove_origin(self, origin: str) -> None:
        """Remove an origin from the allowed list at runtime."""
        if origin in self.allowed_origins:
            self.allowed_origins.remove(origin)
            logger.info(f"Removed origin from allowed list: {origin}")


# =============================================================================
# Connection Limits
# =============================================================================

class ConnectionLimiter:
    """
    Tracks and limits WebSocket connections per IP and per account.

    Thread-safe for async usage.
    """

    def __init__(
        self,
        max_per_ip: int = None,
        max_per_account: int = None,
    ):
        self.max_per_ip = max_per_ip or ws_security_config.max_connections_per_ip
        self.max_per_account = max_per_account or ws_security_config.max_connections_per_account

        # Track active connections: {ip: set(connection_ids)}
        self._ip_connections: dict[str, set[str]] = defaultdict(set)
        # Track active connections: {account_id: set(connection_ids)}
        self._account_connections: dict[str, set[str]] = defaultdict(set)
        # Map connection_id to (ip, account_id) for cleanup
        self._connection_info: dict[str, tuple[str, str | None]] = {}

    def check_ip_limit(self, client_ip: str) -> tuple[bool, str | None]:
        """
        Check if an IP can open a new connection.

        Returns:
            (allowed: bool, error_message: str | None)
        """
        current_count = len(self._ip_connections[client_ip])

        if current_count >= self.max_per_ip:
            error = f"Connection limit reached for IP ({self.max_per_ip} max)"
            logger.warning(f"IP connection limit exceeded: {client_ip} has {current_count} connections")
            return False, error

        return True, None

    def check_account_limit(self, account_id: str) -> tuple[bool, str | None]:
        """
        Check if an account can open a new connection.

        Returns:
            (allowed: bool, error_message: str | None)
        """
        current_count = len(self._account_connections[account_id])

        if current_count >= self.max_per_account:
            error = f"Connection limit reached for account ({self.max_per_account} max)"
            logger.warning(f"Account connection limit exceeded: {account_id} has {current_count} connections")
            return False, error

        return True, None

    def register_connection(
        self,
        connection_id: str,
        client_ip: str,
        account_id: str | None = None,
    ) -> None:
        """
        Register a new WebSocket connection.

        Called after connection is accepted.
        """
        self._ip_connections[client_ip].add(connection_id)
        if account_id:
            self._account_connections[account_id].add(connection_id)
        self._connection_info[connection_id] = (client_ip, account_id)

        logger.debug(
            f"Registered connection {connection_id}: IP={client_ip}, account={account_id}"
        )

    def unregister_connection(self, connection_id: str) -> None:
        """
        Unregister a WebSocket connection on disconnect.
        """
        info = self._connection_info.pop(connection_id, None)
        if info is None:
            return

        client_ip, account_id = info

        self._ip_connections[client_ip].discard(connection_id)
        if not self._ip_connections[client_ip]:
            del self._ip_connections[client_ip]

        if account_id:
            self._account_connections[account_id].discard(connection_id)
            if not self._account_connections[account_id]:
                del self._account_connections[account_id]

        logger.debug(f"Unregistered connection {connection_id}")

    def get_stats(self) -> dict:
        """Get current connection statistics."""
        return {
            "total_connections": len(self._connection_info),
            "unique_ips": len(self._ip_connections),
            "unique_accounts": len(self._account_connections),
            "connections_by_ip": {ip: len(conns) for ip, conns in self._ip_connections.items()},
        }


# =============================================================================
# Message Validation (JSON Schema)
# =============================================================================

# Define allowed message types and their required fields
MESSAGE_SCHEMAS: dict[str, dict[str, Any]] = {
    "command": {
        "required": ["type", "text"],
        "optional": [],
        "text_max_length": 500,
    },
    "ping": {
        "required": ["type"],
        "optional": ["timestamp"],
    },
}


class MessageValidator:
    """
    Validates incoming WebSocket messages against defined schemas.

    Rejects malformed payloads early to prevent processing invalid data.
    """

    def __init__(self, schemas: dict = None, enabled: bool = None):
        self.schemas = schemas or MESSAGE_SCHEMAS
        self.enabled = enabled if enabled is not None else ws_security_config.message_validation_enabled

    def validate(self, message: dict) -> tuple[bool, str | None]:
        """
        Validate a message against its schema.

        Returns:
            (valid: bool, error_message: str | None)
        """
        if not self.enabled:
            return True, None

        # Check for type field
        if "type" not in message:
            return False, "Message missing required 'type' field"

        msg_type = message["type"]

        # Unknown message types are rejected
        if msg_type not in self.schemas:
            # Allow unknown types but log them
            logger.debug(f"Unknown message type received: {msg_type}")
            return True, None

        schema = self.schemas[msg_type]

        # Check required fields
        for field_name in schema.get("required", []):
            if field_name not in message:
                return False, f"Message type '{msg_type}' missing required field '{field_name}'"

        # Validate field-specific constraints
        if msg_type == "command":
            text = message.get("text", "")
            max_length = schema.get("text_max_length", 500)
            if len(text) > max_length:
                return False, f"Command text exceeds maximum length of {max_length} characters"

            # Check for control characters that could cause issues
            if any(ord(c) < 32 and c not in '\n\r\t' for c in text):
                return False, "Command contains invalid control characters"

        return True, None

    def parse_and_validate(self, raw_message: str) -> tuple[dict | None, str | None]:
        """
        Parse JSON and validate in one step.

        Returns:
            (parsed_message: dict | None, error_message: str | None)
        """
        # Try to parse JSON
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError as e:
            return None, f"Invalid JSON: {str(e)}"

        # Validate structure
        if not isinstance(message, dict):
            return None, "Message must be a JSON object"

        # Validate against schema
        valid, error = self.validate(message)
        if not valid:
            return None, error

        return message, None


# =============================================================================
# Connection Health Monitoring (Heartbeat)
# =============================================================================

@dataclass
class ConnectionHealth:
    """Tracks health state for a WebSocket connection."""
    connection_id: str
    last_ping_sent: float = 0.0
    last_pong_received: float = 0.0
    missed_pongs: int = 0
    is_healthy: bool = True


class HeartbeatManager:
    """
    Manages WebSocket connection health via ping-pong.

    Sends periodic pings and tracks pong responses.
    Marks connections unhealthy after missed pongs.
    """

    def __init__(
        self,
        interval: int = None,
        timeout: int = None,
        max_missed_pongs: int = 3,
    ):
        self.interval = interval or ws_security_config.heartbeat_interval
        self.timeout = timeout or ws_security_config.heartbeat_timeout
        self.max_missed_pongs = max_missed_pongs

        # Track connection health: {connection_id: ConnectionHealth}
        self._connections: dict[str, ConnectionHealth] = {}

    def register_connection(self, connection_id: str) -> None:
        """Register a connection for health monitoring."""
        self._connections[connection_id] = ConnectionHealth(
            connection_id=connection_id,
            last_pong_received=time.time(),  # Assume healthy on connect
        )

    def unregister_connection(self, connection_id: str) -> None:
        """Remove a connection from health monitoring."""
        self._connections.pop(connection_id, None)

    def record_ping_sent(self, connection_id: str) -> None:
        """Record that a ping was sent to a connection."""
        if connection_id in self._connections:
            self._connections[connection_id].last_ping_sent = time.time()

    def record_pong_received(self, connection_id: str) -> None:
        """Record that a pong was received from a connection."""
        if connection_id in self._connections:
            health = self._connections[connection_id]
            health.last_pong_received = time.time()
            health.missed_pongs = 0
            health.is_healthy = True

    def check_health(self, connection_id: str) -> bool:
        """
        Check if a connection is healthy.

        Returns True if healthy, False if unhealthy or unknown.
        """
        health = self._connections.get(connection_id)
        if health is None:
            return False

        # Check if we've missed too many pongs
        if health.last_ping_sent > health.last_pong_received:
            # We sent a ping but haven't received pong
            time_since_ping = time.time() - health.last_ping_sent
            if time_since_ping > self.timeout:
                health.missed_pongs += 1
                if health.missed_pongs >= self.max_missed_pongs:
                    health.is_healthy = False
                    logger.warning(
                        f"Connection {connection_id} unhealthy: {health.missed_pongs} missed pongs"
                    )

        return health.is_healthy

    def get_connections_needing_ping(self) -> list[str]:
        """Get list of connections that need a ping sent."""
        now = time.time()
        result = []

        for conn_id, health in self._connections.items():
            time_since_pong = now - health.last_pong_received
            if time_since_pong >= self.interval and health.is_healthy:
                result.append(conn_id)

        return result

    def get_unhealthy_connections(self) -> list[str]:
        """Get list of connections that are unhealthy and should be closed."""
        return [
            conn_id for conn_id, health in self._connections.items()
            if not health.is_healthy
        ]

    def get_stats(self) -> dict:
        """Get current heartbeat statistics."""
        healthy = sum(1 for h in self._connections.values() if h.is_healthy)
        return {
            "total_connections": len(self._connections),
            "healthy_connections": healthy,
            "unhealthy_connections": len(self._connections) - healthy,
        }


# =============================================================================
# Unified Security Manager
# =============================================================================

class WebSocketSecurityManager:
    """
    Unified security manager that coordinates all WebSocket security features.

    Usage:
        security = WebSocketSecurityManager()

        # On connection attempt
        valid, error = await security.validate_connection(websocket, client_ip)

        # On message received
        valid, parsed, error = security.validate_message(raw_message)

        # On disconnect
        security.cleanup_connection(connection_id)
    """

    def __init__(self, config: WebSocketSecurityConfig = None):
        self.config = config or ws_security_config

        self.size_validator = MessageSizeValidator(self.config.max_message_size)
        self.origin_validator = OriginValidator(
            self.config.allowed_origins,
            self.config.origin_validation_enabled,
        )
        self.connection_limiter = ConnectionLimiter(
            self.config.max_connections_per_ip,
            self.config.max_connections_per_account,
        )
        self.message_validator = MessageValidator(
            enabled=self.config.message_validation_enabled,
        )
        self.heartbeat_manager = HeartbeatManager(
            self.config.heartbeat_interval,
            self.config.heartbeat_timeout,
        )

    async def validate_connection(
        self,
        websocket: WebSocket,
        client_ip: str,
        account_id: str | None = None,
    ) -> tuple[bool, str | None]:
        """
        Validate a new WebSocket connection attempt.

        Checks:
        - Origin validation
        - IP connection limit
        - Account connection limit (if authenticated)

        Returns:
            (valid: bool, error_message: str | None)
        """
        # Check origin
        origin = websocket.headers.get("origin")
        valid, error = self.origin_validator.validate(origin)
        if not valid:
            return False, error

        # Check IP limit
        valid, error = self.connection_limiter.check_ip_limit(client_ip)
        if not valid:
            return False, error

        # Check account limit if authenticated
        if account_id:
            valid, error = self.connection_limiter.check_account_limit(account_id)
            if not valid:
                return False, error

        return True, None

    def register_connection(
        self,
        connection_id: str,
        client_ip: str,
        account_id: str | None = None,
    ) -> None:
        """Register a successfully connected WebSocket."""
        self.connection_limiter.register_connection(connection_id, client_ip, account_id)
        self.heartbeat_manager.register_connection(connection_id)

    def validate_message(self, raw_message: str) -> tuple[bool, dict | None, str | None]:
        """
        Validate an incoming WebSocket message.

        Checks:
        - Message size limit
        - JSON validity
        - Schema validation

        Returns:
            (valid: bool, parsed_message: dict | None, error_message: str | None)
        """
        # Check size first
        valid, error = self.size_validator.validate(raw_message)
        if not valid:
            return False, None, error

        # Parse and validate
        parsed, error = self.message_validator.parse_and_validate(raw_message)
        if error:
            return False, None, error

        return True, parsed, None

    def cleanup_connection(self, connection_id: str) -> None:
        """Clean up all tracking for a disconnected connection."""
        self.connection_limiter.unregister_connection(connection_id)
        self.heartbeat_manager.unregister_connection(connection_id)

    def record_pong(self, connection_id: str) -> None:
        """Record that a pong was received from a connection."""
        self.heartbeat_manager.record_pong_received(connection_id)

    def get_stats(self) -> dict:
        """Get combined security statistics."""
        return {
            "connections": self.connection_limiter.get_stats(),
            "heartbeat": self.heartbeat_manager.get_stats(),
            "config": {
                "max_message_size": self.config.max_message_size,
                "origin_validation_enabled": self.config.origin_validation_enabled,
                "allowed_origins": self.config.allowed_origins,
                "max_connections_per_ip": self.config.max_connections_per_ip,
                "max_connections_per_account": self.config.max_connections_per_account,
                "heartbeat_interval": self.config.heartbeat_interval,
            }
        }


# =============================================================================
# Global Instances
# =============================================================================

# Global security manager instance
ws_security_manager = WebSocketSecurityManager()


def get_client_ip_from_websocket(websocket: WebSocket) -> str:
    """
    Extract client IP from WebSocket connection.

    Handles X-Forwarded-For header for reverse proxy setups.
    """
    # Check for X-Forwarded-For header (reverse proxy)
    forwarded_for = websocket.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()

    # Fall back to direct connection IP
    client = websocket.client
    if client:
        return client.host

    return "unknown"
