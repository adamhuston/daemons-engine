"""
Pytest configuration and shared fixtures for Phase 10.1 tests.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))
