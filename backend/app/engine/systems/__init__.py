# backend/app/engine/systems/__init__.py
"""
Game systems - extracted from WorldEngine for modularity.

Each system handles a specific domain of game logic:
- TimeEventManager: Scheduled events, recurring timers
- EventDispatcher: Event creation and routing to players
- CombatSystem: Attack, damage, death, loot handling
- EffectSystem: Buffs, debuffs, DoT effects
- CommandRouter: Command parsing and handler routing
- TriggerSystem: Room-based reactive triggers
- StateTracker: Dirty tracking and persistence (Phase 6)
- AuthSystem: Authentication and authorization (Phase 7)
- d20: Centralized D20 tabletop RPG mechanics
"""

# Import d20 first (no dependencies)
from . import d20
from .auth import (AuthSystem, Permission, SecurityEventType, UserRole,
                   requires_permission, requires_role)
from .combat import CombatConfig, CombatSystem
from .context import GameContext
from .effects import EffectConfig, EffectSystem
from .events import EventDispatcher
from .persistence import (ENTITY_ITEM, ENTITY_NPC, ENTITY_PLAYER, ENTITY_ROOM,
                          ENTITY_TRIGGER, DirtyState, StateTracker)
from .quests import (DialogueAction, DialogueCondition, DialogueNode,
                     DialogueOption, DialogueTree, ObjectiveType, QuestChain,
                     QuestObjective, QuestProgress, QuestReward, QuestStatus,
                     QuestSystem, QuestTemplate)
from .router import CommandMeta, CommandRouter
from .time_manager import TimeEventManager
from .triggers import (RoomTrigger, TriggerAction, TriggerCondition,
                       TriggerContext, TriggerState, TriggerSystem)

__all__ = [
    "d20",
    "GameContext",
    "TimeEventManager",
    "EventDispatcher",
    "CombatSystem",
    "CombatConfig",
    "EffectSystem",
    "EffectConfig",
    "CommandRouter",
    "CommandMeta",
    "TriggerSystem",
    "TriggerCondition",
    "TriggerAction",
    "RoomTrigger",
    "TriggerState",
    "TriggerContext",
    "QuestSystem",
    "QuestTemplate",
    "QuestObjective",
    "QuestReward",
    "QuestProgress",
    "QuestStatus",
    "ObjectiveType",
    "QuestChain",
    "DialogueTree",
    "DialogueNode",
    "DialogueOption",
    "DialogueCondition",
    "DialogueAction",
    "StateTracker",
    "DirtyState",
    "ENTITY_PLAYER",
    "ENTITY_ROOM",
    "ENTITY_NPC",
    "ENTITY_ITEM",
    "ENTITY_TRIGGER",
    # Phase 7: Auth
    "AuthSystem",
    "UserRole",
    "Permission",
    "SecurityEventType",
    "requires_role",
    "requires_permission",
]
