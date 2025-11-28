# backend/app/engine/systems/__init__.py
"""
Game systems - extracted from WorldEngine for modularity.

Each system handles a specific domain of game logic:
- TimeEventManager: Scheduled events, recurring timers
- EventDispatcher: Event creation and routing to players
- CombatSystem: Attack, damage, death, loot handling
- EffectSystem: Buffs, debuffs, DoT effects
- CommandRouter: Command parsing and handler routing
"""

from .time_manager import TimeEventManager
from .events import EventDispatcher
from .combat import CombatSystem, CombatConfig
from .effects import EffectSystem, EffectConfig
from .router import CommandRouter, CommandMeta
from .context import GameContext

__all__ = [
    "GameContext",
    "TimeEventManager",
    "EventDispatcher",
    "CombatSystem",
    "CombatConfig",
    "EffectSystem",
    "EffectConfig",
    "CommandRouter",
    "CommandMeta",
]
