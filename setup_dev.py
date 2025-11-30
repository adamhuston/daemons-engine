#!/usr/bin/env python3
"""
Setup script for Daemonswright development environment.

Installs necessary development tools and pre-commit hooks.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], cwd: Path = None) -> bool:
    """Run a command and return success status."""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, cwd=cwd, check=True, capture_output=True, text=True
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}", file=sys.stderr)
        return False


def main():
    """Setup development environment."""
    print("=" * 60)
    print("Daemonswright Development Environment Setup")
    print("=" * 60)
    print()

    repo_root = Path(__file__).parent
    backend_dir = repo_root / "backend"

    # Install development dependencies
    print("1. Installing development dependencies...")
    dev_packages = [
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "pytest-timeout",
        "pytest-xdist",  # For parallel test execution
        "pre-commit",
        "ruff",
        "black",
        "isort",
        "mypy",
        "safety",
    ]

    if not run_command(
        [sys.executable, "-m", "pip", "install", "--upgrade"] + dev_packages
    ):
        print("Failed to install development dependencies")
        return 1

    print()

    # Install project dependencies
    print("2. Installing project dependencies...")
    requirements_file = backend_dir / "requirements.txt"
    if requirements_file.exists():
        if not run_command(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
        ):
            print("Failed to install project dependencies")
            return 1
    else:
        print(f"Warning: {requirements_file} not found")

    print()

    # Setup pre-commit hooks
    print("3. Setting up pre-commit hooks...")
    if not run_command(["pre-commit", "install"], cwd=repo_root):
        print("Failed to install pre-commit hooks")
        return 1

    print()

    # Run pre-commit on all files (first time)
    print("4. Running pre-commit on all files (this may take a while)...")
    print("   (Some failures are expected on first run)")
    run_command(["pre-commit", "run", "--all-files"], cwd=repo_root)

    print()
    print("=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Run tests: cd backend && pytest")
    print("  2. Check coverage: cd backend && pytest --cov=app --cov-report=html")
    print("  3. Open coverage report: open backend/htmlcov/index.html")
    print()
    print("Pre-commit hooks are now active and will run on every commit.")
    print("To bypass hooks: git commit --no-verify")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
