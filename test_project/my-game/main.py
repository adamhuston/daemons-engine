"""
Game server entry point.

Run with: uvicorn main:app --reload
Or use: daemons run
"""

from daemons.main import app

# Re-export the FastAPI app for uvicorn
__all__ = ["app"]
