"""
QuestSystem: Manages quest templates, player progress, and quest-related events.

Phase X.1 - Core Quest Infrastructure

Handles:
- Quest template registration and lookup
- Quest state machine (accept, update, complete, turn_in)
- Objective tracking (KILL, COLLECT, VISIT, TALK, INTERACT)
- Event hooks for objective updates
- Quest journal display
"""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Set, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import GameContext
    from ..world import PlayerId, RoomId, WorldPlayer, WorldNpc, EntityId

# Type alias for events
Event = Dict[str, Any]


class QuestStatus(Enum):
    """Possible states of a quest for a player."""
    NOT_AVAILABLE = "not_available"  # Prerequisites not met
    AVAILABLE = "available"          # Can be accepted
    ACCEPTED = "accepted"            # Just accepted, objectives not started
    IN_PROGRESS = "in_progress"      # Working on objectives
    COMPLETED = "completed"          # All objectives done, needs turn-in
    TURNED_IN = "turned_in"          # Rewards received, quest finished
    FAILED = "failed"                # Quest failed (optional state)
    ABANDONED = "abandoned"          # Player abandoned the quest


class ObjectiveType(Enum):
    """Types of quest objectives."""
    KILL = "kill"                    # Kill N of NPC template
    COLLECT = "collect"              # Collect N of item template
    VISIT = "visit"                  # Enter a specific room
    TALK = "talk"                    # Speak to NPC
    INTERACT = "interact"            # Use command in room (trigger-based)
    DELIVER = "deliver"              # Bring item to NPC
    USE_ITEM = "use_item"            # Use specific item
    ESCORT = "escort"                # Keep NPC alive to destination
    DEFEND = "defend"                # Prevent NPCs from reaching location


@dataclass
class QuestObjective:
    """A single objective within a quest."""
    id: str
    type: ObjectiveType
    description: str
    
    # Type-specific parameters
    target_template_id: str | None = None  # NPC or item template for KILL/COLLECT
    target_room_id: str | None = None      # For VISIT objectives
    target_npc_name: str | None = None     # For TALK/DELIVER
    required_count: int = 1                 # For KILL/COLLECT
    command_pattern: str | None = None     # For INTERACT
    
    # Display
    hidden: bool = False                   # Don't show in journal until discovered
    optional: bool = False                 # Not required for completion


@dataclass
class QuestReward:
    """Rewards given upon quest completion."""
    experience: int = 0
    items: List[tuple[str, int]] = field(default_factory=list)  # (template_id, quantity)
    effects: List[Dict[str, Any]] = field(default_factory=list) # Effect definitions
    flags: Dict[str, Any] = field(default_factory=dict)         # Player flags to set
    currency: int = 0                                            # Future: gold/currency
    reputation: Dict[str, int] = field(default_factory=dict)    # Future: faction rep


@dataclass
class QuestTemplate:
    """Definition of a quest."""
    id: str
    name: str
    description: str
    
    # Quest giver
    giver_npc_template: str | None = None  # NPC who gives quest
    giver_room_id: str | None = None       # Or location-based
    
    # Requirements to see/accept quest
    prerequisites: List[str] = field(default_factory=list)      # Quest IDs
    level_requirement: int = 1
    required_items: List[str] = field(default_factory=list)     # Must have to accept
    required_flags: Dict[str, Any] = field(default_factory=dict)
    
    # Objectives
    objectives: List[QuestObjective] = field(default_factory=list)
    
    # Completion
    turn_in_npc_template: str | None = None  # NPC to turn in to (None = auto-complete)
    turn_in_room_id: str | None = None       # Or location-based turn-in
    auto_complete: bool = False              # Auto-complete when objectives done (no turn-in)
    rewards: QuestReward = field(default_factory=QuestReward)
    
    # Metadata
    category: str = "main"                   # main, side, daily, repeatable
    repeatable: bool = False
    cooldown_hours: float = 0                # For repeatable quests
    time_limit_minutes: float | None = None  # Optional time limit
    
    # Dialogue text
    accept_dialogue: str = "Quest accepted."
    progress_dialogue: str = "Still working on it?"
    complete_dialogue: str = "Well done!"
    
    # Triggers on state changes (future: integrate with TriggerSystem actions)
    on_accept_actions: List[Dict[str, Any]] = field(default_factory=list)
    on_complete_actions: List[Dict[str, Any]] = field(default_factory=list)
    on_turn_in_actions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class QuestProgress:
    """Player's progress on a specific quest."""
    quest_id: str
    status: QuestStatus = QuestStatus.ACCEPTED
    
    # Objective tracking: objective_id -> current_count
    objective_progress: Dict[str, int] = field(default_factory=dict)
    
    # Timing
    accepted_at: float | None = None
    completed_at: float | None = None
    turned_in_at: float | None = None
    
    # For repeatable quests
    completion_count: int = 0
    last_completed_at: float | None = None
    
    # For timed quests
    expires_at: float | None = None  # Unix timestamp when quest fails


# =============================================================================
# Quest Chain Data Structures (Phase X.4)
# =============================================================================

@dataclass
class QuestChain:
    """Definition of a quest chain (series of linked quests)."""
    id: str
    name: str
    description: str
    
    # Ordered list of quest IDs in the chain
    quest_ids: List[str] = field(default_factory=list)
    
    # Requirements to unlock/start this chain
    unlock_requirements: List[Dict[str, Any]] = field(default_factory=list)
    
    # Rewards for completing the entire chain
    chain_rewards: 'QuestReward' = field(default_factory=lambda: QuestReward())
    
    # Flags to set on chain completion
    completion_flags: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChainProgress:
    """Player's progress on a quest chain."""
    chain_id: str
    current_quest_index: int = 0  # Index into chain.quest_ids
    completed: bool = False
    started_at: float | None = None
    completed_at: float | None = None


# =============================================================================
# Dialogue Data Structures (Phase X.2)
# =============================================================================

@dataclass
class DialogueCondition:
    """
    A condition for dialogue options or entry overrides.
    
    Reuses trigger condition pattern but evaluated in dialogue context.
    """
    type: str  # "quest_status", "has_item", "flag_set", "level", etc.
    params: Dict[str, Any] = field(default_factory=dict)
    negate: bool = False  # Invert the condition result


@dataclass
class DialogueAction:
    """
    An action to execute during dialogue.
    
    Reuses trigger action pattern but executed in dialogue context.
    """
    type: str  # "accept_quest", "turn_in_quest", "set_flag", "message_player", etc.
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DialogueOption:
    """A player's response option in dialogue."""
    text: str                                    # What player can say
    next_node: str | None = None                 # Next dialogue node ID (None = ends dialogue)
    conditions: List[DialogueCondition] = field(default_factory=list)
    actions: List[DialogueAction] = field(default_factory=list)
    
    # Quest integration shortcuts (convenience - can also use actions)
    accept_quest: str | None = None              # Quest ID to accept
    turn_in_quest: str | None = None             # Quest ID to turn in
    
    # Visibility
    hidden_if_unavailable: bool = True           # Hide if conditions fail


@dataclass
class DialogueNode:
    """A node in an NPC dialogue tree."""
    id: str
    text: str  # What NPC says (supports {player.name}, {npc.name} substitution)
    
    # Player response options
    options: List[DialogueOption] = field(default_factory=list)
    
    # Conditions to show this node (usually for entry_overrides)
    conditions: List[DialogueCondition] = field(default_factory=list)
    
    # Actions when this node is displayed
    actions: List[DialogueAction] = field(default_factory=list)


@dataclass
class DialogueEntryOverride:
    """Context-sensitive entry point for dialogue."""
    conditions: List[DialogueCondition]
    node_id: str  # Node to use if conditions match


@dataclass
class DialogueTree:
    """Complete dialogue tree for an NPC."""
    npc_template_id: str
    nodes: Dict[str, DialogueNode] = field(default_factory=dict)
    entry_node: str = "greet"                    # Default starting node ID
    
    # Context-sensitive entry points (evaluated in order, first match wins)
    entry_overrides: List[DialogueEntryOverride] = field(default_factory=list)


class QuestSystem:
    """
    Manages quest templates, player progress, and quest-related events.
    
    Uses GameContext for:
    - world: player and entity access
    - event creation via ctx.msg_to_player
    
    Phase X.4 additions:
    - Quest chains with multi-part storylines
    - Timed quests with expiration
    - Repeatable quests with cooldowns
    - Quest trigger integration (on_accept, on_complete, on_turn_in actions)
    """
    
    def __init__(self, ctx: 'GameContext'):
        self.ctx = ctx
        self.templates: Dict[str, QuestTemplate] = {}
        self.dialogue_trees: Dict[str, DialogueTree] = {}  # npc_template_id -> DialogueTree
        self.chains: Dict[str, QuestChain] = {}  # chain_id -> QuestChain
        self._quest_to_chain: Dict[str, str] = {}  # quest_id -> chain_id (reverse lookup)
    
    # === Template Management ===
    
    def register_quest(self, template: QuestTemplate) -> None:
        """Register a quest template."""
        self.templates[template.id] = template
    
    def register_chain(self, chain: QuestChain) -> None:
        """Register a quest chain."""
        self.chains[chain.id] = chain
        # Build reverse lookup
        for quest_id in chain.quest_ids:
            self._quest_to_chain[quest_id] = chain.id
    
    def register_dialogue(self, tree: DialogueTree) -> None:
        """Register an NPC dialogue tree."""
        self.dialogue_trees[tree.npc_template_id] = tree
    
    def get_dialogue_tree(self, npc_template_id: str) -> DialogueTree | None:
        """Get a dialogue tree by NPC template ID."""
        return self.dialogue_trees.get(npc_template_id)
    
    def get_template(self, quest_id: str) -> QuestTemplate | None:
        """Get a quest template by ID."""
        return self.templates.get(quest_id)
    
    # === Quest State Management ===
    
    def get_quest_status(self, player_id: 'PlayerId', quest_id: str) -> QuestStatus:
        """Get player's current status on a quest."""
        player = self.ctx.world.players.get(player_id)
        if not player:
            return QuestStatus.NOT_AVAILABLE
        
        # Check if turned in
        if quest_id in player.completed_quests:
            return QuestStatus.TURNED_IN
        
        # Check in-progress
        progress = player.quest_progress.get(quest_id)
        if progress:
            return progress.status
        
        # Check availability
        if self.check_availability(player_id, quest_id):
            return QuestStatus.AVAILABLE
        
        return QuestStatus.NOT_AVAILABLE
    
    def check_availability(self, player_id: 'PlayerId', quest_id: str) -> bool:
        """
        Check if a quest is available to a player.
        
        Handles:
        - Basic prerequisites (level, flags, items, prior quests)
        - Repeatable quests with cooldown
        - Quest chain ordering
        """
        template = self.templates.get(quest_id)
        if not template:
            return False
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return False
        
        # Currently in progress?
        if quest_id in player.quest_progress:
            return False
        
        # Handle repeatable vs non-repeatable quests
        if quest_id in player.completed_quests:
            if not template.repeatable:
                return False
            
            # Check cooldown for repeatable quests
            if template.cooldown_hours > 0:
                # Need to check when it was last completed
                # This info is stored in completed quest history
                last_completed = self._get_last_completion_time(player, quest_id)
                if last_completed:
                    cooldown_seconds = template.cooldown_hours * 3600
                    if time.time() - last_completed < cooldown_seconds:
                        return False
        
        # Level requirement
        if player.level < template.level_requirement:
            return False
        
        # Prerequisites
        for prereq_id in template.prerequisites:
            if prereq_id not in player.completed_quests:
                return False
        
        # Required flags
        for flag_name, flag_value in template.required_flags.items():
            if player.player_flags.get(flag_name) != flag_value:
                return False
        
        # Required items
        for item_template_id in template.required_items:
            if not self._player_has_item(player, item_template_id):
                return False
        
        # Check quest chain ordering
        chain_id = self._quest_to_chain.get(quest_id)
        if chain_id:
            chain = self.chains.get(chain_id)
            if chain:
                quest_index = chain.quest_ids.index(quest_id)
                # Must complete all prior quests in chain
                for i in range(quest_index):
                    if chain.quest_ids[i] not in player.completed_quests:
                        return False
        
        return True
    
    def _get_last_completion_time(self, player: 'WorldPlayer', quest_id: str) -> float | None:
        """Get the last time a player completed a quest (for repeatable quests)."""
        # Check if stored in player flags as completion history
        completion_times = player.player_flags.get('_quest_completion_times', {})
        return completion_times.get(quest_id)
    
    def _player_has_item(self, player: 'WorldPlayer', item_template_id: str) -> bool:
        """Check if player has an item of the given template."""
        for item_id in player.inventory_items:
            item = self.ctx.world.item_instances.get(item_id)
            if item and item.template_id == item_template_id:
                return True
        return False
    
    def accept_quest(self, player_id: 'PlayerId', quest_id: str) -> List[Event]:
        """
        Player accepts a quest.
        
        Phase X.4: Now handles timed quests and executes on_accept_actions.
        """
        events: List[Event] = []
        
        template = self.templates.get(quest_id)
        if not template:
            events.append(self.ctx.msg_to_player(player_id, "Quest not found."))
            return events
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        # Check availability
        if not self.check_availability(player_id, quest_id):
            events.append(self.ctx.msg_to_player(player_id, "You cannot accept this quest."))
            return events
        
        # For repeatable quests, remove from completed_quests to allow re-tracking
        if template.repeatable and quest_id in player.completed_quests:
            player.completed_quests.discard(quest_id)
        
        # Create progress
        now = time.time()
        progress = QuestProgress(
            quest_id=quest_id,
            status=QuestStatus.IN_PROGRESS,
            accepted_at=now,
        )
        
        # Set expiration for timed quests
        if template.time_limit_minutes:
            progress.expires_at = now + (template.time_limit_minutes * 60)
        
        # Initialize objective progress
        for objective in template.objectives:
            progress.objective_progress[objective.id] = 0
        
        player.quest_progress[quest_id] = progress
        
        # Build acceptance message
        objective_lines = []
        for obj in template.objectives:
            if not obj.hidden:
                if obj.required_count > 1:
                    objective_lines.append(f"   • {obj.description} (0/{obj.required_count})")
                else:
                    objective_lines.append(f"   • {obj.description}")
        
        objectives_text = "\n".join(objective_lines)
        msg = f"📜 Quest Accepted: {template.name}\n{objectives_text}"
        
        # Add time limit warning if applicable
        if template.time_limit_minutes:
            if template.time_limit_minutes >= 60:
                time_str = f"{template.time_limit_minutes / 60:.1f} hours"
            else:
                time_str = f"{template.time_limit_minutes:.0f} minutes"
            msg += f"\n   ⏱️ Time Limit: {time_str}"
        
        events.append(self.ctx.msg_to_player(player_id, msg))
        
        # Execute on_accept_actions (Phase X.4)
        if template.on_accept_actions:
            action_events = self._execute_quest_actions(
                player_id, template.on_accept_actions, quest_id
            )
            events.extend(action_events)
        
        return events
    
    def update_objective(
        self, 
        player_id: 'PlayerId', 
        quest_id: str, 
        objective_id: str, 
        delta: int = 1
    ) -> List[Event]:
        """Update progress on an objective."""
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        progress = player.quest_progress.get(quest_id)
        if not progress or progress.status not in (QuestStatus.ACCEPTED, QuestStatus.IN_PROGRESS):
            return events
        
        # Check if timed quest has expired (Phase X.4)
        if progress.expires_at and time.time() > progress.expires_at:
            fail_events = self.fail_quest(player_id, quest_id, "Time expired!")
            events.extend(fail_events)
            return events
        
        template = self.templates.get(quest_id)
        if not template:
            return events
        
        # Find objective
        objective = None
        for obj in template.objectives:
            if obj.id == objective_id:
                objective = obj
                break
        
        if not objective:
            return events
        
        # Update count
        old_count = progress.objective_progress.get(objective_id, 0)
        new_count = min(old_count + delta, objective.required_count)
        progress.objective_progress[objective_id] = new_count
        
        # Notify if progress was made
        if new_count > old_count:
            progress.status = QuestStatus.IN_PROGRESS
            
            if new_count >= objective.required_count:
                events.append(self.ctx.msg_to_player(
                    player_id,
                    f"✅ Objective Complete: {objective.description}"
                ))
            else:
                events.append(self.ctx.msg_to_player(
                    player_id,
                    f"📋 {template.name}: {objective.description} ({new_count}/{objective.required_count})"
                ))
        
        # Check if all required objectives complete
        if self.check_completion(player_id, quest_id):
            progress.status = QuestStatus.COMPLETED
            progress.completed_at = time.time()
            
            # Execute on_complete_actions (Phase X.4)
            if template.on_complete_actions:
                action_events = self._execute_quest_actions(
                    player_id, template.on_complete_actions, quest_id
                )
                events.extend(action_events)
            
            if template.auto_complete:
                # Auto-complete: immediately turn in
                turn_in_events = self.turn_in_quest(player_id, quest_id)
                events.extend(turn_in_events)
            else:
                events.append(self.ctx.msg_to_player(
                    player_id,
                    f"📜 Quest Complete: {template.name}\n   Return to turn in for rewards!"
                ))
        
        return events
        
        return events
    
    def check_completion(self, player_id: 'PlayerId', quest_id: str) -> bool:
        """Check if all required objectives are complete."""
        player = self.ctx.world.players.get(player_id)
        if not player:
            return False
        
        progress = player.quest_progress.get(quest_id)
        if not progress:
            return False
        
        template = self.templates.get(quest_id)
        if not template:
            return False
        
        for objective in template.objectives:
            if objective.optional:
                continue
            
            current = progress.objective_progress.get(objective.id, 0)
            if current < objective.required_count:
                return False
        
        return True
    
    def turn_in_quest(self, player_id: 'PlayerId', quest_id: str) -> List[Event]:
        """
        Turn in a completed quest for rewards.
        
        Phase X.4: Handles chain progression and on_turn_in_actions.
        """
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        progress = player.quest_progress.get(quest_id)
        if not progress or progress.status != QuestStatus.COMPLETED:
            events.append(self.ctx.msg_to_player(
                player_id,
                "You haven't completed this quest yet."
            ))
            return events
        
        template = self.templates.get(quest_id)
        if not template:
            return events
        
        # Apply rewards
        reward_lines = []
        
        # Experience
        if template.rewards.experience > 0:
            player.experience += template.rewards.experience
            reward_lines.append(f"   {template.rewards.experience} XP")
        
        # Currency
        if template.rewards.currency > 0:
            # Store currency in player flags for now
            current_gold = player.player_flags.get('gold', 0)
            player.player_flags['gold'] = current_gold + template.rewards.currency
            reward_lines.append(f"   💰 {template.rewards.currency} gold")
        
        # Items (future: integrate with ItemSystem)
        for item_template_id, quantity in template.rewards.items:
            reward_lines.append(f"   📦 {quantity}x {item_template_id}")
            # TODO: Actually give items via ItemSystem
        
        # Player flags
        for flag_name, flag_value in template.rewards.flags.items():
            player.player_flags[flag_name] = flag_value
        
        # Update progress
        progress.status = QuestStatus.TURNED_IN
        now = time.time()
        progress.turned_in_at = now
        progress.completion_count += 1
        progress.last_completed_at = now
        
        # Store completion time for repeatable quest cooldowns
        if template.repeatable:
            if '_quest_completion_times' not in player.player_flags:
                player.player_flags['_quest_completion_times'] = {}
            player.player_flags['_quest_completion_times'][quest_id] = now
        
        # Move to completed quests
        player.completed_quests.add(quest_id)
        del player.quest_progress[quest_id]
        
        # Build reward message
        rewards_text = "\n".join(reward_lines) if reward_lines else "   (no rewards)"
        msg = f"🎉 Quest Turned In: {template.name}\n{template.complete_dialogue}\n\nRewards:\n{rewards_text}"
        events.append(self.ctx.msg_to_player(player_id, msg))
        
        # Execute on_turn_in_actions (Phase X.4)
        if template.on_turn_in_actions:
            action_events = self._execute_quest_actions(
                player_id, template.on_turn_in_actions, quest_id
            )
            events.extend(action_events)
        
        # Check for quest chain completion (Phase X.4)
        chain_events = self._check_chain_completion(player_id, quest_id)
        events.extend(chain_events)
        
        # Phase 6: Critical save on quest turn-in (rewards given)
        if self.ctx.state_tracker:
            from .persistence import ENTITY_PLAYER
            import asyncio
            asyncio.create_task(self.ctx.state_tracker.mark_dirty(ENTITY_PLAYER, player_id, critical=True))
        
        return events
    
    def fail_quest(self, player_id: 'PlayerId', quest_id: str, reason: str = "") -> List[Event]:
        """
        Fail a quest (for timed quests or other failure conditions).
        
        Phase X.4: New method for handling quest failure.
        """
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        progress = player.quest_progress.get(quest_id)
        if not progress:
            return events
        
        template = self.templates.get(quest_id)
        quest_name = template.name if template else quest_id
        
        # Mark as failed and remove from active quests
        progress.status = QuestStatus.FAILED
        del player.quest_progress[quest_id]
        
        # Build failure message
        reason_text = f" ({reason})" if reason else ""
        msg = f"Quest Failed: {quest_name}{reason_text}"
        events.append(self.ctx.msg_to_player(player_id, msg))
        
        return events
    
    def _execute_quest_actions(
        self, 
        player_id: 'PlayerId', 
        actions: List[Dict[str, Any]],
        quest_id: str
    ) -> List[Event]:
        """
        Execute quest-related actions (on_accept, on_complete, on_turn_in).
        
        Supports:
        - message_player: Send a message to the player
        - set_flag: Set a player flag
        - spawn_npc: Spawn an NPC (via TriggerSystem)
        - give_item: Give item to player (future)
        - apply_effect: Apply effect to player (future)
        """
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        for action in actions:
            action_type = action.get('type')
            params = action.get('params', {})
            
            if action_type == 'message_player':
                text = params.get('text', '')
                # Substitute variables
                text = text.replace('{player.name}', player.name)
                text = text.replace('{quest.name}', self.templates.get(quest_id, QuestTemplate(id='', name='', description='')).name)
                events.append(self.ctx.msg_to_player(player_id, text))
            
            elif action_type == 'set_flag':
                flag_name = params.get('name')
                flag_value = params.get('value', True)
                if flag_name:
                    player.player_flags[flag_name] = flag_value
            
            elif action_type == 'spawn_npc':
                # Delegate to trigger system if available
                # For now, just log it
                template_id = params.get('template_id')
                room_id = params.get('room_id') or player.room_id
                print(f"[QuestSystem] Would spawn NPC {template_id} in {room_id}")
            
            elif action_type == 'give_xp':
                xp_amount = params.get('amount', 0)
                if xp_amount > 0:
                    player.experience += xp_amount
                    events.append(self.ctx.msg_to_player(
                        player_id, f"You gained {xp_amount} experience!"
                    ))
        
        return events
    
    def _check_chain_completion(self, player_id: 'PlayerId', quest_id: str) -> List[Event]:
        """
        Check if completing this quest finishes a quest chain.
        
        Phase X.4: Awards chain rewards when all quests in a chain are complete.
        """
        events: List[Event] = []
        
        # Check if this quest is part of a chain
        chain_id = self._quest_to_chain.get(quest_id)
        if not chain_id:
            return events
        
        chain = self.chains.get(chain_id)
        if not chain:
            return events
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        # Check if all quests in chain are completed
        all_complete = all(qid in player.completed_quests for qid in chain.quest_ids)
        if not all_complete:
            return events
        
        # Check if chain was already completed (avoid double rewards)
        chain_complete_flag = f'_chain_complete_{chain_id}'
        if player.player_flags.get(chain_complete_flag):
            return events
        
        # Mark chain as complete
        player.player_flags[chain_complete_flag] = True
        
        # Award chain rewards
        reward_lines = []
        
        if chain.chain_rewards.experience > 0:
            player.experience += chain.chain_rewards.experience
            reward_lines.append(f"   {chain.chain_rewards.experience} XP")
        
        if chain.chain_rewards.currency > 0:
            current_gold = player.player_flags.get('gold', 0)
            player.player_flags['gold'] = current_gold + chain.chain_rewards.currency
            reward_lines.append(f"   💰 {chain.chain_rewards.currency} gold")
        
        for flag_name, flag_value in chain.chain_rewards.flags.items():
            player.player_flags[flag_name] = flag_value
        
        for flag_name, flag_value in chain.completion_flags.items():
            player.player_flags[flag_name] = flag_value
        
        # Build chain completion message
        rewards_text = "\n".join(reward_lines) if reward_lines else ""
        msg = f"\n🏆 Quest Chain Complete: {chain.name}!\n{chain.description}"
        if rewards_text:
            msg += f"\n\nBonus Rewards:\n{rewards_text}"
        
        events.append(self.ctx.msg_to_player(player_id, msg))
        
        return events
    
    def check_timed_quests(self, player_id: 'PlayerId') -> List[Event]:
        """
        Check all active quests for time expiration.
        
        Phase X.4: Called periodically to fail expired timed quests.
        """
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        now = time.time()
        
        for quest_id, progress in list(player.quest_progress.items()):
            if progress.expires_at and now > progress.expires_at:
                fail_events = self.fail_quest(player_id, quest_id, "Time expired!")
                events.extend(fail_events)
        
        return events
    
    def get_chain_progress(self, player_id: 'PlayerId', chain_id: str) -> Optional[Dict[str, Any]]:
        """
        Get player's progress on a quest chain.
        
        Phase X.4: Returns information about chain completion status for UI/journal.
        
        Returns dict with:
        - chain_id: ID of the chain
        - chain_name: Name of the chain
        - total_quests: Number of quests in chain
        - completed_quests: Number completed by player
        - current_quest: ID of next incomplete quest (if any)
        - is_complete: Whether chain is fully complete
        - unlocked: Whether chain is available to start
        """
        chain = self.chains.get(chain_id)
        if not chain:
            return None
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return None
        
        completed_count = sum(1 for qid in chain.quest_ids if qid in player.completed_quests)
        total = len(chain.quest_ids)
        
        # Find current quest (first not completed)
        current_quest = None
        for qid in chain.quest_ids:
            if qid not in player.completed_quests:
                current_quest = qid
                break
        
        # Check if chain is unlocked
        unlocked = self._check_chain_requirements(player, chain)
        
        return {
            'chain_id': chain_id,
            'chain_name': chain.name,
            'description': chain.description,
            'total_quests': total,
            'completed_quests': completed_count,
            'current_quest': current_quest,
            'is_complete': completed_count == total,
            'unlocked': unlocked,
            'quest_ids': chain.quest_ids,
        }
    
    def _check_chain_requirements(self, player, chain: QuestChain) -> bool:
        """Check if player meets chain unlock requirements."""
        for req in chain.unlock_requirements:
            req_type = req.get('type')
            if req_type == 'flag':
                flag_name = req.get('name')
                expected = req.get('value', True)
                if player.player_flags.get(flag_name) != expected:
                    return False
            elif req_type == 'level':
                min_level = req.get('min', 1)
                if player.level < min_level:
                    return False
            elif req_type == 'quest_completed':
                req_quest = req.get('quest_id')
                if req_quest not in player.completed_quests:
                    return False
        return True
    
    def list_available_chains(self, player_id: 'PlayerId') -> List[Dict[str, Any]]:
        """
        List all quest chains available to a player.
        
        Returns list of chain progress dicts for chains the player can start or continue.
        """
        results = []
        
        for chain_id in self.chains:
            progress = self.get_chain_progress(player_id, chain_id)
            if progress and progress['unlocked']:
                results.append(progress)
        
        return results

    def abandon_quest(self, player_id: 'PlayerId', quest_id: str) -> List[Event]:
        """Abandon a quest."""
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        progress = player.quest_progress.get(quest_id)
        if not progress:
            events.append(self.ctx.msg_to_player(player_id, "You don't have that quest."))
            return events
        
        template = self.templates.get(quest_id)
        quest_name = template.name if template else quest_id
        
        del player.quest_progress[quest_id]
        events.append(self.ctx.msg_to_player(player_id, f"Quest Abandoned: {quest_name}"))
        
        return events
    
    # === Event Observers (called by engine hooks) ===
    
    def on_npc_killed(
        self, 
        player_id: 'PlayerId', 
        npc_template_id: str
    ) -> List[Event]:
        """Called when player kills an NPC. Updates KILL objectives."""
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        # Check all active quests
        for quest_id, progress in list(player.quest_progress.items()):
            if progress.status not in (QuestStatus.ACCEPTED, QuestStatus.IN_PROGRESS):
                continue
            
            template = self.templates.get(quest_id)
            if not template:
                continue
            
            # Check objectives
            for objective in template.objectives:
                if objective.type != ObjectiveType.KILL:
                    continue
                if objective.target_template_id != npc_template_id:
                    continue
                
                # Update this objective
                obj_events = self.update_objective(player_id, quest_id, objective.id, 1)
                events.extend(obj_events)
        
        return events
    
    def on_item_acquired(
        self, 
        player_id: 'PlayerId', 
        item_template_id: str, 
        quantity: int = 1
    ) -> List[Event]:
        """Called when player picks up an item. Updates COLLECT objectives."""
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        # Check all active quests
        for quest_id, progress in list(player.quest_progress.items()):
            if progress.status not in (QuestStatus.ACCEPTED, QuestStatus.IN_PROGRESS):
                continue
            
            template = self.templates.get(quest_id)
            if not template:
                continue
            
            # Check objectives
            for objective in template.objectives:
                if objective.type != ObjectiveType.COLLECT:
                    continue
                if objective.target_template_id != item_template_id:
                    continue
                
                # Update this objective
                obj_events = self.update_objective(player_id, quest_id, objective.id, quantity)
                events.extend(obj_events)
        
        return events
    
    def on_room_entered(
        self, 
        player_id: 'PlayerId', 
        room_id: 'RoomId'
    ) -> List[Event]:
        """Called when player enters a room. Updates VISIT objectives."""
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        # Check all active quests
        for quest_id, progress in list(player.quest_progress.items()):
            if progress.status not in (QuestStatus.ACCEPTED, QuestStatus.IN_PROGRESS):
                continue
            
            template = self.templates.get(quest_id)
            if not template:
                continue
            
            # Check objectives
            for objective in template.objectives:
                if objective.type != ObjectiveType.VISIT:
                    continue
                if objective.target_room_id != room_id:
                    continue
                
                # Check if already completed
                current = progress.objective_progress.get(objective.id, 0)
                if current >= objective.required_count:
                    continue
                
                # Update this objective
                obj_events = self.update_objective(player_id, quest_id, objective.id, 1)
                events.extend(obj_events)
        
        return events
    
    def on_npc_talked(
        self, 
        player_id: 'PlayerId', 
        npc_template_id: str
    ) -> List[Event]:
        """Called when player talks to NPC. Updates TALK objectives."""
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        # Check all active quests
        for quest_id, progress in list(player.quest_progress.items()):
            if progress.status not in (QuestStatus.ACCEPTED, QuestStatus.IN_PROGRESS):
                continue
            
            template = self.templates.get(quest_id)
            if not template:
                continue
            
            # Check objectives
            for objective in template.objectives:
                if objective.type != ObjectiveType.TALK:
                    continue
                if objective.target_template_id != npc_template_id:
                    continue
                
                # Check if already completed
                current = progress.objective_progress.get(objective.id, 0)
                if current >= objective.required_count:
                    continue
                
                # Update this objective
                obj_events = self.update_objective(player_id, quest_id, objective.id, 1)
                events.extend(obj_events)
        
        return events
    
    # === Journal/UI ===
    
    def get_quest_log(self, player_id: 'PlayerId') -> List[Event]:
        """Get formatted quest log for player."""
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        lines = [
            "═══════════════════════════════════════",
            "           📜 QUEST JOURNAL",
            "═══════════════════════════════════════",
            "",
        ]
        
        # Active quests
        active_quests = []
        completed_ready = []
        
        for quest_id, progress in player.quest_progress.items():
            template = self.templates.get(quest_id)
            if not template:
                continue
            
            if progress.status == QuestStatus.COMPLETED:
                completed_ready.append((quest_id, template, progress))
            elif progress.status in (QuestStatus.ACCEPTED, QuestStatus.IN_PROGRESS):
                active_quests.append((quest_id, template, progress))
        
        # Show active quests
        lines.append("ACTIVE QUESTS")
        lines.append("─────────────")
        
        if active_quests:
            for quest_id, template, progress in active_quests:
                lines.append(f"▸ {template.name}")
                for obj in template.objectives:
                    if obj.hidden:
                        current = progress.objective_progress.get(obj.id, 0)
                        if current == 0:
                            continue  # Don't show hidden objectives with no progress
                    
                    current = progress.objective_progress.get(obj.id, 0)
                    if obj.required_count > 1:
                        status = "✅" if current >= obj.required_count else "  "
                        lines.append(f"  {status} {obj.description}: {current}/{obj.required_count}")
                    else:
                        status = "✅" if current >= obj.required_count else "  "
                        lines.append(f"  {status} {obj.description}")
                lines.append("")
        else:
            lines.append("  (none)")
            lines.append("")
        
        # Show completed (ready to turn in)
        lines.append("COMPLETED (Ready to turn in)")
        lines.append("────────────────────────────")
        
        if completed_ready:
            for quest_id, template, progress in completed_ready:
                turn_in_to = template.turn_in_npc_template or "quest giver"
                lines.append(f"▸ {template.name} - Return to {turn_in_to}")
        else:
            lines.append("  (none)")
        
        lines.append("")
        lines.append("═══════════════════════════════════════")
        
        events.append(self.ctx.msg_to_player(player_id, "\n".join(lines)))
        return events
    
    def get_quest_details(self, player_id: 'PlayerId', quest_name: str) -> List[Event]:
        """Get details for a specific quest."""
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        # Find quest by name (fuzzy match)
        quest_name_lower = quest_name.lower().strip()
        found_quest = None
        found_template = None
        found_progress = None
        
        for quest_id, progress in player.quest_progress.items():
            template = self.templates.get(quest_id)
            if template and quest_name_lower in template.name.lower():
                found_quest = quest_id
                found_template = template
                found_progress = progress
                break
        
        if not found_template or not found_progress:
            events.append(self.ctx.msg_to_player(player_id, f"Quest not found: {quest_name}"))
            return events
        
        lines = [
            f"═══ {found_template.name} ═══",
            "",
            found_template.description,
            "",
            "Objectives:",
        ]
        
        for obj in found_template.objectives:
            current = found_progress.objective_progress.get(obj.id, 0)
            if obj.hidden and current == 0:
                continue
            
            if obj.required_count > 1:
                status = "✅" if current >= obj.required_count else "☐"
                lines.append(f"  {status} {obj.description} ({current}/{obj.required_count})")
            else:
                status = "✅" if current >= obj.required_count else "☐"
                lines.append(f"  {status} {obj.description}")
        
        lines.append("")
        lines.append(f"Status: {found_progress.status.value}")
        
        if found_template.turn_in_npc_template and found_progress.status == QuestStatus.COMPLETED:
            lines.append(f"Turn in to: {found_template.turn_in_npc_template}")
        
        events.append(self.ctx.msg_to_player(player_id, "\n".join(lines)))
        return events
    
    # === Dialogue System (Phase X.2) ===
    
    def start_dialogue(
        self,
        player_id: 'PlayerId',
        npc_id: 'EntityId',
        npc_template_id: str
    ) -> List[Event]:
        """Initiate dialogue with an NPC."""
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        # Check if already in dialogue
        if player.active_dialogue:
            events.append(self.ctx.msg_to_player(
                player_id,
                "You're already in a conversation. Say 'bye' to end it first."
            ))
            return events
        
        # Get dialogue tree for this NPC
        tree = self.dialogue_trees.get(npc_template_id)
        if not tree:
            # NPC has no dialogue tree - show generic message
            npc = self.ctx.world.npcs.get(npc_id)
            npc_name = npc.name if npc else "The creature"
            events.append(self.ctx.msg_to_player(
                player_id,
                f"{npc_name} has nothing to say."
            ))
            return events
        
        # Set dialogue state
        player.active_dialogue = npc_template_id
        player.active_dialogue_npc_id = npc_id
        
        # Find the appropriate entry node
        entry_node_id = self._get_entry_node(player_id, tree)
        player.dialogue_node = entry_node_id
        
        # Display the entry node
        events.extend(self._display_dialogue_node(player_id, tree, entry_node_id))
        
        return events
    
    def _get_entry_node(self, player_id: 'PlayerId', tree: DialogueTree) -> str:
        """Find the appropriate entry node based on conditions."""
        player = self.ctx.world.players.get(player_id)
        if not player:
            return tree.entry_node
        
        # Check entry overrides in order
        for override in tree.entry_overrides:
            if self._check_dialogue_conditions(player_id, override.conditions):
                return override.node_id
        
        return tree.entry_node
    
    def _check_dialogue_conditions(
        self,
        player_id: 'PlayerId',
        conditions: List[DialogueCondition]
    ) -> bool:
        """Evaluate dialogue conditions (AND logic)."""
        player = self.ctx.world.players.get(player_id)
        if not player:
            return False
        
        for condition in conditions:
            result = self._evaluate_condition(player_id, condition)
            if condition.negate:
                result = not result
            if not result:
                return False
        
        return True
    
    def _evaluate_condition(
        self,
        player_id: 'PlayerId',
        condition: DialogueCondition
    ) -> bool:
        """Evaluate a single dialogue condition."""
        player = self.ctx.world.players.get(player_id)
        if not player:
            return False
        
        params = condition.params
        
        if condition.type == "quest_status":
            # Check player's quest status
            quest_id = params.get("quest_id")
            expected_status = params.get("status")
            if not quest_id or not expected_status:
                return False
            
            current_status = self.get_quest_status(player_id, quest_id)
            return current_status.value == expected_status
        
        elif condition.type == "quest_complete":
            # Check if quest is in completed_quests
            quest_id = params.get("quest_id")
            return quest_id in player.completed_quests
        
        elif condition.type == "has_quest":
            # Check if player has an active quest
            quest_id = params.get("quest_id")
            return quest_id in player.quest_progress
        
        elif condition.type == "flag_set":
            # Check player flags
            flag_name = params.get("name")
            expected_value = params.get("value", True)
            return player.player_flags.get(flag_name) == expected_value
        
        elif condition.type == "level":
            # Check player level
            min_level = params.get("min_level", 0)
            max_level = params.get("max_level", 999)
            return min_level <= player.level <= max_level
        
        elif condition.type == "has_item":
            # Check if player has item
            item_template_id = params.get("template_id")
            return self._player_has_item(player, item_template_id)
        
        # Default: unknown condition fails
        return False
    
    def _display_dialogue_node(
        self,
        player_id: 'PlayerId',
        tree: DialogueTree,
        node_id: str
    ) -> List[Event]:
        """Display a dialogue node with available options."""
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        node = tree.nodes.get(node_id)
        if not node:
            events.append(self.ctx.msg_to_player(player_id, "[Dialogue error: node not found]"))
            self.end_dialogue(player_id)
            return events
        
        # Get NPC name
        npc = self.ctx.world.npcs.get(player.active_dialogue_npc_id) if player.active_dialogue_npc_id else None
        npc_name = npc.name if npc else "NPC"
        
        # Execute node actions
        for action in node.actions:
            action_events = self._execute_dialogue_action(player_id, action)
            events.extend(action_events)
        
        # Build display text
        lines = [f"\n{npc_name} says:"]
        lines.append("")
        
        # Substitute variables in text
        text = self._substitute_dialogue_variables(player_id, node.text)
        lines.append(text)
        lines.append("")
        
        # Get available options
        available_options = []
        for i, option in enumerate(node.options):
            if option.hidden_if_unavailable:
                if not self._check_dialogue_conditions(player_id, option.conditions):
                    continue
            available_options.append((i, option))
        
        if available_options:
            for display_num, (orig_idx, option) in enumerate(available_options, 1):
                lines.append(f"  [{display_num}] {option.text}")
        else:
            # No options = end of dialogue
            lines.append("  (End of conversation)")
        
        events.append(self.ctx.msg_to_player(player_id, "\n".join(lines)))
        
        # Store mapping of display numbers to original indices for selection
        player_dialogue_options = [(orig_idx, option) for orig_idx, option in available_options]
        # Store in player for later selection (we'll use a simple approach)
        # Since we can't easily store this, we'll re-evaluate on selection
        
        return events
    
    def select_option(self, player_id: 'PlayerId', option_number: int) -> List[Event]:
        """Player selects a dialogue option by number (1-indexed)."""
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player or not player.active_dialogue:
            events.append(self.ctx.msg_to_player(player_id, "You're not in a conversation."))
            return events
        
        tree = self.dialogue_trees.get(player.active_dialogue)
        if not tree:
            self.end_dialogue(player_id)
            return events
        
        node = tree.nodes.get(player.dialogue_node) if player.dialogue_node else None
        if not node:
            self.end_dialogue(player_id)
            return events
        
        # Re-evaluate available options
        available_options = []
        for i, option in enumerate(node.options):
            if option.hidden_if_unavailable:
                if not self._check_dialogue_conditions(player_id, option.conditions):
                    continue
            available_options.append((i, option))
        
        # Validate selection
        if option_number < 1 or option_number > len(available_options):
            events.append(self.ctx.msg_to_player(
                player_id,
                f"Invalid option. Choose 1-{len(available_options)}."
            ))
            return events
        
        # Get selected option
        orig_idx, selected_option = available_options[option_number - 1]
        
        # Show what player said
        events.append(self.ctx.msg_to_player(player_id, f'\nYou say: "{selected_option.text}"'))
        
        # Execute option actions
        for action in selected_option.actions:
            action_events = self._execute_dialogue_action(player_id, action)
            events.extend(action_events)
        
        # Handle quest shortcuts
        if selected_option.accept_quest:
            accept_events = self.accept_quest(player_id, selected_option.accept_quest)
            events.extend(accept_events)
        
        if selected_option.turn_in_quest:
            turn_in_events = self.turn_in_quest(player_id, selected_option.turn_in_quest)
            events.extend(turn_in_events)
        
        # Navigate to next node
        if selected_option.next_node is None:
            # End dialogue
            events.extend(self.end_dialogue(player_id))
        else:
            player.dialogue_node = selected_option.next_node
            events.extend(self._display_dialogue_node(player_id, tree, selected_option.next_node))
        
        return events
    
    def end_dialogue(self, player_id: 'PlayerId') -> List[Event]:
        """End the current dialogue."""
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        if player.active_dialogue:
            npc = self.ctx.world.npcs.get(player.active_dialogue_npc_id) if player.active_dialogue_npc_id else None
            npc_name = npc.name if npc else "The NPC"
            events.append(self.ctx.msg_to_player(player_id, f"\n{npc_name} nods as you step away."))
        
        # Clear dialogue state
        player.active_dialogue = None
        player.dialogue_node = None
        player.active_dialogue_npc_id = None
        
        return events
    
    def _execute_dialogue_action(
        self,
        player_id: 'PlayerId',
        action: DialogueAction
    ) -> List[Event]:
        """Execute a dialogue action."""
        events: List[Event] = []
        
        player = self.ctx.world.players.get(player_id)
        if not player:
            return events
        
        params = action.params
        
        if action.type == "set_flag":
            # Set player flag
            flag_name = params.get("name")
            flag_value = params.get("value", True)
            if flag_name:
                player.player_flags[flag_name] = flag_value
        
        elif action.type == "message_player":
            # Send a message to the player
            text = params.get("text", "")
            text = self._substitute_dialogue_variables(player_id, text)
            events.append(self.ctx.msg_to_player(player_id, text))
        
        elif action.type == "accept_quest":
            # Accept a quest
            quest_id = params.get("quest_id")
            if quest_id:
                accept_events = self.accept_quest(player_id, quest_id)
                events.extend(accept_events)
        
        elif action.type == "turn_in_quest":
            # Turn in a quest
            quest_id = params.get("quest_id")
            if quest_id:
                turn_in_events = self.turn_in_quest(player_id, quest_id)
                events.extend(turn_in_events)
        
        return events
    
    def _substitute_dialogue_variables(self, player_id: 'PlayerId', text: str) -> str:
        """Substitute variables in dialogue text."""
        player = self.ctx.world.players.get(player_id)
        if not player:
            return text
        
        # Player variables
        text = text.replace("{player.name}", player.name)
        text = text.replace("{player.level}", str(player.level))
        
        # NPC variables
        if player.active_dialogue_npc_id:
            npc = self.ctx.world.npcs.get(player.active_dialogue_npc_id)
            if npc:
                text = text.replace("{npc.name}", npc.name)
        
        # Quest variables - pattern: {quest.QUEST_ID.objectives.OBJ_ID.remaining}
        import re
        quest_pattern = r'\{quest\.([^.]+)\.objectives\.([^.]+)\.(current|remaining|required)\}'
        
        def replace_quest_var(match):
            quest_id = match.group(1)
            obj_id = match.group(2)
            var_type = match.group(3)
            
            progress = player.quest_progress.get(quest_id)
            template = self.templates.get(quest_id)
            
            if not progress or not template:
                return "?"
            
            current = progress.objective_progress.get(obj_id, 0)
            
            # Find objective for required count
            required = 1
            for obj in template.objectives:
                if obj.id == obj_id:
                    required = obj.required_count
                    break
            
            if var_type == "current":
                return str(current)
            elif var_type == "remaining":
                return str(max(0, required - current))
            elif var_type == "required":
                return str(required)
            
            return "?"
        
        text = re.sub(quest_pattern, replace_quest_var, text)
        
        return text
