# backend/app/engine/world.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Set, Callable, Awaitable, Any, Protocol, runtime_checkable
import time

# Import behavior system from behaviors package
from .behaviors import BEHAVIOR_SCRIPTS, DEFAULT_BEHAVIOR, resolve_behaviors


# Entity type enumeration
class EntityType(Enum):
    PLAYER = "player"
    NPC = "npc"


# Targetable type enumeration (includes items)
class TargetableType(Enum):
    PLAYER = "player"
    NPC = "npc"
    ITEM = "item"


# Simple type aliases for clarity
RoomId = str
PlayerId = str
AreaId = str
Direction = str  # "north", "south", "east", "west", "up", "down"
ItemId = str
ItemTemplateId = str
NpcId = str
NpcTemplateId = str
EntityId = str  # Unified ID for players and NPCs
TargetableId = str  # Unified ID for anything targetable (entities + items)


# Room type emoji mapping
ROOM_TYPE_EMOJIS = {
    "forest": "🌲",
    "urban": "🏙️",
    "rural": "🏘️",
    "underground": "🕳️",
    "underwater": "🌊",
    "lake": "🏞️",
    "ocean": "🌊",
    "river": "🏞️",
    "marsh": "🌾",
    "grassland": "🌾",
    "desert": "🏜️",
    "sky": "☁️",
    "ethereal": "✨",
    "forsaken": "💀",
}


@runtime_checkable
class Targetable(Protocol):
    """
    Protocol for anything that can be targeted by commands (entities, items, etc.).
    
    Provides a unified interface for targeting, allowing commands like:
    - look <target>
    - give <target>
    - examine <target>
    
    Any object implementing this protocol can be found via unified targeting logic.
    """
    id: str
    name: str
    room_id: RoomId | None
    keywords: list[str]
    
    def get_description(self) -> str:
        """Return a description of the targetable object."""
        ...
    
    def get_targetable_type(self) -> TargetableType:
        """Return the type of this targetable (PLAYER, NPC, or ITEM)."""
        ...


def get_room_emoji(room_type: str) -> str:
    """Get the emoji for a room type, or a default if unknown."""
    return ROOM_TYPE_EMOJIS.get(room_type, "❓")


# Experience thresholds for leveling up
# Index = level, value = total XP needed to reach that level
# Level 1 starts at 0 XP, level 2 requires 100 XP total, etc.
XP_THRESHOLDS = [
    0,      # Level 1
    100,    # Level 2
    250,    # Level 3
    500,    # Level 4
    1000,   # Level 5
    1750,   # Level 6
    2750,   # Level 7
    4000,   # Level 8
    5500,   # Level 9
    7500,   # Level 10
    10000,  # Level 11
    13000,  # Level 12
    16500,  # Level 13
    20500,  # Level 14
    25000,  # Level 15
    30000,  # Level 16
    36000,  # Level 17
    43000,  # Level 18
    51000,  # Level 19
    60000,  # Level 20
]

# Fixed stat gains per level (will be extensible by class in future)
# These are added to the entity's stats each time they level up
LEVEL_UP_STAT_GAINS = {
    "max_health": 10,
    "max_energy": 5,
    "strength": 1,
    "dexterity": 1,
    "intelligence": 1,
    "vitality": 1,
}


def get_level_for_xp(experience: int) -> int:
    """Get the level for a given amount of experience."""
    for level, threshold in enumerate(XP_THRESHOLDS):
        if experience < threshold:
            return level  # Return the previous level
    return len(XP_THRESHOLDS)  # Max level


def get_xp_for_next_level(current_level: int) -> int | None:
    """Get the XP threshold for the next level, or None if at max."""
    if current_level >= len(XP_THRESHOLDS):
        return None
    return XP_THRESHOLDS[current_level]


# Time conversion constants
# 24 game hours = 12 real minutes
REAL_SECONDS_PER_GAME_HOUR = 30.0  # 12 minutes / 24 hours = 0.5 minutes = 30 seconds
REAL_SECONDS_PER_GAME_DAY = REAL_SECONDS_PER_GAME_HOUR * 24  # 720 seconds = 12 minutes
GAME_HOURS_PER_REAL_SECOND = 1.0 / REAL_SECONDS_PER_GAME_HOUR


def real_seconds_to_game_hours(real_seconds: float) -> float:
    """Convert real-world seconds to game hours."""
    return real_seconds * GAME_HOURS_PER_REAL_SECOND


def real_seconds_to_game_minutes(real_seconds: float) -> float:
    """Convert real-world seconds to game minutes."""
    return real_seconds_to_game_hours(real_seconds) * 60


def game_hours_to_real_seconds(game_hours: float) -> float:
    """Convert game hours to real-world seconds."""
    return game_hours * REAL_SECONDS_PER_GAME_HOUR


def game_minutes_to_real_seconds(game_minutes: float) -> float:
    """Convert game minutes to real-world seconds."""
    return game_hours_to_real_seconds(game_minutes / 60)


@dataclass
class WorldTime:
    """
    Tracks in-game time.
    
    Time scale: 24 game hours = 12 real minutes
    This means 1 game hour = 30 real seconds
    """
    day: int = 1  # Day number (starts at 1)
    hour: int = 6  # Hour of day (0-23), default 6 AM (dawn)
    minute: int = 0  # Minute of hour (0-59)
    
    # When this time was last updated (Unix timestamp)
    last_update: float = field(default_factory=time.time)
    
    def advance(self, real_seconds_elapsed: float, time_scale: float = 1.0) -> None:
        """
        Advance game time based on real seconds elapsed.
        
        Args:
            real_seconds_elapsed: Real-world seconds that have passed
            time_scale: Multiplier for time passage (1.0 = normal, 2.0 = double speed, etc.)
        """
        # Calculate game time advancement
        game_minutes_elapsed = real_seconds_to_game_minutes(real_seconds_elapsed) * time_scale
        
        # Add to current time
        self.minute += int(game_minutes_elapsed)
        
        # Handle minute overflow
        if self.minute >= 60:
            hours_to_add = self.minute // 60
            self.minute = self.minute % 60
            self.hour += hours_to_add
        
        # Handle hour overflow
        if self.hour >= 24:
            days_to_add = self.hour // 24
            self.hour = self.hour % 24
            self.day += days_to_add
        
        self.last_update = time.time()
    
    def get_current_time(self, time_scale: float = 1.0) -> tuple[int, int, int]:
        """
        Get the current time accounting for elapsed time since last update.
        
        Args:
            time_scale: Multiplier for time passage
            
        Returns:
            Tuple of (day, hour, minute) representing current game time
        """
        # Calculate elapsed real time since last update
        elapsed_real_seconds = time.time() - self.last_update
        
        # Convert to game time
        game_minutes_elapsed = real_seconds_to_game_minutes(elapsed_real_seconds) * time_scale
        
        # Calculate current time
        current_minute = self.minute + int(game_minutes_elapsed)
        current_hour = self.hour
        current_day = self.day
        
        # Handle minute overflow
        if current_minute >= 60:
            hours_to_add = current_minute // 60
            current_minute = current_minute % 60
            current_hour += hours_to_add
        
        # Handle hour overflow
        if current_hour >= 24:
            days_to_add = current_hour // 24
            current_hour = current_hour % 24
            current_day += days_to_add
        
        return current_day, current_hour, current_minute
    
    def get_time_of_day(self, time_scale: float = 1.0) -> str:
        """
        Get the current time of day phase.
        
        Args:
            time_scale: Multiplier for time passage (used to calculate current hour)
        
        Returns: "dawn" (5-7), "morning" (7-12), "afternoon" (12-17), 
                 "dusk" (17-19), "evening" (19-22), "night" (22-5)
        """
        _, current_hour, _ = self.get_current_time(time_scale)
        
        if 5 <= current_hour < 7:
            return "dawn"
        elif 7 <= current_hour < 12:
            return "morning"
        elif 12 <= current_hour < 17:
            return "afternoon"
        elif 17 <= current_hour < 19:
            return "dusk"
        elif 19 <= current_hour < 22:
            return "evening"
        else:  # 22-24 or 0-5
            return "night"
    
    def get_time_emoji(self, time_scale: float = 1.0) -> str:
        """Get an emoji representing current time of day."""
        phase = self.get_time_of_day(time_scale)
        emojis = {
            "dawn": "🌅",
            "morning": "🌄",
            "afternoon": "☀️",
            "dusk": "🌆",
            "evening": "🌃",
            "night": "🌙",
        }
        return emojis.get(phase, "🕐")
    
    def format_time(self, time_scale: float = 1.0) -> str:
        """Format current time as HH:MM."""
        _, current_hour, current_minute = self.get_current_time(time_scale)
        return f"{current_hour:02d}:{current_minute:02d}"
    
    def format_full(self, time_scale: float = 1.0) -> str:
        """Format full time with phase."""
        current_day, current_hour, current_minute = self.get_current_time(time_scale)
        phase = self.get_time_of_day(time_scale)
        return f"{current_hour:02d}:{current_minute:02d} ({phase})"


# Default time phase flavor text
DEFAULT_TIME_PHASES = {
    "dawn": "The sun rises in the east, painting the sky in hues of orange and pink.",
    "morning": "The morning sun shines brightly overhead.",
    "afternoon": "The sun reaches its peak, warming the land below.",
    "dusk": "The sun sets in the west, casting long shadows across the world.",
    "evening": "Twilight descends, and the first stars appear in the darkening sky.",
    "night": "The moon hangs in the starry night sky, casting silver light upon the world."
}


@dataclass
class WorldArea:
    """Represents a geographic area containing multiple rooms."""
    id: AreaId
    name: str
    description: str
    area_time: WorldTime
    time_scale: float = 1.0
    biome: str = "ethereal"
    climate: str = "temperate"
    ambient_lighting: str = "normal"
    weather_profile: str = "clear"
    danger_level: int = 1  # ADD THIS
    magic_intensity: str = "normal"  # ADD THIS
    ambient_sound: str | None = None
    time_phases: dict[str, str] = field(default_factory=lambda: DEFAULT_TIME_PHASES.copy())
    entry_points: set[RoomId] = field(default_factory=set)
    room_ids: set[RoomId] = field(default_factory=set)
    neighbor_areas: set[AreaId] = field(default_factory=set)


@dataclass
class TimeEvent:
    """
    Represents a scheduled event in the time system.
    
    Events are ordered by execute_at time and can be:
    - One-shot (execute once then remove)
    - Recurring (reschedule after execution)
    """
    execute_at: float  # Unix timestamp when event should execute
    callback: Callable[[], Awaitable[None]]  # Async function to call
    event_id: str  # Unique identifier for cancellation
    recurring: bool = False  # If True, reschedule after execution
    interval: float = 0.0  # Seconds between recurrences (if recurring)
    
    def __lt__(self, other: 'TimeEvent') -> bool:
        """Compare events by execution time for priority queue."""
        return self.execute_at < other.execute_at


@dataclass
class Effect:
    """
    Represents a temporary effect (buff/debuff/DoT/HoT) on a player.
    
    Effects modify player stats temporarily and can apply periodic changes.
    """
    effect_id: str  # Unique identifier
    name: str  # Display name (e.g., "Blessed", "Poisoned")
    effect_type: str  # "buff", "debuff", "dot" (damage over time), "hot" (heal over time)
    
    # Stat modifications applied while active
    stat_modifiers: Dict[str, int] = field(default_factory=dict)
    # e.g., {"armor_class": 5, "strength": 2}
    
    # Duration tracking
    duration: float = 0.0  # Total duration in seconds
    applied_at: float = 0.0  # Unix timestamp when applied
    
    # Periodic effects (DoT/HoT)
    interval: float = 0.0  # Seconds between periodic ticks (0 = not periodic)
    magnitude: int = 0  # HP change per tick (positive for HoT, negative for DoT)
    
    # Associated time event IDs for cleanup
    expiration_event_id: str | None = None  # Event that removes this effect
    periodic_event_id: str | None = None  # Event for periodic damage/healing
    
    def get_remaining_duration(self) -> float:
        """Calculate remaining duration in seconds."""
        if self.applied_at == 0.0:
            return self.duration
        elapsed = time.time() - self.applied_at
        return max(0.0, self.duration - elapsed)


# =============================================================================
# Real-Time Combat System
# =============================================================================

class CombatPhase(Enum):
    """Current phase of a combat action."""
    IDLE = "idle"           # Not in combat
    WINDUP = "windup"       # Preparing attack (can be interrupted)
    SWING = "swing"         # Attack in progress (committed)
    RECOVERY = "recovery"   # After attack, before next action
    BLOCKING = "blocking"   # Actively blocking
    DODGING = "dodging"     # Mid-dodge (brief invulnerability)


@dataclass
class WeaponStats:
    """Combat stats derived from equipped weapon or natural attacks."""
    damage_min: int = 1
    damage_max: int = 4
    swing_speed: float = 2.5      # Seconds for full attack cycle
    windup_ratio: float = 0.3     # Portion of swing that's interruptible windup
    damage_type: str = "physical" # physical, magic, fire, etc.
    reach: int = 1                # Melee range (for future positioning)
    
    @property
    def windup_time(self) -> float:
        """Time spent in interruptible windup phase."""
        return self.swing_speed * self.windup_ratio
    
    @property
    def swing_time(self) -> float:
        """Time spent in committed swing phase."""
        return self.swing_speed * (1 - self.windup_ratio)


@dataclass
class CombatState:
    """
    Tracks an entity's current combat status.
    
    Real-time combat flow:
    1. IDLE -> WINDUP: Attack initiated, timer starts
    2. WINDUP -> SWING: Windup complete, attack is committed
    3. SWING -> RECOVERY: Attack lands, damage applied
    4. RECOVERY -> WINDUP: Auto-attack continues (or IDLE if stopped)
    
    Interrupts:
    - Taking damage during WINDUP can interrupt and reset to IDLE
    - Moving cancels combat entirely
    - Blocking/dodging are alternative actions with their own timing
    """
    phase: CombatPhase = CombatPhase.IDLE
    target_id: EntityId | None = None  # Who we're attacking
    
    # Timing
    phase_started_at: float = 0.0     # Unix timestamp when current phase started
    phase_duration: float = 0.0        # How long current phase should last
    
    # Combat event tracking
    swing_event_id: str | None = None  # Scheduled event for swing completion
    auto_attack: bool = True           # Continue attacking after each swing
    
    # Combat stats (cached from weapon/skills)
    current_weapon: WeaponStats = field(default_factory=WeaponStats)
    
    # Defensive state
    block_reduction: float = 0.0       # Damage reduction while blocking (0-1)
    dodge_window: float = 0.0          # Remaining i-frames
    
    # Aggro tracking (for NPCs)
    threat_table: dict[EntityId, float] = field(default_factory=dict)
    
    def is_in_combat(self) -> bool:
        """Check if entity is actively in combat."""
        return self.phase != CombatPhase.IDLE
    
    def get_phase_progress(self) -> float:
        """Get progress through current phase (0.0 to 1.0)."""
        if self.phase_duration <= 0:
            return 1.0
        elapsed = time.time() - self.phase_started_at
        return min(1.0, elapsed / self.phase_duration)
    
    def get_phase_remaining(self) -> float:
        """Get time remaining in current phase."""
        elapsed = time.time() - self.phase_started_at
        return max(0.0, self.phase_duration - elapsed)
    
    def can_be_interrupted(self) -> bool:
        """Check if current action can be interrupted."""
        return self.phase in (CombatPhase.IDLE, CombatPhase.WINDUP, CombatPhase.RECOVERY)
    
    def start_phase(self, phase: CombatPhase, duration: float) -> None:
        """Transition to a new combat phase."""
        self.phase = phase
        self.phase_started_at = time.time()
        self.phase_duration = duration
    
    def add_threat(self, entity_id: EntityId, amount: float) -> None:
        """Add threat from an entity (for NPC target selection)."""
        current = self.threat_table.get(entity_id, 0.0)
        self.threat_table[entity_id] = current + amount
    
    def get_highest_threat(self) -> EntityId | None:
        """Get entity with highest threat."""
        if not self.threat_table:
            return None
        return max(self.threat_table.items(), key=lambda x: x[1])[0]
    
    def clear_combat(self) -> None:
        """Reset combat state to idle."""
        self.phase = CombatPhase.IDLE
        self.target_id = None
        self.phase_started_at = 0.0
        self.phase_duration = 0.0
        self.swing_event_id = None


@dataclass
class CombatResult:
    """Result of a combat action (attack, block, dodge)."""
    success: bool = False
    damage_dealt: int = 0
    damage_type: str = "physical"
    was_critical: bool = False
    was_blocked: bool = False
    was_dodged: bool = False
    was_interrupted: bool = False
    message: str = ""
    
    # Reactions triggered
    attacker_id: EntityId | None = None
    defender_id: EntityId | None = None


@dataclass
class WorldEntity:
    """
    Base class for all entities in the world (players and NPCs).
    
    Implements the Targetable protocol for unified command targeting.
    Provides unified interface for targeting, combat, effects, and room occupancy.
    All entities share:
    - Core stats (health, armor, attributes)
    - Inventory and equipment
    - Active effects (buffs/debuffs)
    - Combat capabilities
    - Character progression
    """
    id: EntityId
    entity_type: EntityType
    name: str
    room_id: RoomId
    
    # Keywords for targeting (alternative names to match against)
    keywords: list[str] = field(default_factory=list)
    
    # Core stats shared by all entities
    level: int = 1
    max_health: int = 100
    current_health: int = 100
    armor_class: int = 10
    
    # Primary attributes
    strength: int = 10
    dexterity: int = 10
    intelligence: int = 10
    vitality: int = 10
    
    # Energy system (mana/stamina)
    max_energy: int = 50
    current_energy: int = 50
    
    # Character progression
    character_class: str = "creature"  # e.g., "adventurer", "warrior", "goblin"
    experience: int = 0
    
    # Movement effects - flavor text triggered by movement
    on_move_effect: str | None = None  # e.g., "You glide gracefully" or "shuffles menacingly"
    
    # Inventory system (unified for players and NPCs)
    inventory_items: Set[ItemId] = field(default_factory=set)  # Items carried
    equipped_items: Dict[str, ItemId] = field(default_factory=dict)  # slot -> item_id
    
    # Combat properties (base values, can be overridden by equipment)
    base_attack_damage_min: int = 1
    base_attack_damage_max: int = 4
    base_attack_speed: float = 2.0  # seconds between attacks
    
    # Active effects (buffs/debuffs)
    active_effects: Dict[str, Effect] = field(default_factory=dict)
    
    # Real-time combat state
    combat: CombatState = field(default_factory=CombatState)
    
    def is_alive(self) -> bool:
        """Check if entity is alive."""
        return self.current_health > 0
    
    def apply_effect(self, effect: Effect) -> None:
        """
        Apply an effect to this entity.
        Replaces existing effect with same ID if present.
        """
        effect.applied_at = time.time()
        self.active_effects[effect.effect_id] = effect
    
    def remove_effect(self, effect_id: str) -> Effect | None:
        """
        Remove an effect by ID.
        Returns the removed effect, or None if not found.
        """
        return self.active_effects.pop(effect_id, None)
    
    def get_effective_stat(self, stat_name: str, base_value: int) -> int:
        """
        Calculate effective stat value with all active effect modifiers applied.
        
        Args:
            stat_name: Name of the stat (e.g., "armor_class", "strength")
            base_value: Base value of the stat before modifiers
            
        Returns:
            Effective value with all modifiers applied
        """
        total = base_value
        for effect in self.active_effects.values():
            if stat_name in effect.stat_modifiers:
                total += effect.stat_modifiers[stat_name]
        return total
    
    def get_effective_armor_class(self) -> int:
        """Get armor class with all effect modifiers applied."""
        return self.get_effective_stat("armor_class", self.armor_class)
    
    def get_effective_strength(self) -> int:
        """Get strength with all effect modifiers applied."""
        return self.get_effective_stat("strength", self.strength)
    
    def get_effective_dexterity(self) -> int:
        """Get dexterity with all effect modifiers applied."""
        return self.get_effective_stat("dexterity", self.dexterity)
    
    def get_effective_intelligence(self) -> int:
        """Get intelligence with all effect modifiers applied."""
        return self.get_effective_stat("intelligence", self.intelligence)
    
    def get_effective_vitality(self) -> int:
        """Get vitality with all effect modifiers applied."""
        return self.get_effective_stat("vitality", self.vitality)
    
    def get_attack_damage_range(self, item_templates: Dict[str, 'ItemTemplate'] | None = None) -> tuple[int, int]:
        """
        Get effective attack damage range.
        Checks equipped weapon first, falls back to base (unarmed) stats.
        
        Args:
            item_templates: Dict of item templates to look up equipped weapon stats.
                           If None, uses base stats only.
        """
        # Check for equipped weapon
        if item_templates and "weapon" in self.equipped_items:
            weapon_item_id = self.equipped_items["weapon"]
            # We need to look up the item to get its template_id
            # For now, equipped_items stores template_id directly for simplicity
            # TODO: If we want instance-specific weapon stats, we'd need to look up the WorldItem
            weapon_template = item_templates.get(weapon_item_id)
            if weapon_template and weapon_template.is_weapon():
                return (weapon_template.damage_min, weapon_template.damage_max)
        
        return (self.base_attack_damage_min, self.base_attack_damage_max)
    
    def get_attack_speed(self, item_templates: Dict[str, 'ItemTemplate'] | None = None) -> float:
        """
        Get effective attack speed in seconds.
        Checks equipped weapon first, falls back to base stats.
        
        Args:
            item_templates: Dict of item templates to look up equipped weapon stats.
        """
        # Check for equipped weapon
        if item_templates and "weapon" in self.equipped_items:
            weapon_item_id = self.equipped_items["weapon"]
            weapon_template = item_templates.get(weapon_item_id)
            if weapon_template and weapon_template.is_weapon():
                return weapon_template.attack_speed
        
        return self.base_attack_speed
    
    def get_weapon_stats(self, item_templates: Dict[str, 'ItemTemplate'] | None = None) -> WeaponStats:
        """
        Get combat stats for currently equipped weapon (or natural attacks).
        
        Args:
            item_templates: Dict of item templates to look up equipped weapon stats.
                           If None, uses base (unarmed) stats.
        
        Returns:
            WeaponStats for the equipped weapon, or unarmed defaults.
        """
        # Check for equipped weapon
        if item_templates and "weapon" in self.equipped_items:
            weapon_item_id = self.equipped_items["weapon"]
            weapon_template = item_templates.get(weapon_item_id)
            if weapon_template and weapon_template.is_weapon():
                return weapon_template.get_weapon_stats()
        
        # Fall back to base (unarmed) stats
        return WeaponStats(
            damage_min=self.base_attack_damage_min,
            damage_max=self.base_attack_damage_max,
            swing_speed=self.base_attack_speed,
        )
    
    def start_attack(self, target_id: EntityId, item_templates: Dict[str, 'ItemTemplate'] | None = None) -> None:
        """Begin an attack against a target."""
        weapon = self.get_weapon_stats(item_templates)
        self.combat.target_id = target_id
        self.combat.current_weapon = weapon
        self.combat.start_phase(CombatPhase.WINDUP, weapon.windup_time)
    
    def is_in_combat(self) -> bool:
        """Check if entity is currently in combat."""
        return self.combat.is_in_combat()
    
    def can_attack(self) -> bool:
        """Check if entity can initiate an attack."""
        return self.is_alive() and self.combat.phase in (
            CombatPhase.IDLE, CombatPhase.RECOVERY
        )
    
    def interrupt_attack(self) -> bool:
        """
        Attempt to interrupt current attack.
        Returns True if interrupted, False if attack was committed.
        """
        if self.combat.can_be_interrupted():
            self.combat.clear_combat()
            return True
        return False
    
    def check_level_up(self) -> list[dict]:
        """
        Check if entity has enough XP to level up.
        Handles multiple level-ups if XP is sufficient.
        
        Returns:
            List of level-up info dicts: [{"old_level": 1, "new_level": 2, "stat_gains": {...}}]
        """
        level_ups = []
        
        while True:
            next_threshold = get_xp_for_next_level(self.level)
            if next_threshold is None or self.experience < next_threshold:
                break
            
            old_level = self.level
            self.level += 1
            
            # Apply stat gains
            stat_gains = {}
            for stat, gain in LEVEL_UP_STAT_GAINS.items():
                if hasattr(self, stat):
                    old_val = getattr(self, stat)
                    setattr(self, stat, old_val + gain)
                    stat_gains[stat] = gain
            
            # Heal to new max health/energy
            self.current_health = self.max_health
            self.current_energy = self.max_energy
            
            level_ups.append({
                "old_level": old_level,
                "new_level": self.level,
                "stat_gains": stat_gains,
            })
        
        return level_ups
    
    # Targetable protocol implementation
    def get_description(self) -> str:
        """
        Return a description of this entity.
        Override in subclasses for more specific descriptions.
        """
        health_status = "healthy" if self.current_health > self.max_health * 0.7 else (
            "wounded" if self.current_health > self.max_health * 0.3 else "badly injured"
        )
        return f"{self.name} - Level {self.level} {self.character_class} ({health_status})"
    
    def get_targetable_type(self) -> TargetableType:
        """Return the targetable type based on entity type."""
        if self.entity_type == EntityType.PLAYER:
            return TargetableType.PLAYER
        return TargetableType.NPC
    
    def matches_keyword(self, keyword: str, match_mode: str = "contains") -> bool:
        """
        Check if this entity matches a keyword for targeting.
        Matches against name and keywords list (case-insensitive).
        
        Args:
            keyword: The search term to match against
            match_mode: "exact" for exact match, "startswith" for prefix match, 
                       "contains" for substring match (default)
        
        Returns:
            True if the entity matches the keyword
        """
        keyword_lower = keyword.lower()
        name_lower = self.name.lower()
        
        if match_mode == "exact":
            if keyword_lower == name_lower:
                return True
            return any(keyword_lower == kw.lower() for kw in self.keywords)
        elif match_mode == "startswith":
            if name_lower.startswith(keyword_lower):
                return True
            return any(kw.lower().startswith(keyword_lower) for kw in self.keywords)
        else:  # contains (default)
            if keyword_lower in name_lower:
                return True
            return any(keyword_lower in kw.lower() for kw in self.keywords)


@dataclass
class ItemTemplate:
    """Runtime representation of an item template (read-only blueprint)."""
    id: ItemTemplateId
    name: str
    description: str
    item_type: str
    item_subtype: str | None
    equipment_slot: str | None
    stat_modifiers: Dict[str, int]
    weight: float
    max_stack_size: int
    has_durability: bool
    max_durability: int | None
    is_container: bool
    container_capacity: int | None
    container_type: str | None
    is_consumable: bool
    consume_effect: dict | None
    flavor_text: str | None
    rarity: str
    value: int
    flags: dict
    keywords: list  # Alternative names for searching
    
    # Weapon combat stats (only used when item_type="weapon")
    damage_min: int = 0
    damage_max: int = 0
    attack_speed: float = 2.0  # seconds per swing
    damage_type: str = "physical"  # physical, magic, fire, etc.
    
    def is_weapon(self) -> bool:
        """Check if this item is a weapon."""
        return self.item_type == "weapon"
    
    def get_weapon_stats(self) -> 'WeaponStats':
        """Get WeaponStats from this template (for weapons only)."""
        return WeaponStats(
            damage_min=self.damage_min,
            damage_max=self.damage_max,
            swing_speed=self.attack_speed,
            damage_type=self.damage_type,
        )


@dataclass
class WorldItem:
    """
    Runtime representation of a specific item instance.
    
    Implements the Targetable protocol for unified command targeting.
    Note: name and keywords are cached from the template for Targetable compatibility.
    """
    id: ItemId
    template_id: ItemTemplateId
    
    # Cached from template for Targetable protocol
    name: str = ""  # Cached from template
    keywords: list[str] = field(default_factory=list)  # Cached from template
    
    # Location (exactly one should be set)
    room_id: RoomId | None = None
    player_id: PlayerId | None = None
    container_id: ItemId | None = None
    
    # Instance state
    quantity: int = 1
    current_durability: int | None = None
    equipped_slot: str | None = None
    instance_data: dict = field(default_factory=dict)
    
    # Cached description from template
    _description: str = ""
    
    def is_equipped(self) -> bool:
        """Check if item is currently equipped."""
        return self.equipped_slot is not None
    
    def is_stackable(self, template: ItemTemplate) -> bool:
        """Check if this item can stack with others."""
        return template.max_stack_size > 1
    
    def can_stack_with(self, other: 'WorldItem', template: ItemTemplate) -> bool:
        """Check if this item can stack with another item."""
        return (
            self.template_id == other.template_id
            and self.is_stackable(template)
            and not self.is_equipped()
            and not other.is_equipped()
            and self.current_durability == other.current_durability
        )
    
    # Targetable protocol implementation
    def get_description(self) -> str:
        """Return the description of this item."""
        if self.quantity > 1:
            return f"{self._description} (x{self.quantity})"
        return self._description
    
    def get_targetable_type(self) -> TargetableType:
        """Return ITEM as the targetable type."""
        return TargetableType.ITEM
    
    def matches_keyword(self, keyword: str, match_mode: str = "contains") -> bool:
        """
        Check if this item matches a keyword for targeting.
        Matches against name and keywords list (case-insensitive).
        
        Args:
            keyword: The search term to match against
            match_mode: "exact" for exact match, "startswith" for prefix match, 
                       "contains" for substring match (default)
        
        Returns:
            True if the item matches the keyword
        """
        keyword_lower = keyword.lower()
        name_lower = self.name.lower()
        
        if match_mode == "exact":
            if keyword_lower == name_lower:
                return True
            return any(keyword_lower == kw.lower() for kw in self.keywords)
        elif match_mode == "startswith":
            if name_lower.startswith(keyword_lower):
                return True
            return any(kw.lower().startswith(keyword_lower) for kw in self.keywords)
        else:  # contains (default)
            if keyword_lower in name_lower:
                return True
            return any(keyword_lower in kw.lower() for kw in self.keywords)


@dataclass
class PlayerInventory:
    """Runtime representation of player inventory metadata."""
    player_id: PlayerId
    max_weight: float = 100.0
    max_slots: int = 20
    current_weight: float = 0.0
    current_slots: int = 0


@dataclass
class NpcTemplate:
    """Runtime representation of an NPC template (read-only blueprint)."""
    id: NpcTemplateId
    name: str
    description: str
    npc_type: str  # "hostile", "neutral", "friendly", "merchant"
    
    # Stats (these initialize the NPC instance's WorldEntity stats)
    level: int
    max_health: int
    armor_class: int
    strength: int
    dexterity: int
    intelligence: int
    
    # Combat properties
    attack_damage_min: int
    attack_damage_max: int
    attack_speed: float
    experience_reward: int
    
    # AI behavior - list of behavior tags that get resolved at load time
    behaviors: list  # ["wanders_sometimes", "aggressive", "cowardly", ...]
    
    # Drop table (items that may drop when killed - NOT inventory)
    # Format: [{"template_id": "...", "chance": 0.5, "quantity": [1, 3]}]
    drop_table: list
    
    # Flavor
    idle_messages: list  # Random messages NPC says when idle
    keywords: list  # For targeting: ["goblin", "warrior"]
    
    # Resolved behavior config (populated at load time from behavior tags)
    resolved_behavior: dict = field(default_factory=dict)


@dataclass
class WorldNpc(WorldEntity):
    """
    Runtime representation of a specific NPC instance in the world.
    
    Inherits from WorldEntity:
    - id, entity_type, name, room_id
    - level, max_health, current_health, armor_class
    - strength, dexterity, intelligence, vitality
    - max_energy, current_energy
    - character_class, experience
    - on_move_effect
    - inventory_items, equipped_items (NPCs can carry/equip items!)
    - base_attack_damage_min/max, base_attack_speed
    - active_effects
    """
    # NPC-specific: template reference
    template_id: NpcTemplateId = ""
    spawn_room_id: RoomId = ""
    
    # Respawn tracking
    respawn_time: int = 300  # seconds
    last_killed_at: float | None = None
    
    # Combat state
    target_id: EntityId | None = None  # Who the NPC is attacking
    last_attack_time: float = 0.0
    
    # Experience reward given to killer (different from entity's own experience)
    experience_reward: int = 10
    
    # Instance-specific data (name overrides, custom behavior, etc.)
    instance_data: dict = field(default_factory=dict)
    
    # AI state (legacy - kept for compatibility)
    last_idle_message_time: float = 0.0
    wander_cooldown: float = 0.0
    
    # Per-NPC behavior timer tracking
    idle_event_id: str | None = None
    wander_event_id: str | None = None
    
    def __post_init__(self):
        """Ensure entity_type is set correctly."""
        object.__setattr__(self, 'entity_type', EntityType.NPC)


@dataclass
class WorldPlayer(WorldEntity):
    """
    Runtime representation of a player in the world.
    
    Inherits from WorldEntity:
    - id, entity_type, name, room_id
    - level, max_health, current_health, armor_class
    - strength, dexterity, intelligence, vitality
    - max_energy, current_energy
    - character_class, experience
    - on_move_effect
    - inventory_items, equipped_items
    - base_attack_damage_min/max, base_attack_speed
    - active_effects
    """
    # Player-specific inventory capacity tracking
    inventory_meta: PlayerInventory | None = None
    
    # Connection state - whether player is actively connected
    is_connected: bool = False
    
    def __post_init__(self):
        """Ensure entity_type is set correctly."""
        object.__setattr__(self, 'entity_type', EntityType.PLAYER)


@dataclass
class WorldRoom:
    """Runtime representation of a room in the world."""
    id: RoomId
    name: str
    description: str
    room_type: str = "ethereal"
    exits: Dict[Direction, RoomId] = field(default_factory=dict)
    
    # Unified entity tracking (players + NPCs)
    entities: Set[EntityId] = field(default_factory=set)
    
    # Area membership
    area_id: AreaId | None = None  # Which area this room belongs to
    # Movement effects - flavor text triggered when entering/leaving
    on_enter_effect: str | None = None  # e.g., "Mist swirls as you enter"
    on_exit_effect: str | None = None   # e.g., "Clouds part around you as you leave"
    # Time dilation - multiplier for time passage in this room (1.0 = normal)
    time_scale: float = 1.0  # e.g., 2.0 = double speed, 0.5 = half speed, 0.0 = frozen
    # Items in this room
    items: Set[ItemId] = field(default_factory=set)


@dataclass
class World:
    """
    In-memory world state.

    This is the authoritative runtime graph used by WorldEngine.
    It is built from the database at startup and updated by game logic.
    """
    rooms: Dict[RoomId, WorldRoom]
    players: Dict[PlayerId, WorldPlayer]
    areas: Dict[AreaId, WorldArea] = field(default_factory=dict)  # Geographic areas
    world_time: WorldTime = field(default_factory=WorldTime)  # Global time tracker
    
    # Item system
    item_templates: Dict[ItemTemplateId, ItemTemplate] = field(default_factory=dict)
    items: Dict[ItemId, WorldItem] = field(default_factory=dict)
    player_inventories: Dict[PlayerId, PlayerInventory] = field(default_factory=dict)
    
    # NPC system
    npc_templates: Dict[NpcTemplateId, NpcTemplate] = field(default_factory=dict)
    npcs: Dict[NpcId, WorldNpc] = field(default_factory=dict)
    
    def get_entity(self, entity_id: EntityId) -> WorldEntity | None:
        """
        Get any entity (player or NPC) by ID.
        
        Returns:
            The entity, or None if not found.
        """
        if entity_id in self.players:
            return self.players[entity_id]
        if entity_id in self.npcs:
            return self.npcs[entity_id]
        return None
    
    def get_entities_in_room(self, room_id: RoomId) -> list[WorldEntity]:
        """
        Get all entities (players and NPCs) in a room.
        
        Returns:
            List of entities in the room.
        """
        room = self.rooms.get(room_id)
        if not room:
            return []
        
        entities = []
        for entity_id in room.entities:
            entity = self.get_entity(entity_id)
            if entity:
                entities.append(entity)
        return entities
    
    def get_entity_type(self, entity_id: EntityId) -> EntityType | None:
        """
        Determine the type of an entity by ID.
        
        Returns:
            EntityType.PLAYER, EntityType.NPC, or None if not found.
        """
        if entity_id in self.players:
            return EntityType.PLAYER
        if entity_id in self.npcs:
            return EntityType.NPC
        return None
