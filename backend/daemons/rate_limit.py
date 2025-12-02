# backend/daemons/rate_limit.py
"""
Rate limiting configuration for the Daemons engine.

Phase 16.1 - Cybersecurity Audit: Rate Limiting

This module provides rate limiting for:
- Authentication endpoints (login, register, refresh)
- Admin API endpoints (higher thresholds)
- WebSocket command messages

Uses slowapi for HTTP rate limiting and a custom in-memory tracker
for WebSocket message throttling.
"""

import logging
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# HTTP Rate Limiting (slowapi)
# -----------------------------------------------------------------------------

def get_client_ip(request: Request) -> str:
    """
    Get client IP address from request.

    Handles X-Forwarded-For header for reverse proxy setups.
    """
    # Check for X-Forwarded-For header (reverse proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()

    # Fall back to direct connection IP
    return get_remote_address(request)


# Create the limiter instance with IP-based key function
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["100/minute"],  # Default for unlisted endpoints
    headers_enabled=True,  # Include X-RateLimit-* headers
    strategy="fixed-window",  # Use fixed window strategy
)

# Rate limit strings for different endpoint types
# Format: "count/period" where period is second, minute, hour, day
RATE_LIMITS = {
    # Authentication endpoints - strict limits to prevent brute force
    "auth_login": "5/minute",
    "auth_register": "3/minute",
    "auth_refresh": "10/minute",
    "auth_logout": "10/minute",

    # Admin API endpoints - more relaxed for legitimate use
    "admin_default": "60/minute",
    "admin_content": "30/minute",  # Content operations can be intensive
    "admin_bulk": "10/minute",  # Bulk operations are expensive

    # WebSocket commands - per connection
    "ws_commands": "30/second",  # Max 30 commands per second
    "ws_chat": "5/second",  # Chat throttling
}


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded errors.

    Returns a 429 Too Many Requests response with Retry-After header.
    """
    retry_after = getattr(exc, "retry_after", 60)

    logger.warning(
        "Rate limit exceeded",
        extra={
            "client_ip": get_client_ip(request),
            "path": request.url.path,
            "limit": str(exc.detail) if hasattr(exc, "detail") else "unknown",
        }
    )

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(getattr(exc, "limit", "unknown")),
        }
    )


# -----------------------------------------------------------------------------
# WebSocket Rate Limiting (custom in-memory tracker)
# -----------------------------------------------------------------------------

class WebSocketRateLimiter:
    """
    In-memory rate limiter for WebSocket connections.

    Tracks command counts per connection using a sliding window approach.
    Thread-safe for async usage.
    """

    def __init__(self):
        # Structure: {connection_id: [(timestamp, count), ...]}
        self._command_windows: dict[str, list[tuple[float, int]]] = defaultdict(list)
        self._chat_windows: dict[str, list[tuple[float, int]]] = defaultdict(list)

        # Parse rate limits
        self._command_limit = self._parse_limit(RATE_LIMITS["ws_commands"])
        self._chat_limit = self._parse_limit(RATE_LIMITS["ws_chat"])

    def _parse_limit(self, limit_str: str) -> tuple[int, float]:
        """Parse '30/second' format into (count, window_seconds)."""
        count, period = limit_str.split("/")
        period_seconds = {
            "second": 1.0,
            "minute": 60.0,
            "hour": 3600.0,
            "day": 86400.0,
        }
        return int(count), period_seconds.get(period, 60.0)

    def _cleanup_window(self, window: list[tuple[float, int]], window_seconds: float) -> list[tuple[float, int]]:
        """Remove expired entries from the sliding window."""
        cutoff = time.time() - window_seconds
        return [(ts, count) for ts, count in window if ts > cutoff]

    def check_command_rate(self, connection_id: str) -> tuple[bool, str | None]:
        """
        Check if a command is allowed for the given connection.

        Returns:
            (allowed: bool, error_message: str | None)
        """
        max_count, window_seconds = self._command_limit

        # Clean up old entries
        self._command_windows[connection_id] = self._cleanup_window(
            self._command_windows[connection_id],
            window_seconds
        )

        # Count commands in current window
        total = sum(count for _, count in self._command_windows[connection_id])

        if total >= max_count:
            return False, f"Command rate limit exceeded ({max_count}/second). Slow down!"

        # Record this command
        self._command_windows[connection_id].append((time.time(), 1))
        return True, None

    def check_chat_rate(self, connection_id: str) -> tuple[bool, str | None]:
        """
        Check if a chat message is allowed for the given connection.

        Returns:
            (allowed: bool, error_message: str | None)
        """
        max_count, window_seconds = self._chat_limit

        # Clean up old entries
        self._chat_windows[connection_id] = self._cleanup_window(
            self._chat_windows[connection_id],
            window_seconds
        )

        # Count chats in current window
        total = sum(count for _, count in self._chat_windows[connection_id])

        if total >= max_count:
            return False, f"Chat rate limit exceeded ({max_count}/second). Wait a moment."

        # Record this chat
        self._chat_windows[connection_id].append((time.time(), 1))
        return True, None

    def disconnect(self, connection_id: str):
        """Clean up rate limit tracking for a disconnected client."""
        self._command_windows.pop(connection_id, None)
        self._chat_windows.pop(connection_id, None)

    def get_stats(self) -> dict:
        """Get current rate limiting statistics."""
        return {
            "active_connections": len(self._command_windows),
            "command_windows": len(self._command_windows),
            "chat_windows": len(self._chat_windows),
        }


# Global WebSocket rate limiter instance
ws_rate_limiter = WebSocketRateLimiter()


# -----------------------------------------------------------------------------
# Utility functions for checking rate limits
# -----------------------------------------------------------------------------

def is_chat_command(command: str) -> bool:
    """Check if a command is a chat-related command."""
    chat_commands = {"say", "yell", "shout", "tell", "group", "clan", "faction"}
    cmd_lower = command.strip().lower().split()[0] if command.strip() else ""
    return cmd_lower in chat_commands
