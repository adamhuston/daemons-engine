"""
Unit tests for Debug Event Logger (Phase QA - Task 1.8).

Tests the DebugEventLogger class including:
- Event recording (errors, warnings, performance, race conditions, etc.)
- Circular buffer functionality
- Subscription/unsubscription
- Event filtering
- Event counts
- Buffer clearing
"""

import asyncio
from datetime import datetime

import pytest

from daemons.logging import DebugEventLogger

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def debug_logger():
    """Create a fresh DebugEventLogger instance for testing."""
    return DebugEventLogger(buffer_size=100)


@pytest.fixture
def small_buffer_logger():
    """Create a DebugEventLogger with a small buffer for testing overflow."""
    return DebugEventLogger(buffer_size=5)


# =============================================================================
# Test Initialization
# =============================================================================


class TestDebugEventLoggerInit:
    """Tests for DebugEventLogger initialization."""

    def test_default_initialization(self):
        """Test default buffer size initialization."""
        logger = DebugEventLogger()
        assert logger._buffer_size == 1000
        assert logger.buffer_count == 0
        assert logger.subscriber_count == 0

    def test_custom_buffer_size(self):
        """Test custom buffer size initialization."""
        logger = DebugEventLogger(buffer_size=50)
        assert logger._buffer_size == 50

    def test_initial_event_counter(self):
        """Test that event counter starts at 0."""
        logger = DebugEventLogger()
        assert logger._event_counter == 0


# =============================================================================
# Test Event Recording
# =============================================================================


class TestRecordError:
    """Tests for record_error method."""

    def test_record_error_basic(self, debug_logger):
        """Test basic error recording."""
        debug_logger.record_error(
            error_type="test_error",
            message="Test error message",
        )

        assert debug_logger.buffer_count == 1
        events = debug_logger.get_recent_events()
        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert events[0]["severity"] == "error"
        assert events[0]["message"] == "Test error message"
        assert "test_error" in events[0]["context"].get("error_type", "")

    def test_record_error_with_context(self, debug_logger):
        """Test error recording with additional context."""
        debug_logger.record_error(
            error_type="test_error",
            message="Error with context",
            context={"player_id": "player_123", "command": "test_command"},
        )

        events = debug_logger.get_recent_events()
        assert events[0]["context"]["player_id"] == "player_123"
        assert events[0]["context"]["command"] == "test_command"

    def test_record_error_with_exception(self, debug_logger):
        """Test error recording with exception details."""
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            debug_logger.record_error(
                error_type="test_error",
                message="Error with exception",
                exception=e,
            )

        events = debug_logger.get_recent_events()
        assert "exception" in events[0]
        assert events[0]["exception"]["type"] == "ValueError"
        assert events[0]["exception"]["message"] == "Test exception"

    def test_record_error_severity_override(self, debug_logger):
        """Test error recording with custom severity."""
        debug_logger.record_error(
            error_type="test_error",
            message="Critical error",
            severity="critical",
        )

        events = debug_logger.get_recent_events()
        assert events[0]["severity"] == "critical"


class TestRecordWarning:
    """Tests for record_warning method."""

    def test_record_warning_basic(self, debug_logger):
        """Test basic warning recording."""
        debug_logger.record_warning(
            warning_type="test_warning",
            message="Test warning message",
        )

        events = debug_logger.get_recent_events()
        assert len(events) == 1
        assert events[0]["type"] == "warning"
        assert events[0]["severity"] == "warning"


class TestRecordPerformanceAnomaly:
    """Tests for record_performance_anomaly method."""

    def test_record_performance_anomaly(self, debug_logger):
        """Test performance anomaly recording."""
        debug_logger.record_performance_anomaly(
            operation="test_operation",
            duration_ms=500.0,
            threshold_ms=100.0,
        )

        events = debug_logger.get_recent_events()
        assert len(events) == 1
        assert events[0]["type"] == "performance"
        assert events[0]["context"]["operation"] == "test_operation"
        assert events[0]["context"]["duration_ms"] == 500.0
        assert events[0]["context"]["threshold_ms"] == 100.0
        assert events[0]["context"]["exceeded_by_pct"] == 400.0


class TestRecordRaceConditionIndicator:
    """Tests for record_race_condition_indicator method."""

    def test_record_race_condition(self, debug_logger):
        """Test race condition indicator recording."""
        debug_logger.record_race_condition_indicator(
            indicator_type="stale_read",
            message="Detected stale data",
            context={"player_id": "player_123", "entity_id": "entity_456"},
        )

        events = debug_logger.get_recent_events()
        assert len(events) == 1
        assert events[0]["type"] == "race_condition"
        assert events[0]["severity"] == "warning"
        assert events[0]["context"]["indicator_type"] == "stale_read"


class TestRecordConnectionEvent:
    """Tests for record_connection_event method."""

    def test_record_connection_event(self, debug_logger):
        """Test connection event recording."""
        debug_logger.record_connection_event(
            event_subtype="connect",
            message="Player connected",
            context={"player_id": "player_123", "ip_address": "192.168.1.1"},
        )

        events = debug_logger.get_recent_events()
        assert len(events) == 1
        assert events[0]["type"] == "connection"
        assert events[0]["context"]["connection_event"] == "connect"


class TestRecordStateConflict:
    """Tests for record_state_conflict method."""

    def test_record_state_conflict(self, debug_logger):
        """Test state conflict recording."""
        debug_logger.record_state_conflict(
            entity_type="player",
            entity_id="player_123",
            field="gold",
            expected_value=100,
            actual_value=50,
        )

        events = debug_logger.get_recent_events()
        assert len(events) == 1
        assert events[0]["type"] == "state_conflict"
        assert events[0]["context"]["expected_value"] == "100"
        assert events[0]["context"]["actual_value"] == "50"


class TestRecordAbilityError:
    """Tests for record_ability_error method."""

    def test_record_ability_error(self, debug_logger):
        """Test ability error recording."""
        debug_logger.record_ability_error(
            ability_id="fireball",
            error_type="execution",
            message="Failed to cast fireball",
            player_id="player_123",
            target_id="enemy_456",
        )

        events = debug_logger.get_recent_events()
        assert len(events) == 1
        assert events[0]["context"]["ability_id"] == "fireball"
        assert events[0]["context"]["player_id"] == "player_123"


class TestRecordCommandError:
    """Tests for record_command_error method."""

    def test_record_command_error(self, debug_logger):
        """Test command error recording."""
        debug_logger.record_command_error(
            command="attack",
            error_type="execution",
            message="Command execution failed",
            player_id="player_123",
        )

        events = debug_logger.get_recent_events()
        assert len(events) == 1
        assert events[0]["context"]["command"] == "attack"


class TestRecordWebsocketError:
    """Tests for record_websocket_error method."""

    def test_record_websocket_error(self, debug_logger):
        """Test websocket error recording."""
        debug_logger.record_websocket_error(
            error_type="connection_lost",
            message="WebSocket connection lost",
            player_id="player_123",
        )

        events = debug_logger.get_recent_events()
        assert len(events) == 1
        assert "websocket_connection_lost" in events[0]["context"]["error_type"]


# =============================================================================
# Test Circular Buffer
# =============================================================================


class TestCircularBuffer:
    """Tests for circular buffer functionality."""

    def test_buffer_stores_events(self, debug_logger):
        """Test that events are stored in buffer."""
        for i in range(5):
            debug_logger.record_error("test", f"Error {i}")

        assert debug_logger.buffer_count == 5

    def test_buffer_overflow(self, small_buffer_logger):
        """Test buffer overflow behavior (oldest events removed)."""
        # Fill buffer beyond capacity
        for i in range(10):
            small_buffer_logger.record_error("test", f"Error {i}")

        # Should only have last 5 events
        assert small_buffer_logger.buffer_count == 5
        events = small_buffer_logger.get_recent_events()
        # Oldest event should be Error 5 (0-4 were dropped)
        assert events[0]["message"] == "Error 5"
        assert events[-1]["message"] == "Error 9"

    def test_event_ids_increment(self, debug_logger):
        """Test that event IDs increment correctly."""
        for i in range(3):
            debug_logger.record_error("test", f"Error {i}")

        events = debug_logger.get_recent_events()
        assert events[0]["id"] == 1
        assert events[1]["id"] == 2
        assert events[2]["id"] == 3


# =============================================================================
# Test Event Filtering
# =============================================================================


class TestGetRecentEvents:
    """Tests for get_recent_events with filters."""

    def test_get_all_events(self, debug_logger):
        """Test getting all events without filters."""
        debug_logger.record_error("test", "Error 1")
        debug_logger.record_warning("test", "Warning 1")

        events = debug_logger.get_recent_events()
        assert len(events) == 2

    def test_filter_by_event_type(self, debug_logger):
        """Test filtering by event type."""
        debug_logger.record_error("test", "Error 1")
        debug_logger.record_warning("test", "Warning 1")
        debug_logger.record_error("test", "Error 2")

        events = debug_logger.get_recent_events(event_type="error")
        assert len(events) == 2
        assert all(e["type"] == "error" for e in events)

    def test_filter_by_severity(self, debug_logger):
        """Test filtering by severity."""
        debug_logger.record_error("test", "Error 1")
        debug_logger.record_error("test", "Critical 1", severity="critical")
        debug_logger.record_warning("test", "Warning 1")

        events = debug_logger.get_recent_events(severity="critical")
        assert len(events) == 1
        assert events[0]["severity"] == "critical"

    def test_filter_by_since_id(self, debug_logger):
        """Test filtering by since_id."""
        for i in range(5):
            debug_logger.record_error("test", f"Error {i}")

        events = debug_logger.get_recent_events(since_id=3)
        assert len(events) == 2
        assert events[0]["id"] == 4
        assert events[1]["id"] == 5

    def test_limit_results(self, debug_logger):
        """Test limiting number of results."""
        for i in range(10):
            debug_logger.record_error("test", f"Error {i}")

        events = debug_logger.get_recent_events(count=3)
        assert len(events) == 3

    def test_combined_filters(self, debug_logger):
        """Test combining multiple filters."""
        debug_logger.record_error("test", "Error 1")
        debug_logger.record_warning("test", "Warning 1")
        debug_logger.record_error("test", "Error 2")
        debug_logger.record_error("test", "Error 3")

        events = debug_logger.get_recent_events(
            event_type="error",
            since_id=1,
            count=2
        )
        assert len(events) == 2
        assert all(e["type"] == "error" for e in events)


# =============================================================================
# Test Event Counts
# =============================================================================


class TestGetEventCounts:
    """Tests for get_event_counts method."""

    def test_empty_counts(self, debug_logger):
        """Test counts with empty buffer."""
        counts = debug_logger.get_event_counts()
        assert counts == {}

    def test_count_by_type(self, debug_logger):
        """Test counting events by type."""
        debug_logger.record_error("test", "Error 1")
        debug_logger.record_error("test", "Error 2")
        debug_logger.record_warning("test", "Warning 1")

        counts = debug_logger.get_event_counts()
        assert counts.get("error", {}).get("error", 0) == 2
        assert counts.get("warning", {}).get("warning", 0) == 1


# =============================================================================
# Test Clear Buffer
# =============================================================================


class TestClearBuffer:
    """Tests for clear_buffer method."""

    def test_clear_buffer(self, debug_logger):
        """Test clearing the buffer."""
        for i in range(5):
            debug_logger.record_error("test", f"Error {i}")

        assert debug_logger.buffer_count == 5

        cleared = debug_logger.clear_buffer()

        assert cleared == 5
        assert debug_logger.buffer_count == 0

    def test_clear_empty_buffer(self, debug_logger):
        """Test clearing an empty buffer."""
        cleared = debug_logger.clear_buffer()
        assert cleared == 0


# =============================================================================
# Test Subscriptions (Async)
# =============================================================================


class TestSubscriptions:
    """Tests for subscription functionality."""

    def test_subscribe(self, debug_logger):
        """Test subscribing to events."""
        queue = debug_logger.subscribe("test_subscriber")

        assert queue is not None
        assert debug_logger.subscriber_count == 1

    def test_subscribe_duplicate(self, debug_logger):
        """Test subscribing with same ID returns existing queue."""
        queue1 = debug_logger.subscribe("test_subscriber")
        queue2 = debug_logger.subscribe("test_subscriber")

        assert queue1 is queue2
        assert debug_logger.subscriber_count == 1

    def test_unsubscribe(self, debug_logger):
        """Test unsubscribing from events."""
        debug_logger.subscribe("test_subscriber")
        assert debug_logger.subscriber_count == 1

        result = debug_logger.unsubscribe("test_subscriber")

        assert result is True
        assert debug_logger.subscriber_count == 0

    def test_unsubscribe_nonexistent(self, debug_logger):
        """Test unsubscribing non-existent subscriber."""
        result = debug_logger.unsubscribe("nonexistent")
        assert result is False

    def test_multiple_subscribers(self, debug_logger):
        """Test multiple subscribers."""
        debug_logger.subscribe("subscriber_1")
        debug_logger.subscribe("subscriber_2")
        debug_logger.subscribe("subscriber_3")

        assert debug_logger.subscriber_count == 3

    @pytest.mark.asyncio
    async def test_subscriber_receives_events(self, debug_logger):
        """Test that subscribers receive events."""
        queue = debug_logger.subscribe("test_subscriber")

        # Record an event
        debug_logger.record_error("test", "Test error")

        # Check queue received the event
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event["message"] == "Test error"

    @pytest.mark.asyncio
    async def test_subscriber_queue_full_handling(self, debug_logger):
        """Test handling of full subscriber queue."""
        # Subscribe with small queue
        queue = debug_logger.subscribe("test_subscriber", queue_size=2)

        # Record more events than queue can hold
        for i in range(5):
            debug_logger.record_error("test", f"Error {i}")

        # Should have dropped oldest events, queue should have latest
        assert queue.qsize() == 2


# =============================================================================
# Test Event Structure
# =============================================================================


class TestEventStructure:
    """Tests for event structure and timestamps."""

    def test_event_has_required_fields(self, debug_logger):
        """Test that events have all required fields."""
        debug_logger.record_error("test", "Test error")

        events = debug_logger.get_recent_events()
        event = events[0]

        assert "id" in event
        assert "timestamp" in event
        assert "type" in event
        assert "severity" in event
        assert "message" in event
        assert "context" in event

    def test_timestamp_format(self, debug_logger):
        """Test that timestamp is in ISO format with Z suffix."""
        debug_logger.record_error("test", "Test error")

        events = debug_logger.get_recent_events()
        timestamp = events[0]["timestamp"]

        # Should be parseable as ISO format
        assert timestamp.endswith("Z")
        # Should be valid ISO format
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    def test_event_types_constants(self):
        """Test that event type constants are defined."""
        assert DebugEventLogger.EVENT_TYPE_ERROR == "error"
        assert DebugEventLogger.EVENT_TYPE_WARNING == "warning"
        assert DebugEventLogger.EVENT_TYPE_PERFORMANCE == "performance"
        assert DebugEventLogger.EVENT_TYPE_RACE_CONDITION == "race_condition"
        assert DebugEventLogger.EVENT_TYPE_CONNECTION == "connection"
        assert DebugEventLogger.EVENT_TYPE_STATE_CONFLICT == "state_conflict"

    def test_severity_constants(self):
        """Test that severity level constants are defined."""
        assert DebugEventLogger.SEVERITY_DEBUG == "debug"
        assert DebugEventLogger.SEVERITY_INFO == "info"
        assert DebugEventLogger.SEVERITY_WARNING == "warning"
        assert DebugEventLogger.SEVERITY_ERROR == "error"
        assert DebugEventLogger.SEVERITY_CRITICAL == "critical"


# =============================================================================
# Test Properties
# =============================================================================


class TestProperties:
    """Tests for logger properties."""

    def test_buffer_count_property(self, debug_logger):
        """Test buffer_count property."""
        assert debug_logger.buffer_count == 0

        debug_logger.record_error("test", "Error")
        assert debug_logger.buffer_count == 1

    def test_subscriber_count_property(self, debug_logger):
        """Test subscriber_count property."""
        assert debug_logger.subscriber_count == 0

        debug_logger.subscribe("sub1")
        assert debug_logger.subscriber_count == 1

        debug_logger.subscribe("sub2")
        assert debug_logger.subscriber_count == 2

        debug_logger.unsubscribe("sub1")
        assert debug_logger.subscriber_count == 1
