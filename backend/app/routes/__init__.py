# backend/app/routes/__init__.py
"""
Route modules for the Daemons API.
"""

from .admin import router as admin_router

__all__ = ["admin_router"]
