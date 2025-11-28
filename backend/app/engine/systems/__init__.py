# backend/app/engine/systems/__init__.py
"""
Game systems - extracted from WorldEngine for modularity.

Each system handles a specific domain of game logic:
- TimeEventManager: Scheduled events, recurring timers
- EventDispatcher: Message routing to players (future)
- CombatSystem: Attack, damage, death handling (future)
- EffectSystem: Buffs, debuffs, DoT effects (future)
"""

from .time_manager import TimeEventManager
from .context import GameContext

__all__ = [
    "TimeEventManager",
    "GameContext",
]
