# Step 3 TODO: Immediate Actions

## Priority 1: Fix Existing Tests (1-2 hours)

### A. Fix Model Test Field Names
**File:** `backend/tests/unit/test_models.py`

**Changes Needed:**
```python
# OLD (incorrect):
player = Player(player_id="test", name="Hero", ...)

# NEW (correct):
player = Player(id="test", name="Hero", current_room_id="room_1", ...)
```

**Field Mappings to Fix:**
- `player_id` → `id`
- `room_id` → `id`
- `area_id` → `id`
- `room_type_id` → `id`
- `item_id` → `id`
- `npc_id` → `id`
- `clan_id` → `id`
- `faction_id` → `id`
- `health/max_health` → `current_health/max_health`
- `mana/max_mana` → `current_energy/max_energy`
- Check UserAccount, SecurityEvent, AdminAction schemas

### B. Enhance DB Fixture
**File:** `backend/tests/conftest.py`

Add this function (check if exists first):
```python
@pytest.fixture(scope="session")
async def test_engine():
    """Create in-memory SQLite database engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=NullPool,
        echo=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()
```

### C. Add GameContext to System Tests
**File:** `backend/tests/systems/conftest.py`

Add minimal GameContext fixture or mock:
```python
@pytest.fixture
def mock_context():
    """Create mock GameContext for system tests."""
    from unittest.mock import Mock
    ctx = Mock()
    ctx.world = Mock()
    return ctx
```

## Priority 2: Run Tests (30 minutes)

```bash
# Run unit tests
cd backend
python -m pytest tests/unit/test_world.py -v
python -m pytest tests/unit/test_stats.py -v
python -m pytest tests/unit/test_models.py -v  # After fixes

# Run system tests
python -m pytest tests/systems/ -v  # After GameContext fix

# Check for any import errors
python -m pytest tests/ --collect-only
```

## Priority 3: Verify Coverage (15 minutes)

```bash
# Run with coverage
python -m pytest tests/unit/ --cov=app.models --cov=app.engine.world --cov-report=term

# Generate HTML report
python -m pytest tests/unit/ --cov=app --cov-report=html
# Open htmlcov/index.html
```

## Priority 4: Document Results (15 minutes)

Update `test_architecture.md` with:
- Number of passing tests
- Current coverage percentage
- Any discovered issues
- Next steps for Phase 13.3 (ability behavior tests)

## Quick Wins (Already Working)

These should pass without changes:
- ✅ `test_world.py` - Pure Python data structures
- ✅ `test_stats.py` - Pure calculation tests
- ⚠️ `test_models.py` - Needs field name fixes
- ⚠️ `test_time_manager.py` - Needs GameContext
- ⚠️ `test_persistence.py` - Needs DB tables

## Expected Results After Fixes

- **Unit Tests:** ~68 passing (all concrete tests)
- **System Tests:** ~27 passing (after GameContext fix)
- **API Tests:** 0 passing (placeholders, expected)
- **Integration Tests:** 0 passing (placeholders, expected)

**Total:** 95 passing tests (concrete implementations only)

## Time Estimate

- Fix model field names: 30-45 minutes
- Enhance DB fixture: 15 minutes
- Add GameContext mock: 15 minutes
- Run and verify tests: 30 minutes
- **Total: 1.5-2 hours**

## Commands Cheat Sheet

```bash
# Activate venv (if needed)
.venv\Scripts\activate

# Run specific test file
pytest tests/unit/test_world.py -v

# Run specific test
pytest tests/unit/test_world.py::test_world_player_creation -v

# Run with markers
pytest -m unit -v
pytest -m systems -v

# Show test collection
pytest --collect-only

# Verbose with traceback
pytest tests/unit/ -vv --tb=short

# Stop on first failure
pytest tests/unit/ -x

# Run only failed tests from last run
pytest --lf
```
