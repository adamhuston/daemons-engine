We built fast and sloppy, there are lots of random bugs that crop up in runtime. We need a way to track and fix them. This is the roadmap for our QA process and the tools we will use to manage it.

## Current Testing Infrastructure

### Testing Framework
- **Primary Tool**: pytest with hierarchical configuration using `conftest.py` files
- **Test Data**: Organized fixture system with reusable test data (players, YAML samples, ability samples)
- **Test Builders**: Custom builders for creating test objects (particularly for abilities testing)

### Test Organization Structure

Our tests are organized into well-defined categories that mirror our development phases:

#### **Unit Tests** (`backend/tests/unit/`)
Core component testing covering:
- Models, stats, and world mechanics (`test_models.py`, `test_stats.py`, `test_world.py`)
- Environmental systems (`test_weather.py`, `test_temperature.py`, `test_biome.py`, `test_flora.py`)
- Security components (`test_websocket_security.py`, `test_input_sanitization.py`)
- Legacy system deprecation tracking (`test_legacy_deprecation.py`)

#### **Integration Tests** (`backend/tests/integration/`)
End-to-end workflow testing:
- Combat flow validation (`test_combat_flow.py`)
- Quest progression systems (`test_quest_flow.py`)

#### **Systems Tests** (`backend/tests/systems/`)
Service layer and infrastructure testing:
- Persistence and data management (`test_persistence.py`, `test_bulk_service.py`)
- File management and schema validation (`test_file_manager.py`, `test_schema_registry.py`)
- Population and spawning systems (`test_spawn_population.py`)
- Time management system (`test_time_manager.py`)
- Query and validation services (`test_query_service.py`, `test_validation_service.py`)

#### **API Tests** (`backend/tests/api/`)
Protocol and interface testing:
- WebSocket protocol validation (`test_websocket.py`)
- Admin route functionality (`test_admin_routes.py`)
- Schema API validation (`test_schema_api.py`)

#### **Feature-Specific Tests**
- **Abilities System** (`backend/tests/abilities/`) - Phase 9 combat abilities
- **Social Systems** (`backend/tests/commands/`) - Phase 10 clans, factions, groups

### Test Execution
- **Full Suite**: `pytest` from backend directory
- **By Category**: `pytest tests/unit/`, `pytest tests/integration/`, etc.
- **Specific Features**: `pytest tests/abilities/`, `pytest tests/commands/`

### Current Gaps and Runtime Bug Sources

While we have comprehensive test coverage across architectural layers, **runtime bugs still occur** due to:
- Lack of property-based testing for edge cases
- Limited chaos engineering or fault injection testing
- Insufficient load testing for WebSocket connections under stress
- Missing end-to-end protocol testing with real client connections
- Race condition testing in the real-time engine systems

## Proposed QA Process and Debugging Infrastructure

To address the runtime bug issues that our comprehensive test suite isn't catching, we need a **hybrid debugging approach** that combines enhanced backend instrumentation with real-time monitoring tools.

### Debugging Client Architecture (Recommended)

#### **1. Enhanced Backend Instrumentation** (Built-in)
Extend our existing logging and metrics infrastructure:
- **Structured Error Events**: New WebSocket event type specifically for debugging clients to monitor real-time issues
- **Enhanced Metrics**: Expand existing metrics system to track race conditions, connection drops, and ability execution failures
- **Debug Admin Endpoints**: Add `/api/admin/debug/*` endpoints for error logs, performance data, and system diagnostics
- **Runtime Pattern Detection**: Hook into existing persistence and metrics to identify error clusters

#### **2. Concurrent Debugging Client** (Primary Solution)
Build a debugging client that launches alongside the main application:

**Connection Methods:**
- WebSocket protocol for real-time event monitoring
- Admin REST API for server state inspection via existing `/api/admin/server/status` and `/api/admin/world/state` endpoints
- Direct log file access or new log streaming endpoint

**Core Features:**
- **Real-time WebSocket Event Monitor**: Subscribe to all event types, track patterns in `stat_update`, `ability_cast_complete`, `ability_error` events
- **Admin API Dashboard**: Pull from `/api/admin/server/metrics`, `/api/admin/world/players` for live system state
- **Error Pattern Detection**: Monitor clusters of ability errors, connection drops, combat flow issues
- **Load Testing Integration**: Generate concurrent connections to test WebSocket scaling limits

**Target Issues:**
- Race conditions in real-time engine systems
- WebSocket connection stability under load
- End-to-end protocol validation with actual client connections
- Property-based edge case discovery

#### **3. Error Tracking Integration**
Integrate with external error tracking service (Sentry, Rollbar):
- Automatic error aggregation and alerting for runtime issues
- Stack trace collection for debugging "random bugs"
- Performance monitoring for time-critical systems (abilities, combat, movement)
- Historical error pattern analysis

### Implementation Benefits for Our Architecture

**Leverages Existing Infrastructure:**
- Our protocol already supports multiple concurrent connections
- Admin API provides comprehensive server inspection capabilities
- WebSocket event system enables real-time debugging without code changes
- Existing structured logging and metrics provide foundation for enhanced monitoring

**Addresses Specific Gaps:**
- **Race Condition Detection**: Real-time monitoring of ability execution timing and stat updates
- **WebSocket Load Testing**: Concurrent debugging clients can simulate high connection loads
- **End-to-End Protocol Testing**: Full client-server interaction validation using real WebSocket connections
- **Property-Based Edge Cases**: Monitor actual gameplay for unexpected event sequences and state combinations

### Deployment Strategy

**Phase 1**: Enhanced backend instrumentation and basic debugging client
**Phase 2**: Advanced error pattern detection and load testing capabilities
**Phase 3**: Integration with external monitoring services and automated alerting

This approach separates debugging concerns from production code while providing comprehensive real-time visibility into the runtime issues that traditional testing hasn't captured.
