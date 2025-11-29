# Phase X Design Document: Quest System and Narrative Progression

## Executive Summary

Phase X introduces a comprehensive quest system that enables structured narrative experiences, player-driven story progression, and meaningful rewards. Building on the trigger infrastructure from Phase 5, quests become first-class entities that track player progress, gate content behind achievements, and provide the backbone for long-term engagement. This phase leverages our existing systems (TriggerSystem, EffectSystem, ItemSystem, NPCs) to create quests without introducing architectural complexity.

---

## Current State Analysis

### What We Already Have

**TriggerSystem (Phase 5)** - Event-driven room reactivity:
```python
class TriggerSystem:
    def fire_event(self, room: WorldRoom, event: str, ctx: TriggerContext) -> list[Event]
    def fire_command(self, room: WorldRoom, raw_command: str, ctx: TriggerContext) -> list[Event]
    
# Conditions: flag_set, has_item, level, health_percent, in_combat, has_effect, entity_present, player_count
# Actions: message_player, message_room, set_flag, damage, heal, apply_effect, spawn_npc, despawn_npc,
#          open_exit, close_exit, spawn_item, give_item, take_item, enable_trigger, disable_trigger
```

**NPC Behavior System** - Reactive NPCs with hooks:
```python
class BehaviorHook(Protocol):
    def on_player_enter(self, npc, player, room, world) -> BehaviorResult | None
    def on_damaged(self, npc, attacker, damage, world) -> BehaviorResult | None
    def on_idle(self, npc, room, world) -> BehaviorResult | None
    def on_death(self, npc, killer, world) -> BehaviorResult | None
```

**Item System** - Full inventory management:
- Item templates with types, stats, equipment slots
- Item instances with location tracking
- Container support (bags, chests)
- Consumables with effects

**Combat System** - Real-time auto-attack:
- Weapon-based swing timing
- Experience rewards on kill
- Death and respawn mechanics

**Effect System** - Temporary state modifications:
- Buffs/debuffs with duration
- Stat modifiers
- Periodic effects (DoT/HoT)

### The Gap

While we have reactive rooms and NPCs, we lack:
- **Persistent quest state** tracking across sessions
- **Quest objectives** (kill X, collect Y, visit Z)
- **Quest chains** with prerequisites
- **NPC dialogue trees** for quest givers
- **Quest rewards** (XP, items, currency, reputation)
- **Quest journal** for players to track progress
- **World integration** where quests modify the environment

---

## Design Philosophy

### Principle 1: Quests as State Machines

Each quest is a finite state machine with well-defined transitions:

```
NOT_AVAILABLE → AVAILABLE → ACCEPTED → IN_PROGRESS → COMPLETED → TURNED_IN
                    ↑            ↓           ↓
                    └────────────┴── FAILED ─┘
```

State changes are triggered by player actions, NPC interactions, or world events.

### Principle 2: Objectives as Observers

Quest objectives observe game events through the existing hook system:

| Event | Observer Hook |
|-------|---------------|
| NPC killed | `on_npc_death` |
| Item acquired | `on_item_pickup` |
| Room entered | `on_room_enter` |
| Command issued | `on_command` |
| Trigger fired | `on_trigger` |

### Principle 3: Dialogue as Branching Triggers

NPC dialogue trees are a specialized form of command triggers:

```yaml
dialogue:
  - id: greet
    text: "Greetings, traveler. I have a task for you."
    options:
      - text: "What do you need?"
        next: explain_quest
      - text: "Not interested."
        next: farewell
```

This reuses our trigger condition/action pattern for dialogue outcomes.

### Principle 4: Rewards Through Existing Systems

Quest rewards flow through established channels:

| Reward Type | System Used |
|-------------|-------------|
| Experience | `player.experience += amount` |
| Items | `ItemSystem.give_item()` |
| Effects | `EffectSystem.apply_effect()` |
| Flags | `room.room_flags`, `player.data` |
| Triggers | `TriggerSystem.enable_trigger()` |

---

## Proposed Architecture

### Core Data Structures

```python
class QuestStatus(Enum):
    """Possible states of a quest for a player."""
    NOT_AVAILABLE = "not_available"  # Prerequisites not met
    AVAILABLE = "available"          # Can be accepted
    ACCEPTED = "accepted"            # Just accepted, objectives not started
    IN_PROGRESS = "in_progress"      # Working on objectives
    COMPLETED = "completed"          # All objectives done, needs turn-in
    TURNED_IN = "turned_in"          # Rewards received, quest finished
    FAILED = "failed"                # Quest failed (optional state)

class ObjectiveType(Enum):
    """Types of quest objectives."""
    KILL = "kill"                    # Kill N of NPC template
    COLLECT = "collect"              # Collect N of item template
    DELIVER = "deliver"              # Bring item to NPC
    VISIT = "visit"                  # Enter a specific room
    INTERACT = "interact"            # Use command in room (trigger-based)
    ESCORT = "escort"                # Keep NPC alive to destination
    DEFEND = "defend"                # Prevent NPCs from reaching location
    TALK = "talk"                    # Speak to NPC
    USE_ITEM = "use_item"            # Use specific item

@dataclass
class QuestObjective:
    """A single objective within a quest."""
    id: str
    type: ObjectiveType
    description: str
    
    # Type-specific parameters
    target_template_id: str | None = None  # NPC or item template
    target_room_id: RoomId | None = None   # For VISIT objectives
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
    items: list[tuple[str, int]] = field(default_factory=list)  # (template_id, quantity)
    effects: list[dict] = field(default_factory=list)           # Effect definitions
    flags: dict[str, Any] = field(default_factory=dict)         # Player flags to set
    currency: int = 0                                            # Future: gold/currency
    reputation: dict[str, int] = field(default_factory=dict)    # Future: faction rep

@dataclass
class QuestTemplate:
    """Definition of a quest."""
    id: str
    name: str
    description: str
    
    # Quest giver
    giver_npc_template: str | None = None  # NPC who gives quest
    giver_room_id: RoomId | None = None    # Or location-based
    
    # Requirements to see/accept quest
    prerequisites: list[str] = field(default_factory=list)      # Quest IDs
    level_requirement: int = 1
    required_items: list[str] = field(default_factory=list)     # Must have to accept
    required_flags: dict[str, Any] = field(default_factory=dict)
    
    # Objectives
    objectives: list[QuestObjective] = field(default_factory=list)
    
    # Completion
    turn_in_npc_template: str | None = None  # NPC to turn in to (None = auto-complete)
    turn_in_room_id: RoomId | None = None    # Or location-based turn-in
    rewards: QuestReward = field(default_factory=QuestReward)
    
    # Metadata
    category: str = "main"                   # main, side, daily, repeatable
    repeatable: bool = False
    cooldown_hours: float = 0                # For repeatable quests
    time_limit_minutes: float | None = None  # Optional time limit
    
    # Dialogue
    accept_dialogue: str = "Quest accepted."
    progress_dialogue: str = "Still working on it?"
    complete_dialogue: str = "Well done!"
    
    # Triggers on state changes
    on_accept_actions: list[dict] = field(default_factory=list)
    on_complete_actions: list[dict] = field(default_factory=list)
    on_turn_in_actions: list[dict] = field(default_factory=list)

@dataclass
class QuestProgress:
    """Player's progress on a specific quest."""
    quest_id: str
    status: QuestStatus = QuestStatus.NOT_AVAILABLE
    
    # Objective tracking: objective_id -> current_count
    objective_progress: dict[str, int] = field(default_factory=dict)
    
    # Timing
    accepted_at: float | None = None
    completed_at: float | None = None
    turned_in_at: float | None = None
    
    # For repeatable quests
    completion_count: int = 0
    last_completed_at: float | None = None

@dataclass  
class DialogueNode:
    """A node in an NPC dialogue tree."""
    id: str
    text: str  # What NPC says (supports {player.name} substitution)
    
    # Player response options
    options: list[DialogueOption] = field(default_factory=list)
    
    # Conditions to show this node
    conditions: list[TriggerCondition] = field(default_factory=list)
    
    # Actions when this node is displayed
    actions: list[TriggerAction] = field(default_factory=list)

@dataclass
class DialogueOption:
    """A player's response option in dialogue."""
    text: str                                    # What player can say
    next_node: str | None = None                 # Next dialogue node ID
    conditions: list[TriggerCondition] = field(default_factory=list)
    actions: list[TriggerAction] = field(default_factory=list)
    
    # Quest integration
    accept_quest: str | None = None              # Quest ID to accept
    turn_in_quest: str | None = None             # Quest ID to turn in
    
    # Visibility
    hidden_if_unavailable: bool = True           # Hide if conditions fail

@dataclass
class DialogueTree:
    """Complete dialogue for an NPC."""
    npc_template_id: str
    nodes: dict[str, DialogueNode] = field(default_factory=dict)
    entry_node: str = "greet"                    # Starting node ID
    
    # Context-sensitive entry points
    entry_overrides: list[tuple[list[TriggerCondition], str]] = field(default_factory=list)
```

### Player Extensions

```python
@dataclass
class WorldPlayer:
    # ... existing fields ...
    
    # Quest tracking
    quest_progress: dict[str, QuestProgress] = field(default_factory=dict)
    completed_quests: set[str] = field(default_factory=set)  # For quick lookup
    
    # Dialogue state
    active_dialogue: str | None = None           # Current dialogue tree ID
    dialogue_node: str | None = None             # Current node in tree
    
    # Player flags (persistent state)
    player_flags: dict[str, Any] = field(default_factory=dict)
```

### QuestSystem Class

```python
class QuestSystem:
    """Manages quest templates, player progress, and quest-related events."""
    
    def __init__(self, ctx: GameContext):
        self.ctx = ctx
        self.templates: dict[str, QuestTemplate] = {}
        self.dialogue_trees: dict[str, DialogueTree] = {}
        self._register_objective_handlers()
    
    # === Template Management ===
    
    def register_quest(self, template: QuestTemplate) -> None:
        """Register a quest template."""
        self.templates[template.id] = template
    
    def register_dialogue(self, tree: DialogueTree) -> None:
        """Register an NPC dialogue tree."""
        self.dialogue_trees[tree.npc_template_id] = tree
    
    # === Quest State Management ===
    
    def get_quest_status(self, player_id: PlayerId, quest_id: str) -> QuestStatus:
        """Get player's current status on a quest."""
        ...
    
    def check_availability(self, player_id: PlayerId, quest_id: str) -> bool:
        """Check if a quest is available to a player."""
        ...
    
    def accept_quest(self, player_id: PlayerId, quest_id: str) -> list[Event]:
        """Player accepts a quest."""
        ...
    
    def update_objective(
        self, 
        player_id: PlayerId, 
        quest_id: str, 
        objective_id: str, 
        delta: int = 1
    ) -> list[Event]:
        """Update progress on an objective."""
        ...
    
    def check_completion(self, player_id: PlayerId, quest_id: str) -> bool:
        """Check if all required objectives are complete."""
        ...
    
    def turn_in_quest(self, player_id: PlayerId, quest_id: str) -> list[Event]:
        """Turn in a completed quest for rewards."""
        ...
    
    def fail_quest(self, player_id: PlayerId, quest_id: str) -> list[Event]:
        """Fail a quest (optional, for timed/escort quests)."""
        ...
    
    # === Event Observers ===
    
    def on_npc_killed(
        self, 
        player_id: PlayerId, 
        npc: WorldNpc
    ) -> list[Event]:
        """Called when player kills an NPC. Updates KILL objectives."""
        ...
    
    def on_item_acquired(
        self, 
        player_id: PlayerId, 
        item_template_id: str, 
        quantity: int
    ) -> list[Event]:
        """Called when player picks up an item. Updates COLLECT objectives."""
        ...
    
    def on_room_entered(
        self, 
        player_id: PlayerId, 
        room_id: RoomId
    ) -> list[Event]:
        """Called when player enters a room. Updates VISIT objectives."""
        ...
    
    def on_npc_talked(
        self, 
        player_id: PlayerId, 
        npc: WorldNpc
    ) -> list[Event]:
        """Called when player talks to NPC. Updates TALK objectives."""
        ...
    
    # === Dialogue System ===
    
    def start_dialogue(
        self, 
        player_id: PlayerId, 
        npc: WorldNpc
    ) -> list[Event]:
        """Initiate dialogue with an NPC."""
        ...
    
    def select_option(
        self, 
        player_id: PlayerId, 
        option_index: int
    ) -> list[Event]:
        """Player selects a dialogue option."""
        ...
    
    def end_dialogue(self, player_id: PlayerId) -> list[Event]:
        """End the current dialogue."""
        ...
    
    # === Journal/UI ===
    
    def get_quest_log(self, player_id: PlayerId) -> list[dict]:
        """Get formatted quest log for player."""
        ...
    
    def get_objective_display(
        self, 
        player_id: PlayerId, 
        quest_id: str
    ) -> list[str]:
        """Get formatted objective list for a quest."""
        ...
```

---

## Command Integration

### New Player Commands

| Command | Description |
|---------|-------------|
| `talk <npc>` | Initiate dialogue with NPC |
| `1`, `2`, `3`... | Select dialogue option by number |
| `bye`, `farewell` | End dialogue |
| `journal`, `quests`, `quest log` | View quest journal |
| `quest <name>` | View specific quest details |
| `abandon <quest>` | Abandon a quest |

### Dialogue Flow Example

```
> talk elder marcus

Elder Marcus turns to face you.

"Ah, a traveler! These are dark times. Goblins have overrun the 
eastern mines, and we desperately need someone to clear them out."

  [1] "I'll help you deal with the goblins."
  [2] "What's in it for me?"
  [3] "Tell me more about these mines."
  [4] "Farewell."

> 1

"Excellent! Venture into the Eastern Mines and slay 10 Goblin Warriors.
Return to me when the deed is done."

📜 Quest Accepted: Clear the Mines
   • Kill Goblin Warriors (0/10)

> journal

═══════════════════════════════════════
           📜 QUEST JOURNAL
═══════════════════════════════════════

ACTIVE QUESTS
─────────────
▸ Clear the Mines
  Kill Goblin Warriors: 0/10
  Turn in to: Elder Marcus

COMPLETED (Ready to turn in)
────────────────────────────
  (none)

═══════════════════════════════════════
```

---

## YAML Configuration Examples

### Simple Kill Quest

```yaml
# quests/goblin_menace.yaml
quests:
  - id: clear_the_mines
    name: "Clear the Mines"
    description: "Elder Marcus has asked you to clear the goblin infestation from the Eastern Mines."
    category: main
    
    giver_npc_template: elder_marcus
    turn_in_npc_template: elder_marcus
    
    level_requirement: 1
    
    objectives:
      - id: kill_goblins
        type: kill
        description: "Kill Goblin Warriors"
        target_template_id: goblin_warrior
        required_count: 10
    
    rewards:
      experience: 150
      items:
        - ["gold_coins", 25]
        - ["minor_health_potion", 3]
    
    accept_dialogue: |
      "Excellent! Venture into the Eastern Mines and slay 10 Goblin Warriors.
      Return to me when the deed is done."
    
    progress_dialogue: |
      "Have you cleared the mines yet? We cannot rest while those beasts remain."
    
    complete_dialogue: |
      "You've done it! The mines are safe once more. Please, take this reward
      as a token of our gratitude."
```

### Collect and Deliver Quest

```yaml
quests:
  - id: alchemist_supplies
    name: "Alchemist's Supplies"
    description: "The alchemist needs rare herbs from the Whispering Woods."
    category: side
    
    giver_npc_template: alchemist_vera
    turn_in_npc_template: alchemist_vera
    
    level_requirement: 3
    prerequisites:
      - clear_the_mines  # Must complete first quest
    
    objectives:
      - id: collect_moonpetal
        type: collect
        description: "Collect Moonpetal Flowers"
        target_template_id: moonpetal_flower
        required_count: 5
        
      - id: collect_shadowmoss
        type: collect
        description: "Collect Shadowmoss"
        target_template_id: shadowmoss
        required_count: 3
        
      - id: avoid_wolves
        type: kill
        description: "Defeat Forest Wolves (if attacked)"
        target_template_id: forest_wolf
        required_count: 0  # Optional
        optional: true
    
    rewards:
      experience: 200
      items:
        - ["greater_health_potion", 2]
        - ["elixir_of_swiftness", 1]
      effects:
        - name: "Alchemist's Blessing"
          duration: 3600  # 1 hour
          stat_modifiers:
            max_health: 20
```

### Exploration Quest with Hidden Objectives

```yaml
quests:
  - id: secrets_of_the_tower
    name: "Secrets of the Tower"
    description: "Explore the abandoned wizard's tower and uncover its mysteries."
    category: main
    
    giver_npc_template: mysterious_stranger
    
    level_requirement: 5
    prerequisites:
      - alchemist_supplies
    required_items:
      - wizard_key  # Must have obtained this
    
    objectives:
      - id: enter_tower
        type: visit
        description: "Enter the Wizard's Tower"
        target_room_id: wizard_tower_foyer
        
      - id: find_study
        type: visit
        description: "Find the Wizard's Study"
        target_room_id: wizard_study
        hidden: true  # Revealed after entering tower
        
      - id: read_journal
        type: interact
        description: "Read the Wizard's Journal"
        target_room_id: wizard_study
        command_pattern: "read journal"
        hidden: true
        
      - id: discover_secret
        type: interact
        description: "???"  # Truly hidden until discovered
        target_room_id: wizard_study
        command_pattern: "press hidden switch"
        hidden: true
    
    # No turn-in NPC - auto-completes
    rewards:
      experience: 500
      items:
        - ["wizard_staff", 1]
      flags:
        tower_secrets_known: true
    
    on_complete_actions:
      - type: message_player
        params:
          text: |
            📜 As you uncover the final secret, knowledge floods your mind.
            The wizard's legacy is now yours to carry forward.
```

### Quest Chain Definition

```yaml
# quests/chains/goblin_war.yaml
quest_chains:
  - id: goblin_war_chain
    name: "The Goblin War"
    description: "A series of quests to end the goblin threat once and for all."
    quests:
      - clear_the_mines        # Level 1-3
      - goblin_scouts          # Level 3-5
      - find_goblin_camp       # Level 5-7
      - defeat_goblin_chief    # Level 7-10 (boss)
    
    # Rewards for completing the chain
    chain_rewards:
      experience: 1000
      items:
        - ["goblin_slayer_title", 1]  # Cosmetic title
      flags:
        goblin_war_hero: true
```

### NPC Dialogue Tree

```yaml
# dialogues/elder_marcus.yaml
dialogues:
  - npc_template_id: elder_marcus
    entry_node: greet
    
    # Context-sensitive greetings
    entry_overrides:
      - conditions:
          - type: quest_status
            params: { quest_id: "clear_the_mines", status: "completed" }
        node: greet_quest_complete
      - conditions:
          - type: quest_status
            params: { quest_id: "clear_the_mines", status: "in_progress" }
        node: greet_quest_progress
    
    nodes:
      greet:
        text: |
          Elder Marcus looks up from his work, his weathered face creasing with concern.
          
          "Ah, a traveler! These are dark times. Goblins have overrun the 
          eastern mines, and we desperately need someone to clear them out."
        options:
          - text: "I'll help you deal with the goblins."
            accept_quest: clear_the_mines
            next_node: quest_accepted
          - text: "What's in it for me?"
            next_node: discuss_reward
          - text: "Tell me more about these mines."
            next_node: mine_history
          - text: "Farewell."
            next_node: null  # Ends dialogue
      
      quest_accepted:
        text: |
          "Excellent! Venture into the Eastern Mines and slay 10 Goblin Warriors.
          Return to me when the deed is done. May the light guide your blade."
        options:
          - text: "I'll return when it's done."
            next_node: null
      
      discuss_reward:
        text: |
          "We may be a humble village, but we can offer gold and potions for your 
          trouble. More importantly, you'll have our eternal gratitude."
        options:
          - text: "Very well, I'll help."
            accept_quest: clear_the_mines
            next_node: quest_accepted
          - text: "I need to think about it."
            next_node: null
      
      mine_history:
        text: |
          "The Eastern Mines were once our livelihood—rich veins of iron and copper.
          Three weeks ago, goblins emerged from the deeper tunnels. We've lost 
          good miners to those beasts."
        options:
          - text: "I'll clear them out for you."
            accept_quest: clear_the_mines
            next_node: quest_accepted
          - text: "That's terrible. Farewell."
            next_node: null
      
      greet_quest_progress:
        text: |
          "Have you cleared the mines yet? Every night we hear their drums 
          echoing from the tunnels. Please, hurry."
        options:
          - text: "I'm working on it."
            next_node: null
          - text: "How many goblins are left?"
            next_node: progress_check
      
      progress_check:
        text: "{quest.clear_the_mines.objectives.kill_goblins.remaining} goblins remain in the mines. Stay vigilant."
        options:
          - text: "I'll finish the job."
            next_node: null
      
      greet_quest_complete:
        text: |
          Elder Marcus's eyes light up as you approach.
          
          "You've done it! I can see it in your eyes—the mines are clear! 
          Please, accept this reward. You've saved our village."
        options:
          - text: "It was my pleasure."
            turn_in_quest: clear_the_mines
            next_node: after_turn_in
      
      after_turn_in:
        text: |
          "If you seek more adventure, speak with Alchemist Vera. She mentioned 
          needing help gathering rare ingredients. Safe travels, hero."
        actions:
          - type: set_flag
            params: { name: "met_elder_marcus", value: true }
        options:
          - text: "Thank you, Elder."
            next_node: null
```

---

## Integration Points

### Hook into Combat System

```python
# In CombatSystem._process_death()
async def _process_death(self, entity: WorldEntity, killer: WorldEntity) -> list[Event]:
    events = []
    # ... existing death logic ...
    
    # Notify quest system if player killed an NPC
    if isinstance(killer, WorldPlayer) and isinstance(entity, WorldNpc):
        quest_events = await self.ctx.quest_system.on_npc_killed(
            player_id=killer.id,
            npc=entity
        )
        events.extend(quest_events)
    
    return events
```

### Hook into Item Pickup

```python
# In WorldEngine._pickup_item()
async def _pickup_item(self, player_id: PlayerId, item_name: str) -> list[Event]:
    events = []
    # ... existing pickup logic ...
    
    # Notify quest system
    if item:
        quest_events = await self.ctx.quest_system.on_item_acquired(
            player_id=player_id,
            item_template_id=item.template_id,
            quantity=item.quantity
        )
        events.extend(quest_events)
    
    return events
```

### Hook into Movement

```python
# In WorldEngine._move_player() - after trigger hooks
async def _move_player(self, player_id: PlayerId, direction: str) -> list[Event]:
    # ... existing movement ...
    
    # Quest VISIT objective tracking
    quest_events = await self.ctx.quest_system.on_room_entered(
        player_id=player_id,
        room_id=new_room.id
    )
    events.extend(quest_events)
    
    return events
```

### Hook into CommandRouter

```python
# In CommandRouter.dispatch()
def dispatch(self, player_id: PlayerId, raw: str) -> list[Event]:
    # Check if player is in dialogue
    player = self.ctx.world.players.get(player_id)
    if player and player.active_dialogue:
        return self._handle_dialogue_input(player_id, raw)
    
    # ... existing command routing ...
```

---

## Database Schema Extensions

```python
# New model for quest progress persistence
class QuestProgress(Base):
    __tablename__ = "quest_progress"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"))
    quest_id: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50))
    
    # JSON fields for flexible storage
    objective_progress: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Timestamps
    accepted_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    turned_in_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # For repeatable quests
    completion_count: Mapped[int] = mapped_column(Integer, default=0)
    last_completed_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint("player_id", "quest_id", name="uq_player_quest"),
    )

# Extend Player model
class Player(Base):
    # ... existing fields ...
    
    # Player flags (persistent state)
    player_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Relationship
    quest_progress: Mapped[list["QuestProgress"]] = relationship(back_populates="player")
```

---

## Implementation Plan

### Phase X.1: Core Quest Infrastructure

1. **Create `QuestSystem` class** in `backend/app/engine/systems/quests.py`
   - QuestTemplate, QuestProgress, QuestObjective dataclasses
   - Template registration and lookup
   - Basic state machine (accept, update, complete, turn_in)

2. **Extend WorldPlayer** with quest tracking
   - quest_progress dict
   - completed_quests set
   - player_flags dict

3. **Implement objective handlers**
   - KILL objective observer
   - COLLECT objective observer
   - VISIT objective observer

4. **Hook into engine events**
   - Combat death → KILL
   - Item pickup → COLLECT
   - Room enter → VISIT

5. **Add player commands**
   - `journal` / `quests` - View quest log
   - `quest <name>` - View quest details
   - `abandon <quest>` - Abandon quest

### Phase X.2: NPC Dialogue System

1. **Create dialogue data structures**
   - DialogueTree, DialogueNode, DialogueOption
   - Variable substitution ({player.name}, {quest.progress})

2. **Implement dialogue flow**
   - `talk <npc>` command
   - Option selection (1, 2, 3...)
   - Condition evaluation for options
   - Action execution on selection

3. **Quest integration**
   - accept_quest option action
   - turn_in_quest option action
   - Quest status conditions

4. **Context-sensitive entries**
   - Entry overrides based on conditions
   - Quest-aware greetings

### Phase X.3: YAML Loading and Persistence

1. **Quest YAML loader**
   - Parse quest definitions
   - Parse dialogue trees
   - Validate references (NPCs, items, rooms)

2. **Database persistence**
   - QuestProgress model
   - Save/load quest state
   - Player flags persistence

3. **Startup initialization**
   - Load quest templates
   - Load dialogue trees
   - Restore player quest states

### Phase X.4: Advanced Features

1. **Quest chains**
   - Chain definitions
   - Chain progress tracking
   - Chain rewards

2. **Special objective types**
   - ESCORT objectives
   - DEFEND objectives
   - Timed quests

3. **Repeatable quests**
   - Daily quest support
   - Cooldown tracking
   - Reset logic

4. **Quest triggers integration**
   - on_quest_accept trigger event
   - on_quest_complete trigger event
   - Quest conditions for room triggers

---

## Future Considerations

### Reputation System

```yaml
factions:
  - id: village_alliance
    name: "Village Alliance"
    reputation_levels:
      - name: "Hated"
        min: -1000
        max: -500
      - name: "Hostile"
        min: -499
        max: -100
      - name: "Unfriendly"
        min: -99
        max: 0
      - name: "Neutral"
        min: 1
        max: 500
      - name: "Friendly"
        min: 501
        max: 1000
      - name: "Honored"
        min: 1001
        max: 2000
      - name: "Exalted"
        min: 2001
        max: 9999

quests:
  - id: village_defense
    rewards:
      reputation:
        village_alliance: 100
```

### Dynamic Quest Generation

```python
class QuestGenerator:
    """Generate procedural quests based on world state."""
    
    def generate_bounty(self, area: WorldArea) -> QuestTemplate:
        """Create a kill quest for NPCs in area."""
        ...
    
    def generate_fetch(self, requester: WorldNpc) -> QuestTemplate:
        """Create a collection quest based on NPC needs."""
        ...
```

### Party Quests

```yaml
quests:
  - id: dragon_raid
    name: "Slay the Dragon"
    category: raid
    
    party_requirements:
      min_players: 3
      max_players: 5
      
    # Objectives tracked per-player
    shared_objectives:
      - id: slay_dragon
        type: kill
        target_template_id: ancient_dragon
        required_count: 1
        contribution_based: true  # All participants get credit
```

---

## Conclusion

Phase X introduces a comprehensive quest system that provides structured narrative experiences while leveraging our established patterns. By treating quests as state machines, objectives as event observers, and dialogue as branching triggers, we maintain architectural consistency with previous phases.

Key benefits:
- **YAML-driven content**: World builders can create quests without code changes
- **Existing system integration**: Quests flow through combat, items, triggers
- **Extensible foundation**: Reputation, procedural quests, and parties can be added later
- **Player engagement**: Clear progression, meaningful rewards, narrative depth

The quest system transforms scattered NPC interactions and room exploration into cohesive story experiences that give players purpose and direction in the world.