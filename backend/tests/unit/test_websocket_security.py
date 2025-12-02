"""
Unit tests for WebSocket Security Module (Phase 16.4).

Tests message size limits, origin validation, connection limits,
message validation, and heartbeat monitoring.
"""

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from daemons.websocket_security import (
    ConnectionLimiter,
    HeartbeatManager,
    MessageSizeValidator,
    MessageValidator,
    OriginValidator,
    WebSocketSecurityConfig,
    WebSocketSecurityManager,
    get_client_ip_from_websocket,
    ws_security_config,
    ws_security_manager,
)

# =============================================================================
# Test Configuration
# =============================================================================


class TestWebSocketSecurityConfig:
    """Tests for WebSocket security configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = WebSocketSecurityConfig()

        assert config.max_message_size == 65536  # 64KB
        assert config.max_connections_per_ip == 10
        assert config.max_connections_per_account == 3
        assert config.heartbeat_interval == 30
        assert config.heartbeat_timeout == 10
        assert config.origin_validation_enabled is True
        assert config.message_validation_enabled is True

    def test_config_from_environment(self):
        """Test configuration from environment variables."""
        with patch.dict(os.environ, {
            "WS_MAX_MESSAGE_SIZE": "32768",
            "WS_MAX_CONNECTIONS_PER_IP": "5",
            "WS_MAX_CONNECTIONS_PER_ACCOUNT": "2",
            "WS_ORIGIN_VALIDATION_ENABLED": "false",
        }):
            config = WebSocketSecurityConfig()

            assert config.max_message_size == 32768
            assert config.max_connections_per_ip == 5
            assert config.max_connections_per_account == 2
            assert config.origin_validation_enabled is False

    def test_allowed_origins_from_environment(self):
        """Test allowed origins configuration from environment."""
        with patch.dict(os.environ, {
            "WS_ALLOWED_ORIGINS": "https://example.com,https://api.example.com",
        }):
            config = WebSocketSecurityConfig()

            assert "https://example.com" in config.allowed_origins
            assert "https://api.example.com" in config.allowed_origins


# =============================================================================
# Test Message Size Validation
# =============================================================================


class TestMessageSizeValidator:
    """Tests for message size validation."""

    def test_valid_message_size(self):
        """Test that messages under the limit are accepted."""
        validator = MessageSizeValidator(max_size=1024)

        valid, error = validator.validate("Hello, world!")

        assert valid is True
        assert error is None

    def test_message_at_limit(self):
        """Test that messages at exactly the limit are accepted."""
        validator = MessageSizeValidator(max_size=100)
        message = "x" * 100

        valid, error = validator.validate(message)

        assert valid is True
        assert error is None

    def test_message_exceeds_limit(self):
        """Test that messages over the limit are rejected."""
        validator = MessageSizeValidator(max_size=100)
        message = "x" * 200

        valid, error = validator.validate(message)

        assert valid is False
        assert error is not None
        assert "200 bytes" in error
        assert "100 bytes" in error

    def test_binary_message(self):
        """Test validation of binary messages."""
        validator = MessageSizeValidator(max_size=100)
        message = b"x" * 200

        valid, error = validator.validate(message)

        assert valid is False

    def test_unicode_message(self):
        """Test that Unicode characters are counted correctly (UTF-8 bytes)."""
        validator = MessageSizeValidator(max_size=10)
        # Each emoji is 4 bytes in UTF-8
        message = "👋👋👋"  # 12 bytes

        valid, error = validator.validate(message)

        assert valid is False

    def test_default_max_size(self):
        """Test that default max size is used from config."""
        validator = MessageSizeValidator()

        assert validator.max_size == ws_security_config.max_message_size


# =============================================================================
# Test Origin Validation
# =============================================================================


class TestOriginValidator:
    """Tests for WebSocket origin validation."""

    def test_valid_origin(self):
        """Test that allowed origins are accepted."""
        validator = OriginValidator(
            allowed_origins=["http://localhost:3000", "https://example.com"],
            enabled=True,
        )

        valid, error = validator.validate("http://localhost:3000")

        assert valid is True
        assert error is None

    def test_invalid_origin(self):
        """Test that non-allowed origins are rejected."""
        validator = OriginValidator(
            allowed_origins=["http://localhost:3000"],
            enabled=True,
        )

        valid, error = validator.validate("https://evil.com")

        assert valid is False
        assert error is not None
        assert "evil.com" in error

    def test_no_origin_header(self):
        """Test that missing origin header is allowed (same-origin/localhost)."""
        validator = OriginValidator(
            allowed_origins=["http://localhost:3000"],
            enabled=True,
        )

        valid, error = validator.validate(None)

        assert valid is True

    def test_validation_disabled(self):
        """Test that validation can be disabled."""
        validator = OriginValidator(
            allowed_origins=["http://localhost:3000"],
            enabled=False,
        )

        valid, error = validator.validate("https://evil.com")

        assert valid is True

    def test_wildcard_origin(self):
        """Test wildcard origin matching."""
        validator = OriginValidator(
            allowed_origins=["*.example.com"],
            enabled=True,
        )

        valid, error = validator.validate("https://api.example.com")

        assert valid is True

    def test_add_origin_at_runtime(self):
        """Test adding origins at runtime."""
        validator = OriginValidator(
            allowed_origins=["http://localhost:3000"],
            enabled=True,
        )

        # Initially rejected
        valid, _ = validator.validate("https://newsite.com")
        assert valid is False

        # Add origin
        validator.add_origin("https://newsite.com")

        # Now accepted
        valid, _ = validator.validate("https://newsite.com")
        assert valid is True

    def test_remove_origin_at_runtime(self):
        """Test removing origins at runtime."""
        validator = OriginValidator(
            allowed_origins=["http://localhost:3000", "https://oldsite.com"],
            enabled=True,
        )

        # Initially accepted
        valid, _ = validator.validate("https://oldsite.com")
        assert valid is True

        # Remove origin
        validator.remove_origin("https://oldsite.com")

        # Now rejected
        valid, _ = validator.validate("https://oldsite.com")
        assert valid is False


# =============================================================================
# Test Connection Limits
# =============================================================================


class TestConnectionLimiter:
    """Tests for connection limiting per IP and account."""

    def test_ip_limit_not_reached(self):
        """Test that connections are allowed when under IP limit."""
        limiter = ConnectionLimiter(max_per_ip=3, max_per_account=2)

        valid, error = limiter.check_ip_limit("192.168.1.1")

        assert valid is True
        assert error is None

    def test_ip_limit_reached(self):
        """Test that connections are rejected when IP limit is reached."""
        limiter = ConnectionLimiter(max_per_ip=2, max_per_account=5)

        # Register 2 connections from same IP
        limiter.register_connection("conn1", "192.168.1.1")
        limiter.register_connection("conn2", "192.168.1.1")

        # Third connection should fail
        valid, error = limiter.check_ip_limit("192.168.1.1")

        assert valid is False
        assert "limit reached" in error.lower()

    def test_account_limit_not_reached(self):
        """Test that connections are allowed when under account limit."""
        limiter = ConnectionLimiter(max_per_ip=10, max_per_account=3)

        valid, error = limiter.check_account_limit("user123")

        assert valid is True
        assert error is None

    def test_account_limit_reached(self):
        """Test that connections are rejected when account limit is reached."""
        limiter = ConnectionLimiter(max_per_ip=10, max_per_account=2)

        # Register 2 connections for same account
        limiter.register_connection("conn1", "192.168.1.1", "user123")
        limiter.register_connection("conn2", "192.168.1.2", "user123")

        # Third connection should fail
        valid, error = limiter.check_account_limit("user123")

        assert valid is False
        assert "limit reached" in error.lower()

    def test_connection_unregister(self):
        """Test that unregistering connections frees up slots."""
        limiter = ConnectionLimiter(max_per_ip=2, max_per_account=2)

        # Fill up limits
        limiter.register_connection("conn1", "192.168.1.1", "user123")
        limiter.register_connection("conn2", "192.168.1.1", "user123")

        # Should be at limit
        valid, _ = limiter.check_ip_limit("192.168.1.1")
        assert valid is False

        # Unregister one
        limiter.unregister_connection("conn1")

        # Should now be allowed
        valid, _ = limiter.check_ip_limit("192.168.1.1")
        assert valid is True

    def test_different_ips_independent(self):
        """Test that different IPs have independent limits."""
        limiter = ConnectionLimiter(max_per_ip=2, max_per_account=10)

        # Fill up one IP
        limiter.register_connection("conn1", "192.168.1.1")
        limiter.register_connection("conn2", "192.168.1.1")

        # Different IP should still be allowed
        valid, _ = limiter.check_ip_limit("192.168.1.2")
        assert valid is True

    def test_get_stats(self):
        """Test connection statistics."""
        limiter = ConnectionLimiter(max_per_ip=10, max_per_account=5)

        limiter.register_connection("conn1", "192.168.1.1", "user1")
        limiter.register_connection("conn2", "192.168.1.2", "user1")
        limiter.register_connection("conn3", "192.168.1.1", "user2")

        stats = limiter.get_stats()

        assert stats["total_connections"] == 3
        assert stats["unique_ips"] == 2
        assert stats["unique_accounts"] == 2


# =============================================================================
# Test Message Validation
# =============================================================================


class TestMessageValidator:
    """Tests for JSON message schema validation."""

    def test_valid_command_message(self):
        """Test that valid command messages are accepted."""
        validator = MessageValidator(enabled=True)

        message = {"type": "command", "text": "look"}
        valid, error = validator.validate(message)

        assert valid is True
        assert error is None

    def test_missing_type_field(self):
        """Test that messages without type are rejected."""
        validator = MessageValidator(enabled=True)

        message = {"text": "look"}
        valid, error = validator.validate(message)

        assert valid is False
        assert "type" in error.lower()

    def test_missing_required_field(self):
        """Test that messages missing required fields are rejected."""
        validator = MessageValidator(enabled=True)

        message = {"type": "command"}  # missing "text"
        valid, error = validator.validate(message)

        assert valid is False
        assert "text" in error.lower()

    def test_command_text_too_long(self):
        """Test that overly long command text is rejected."""
        validator = MessageValidator(enabled=True)

        message = {"type": "command", "text": "x" * 600}
        valid, error = validator.validate(message)

        assert valid is False
        assert "maximum length" in error.lower()

    def test_command_with_control_characters(self):
        """Test that control characters in commands are rejected."""
        validator = MessageValidator(enabled=True)

        message = {"type": "command", "text": "look\x00here"}
        valid, error = validator.validate(message)

        assert valid is False
        assert "control characters" in error.lower()

    def test_allowed_whitespace_in_command(self):
        """Test that normal whitespace is allowed in commands."""
        validator = MessageValidator(enabled=True)

        message = {"type": "command", "text": "say Hello, world!\nHow are you?"}
        valid, error = validator.validate(message)

        assert valid is True

    def test_valid_ping_message(self):
        """Test that ping messages are accepted."""
        validator = MessageValidator(enabled=True)

        message = {"type": "ping", "timestamp": 1234567890}
        valid, error = validator.validate(message)

        assert valid is True

    def test_unknown_message_type_allowed(self):
        """Test that unknown message types are allowed (for extensibility)."""
        validator = MessageValidator(enabled=True)

        message = {"type": "custom_event", "data": {}}
        valid, error = validator.validate(message)

        assert valid is True

    def test_validation_disabled(self):
        """Test that validation can be disabled."""
        validator = MessageValidator(enabled=False)

        message = {}  # Invalid message
        valid, error = validator.validate(message)

        assert valid is True

    def test_parse_and_validate_valid_json(self):
        """Test parsing and validating valid JSON."""
        validator = MessageValidator(enabled=True)

        raw = '{"type": "command", "text": "north"}'
        message, error = validator.parse_and_validate(raw)

        assert error is None
        assert message["type"] == "command"
        assert message["text"] == "north"

    def test_parse_and_validate_invalid_json(self):
        """Test parsing invalid JSON."""
        validator = MessageValidator(enabled=True)

        raw = '{"type": "command", text: invalid}'
        message, error = validator.parse_and_validate(raw)

        assert message is None
        assert "invalid json" in error.lower()

    def test_parse_and_validate_non_object(self):
        """Test that non-object JSON is rejected."""
        validator = MessageValidator(enabled=True)

        raw = '"just a string"'
        message, error = validator.parse_and_validate(raw)

        assert message is None
        assert "object" in error.lower()


# =============================================================================
# Test Heartbeat Manager
# =============================================================================


class TestHeartbeatManager:
    """Tests for connection heartbeat monitoring."""

    def test_register_connection(self):
        """Test registering a connection for heartbeat monitoring."""
        manager = HeartbeatManager(interval=30, timeout=10)

        manager.register_connection("conn1")

        assert "conn1" in manager._connections
        assert manager._connections["conn1"].is_healthy is True

    def test_unregister_connection(self):
        """Test unregistering a connection."""
        manager = HeartbeatManager()
        manager.register_connection("conn1")

        manager.unregister_connection("conn1")

        assert "conn1" not in manager._connections

    def test_record_pong(self):
        """Test recording a pong response."""
        manager = HeartbeatManager()
        manager.register_connection("conn1")

        # Record a ping was sent
        manager.record_ping_sent("conn1")

        # Record pong received
        manager.record_pong_received("conn1")

        health = manager._connections["conn1"]
        assert health.missed_pongs == 0
        assert health.is_healthy is True

    def test_missed_pong_detection(self):
        """Test detection of missed pongs."""
        manager = HeartbeatManager(interval=30, timeout=1, max_missed_pongs=2)
        manager.register_connection("conn1")

        # Simulate ping sent 2 seconds ago with no pong
        health = manager._connections["conn1"]
        health.last_ping_sent = time.time() - 2
        health.last_pong_received = time.time() - 5

        # Check health - should increment missed_pongs
        is_healthy = manager.check_health("conn1")

        assert health.missed_pongs == 1
        assert is_healthy is True  # Not yet at max

    def test_connection_marked_unhealthy(self):
        """Test that connection is marked unhealthy after too many missed pongs."""
        manager = HeartbeatManager(interval=30, timeout=1, max_missed_pongs=2)
        manager.register_connection("conn1")

        health = manager._connections["conn1"]
        health.missed_pongs = 1
        health.last_ping_sent = time.time() - 2
        health.last_pong_received = time.time() - 10

        # Check health - should mark unhealthy
        is_healthy = manager.check_health("conn1")

        assert health.missed_pongs == 2
        assert health.is_healthy is False
        assert is_healthy is False

    def test_get_connections_needing_ping(self):
        """Test getting connections that need a ping sent."""
        manager = HeartbeatManager(interval=5, timeout=10)
        manager.register_connection("conn1")
        manager.register_connection("conn2")

        # Simulate conn1 last received pong 10 seconds ago
        manager._connections["conn1"].last_pong_received = time.time() - 10
        # Simulate conn2 just received pong
        manager._connections["conn2"].last_pong_received = time.time()

        needs_ping = manager.get_connections_needing_ping()

        assert "conn1" in needs_ping
        assert "conn2" not in needs_ping

    def test_get_unhealthy_connections(self):
        """Test getting unhealthy connections."""
        manager = HeartbeatManager()
        manager.register_connection("conn1")
        manager.register_connection("conn2")

        # Mark conn1 as unhealthy
        manager._connections["conn1"].is_healthy = False

        unhealthy = manager.get_unhealthy_connections()

        assert "conn1" in unhealthy
        assert "conn2" not in unhealthy

    def test_get_stats(self):
        """Test heartbeat statistics."""
        manager = HeartbeatManager()
        manager.register_connection("conn1")
        manager.register_connection("conn2")
        manager._connections["conn2"].is_healthy = False

        stats = manager.get_stats()

        assert stats["total_connections"] == 2
        assert stats["healthy_connections"] == 1
        assert stats["unhealthy_connections"] == 1


# =============================================================================
# Test Security Manager (Integration)
# =============================================================================


class TestWebSocketSecurityManager:
    """Integration tests for the unified security manager."""

    @pytest.mark.asyncio
    async def test_validate_connection_success(self):
        """Test successful connection validation."""
        manager = WebSocketSecurityManager()

        # Mock websocket
        websocket = MagicMock()
        websocket.headers = {"origin": "http://localhost:3000"}

        valid, error = await manager.validate_connection(
            websocket, "192.168.1.1", "user123"
        )

        assert valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_validate_connection_invalid_origin(self):
        """Test connection rejection for invalid origin."""
        config = WebSocketSecurityConfig()
        config.allowed_origins = ["http://localhost:3000"]
        config.origin_validation_enabled = True
        manager = WebSocketSecurityManager(config)

        websocket = MagicMock()
        websocket.headers = {"origin": "https://evil.com"}

        valid, error = await manager.validate_connection(
            websocket, "192.168.1.1"
        )

        assert valid is False
        assert "evil.com" in error

    @pytest.mark.asyncio
    async def test_validate_connection_ip_limit(self):
        """Test connection rejection when IP limit reached."""
        config = WebSocketSecurityConfig()
        config.max_connections_per_ip = 1
        manager = WebSocketSecurityManager(config)

        # Register first connection
        manager.register_connection("conn1", "192.168.1.1")

        websocket = MagicMock()
        websocket.headers = {}

        valid, error = await manager.validate_connection(
            websocket, "192.168.1.1"
        )

        assert valid is False
        assert "limit" in error.lower()

    def test_validate_message_success(self):
        """Test successful message validation."""
        manager = WebSocketSecurityManager()

        raw = '{"type": "command", "text": "look"}'
        valid, message, error = manager.validate_message(raw)

        assert valid is True
        assert message["type"] == "command"
        assert error is None

    def test_validate_message_too_large(self):
        """Test rejection of oversized messages."""
        config = WebSocketSecurityConfig()
        config.max_message_size = 100
        manager = WebSocketSecurityManager(config)

        raw = '{"type": "command", "text": "' + "x" * 200 + '"}'
        valid, message, error = manager.validate_message(raw)

        assert valid is False
        assert message is None
        assert "exceeds limit" in error.lower()

    def test_validate_message_invalid_json(self):
        """Test rejection of invalid JSON."""
        manager = WebSocketSecurityManager()

        raw = "not valid json {"
        valid, message, error = manager.validate_message(raw)

        assert valid is False
        assert message is None
        assert "json" in error.lower()

    def test_register_and_cleanup_connection(self):
        """Test connection lifecycle management."""
        manager = WebSocketSecurityManager()

        # Register
        manager.register_connection("conn1", "192.168.1.1", "user123")

        # Verify registered
        stats = manager.get_stats()
        assert stats["connections"]["total_connections"] == 1

        # Cleanup
        manager.cleanup_connection("conn1")

        # Verify cleaned up
        stats = manager.get_stats()
        assert stats["connections"]["total_connections"] == 0

    def test_get_stats(self):
        """Test combined statistics."""
        manager = WebSocketSecurityManager()

        manager.register_connection("conn1", "192.168.1.1", "user1")
        manager.register_connection("conn2", "192.168.1.2", "user2")

        stats = manager.get_stats()

        assert "connections" in stats
        assert "heartbeat" in stats
        assert "config" in stats
        assert stats["connections"]["total_connections"] == 2


# =============================================================================
# Test Utility Functions
# =============================================================================


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_get_client_ip_direct(self):
        """Test getting client IP from direct connection."""
        websocket = MagicMock()
        websocket.headers = {}
        websocket.client = MagicMock()
        websocket.client.host = "192.168.1.100"

        ip = get_client_ip_from_websocket(websocket)

        assert ip == "192.168.1.100"

    def test_get_client_ip_forwarded(self):
        """Test getting client IP from X-Forwarded-For header."""
        websocket = MagicMock()
        websocket.headers = {"x-forwarded-for": "10.0.0.1, 10.0.0.2, 10.0.0.3"}
        websocket.client = MagicMock()
        websocket.client.host = "192.168.1.100"

        ip = get_client_ip_from_websocket(websocket)

        # Should take first IP (original client)
        assert ip == "10.0.0.1"

    def test_get_client_ip_no_client(self):
        """Test fallback when no client info available."""
        websocket = MagicMock()
        websocket.headers = {}
        websocket.client = None

        ip = get_client_ip_from_websocket(websocket)

        assert ip == "unknown"


# =============================================================================
# Global Instance Tests
# =============================================================================


class TestGlobalInstances:
    """Tests for global security instances."""

    def test_global_config_exists(self):
        """Test that global config is initialized."""
        assert ws_security_config is not None
        assert isinstance(ws_security_config, WebSocketSecurityConfig)

    def test_global_manager_exists(self):
        """Test that global manager is initialized."""
        assert ws_security_manager is not None
        assert isinstance(ws_security_manager, WebSocketSecurityManager)
