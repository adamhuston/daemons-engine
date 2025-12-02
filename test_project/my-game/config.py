"""
Game configuration.

Customize these settings for your game.
"""

import os

# Server settings
HOST = os.getenv("DAEMONS_HOST", "127.0.0.1")
PORT = int(os.getenv("DAEMONS_PORT", "8000"))

# Database settings
DATABASE_URL = os.getenv("DAEMONS_DATABASE_URL", "sqlite+aiosqlite:///./dungeon.db")

# JWT settings (generate your own secret for production!)
JWT_SECRET = os.getenv("DAEMONS_JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Game settings
GAME_NAME = "My Daemons Game"
STARTING_ROOM = "room_1_1_1"
MAX_PLAYERS = 100

# Content directories
WORLD_DATA_DIR = "world_data"
BEHAVIORS_DIR = "behaviors"
