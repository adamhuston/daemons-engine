# backend/tests/unit/test_legacy_deprecation.py
"""
Unit tests for the legacy endpoint deprecation module (Phase 16.6).

Tests cover:
- Configuration loading from environment variables
- Deprecation phase handling (warn, throttle, disabled)
- Connection validation based on phase and limits
- Deprecation message generation
- Rate limit adjustments for throttle phase
- Connection tracking and metrics
"""

import os
from unittest.mock import patch

import pytest

from daemons.legacy_deprecation import (
    DeprecationPhase,
    LegacyDeprecationConfig,
    LegacyDeprecationManager,
    legacy_deprecation_manager,
)

# =============================================================================
# Configuration Tests
# =============================================================================

class TestLegacyDeprecationConfig:
    """Tests for LegacyDeprecationConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            # Need to create new instance to pick up env vars
            config = LegacyDeprecationConfig()

        assert config.legacy_auth_enabled is True
        assert config.deprecation_phase == DeprecationPhase.WARN
        assert "deprecated" in config.deprecation_message.lower()
        assert config.throttle_commands_per_minute == 10
        assert config.throttle_chats_per_minute == 5
        assert config.legacy_max_connections_per_ip == 3
        assert config.log_legacy_connections is True

    def test_env_override_legacy_auth_enabled(self):
        """Test WS_LEGACY_AUTH_ENABLED environment variable."""
        with patch.dict(os.environ, {"WS_LEGACY_AUTH_ENABLED": "false"}):
            config = LegacyDeprecationConfig()
            assert config.legacy_auth_enabled is False

        with patch.dict(os.environ, {"WS_LEGACY_AUTH_ENABLED": "true"}):
            config = LegacyDeprecationConfig()
            assert config.legacy_auth_enabled is True

    def test_env_override_deprecation_phase(self):
        """Test WS_LEGACY_DEPRECATION_PHASE environment variable."""
        with patch.dict(os.environ, {"WS_LEGACY_DEPRECATION_PHASE": "warn"}):
            config = LegacyDeprecationConfig()
            assert config.deprecation_phase == DeprecationPhase.WARN

        with patch.dict(os.environ, {"WS_LEGACY_DEPRECATION_PHASE": "throttle"}):
            config = LegacyDeprecationConfig()
            assert config.deprecation_phase == DeprecationPhase.THROTTLE

        with patch.dict(os.environ, {"WS_LEGACY_DEPRECATION_PHASE": "disabled"}):
            config = LegacyDeprecationConfig()
            assert config.deprecation_phase == DeprecationPhase.DISABLED

    def test_env_override_deprecation_message(self):
        """Test WS_LEGACY_DEPRECATION_MESSAGE environment variable."""
        custom_msg = "Custom deprecation warning"
        with patch.dict(os.environ, {"WS_LEGACY_DEPRECATION_MESSAGE": custom_msg}):
            config = LegacyDeprecationConfig()
            assert config.deprecation_message == custom_msg

    def test_env_override_sunset_date(self):
        """Test WS_LEGACY_SUNSET_DATE environment variable."""
        with patch.dict(os.environ, {"WS_LEGACY_SUNSET_DATE": "2026-01-01"}):
            config = LegacyDeprecationConfig()
            assert config.sunset_date == "2026-01-01"

    def test_env_override_throttle_limits(self):
        """Test throttle rate limit environment variables."""
        with patch.dict(os.environ, {
            "WS_LEGACY_THROTTLE_COMMANDS_PER_MINUTE": "5",
            "WS_LEGACY_THROTTLE_CHATS_PER_MINUTE": "2",
        }):
            config = LegacyDeprecationConfig()
            assert config.throttle_commands_per_minute == 5
            assert config.throttle_chats_per_minute == 2

    def test_env_override_max_connections(self):
        """Test WS_LEGACY_MAX_CONNECTIONS_PER_IP environment variable."""
        with patch.dict(os.environ, {"WS_LEGACY_MAX_CONNECTIONS_PER_IP": "1"}):
            config = LegacyDeprecationConfig()
            assert config.legacy_max_connections_per_ip == 1

    def test_env_override_log_connections(self):
        """Test WS_LOG_LEGACY_CONNECTIONS environment variable."""
        with patch.dict(os.environ, {"WS_LOG_LEGACY_CONNECTIONS": "false"}):
            config = LegacyDeprecationConfig()
            assert config.log_legacy_connections is False


# =============================================================================
# Deprecation Phase Tests
# =============================================================================

class TestDeprecationPhase:
    """Tests for DeprecationPhase enum."""

    def test_phase_values(self):
        """Test all deprecation phase values."""
        assert DeprecationPhase.WARN.value == "warn"
        assert DeprecationPhase.THROTTLE.value == "throttle"
        assert DeprecationPhase.DISABLED.value == "disabled"

    def test_phase_from_string(self):
        """Test creating phase from string value."""
        assert DeprecationPhase("warn") == DeprecationPhase.WARN
        assert DeprecationPhase("throttle") == DeprecationPhase.THROTTLE
        assert DeprecationPhase("disabled") == DeprecationPhase.DISABLED

    def test_invalid_phase_raises(self):
        """Test invalid phase string raises ValueError."""
        with pytest.raises(ValueError):
            DeprecationPhase("invalid")


# =============================================================================
# Manager Tests - Connection Validation
# =============================================================================

class TestLegacyDeprecationManagerValidation:
    """Tests for connection validation logic."""

    def test_validate_connection_warn_phase_allowed(self):
        """Test connections allowed in WARN phase."""
        config = LegacyDeprecationConfig()
        config.legacy_auth_enabled = True
        config.deprecation_phase = DeprecationPhase.WARN
        manager = LegacyDeprecationManager(config)

        valid, error = manager.validate_connection("192.168.1.1")
        assert valid is True
        assert error is None

    def test_validate_connection_throttle_phase_allowed(self):
        """Test connections allowed in THROTTLE phase."""
        config = LegacyDeprecationConfig()
        config.legacy_auth_enabled = True
        config.deprecation_phase = DeprecationPhase.THROTTLE
        manager = LegacyDeprecationManager(config)

        valid, error = manager.validate_connection("192.168.1.1")
        assert valid is True
        assert error is None

    def test_validate_connection_disabled_phase_rejected(self):
        """Test connections rejected in DISABLED phase."""
        config = LegacyDeprecationConfig()
        config.deprecation_phase = DeprecationPhase.DISABLED
        manager = LegacyDeprecationManager(config)

        valid, error = manager.validate_connection("192.168.1.1")
        assert valid is False
        assert "disabled" in error.lower()
        assert "/ws/game/auth" in error

    def test_validate_connection_master_switch_disabled(self):
        """Test connections rejected when legacy_auth_enabled is False."""
        config = LegacyDeprecationConfig()
        config.legacy_auth_enabled = False
        config.deprecation_phase = DeprecationPhase.WARN
        manager = LegacyDeprecationManager(config)

        valid, error = manager.validate_connection("192.168.1.1")
        assert valid is False
        assert "disabled" in error.lower()

    def test_validate_connection_ip_limit_enforced(self):
        """Test IP connection limit is enforced."""
        config = LegacyDeprecationConfig()
        config.legacy_auth_enabled = True
        config.deprecation_phase = DeprecationPhase.WARN
        config.legacy_max_connections_per_ip = 2
        manager = LegacyDeprecationManager(config)

        # First two connections should be allowed
        manager.register_connection("192.168.1.1", "player1")
        manager.register_connection("192.168.1.1", "player2")

        # Third should be rejected
        valid, error = manager.validate_connection("192.168.1.1")
        assert valid is False
        assert "too many" in error.lower()
        assert "2" in error

    def test_validate_connection_different_ips_allowed(self):
        """Test different IPs have separate limits."""
        config = LegacyDeprecationConfig()
        config.legacy_auth_enabled = True
        config.deprecation_phase = DeprecationPhase.WARN
        config.legacy_max_connections_per_ip = 1
        manager = LegacyDeprecationManager(config)

        manager.register_connection("192.168.1.1", "player1")

        # Different IP should be allowed
        valid, error = manager.validate_connection("192.168.1.2")
        assert valid is True


# =============================================================================
# Manager Tests - Connection Registration
# =============================================================================

class TestLegacyDeprecationManagerRegistration:
    """Tests for connection registration and tracking."""

    def test_register_connection_updates_metrics(self):
        """Test registering connection updates all metrics."""
        config = LegacyDeprecationConfig()
        config.log_legacy_connections = False  # Suppress logging
        manager = LegacyDeprecationManager(config)

        manager.register_connection("192.168.1.1", "player1")

        metrics = manager.get_metrics()
        assert metrics["total_legacy_connections"] == 1
        assert metrics["active_legacy_connections"] == 1
        assert metrics["connections_by_ip_count"] == 1

    def test_register_multiple_connections(self):
        """Test registering multiple connections."""
        config = LegacyDeprecationConfig()
        config.log_legacy_connections = False
        manager = LegacyDeprecationManager(config)

        manager.register_connection("192.168.1.1", "player1")
        manager.register_connection("192.168.1.1", "player2")
        manager.register_connection("192.168.1.2", "player3")

        metrics = manager.get_metrics()
        assert metrics["total_legacy_connections"] == 3
        assert metrics["active_legacy_connections"] == 3
        assert metrics["connections_by_ip_count"] == 2

    def test_unregister_connection_updates_metrics(self):
        """Test unregistering connection updates metrics."""
        config = LegacyDeprecationConfig()
        config.log_legacy_connections = False
        manager = LegacyDeprecationManager(config)

        manager.register_connection("192.168.1.1", "player1")
        manager.unregister_connection("192.168.1.1", "player1")

        metrics = manager.get_metrics()
        assert metrics["total_legacy_connections"] == 1  # Total stays
        assert metrics["active_legacy_connections"] == 0
        assert metrics["connections_by_ip_count"] == 0

    def test_unregister_partial_for_ip(self):
        """Test unregistering one connection from IP with multiple."""
        config = LegacyDeprecationConfig()
        config.log_legacy_connections = False
        manager = LegacyDeprecationManager(config)

        manager.register_connection("192.168.1.1", "player1")
        manager.register_connection("192.168.1.1", "player2")
        manager.unregister_connection("192.168.1.1", "player1")

        metrics = manager.get_metrics()
        assert metrics["active_legacy_connections"] == 1
        assert metrics["connections_by_ip_count"] == 1

    def test_unregister_nonexistent_safe(self):
        """Test unregistering non-existent connection is safe."""
        config = LegacyDeprecationConfig()
        manager = LegacyDeprecationManager(config)

        # Should not raise
        manager.unregister_connection("192.168.1.1", "player1")

        metrics = manager.get_metrics()
        assert metrics["active_legacy_connections"] == 0

    def test_reset_metrics(self):
        """Test resetting metrics clears all tracking."""
        config = LegacyDeprecationConfig()
        config.log_legacy_connections = False
        manager = LegacyDeprecationManager(config)

        manager.register_connection("192.168.1.1", "player1")
        manager.register_connection("192.168.1.2", "player2")
        manager.reset_metrics()

        metrics = manager.get_metrics()
        assert metrics["total_legacy_connections"] == 0
        assert metrics["active_legacy_connections"] == 0
        assert metrics["connections_by_ip_count"] == 0


# =============================================================================
# Manager Tests - Deprecation Messages
# =============================================================================

class TestLegacyDeprecationManagerMessages:
    """Tests for deprecation message generation."""

    def test_get_deprecation_message_format(self):
        """Test deprecation message has expected format."""
        config = LegacyDeprecationConfig()
        manager = LegacyDeprecationManager(config)

        msg = manager.get_deprecation_message()

        assert msg["type"] == "deprecation_warning"
        assert "message" in msg
        assert "sunset_date" in msg
        assert "migration_url" in msg
        assert msg["migration_url"] == "/ws/game/auth"
        assert "phase" in msg

    def test_get_deprecation_message_custom_message(self):
        """Test custom deprecation message is used."""
        config = LegacyDeprecationConfig()
        config.deprecation_message = "Custom warning text"
        config.sunset_date = "2030-12-31"
        manager = LegacyDeprecationManager(config)

        msg = manager.get_deprecation_message()

        assert msg["message"] == "Custom warning text"
        assert msg["sunset_date"] == "2030-12-31"

    def test_get_deprecation_message_includes_phase(self):
        """Test deprecation message includes current phase."""
        for phase in DeprecationPhase:
            config = LegacyDeprecationConfig()
            config.deprecation_phase = phase
            manager = LegacyDeprecationManager(config)

            msg = manager.get_deprecation_message()
            assert msg["phase"] == phase.value

    def test_should_send_warning_warn_phase(self):
        """Test warning sent in WARN phase."""
        config = LegacyDeprecationConfig()
        config.deprecation_phase = DeprecationPhase.WARN
        manager = LegacyDeprecationManager(config)

        assert manager.should_send_warning() is True

    def test_should_send_warning_throttle_phase(self):
        """Test warning sent in THROTTLE phase."""
        config = LegacyDeprecationConfig()
        config.deprecation_phase = DeprecationPhase.THROTTLE
        manager = LegacyDeprecationManager(config)

        assert manager.should_send_warning() is True

    def test_should_send_warning_disabled_phase(self):
        """Test no warning in DISABLED phase (connection rejected anyway)."""
        config = LegacyDeprecationConfig()
        config.deprecation_phase = DeprecationPhase.DISABLED
        manager = LegacyDeprecationManager(config)

        # Technically moot since connection rejected, but test the logic
        assert manager.should_send_warning() is False


# =============================================================================
# Manager Tests - Rate Limits
# =============================================================================

class TestLegacyDeprecationManagerRateLimits:
    """Tests for rate limit adjustments based on phase."""

    def test_get_rate_limits_warn_phase(self):
        """Test normal rate limits in WARN phase."""
        config = LegacyDeprecationConfig()
        config.deprecation_phase = DeprecationPhase.WARN
        manager = LegacyDeprecationManager(config)

        commands_per_min, chats_per_min = manager.get_rate_limits()

        # Default limits for warn phase
        assert commands_per_min == 60
        assert chats_per_min == 30

    def test_get_rate_limits_throttle_phase(self):
        """Test reduced rate limits in THROTTLE phase."""
        config = LegacyDeprecationConfig()
        config.deprecation_phase = DeprecationPhase.THROTTLE
        config.throttle_commands_per_minute = 10
        config.throttle_chats_per_minute = 5
        manager = LegacyDeprecationManager(config)

        commands_per_min, chats_per_min = manager.get_rate_limits()

        assert commands_per_min == 10
        assert chats_per_min == 5

    def test_get_rate_limits_throttle_custom_values(self):
        """Test custom throttle rate limits are used."""
        config = LegacyDeprecationConfig()
        config.deprecation_phase = DeprecationPhase.THROTTLE
        config.throttle_commands_per_minute = 3
        config.throttle_chats_per_minute = 1
        manager = LegacyDeprecationManager(config)

        commands_per_min, chats_per_min = manager.get_rate_limits()

        assert commands_per_min == 3
        assert chats_per_min == 1


# =============================================================================
# Manager Tests - Properties
# =============================================================================

class TestLegacyDeprecationManagerProperties:
    """Tests for manager properties."""

    def test_is_enabled_property(self):
        """Test is_enabled property reflects config."""
        config = LegacyDeprecationConfig()
        config.legacy_auth_enabled = True
        manager = LegacyDeprecationManager(config)
        assert manager.is_enabled is True

        config.legacy_auth_enabled = False
        assert manager.is_enabled is False

    def test_phase_property(self):
        """Test phase property reflects config."""
        config = LegacyDeprecationConfig()
        config.deprecation_phase = DeprecationPhase.THROTTLE
        manager = LegacyDeprecationManager(config)

        assert manager.phase == DeprecationPhase.THROTTLE


# =============================================================================
# Manager Tests - Metrics
# =============================================================================

class TestLegacyDeprecationManagerMetrics:
    """Tests for metrics retrieval."""

    def test_get_metrics_format(self):
        """Test metrics dict has expected keys."""
        config = LegacyDeprecationConfig()
        manager = LegacyDeprecationManager(config)

        metrics = manager.get_metrics()

        assert "legacy_auth_enabled" in metrics
        assert "deprecation_phase" in metrics
        assert "total_legacy_connections" in metrics
        assert "active_legacy_connections" in metrics
        assert "connections_by_ip_count" in metrics

    def test_get_metrics_reflects_config(self):
        """Test metrics reflect current config."""
        config = LegacyDeprecationConfig()
        config.legacy_auth_enabled = False
        config.deprecation_phase = DeprecationPhase.DISABLED
        manager = LegacyDeprecationManager(config)

        metrics = manager.get_metrics()

        assert metrics["legacy_auth_enabled"] is False
        assert metrics["deprecation_phase"] == "disabled"


# =============================================================================
# Global Instance Tests
# =============================================================================

class TestGlobalInstance:
    """Tests for the global deprecation manager instance."""

    def test_global_instance_exists(self):
        """Test global instance is available."""
        assert legacy_deprecation_manager is not None

    def test_global_instance_is_manager(self):
        """Test global instance is correct type."""
        assert isinstance(legacy_deprecation_manager, LegacyDeprecationManager)

    def test_global_instance_has_config(self):
        """Test global instance has config."""
        assert legacy_deprecation_manager.config is not None
        assert isinstance(legacy_deprecation_manager.config, LegacyDeprecationConfig)


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_ip_address(self):
        """Test handling of empty IP address."""
        config = LegacyDeprecationConfig()
        config.legacy_auth_enabled = True
        config.deprecation_phase = DeprecationPhase.WARN
        manager = LegacyDeprecationManager(config)

        # Empty IP should still work (degenerate case)
        valid, error = manager.validate_connection("")
        assert valid is True

    def test_none_like_player_id(self):
        """Test handling edge case player IDs."""
        config = LegacyDeprecationConfig()
        config.log_legacy_connections = False
        manager = LegacyDeprecationManager(config)

        # Should not raise
        manager.register_connection("192.168.1.1", "")
        manager.unregister_connection("192.168.1.1", "")

    def test_multiple_active_to_zero(self):
        """Test active count doesn't go negative."""
        config = LegacyDeprecationConfig()
        config.log_legacy_connections = False
        manager = LegacyDeprecationManager(config)

        # Unregister more than registered
        manager.unregister_connection("192.168.1.1", "player1")
        manager.unregister_connection("192.168.1.1", "player1")

        metrics = manager.get_metrics()
        assert metrics["active_legacy_connections"] >= 0

    def test_phase_persistence_across_operations(self):
        """Test phase doesn't change during operations."""
        config = LegacyDeprecationConfig()
        config.deprecation_phase = DeprecationPhase.THROTTLE
        config.log_legacy_connections = False
        manager = LegacyDeprecationManager(config)

        manager.register_connection("192.168.1.1", "player1")
        assert manager.phase == DeprecationPhase.THROTTLE

        manager.unregister_connection("192.168.1.1", "player1")
        assert manager.phase == DeprecationPhase.THROTTLE

        manager.get_rate_limits()
        assert manager.phase == DeprecationPhase.THROTTLE
