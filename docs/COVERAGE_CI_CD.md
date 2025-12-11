# Coverage & CI/CD Setup Guide

## Overview
This document describes the test coverage and continuous integration setup for Daemonswright.

## Coverage Configuration

### Local Coverage Reports

Run tests with coverage locally:

```bash
cd backend

# Run all tests with coverage
pytest --cov=app --cov-report=html --cov-report=term

# Run specific test categories
pytest tests/unit/ --cov=app --cov-report=term
pytest tests/systems/ --cov=app --cov-report=term

# Open HTML coverage report
start htmlcov/index.html  # Windows
open htmlcov/index.html   # Mac
xdg-open htmlcov/index.html  # Linux
```

### Coverage Configuration

Coverage settings are defined in `backend/.coveragerc`:

**Omitted from coverage:**
- Test files
- Migrations (`alembic/versions/`)
- Main entry points
- Virtual environments
- `__pycache__` directories

**Excluded lines:**
- `pragma: no cover` comments
- Debug code (`if self.debug`)
- Defensive assertions
- Non-runnable code (`if __name__ == "__main__"`)
- Type checking blocks (`if TYPE_CHECKING:`)
- Abstract methods

### Coverage Targets

| Category | Target | Current |
|----------|--------|---------|
| Core Systems | 90%+ | TBD |
| Commands | 85%+ | TBD |
| Abilities | 100% | 100% (executor) |
| Models | 80%+ | TBD |
| API Routes | 75%+ | TBD |
| **Overall** | **80%+** | **TBD** |

## Continuous Integration (CI/CD)

### GitHub Actions Workflows

**Location:** `.github/workflows/test.yml`

### Test Workflow

Runs on:
- Every push to `main` or `develop`
- Every pull request to `main`

**Jobs:**

1. **Test** (Matrix: Python 3.11, 3.12, 3.13)
   - Checkout code
   - Setup Python with pip caching
   - Install dependencies
   - Run pytest with coverage
   - Upload coverage to Codecov
   - Archive coverage reports (30 days)
   - Comment coverage on PR

2. **Lint**
   - Run ruff for code quality
   - Run black for formatting
   - Run isort for import sorting
   - All continue on error (warnings only)

3. **Security**
   - Run safety check for dependency vulnerabilities
   - Continues on error (warnings only)

### Codecov Integration

Coverage reports are uploaded to [Codecov](https://codecov.io) for tracking over time.

**Setup:**
1. Enable Codecov for your GitHub repository
2. Add `CODECOV_TOKEN` to GitHub secrets
3. Coverage badge will appear in README

**Badge:**
```markdown
[![codecov](https://codecov.io/gh/USERNAME/REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/USERNAME/REPO)
```

### PR Coverage Comments

Pull requests automatically receive coverage comments showing:
- Overall coverage percentage
- Coverage change from base branch
- Files with coverage changes
- Color-coded warnings (green >70%, orange 50-70%, red <50%)

## Pre-commit Hooks

### Installation

```bash
# Install pre-commit
pip install pre-commit

# Install hooks in your repo
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

### Hooks Configured

1. **Code Quality**
   - Trailing whitespace removal
   - End-of-file fixer
   - Large file check (max 1MB)
   - Merge conflict detection
   - Debug statement detection

2. **Format & Lint**
   - Ruff (auto-fix enabled)
   - Black (Python formatting)
   - isort (import sorting)

3. **File Validation**
   - YAML syntax check
   - JSON syntax check
   - TOML syntax check

4. **Tests**
   - Run unit and system tests before commit
   - Fails commit if tests fail

### Bypassing Hooks

```bash
# Skip hooks for emergency commits
git commit --no-verify -m "Emergency fix"
```

## Local Development Workflow

### Before Committing

```bash
# Run tests
pytest tests/unit/ tests/systems/ -v

# Check coverage
pytest --cov=app --cov-report=term

# Run linters manually
ruff check app/ tests/
black --check app/ tests/
isort --check app/ tests/

# Or let pre-commit handle it
pre-commit run --all-files
```

### Fixing Coverage

If coverage drops below target:

1. **Identify uncovered code:**
   ```bash
   pytest --cov=app --cov-report=term-missing
   ```

2. **Add tests for uncovered lines**

3. **Verify improvement:**
   ```bash
   pytest --cov=app --cov-report=html
   # Check htmlcov/index.html
   ```

## CI/CD Best Practices

### Writing CI-Friendly Tests

1. **Avoid external dependencies**
   - Use mocks for external APIs
   - Use in-memory databases
   - No network calls in unit tests

2. **Keep tests fast**
   - Mark slow tests with `@pytest.mark.slow`
   - Run quick tests first
   - Parallelize when possible

3. **Make tests deterministic**
   - No random values without seeds
   - No time-dependent assertions
   - Clean up test data

4. **Use fixtures**
   - Share setup via conftest.py
   - Scope fixtures appropriately
   - Clean up in teardown

### Debugging CI Failures

1. **Check workflow logs:**
   - GitHub Actions → Failed workflow → Job logs

2. **Reproduce locally:**
   ```bash
   # Use same Python version as CI
   pytest tests/ --cov=app --cov-report=term
   ```

3. **Common issues:**
   - Import errors (missing dependencies)
   - Database not initialized
   - Fixtures not found
   - Platform-specific failures

## Metrics & Monitoring

### Coverage Trends

Monitor coverage over time on Codecov dashboard:
- Overall coverage percentage
- Coverage per file
- Coverage per commit
- Coverage sunburst (visual breakdown)

### Test Performance

Track test execution time:
```bash
pytest --durations=10  # Show 10 slowest tests
pytest --durations=0   # Show all test durations
```

### Badge Status

Add badges to README.md:

```markdown
# Daemonswright

[![Tests](https://github.com/USERNAME/REPO/workflows/Tests/badge.svg)](https://github.com/USERNAME/REPO/actions)
[![codecov](https://codecov.io/gh/USERNAME/REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/USERNAME/REPO)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
```

## Maintenance

### Updating Dependencies

```bash
# Update pytest and coverage tools
pip install --upgrade pytest pytest-asyncio pytest-cov pytest-timeout

# Update pre-commit hooks
pre-commit autoupdate

# Update GitHub Actions
# Edit .github/workflows/test.yml and bump action versions
```

### Adding New Test Categories

1. Add marker to `pytest.ini`:
   ```ini
   markers =
       my_category: Description of test category
   ```

2. Use marker in tests:
   ```python
   @pytest.mark.my_category
   def test_something():
       ...
   ```

3. Run category:
   ```bash
   pytest -m my_category
   ```

## Troubleshooting

### Coverage Not Updating

- Delete `.coverage` and `htmlcov/` directories
- Run pytest again
- Check `.coveragerc` omit patterns

### Pre-commit Hook Failing

- Run manually to see errors: `pre-commit run --all-files`
- Update hooks: `pre-commit autoupdate`
- Reinstall: `pre-commit uninstall && pre-commit install`

### CI Workflow Not Running

- Check GitHub Actions tab
- Verify workflow file syntax
- Check branch protection rules
- Ensure workflow is enabled

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Codecov documentation](https://docs.codecov.com/)
- [pre-commit documentation](https://pre-commit.com/)
- [GitHub Actions documentation](https://docs.github.com/en/actions)
