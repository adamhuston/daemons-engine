# backend/app/engine/world.py
from dataclasses import dataclass, field
from typing import Dict, Set, Callable, Awaitable, Any
import time


# Simple type aliases for clarity
RoomId = str
PlayerId = str
AreaId = str
Direction = str  # "north", "south", "east", "west", "up", "down"


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


def get_room_emoji(room_type: str) -> str:
    """Get the emoji for a room type, or a default if unknown."""
    return ROOM_TYPE_EMOJIS.get(room_type, "❓")


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
        """Format full time with day and phase."""
        current_day, current_hour, current_minute = self.get_current_time(time_scale)
        phase = self.get_time_of_day(time_scale)
        emoji = self.get_time_emoji(time_scale)
        return f"{emoji} Day {current_day}, {current_hour:02d}:{current_minute:02d} ({phase})"


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
    """
    Represents a geographical area containing multiple rooms.
    
    Areas provide environmental context, atmosphere, and can have
    different time progression rates and phase descriptions.
    Each area tracks its own independent time.
    """
    id: AreaId
    name: str
    biome: str  # "forest", "desert", "urban", "underground", "ethereal", etc.
    
    # Time characteristics - each area has its own clock!
    area_time: WorldTime = field(default_factory=WorldTime)  # Independent time for this area
    time_scale: float = 1.0  # Multiplier for time passage (1.0 = normal, 2.0 = double speed, 0.5 = half speed)
    time_phases: Dict[str, str] = field(default_factory=lambda: DEFAULT_TIME_PHASES.copy())
    # Custom phase descriptions override defaults for unique atmosphere
    
    # Spatial organization
    entry_points: Set[RoomId] = field(default_factory=set)  # Rooms that serve as entrances
    room_ids: Set[RoomId] = field(default_factory=set)  # All rooms in this area
    neighbor_areas: Set[AreaId] = field(default_factory=set)  # Adjacent areas
    
    # Environmental characteristics
    climate: str = "temperate"  # "tropical", "arctic", "arid", "temperate", etc.
    ambient_lighting: str = "natural"  # "natural", "dim", "bright", "darkness", "magical"
    weather_profile: str = "clear"  # "clear", "rainy", "stormy", "foggy", "snowy", etc.
    
    # Optional flavor
    description: str = ""  # Area overview/lore
    ambient_sound: str = ""  # e.g., "The rustling of leaves fills the air"


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


@dataclass
class WorldPlayer:
    """Runtime representation of a player in the world."""
    id: PlayerId
    name: str
    room_id: RoomId
    inventory: list[str] = field(default_factory=list)
    # Movement effects - flavor text triggered by player movement
    on_move_effect: str | None = None  # e.g., "You glide gracefully"
    # Connection state - whether player is actively connected
    is_connected: bool = False
    
    # Character progression
    character_class: str = "adventurer"
    level: int = 1
    experience: int = 0
    
    # Base stats (primary attributes)
    strength: int = 10
    dexterity: int = 10
    intelligence: int = 10
    vitality: int = 10
    
    # Derived stats (combat/survival)
    max_health: int = 100
    current_health: int = 100
    armor_class: int = 10
    max_energy: int = 50
    current_energy: int = 50
    
    # Active effects (Phase 2b)
    active_effects: Dict[str, Effect] = field(default_factory=dict)
    
    def apply_effect(self, effect: Effect) -> None:
        """
        Apply an effect to this player.
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


@dataclass
class WorldRoom:
    """Runtime representation of a room in the world."""
    id: RoomId
    name: str
    description: str
    room_type: str = "ethereal"
    exits: Dict[Direction, RoomId] = field(default_factory=dict)
    players: Set[PlayerId] = field(default_factory=set)
    # Area membership
    area_id: AreaId | None = None  # Which area this room belongs to
    # Movement effects - flavor text triggered when entering/leaving
    on_enter_effect: str | None = None  # e.g., "Mist swirls as you enter"
    on_exit_effect: str | None = None   # e.g., "Clouds part around you as you leave"
    # Time dilation - multiplier for time passage in this room (1.0 = normal)
    time_scale: float = 1.0  # e.g., 2.0 = double speed, 0.5 = half speed, 0.0 = frozen


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
