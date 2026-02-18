# backend/app/models.py
from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, MetaData, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Naming convention for constraints (required for batch migrations)
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


class RoomType(Base):
    """
    Room types with their associated emoji icons.

    This table is dynamically populated from rooms in the database,
    allowing new room types to be added without code changes.
    """

    __tablename__ = "room_types"

    name: Mapped[str] = mapped_column(
        String, primary_key=True
    )  # e.g., "forest", "urban"
    emoji: Mapped[str] = mapped_column(
        String, nullable=False, server_default="❓"
    )  # e.g., "🌲"
    description: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # Optional description


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    room_type: Mapped[str] = mapped_column(
        String, nullable=False, server_default="ethereal"
    )
    # Optional per-room emoji override (if None, uses room_type's default emoji)
    room_type_emoji: Mapped[str | None] = mapped_column(String, nullable=True)

    # Link to area (nullable - rooms can exist without areas)
    area_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("areas.id"), nullable=True
    )

    north_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("rooms.id"), nullable=True
    )
    south_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("rooms.id"), nullable=True
    )
    east_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("rooms.id"), nullable=True
    )
    west_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("rooms.id"), nullable=True
    )
    up_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("rooms.id"), nullable=True
    )
    down_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("rooms.id"), nullable=True
    )

    # Movement effects
    on_enter_effect: Mapped[str | None] = mapped_column(String, nullable=True)
    on_exit_effect: Mapped[str | None] = mapped_column(String, nullable=True)

    # Phase 11: Lighting system
    # Per-room lighting override (overrides area ambient_lighting)
    # Example: deep cave room in forest area = "pitch_black"
    lighting_override: Mapped[str | None] = mapped_column(String, nullable=True)

    # Phase 17.1: Temperature system
    # Per-room temperature override in Fahrenheit (overrides area calculation)
    # Example: forge room = 110, ice cave = 20
    temperature_override: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Phase 17.4: Flora system
    # Whether flora cannot grow in this room (default False = flora can grow)
    # Example: pitch-black caves, magically dead zones
    no_flora: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")

    # YAML content management
    # True = managed by YAML files, False = created/modified via API
    yaml_managed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="1"
    )


class Player(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    current_room_id: Mapped[str] = mapped_column(String, ForeignKey("rooms.id"))

    # Account linkage (Phase 7)
    account_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Character class/archetype
    character_class: Mapped[str] = mapped_column(
        String, nullable=False, server_default="adventurer"
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    experience: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Base stats (primary attributes)
    strength: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    dexterity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    intelligence: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="10"
    )
    vitality: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")

    # Derived stats (combat/survival)
    max_health: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="100"
    )
    current_health: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="100"
    )
    armor_class: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="10"
    )
    max_energy: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="50"
    )
    current_energy: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="50"
    )

    # Misc data (flags, temporary effects, etc.)
    data: Mapped[dict] = mapped_column(JSON, default=dict)

    # Phase 10.3: Faction system - player faction membership
    faction_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # Faction membership for player (from factions/*.yaml)

    # Quest system (Phase X)
    player_flags: Mapped[dict] = mapped_column(
        JSON, default=dict
    )  # Persistent player flags for quests and social (Phase 10.1: group_id, followers, following, ignored_players, last_tell_from)
    quest_progress: Mapped[dict] = mapped_column(
        JSON, default=dict
    )  # quest_id -> QuestProgress dict
    completed_quests: Mapped[list] = mapped_column(
        JSON, default=list
    )  # List of completed quest IDs


class Area(Base):
    """
    Defines a cohesive region of the world with shared properties.
    Areas have independent time systems and environmental characteristics.
    """

    __tablename__ = "areas"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Time system
    time_scale: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0"
    )
    starting_day: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    starting_hour: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="6"
    )
    starting_minute: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Environmental properties
    biome: Mapped[str] = mapped_column(
        String, nullable=False, server_default="ethereal"
    )
    climate: Mapped[str] = mapped_column(String, nullable=False, server_default="mild")
    ambient_lighting: Mapped[str] = mapped_column(
        String, nullable=False, server_default="normal"
    )
    weather_profile: Mapped[str] = mapped_column(
        String, nullable=False, server_default="clear"
    )

    # Phase 17.1: Temperature system
    # Base temperature in Fahrenheit (typical range: -50 to 150)
    base_temperature: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="70"
    )
    # Daily temperature variation (+/- degrees based on time of day)
    temperature_variation: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="20"
    )

    # Phase 17.2: Weather system
    # Weather patterns - JSON dict with weather type probabilities
    # Format: {"clear": 0.4, "rain": 0.3, "storm": 0.1, "cloudy": 0.2}
    # If null, uses climate-based defaults
    weather_patterns: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Weather immunity - if true, area has no weather (underground, indoor, etc.)
    weather_immunity: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0"
    )

    # Phase 17.3: Season and Biome Coherence
    # Current season for this area
    current_season: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="summer"
    )
    # Day within current season (1 to days_per_season)
    season_day: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    # How many in-game days per season
    days_per_season: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="30"
    )
    # If true, season never changes (frozen in eternal winter, etc.)
    season_locked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0"
    )
    # Biome coherence data - JSON dict with extended biome configuration
    # Format: {"temperature_range": [40, 80], "seasonal_modifiers": {...}, ...}
    biome_data: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default="{}"
    )
    # Flora compatibility tags for Phase 17.4
    # Format: ["deciduous", "conifer", "grass", "flowering"]
    flora_tags: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    # Fauna compatibility tags for Phase 17.5
    # Format: ["woodland", "predator", "prey", "aquatic"]
    fauna_tags: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )

    # Gameplay properties
    danger_level: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    magic_intensity: Mapped[str] = mapped_column(
        String, nullable=False, server_default="low"
    )
    default_respawn_time: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="300"
    )  # seconds

    # Atmospheric details
    ambient_sound: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Time phase flavor text (stored as JSON)
    # Format: {"dawn": "text", "morning": "text", ...}
    time_phases: Mapped[dict] = mapped_column(JSON, default=dict)

    # Entry points (stored as JSON array of room IDs)
    entry_points: Mapped[list] = mapped_column(JSON, default=list)


class WeatherState(Base):
    """
    Tracks the current weather state for each area.
    
    Weather changes over time based on area's weather_patterns
    and climate. Each area has exactly one WeatherState record.
    """

    __tablename__ = "weather_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    area_id: Mapped[str] = mapped_column(
        String, ForeignKey("areas.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    
    # Current weather type: clear, cloudy, overcast, rain, storm, snow, fog, wind
    weather_type: Mapped[str] = mapped_column(String, nullable=False)
    
    # Weather intensity: light, moderate, heavy
    intensity: Mapped[str] = mapped_column(
        String, nullable=False, server_default="moderate"
    )
    
    # When this weather started (Unix timestamp)
    started_at: Mapped[float] = mapped_column(Float, nullable=False)
    
    # How long this weather will last (seconds)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # When weather will next change (Unix timestamp)
    next_change_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class ItemTemplate(Base):
    """Static item definition - the blueprint for all instances of this item type."""

    __tablename__ = "item_templates"

    id: Mapped[str] = mapped_column(
        String, primary_key=True
    )  # e.g., "item_rusty_sword"
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Item categorization
    item_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "weapon", "armor", "consumable", "container", "quest", "junk"
    item_subtype: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # "sword", "potion", "helmet", etc.

    # Equipment properties
    equipment_slot: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # "weapon", "head", "chest", "hands", "legs", "feet", "neck", "ring", "back"

    # Stat modifiers (JSON: {"strength": 2, "armor_class": 5})
    stat_modifiers: Mapped[dict] = mapped_column(JSON, default=dict)

    # Physical properties
    weight: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")
    max_stack_size: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )  # 1 = unique, >1 = stackable

    # Durability system
    has_durability: Mapped[bool] = mapped_column(
        Integer, nullable=False, server_default="0"
    )  # SQLite uses 0/1 for bool
    max_durability: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # null if has_durability=False

    # Container properties
    is_container: Mapped[bool] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    container_capacity: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # max items or weight
    container_type: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # "weight_based", "slot_based"

    # Consumable properties
    is_consumable: Mapped[bool] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    consume_effect: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Effect applied on consumption

    # Weapon combat stats (only used when item_type="weapon")
    damage_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    damage_max: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    attack_speed: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="2.0"
    )  # seconds per swing
    damage_type: Mapped[str] = mapped_column(
        String, nullable=False, server_default="physical"
    )  # physical, magic, fire, etc.

    # Phase 11: Light source properties (torches, lanterns, glowing items)
    provides_light: Mapped[bool] = mapped_column(
        Integer, nullable=False, server_default="0"
    )  # Whether item emits light
    light_intensity: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )  # Light contribution (0-50)
    light_duration: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Duration in seconds (None = permanent)

    # Phase 14+: Ability system support (magic items with spells)
    class_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # Character class for items with abilities
    default_abilities: Mapped[list] = mapped_column(
        JSON, default=list
    )  # Abilities item grants
    ability_loadout: Mapped[list] = mapped_column(
        JSON, default=list
    )  # Pre-equipped abilities

    # Phase 14+: Combat stats (destructible items like doors, barrels)
    max_health: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # HP for destructible items (None = indestructible)
    base_armor_class: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="10"
    )  # AC for destructible items
    resistances: Mapped[dict] = mapped_column(
        JSON, default=dict
    )  # Damage resistances {"fire": -50, "physical": 20}

    # Flavor and metadata
    flavor_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    rarity: Mapped[str] = mapped_column(
        String, nullable=False, server_default="common"
    )  # "common", "uncommon", "rare", "epic", "legendary"
    value: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )  # Gold value

    # Special flags (JSON: {"quest_item": true, "no_drop": true})
    flags: Mapped[dict] = mapped_column(JSON, default=dict)

    # Keywords for searching (JSON array: ["backpack", "pack", "bag"])
    keywords: Mapped[list] = mapped_column(JSON, default=list)


class ItemInstance(Base):
    """Dynamic item instance - a specific occurrence of an item in the world."""

    __tablename__ = "item_instances"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID
    template_id: Mapped[str] = mapped_column(
        String, ForeignKey("item_templates.id"), nullable=False
    )

    # Location (one of these must be set)
    room_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("rooms.id"), nullable=True
    )  # On ground in room
    player_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("players.id"), nullable=True
    )  # In player inventory
    container_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("item_instances.id"), nullable=True
    )  # Inside another item

    # Instance state
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )  # Stack size
    current_durability: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Equipped state (null = not equipped, slot name if equipped)
    equipped_slot: Mapped[str | None] = mapped_column(String, nullable=True)

    # Custom instance data (JSON: unique flags, enchantments, etc.)
    instance_data: Mapped[dict] = mapped_column(JSON, default=dict)


class PlayerInventory(Base):
    """Player inventory metadata - capacity, organization, etc."""

    __tablename__ = "player_inventories"

    player_id: Mapped[str] = mapped_column(
        String, ForeignKey("players.id"), primary_key=True
    )

    # Capacity limits
    max_weight: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="100.0"
    )
    max_slots: Mapped[int] = mapped_column(Integer, nullable=False, server_default="20")

    # Current usage (denormalized for quick checks)
    current_weight: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.0"
    )
    current_slots: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )


class NpcTemplate(Base):
    """Static NPC definition - blueprint for all instances of this NPC type."""

    __tablename__ = "npc_templates"

    id: Mapped[str] = mapped_column(
        String, primary_key=True
    )  # e.g., "npc_goblin_warrior"
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # NPC categorization
    npc_type: Mapped[str] = mapped_column(
        String, nullable=False, server_default="hostile"
    )  # "hostile", "neutral", "friendly", "merchant"

    # Base stats (combat-ready for Phase 4.5)
    level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    max_health: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="50"
    )
    armor_class: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="10"
    )

    # Primary attributes
    strength: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    dexterity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    intelligence: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="10"
    )

    # Combat properties (for Phase 4.5)
    attack_damage_min: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    attack_damage_max: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="5"
    )
    attack_speed: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="3.0"
    )  # seconds between attacks
    experience_reward: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="10"
    )

    # AI behavior flags (JSON: {"wanders": true, "flees_at_health_percent": 20, "aggro_on_sight": true})
    behavior: Mapped[dict] = mapped_column(JSON, default=dict)

    # Loot table (JSON array for Phase 4.5: [{"template_id": "...", "chance": 0.5, "quantity": [1, 3]}])
    loot_table: Mapped[list] = mapped_column(JSON, default=list)

    # Flavor and metadata
    idle_messages: Mapped[list] = mapped_column(
        JSON, default=list
    )  # Random messages NPC says when idle
    keywords: Mapped[list] = mapped_column(
        JSON, default=list
    )  # For targeting: ["goblin", "warrior"]

    # Phase 14: Character class and abilities
    class_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # "warrior", "mage", "rogue" - enables ability system
    default_abilities: Mapped[list] = mapped_column(
        JSON, default=list
    )  # Abilities NPC spawns with (list of ability_ids)
    ability_loadout: Mapped[list] = mapped_column(
        JSON, default=list
    )  # Pre-equipped abilities in slot order

    # Phase 17.5: Fauna properties
    is_fauna: Mapped[bool] = mapped_column(
        Integer, nullable=False, server_default="0"
    )  # SQLite uses 0/1
    fauna_data: Mapped[dict] = mapped_column(
        JSON, default=dict
    )  # Fauna-specific properties (biome_tags, diet, etc.)

    # Phase 10.3+: Faction affiliation
    faction_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # Faction membership for warfare


class NpcInstance(Base):
    """Dynamic NPC instance - a specific NPC in the world."""

    __tablename__ = "npc_instances"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID
    template_id: Mapped[str] = mapped_column(
        String, ForeignKey("npc_templates.id"), nullable=False
    )

    # Location
    room_id: Mapped[str] = mapped_column(String, ForeignKey("rooms.id"), nullable=False)
    spawn_room_id: Mapped[str] = mapped_column(
        String, ForeignKey("rooms.id"), nullable=False
    )  # Where to respawn

    # Instance state
    current_health: Mapped[int] = mapped_column(Integer, nullable=False)
    is_alive: Mapped[bool] = mapped_column(
        Integer, nullable=False, server_default="1"
    )  # SQLite uses 0/1

    # Respawn tracking
    # If set, overrides area default. Use -1 to disable respawn entirely.
    respawn_time: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # seconds, NULL = use area default
    last_killed_at: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Unix timestamp

    # Phase 2: Patrol System
    patrol_route: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )  # List of room IDs to patrol
    patrol_index: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )  # Current waypoint index
    patrol_mode: Mapped[str] = mapped_column(
        String, nullable=False, server_default="'loop'"
    )  # loop, bounce, once
    home_room_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # Spawn point for respawn/return

    # Instance-specific overrides (JSON: custom name, modified stats, etc.)
    instance_data: Mapped[dict] = mapped_column(JSON, default=dict)


# === Phase 6: Persistence Tables ===


class PlayerEffect(Base):
    """
    Active effects on a player that persist across disconnects.

    Effects continue ticking while offline (can expire), so we store
    the absolute expiration timestamp rather than remaining duration.
    """

    __tablename__ = "player_effects"

    player_id: Mapped[str] = mapped_column(
        String, ForeignKey("players.id"), primary_key=True
    )
    effect_id: Mapped[str] = mapped_column(String, primary_key=True)
    effect_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # buff, debuff, dot, hot
    effect_data: Mapped[dict] = mapped_column(
        JSON, nullable=True
    )  # Full effect serialization
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)  # Unix timestamp
    created_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class RoomState(Base):
    """
    Runtime room state that persists across server restarts.

    Stores flags, dynamic exits, and descriptions that change during gameplay.
    """

    __tablename__ = "room_state"

    room_id: Mapped[str] = mapped_column(
        String, ForeignKey("rooms.id"), primary_key=True
    )
    room_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    dynamic_exits: Mapped[dict] = mapped_column(JSON, default=dict)
    dynamic_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class TriggerState(Base):
    """
    Fire counts for permanent triggers.

    Only permanent triggers are saved here. Non-permanent triggers reset on restart.
    """

    __tablename__ = "trigger_state"

    trigger_id: Mapped[str] = mapped_column(String, primary_key=True)
    scope: Mapped[str] = mapped_column(
        String, primary_key=True
    )  # 'room', 'area', or 'global'
    scope_id: Mapped[str] = mapped_column(
        String, primary_key=True
    )  # room_id or area_id
    fire_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_fired_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class NpcState(Base):
    """
    Runtime state for persistent NPCs (companions, unique bosses, escort targets).

    Only NPCs with persist_state=True in their template are saved here.
    """

    __tablename__ = "npc_state"

    instance_id: Mapped[str] = mapped_column(String, primary_key=True)
    template_id: Mapped[str] = mapped_column(
        String, ForeignKey("npc_templates.id"), nullable=False
    )
    current_room_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("rooms.id"), nullable=True
    )
    current_hp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_alive: Mapped[bool] = mapped_column(Integer, nullable=False, server_default="1")
    owner_player_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("players.id"), nullable=True
    )  # For companions
    instance_data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[float | None] = mapped_column(Float, nullable=True)


# === Phase 7: Authentication & Security Tables ===


class UserAccount(Base):
    """
    User account for authentication.

    Accounts are separate from characters (Players) - one account can have
    multiple characters. The active_character_id tracks which character
    the user is currently playing.
    """

    __tablename__ = "user_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="player"
    )
    is_active: Mapped[bool] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Unix timestamp
    last_login: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Unix timestamp
    active_character_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # FK to players.id
    is_banned: Mapped[bool] = mapped_column(
        Integer, nullable=False, server_default="0"
    )  # Account ban status
    ban_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # Reason for ban
    banned_at: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Unix timestamp when banned
    banned_by: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # Admin who banned the account

    # Phase 16.2: Account lockout
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )  # Count of consecutive failed login attempts
    locked_until: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Unix timestamp when lockout expires (None = not locked)


class RefreshToken(Base):
    """
    Refresh tokens for session management.

    Stores hashed refresh tokens with expiration and rotation support.
    Tokens can be revoked individually or all tokens for an account.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String, ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)  # Unix timestamp
    created_at: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Unix timestamp
    revoked: Mapped[bool] = mapped_column(Integer, nullable=False, server_default="0")
    device_info: Mapped[str | None] = mapped_column(String(255), nullable=True)


class SecurityEvent(Base):
    """
    Audit log for security-relevant events.

    Tracks login attempts, password changes, permission changes, etc.
    Used for security monitoring and debugging authentication issues.
    """

    __tablename__ = "security_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True
    )  # IPv6 max length
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[float] = mapped_column(
        Float, nullable=False, index=True
    )  # Unix timestamp


class AdminAction(Base):
    """
    Audit log for administrative actions.

    Tracks all privileged actions taken by admins, game masters, and moderators:
    - Teleport commands
    - Item/NPC spawning
    - Stat modifications
    - Kicks and bans
    - Content reloads

    Used for accountability and debugging.
    """

    __tablename__ = "admin_actions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    admin_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True
    )
    admin_name: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # Cached for readability
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # teleport, spawn, kick, etc.
    target_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # player, npc, item, room
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    details: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Action-specific data
    success: Mapped[bool] = mapped_column(Integer, nullable=False, server_default="1")
    timestamp: Mapped[float] = mapped_column(
        Float, nullable=False, index=True
    )  # Unix timestamp


class ServerMetric(Base):
    """
    Historical server metrics for performance monitoring.

    Tracks periodic snapshots of server state:
    - Player counts
    - NPC counts
    - Command processing times
    - Tick durations

    Used for capacity planning and performance analysis.
    """

    __tablename__ = "server_metrics"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    timestamp: Mapped[float] = mapped_column(
        Float, nullable=False, index=True
    )  # Unix timestamp
    metric_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # players_online, tick_duration, etc.
    value: Mapped[float] = mapped_column(Float, nullable=False)


class Clan(Base):
    """
    Persistent player clan/guild system (Phase 10.2).

    Represents a long-term player organization with:
    - Leader and member hierarchy
    - Experience and leveling
    - Persistent storage across restarts
    """

    __tablename__ = "clans"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    leader_id: Mapped[str] = mapped_column(
        String, ForeignKey("players.id"), nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    experience: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    leader: Mapped["Player"] = relationship("Player", foreign_keys=[leader_id])
    members: Mapped[list["ClanMember"]] = relationship(
        "ClanMember", back_populates="clan", cascade="all, delete-orphan"
    )


class ClanMember(Base):
    """
    Tracks a player's membership in a clan with rank and contribution points.

    Rank hierarchy: leader > officer > member > initiate
    Contribution points track player's value to clan for leveling.
    """

    __tablename__ = "clan_members"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    clan_id: Mapped[str] = mapped_column(
        String, ForeignKey("clans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    player_id: Mapped[str] = mapped_column(
        String, ForeignKey("players.id"), nullable=False, index=True
    )
    rank: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )  # leader|officer|member|initiate
    joined_at: Mapped[float] = mapped_column(Float, nullable=False)
    contribution_points: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Relationships
    clan: Mapped["Clan"] = relationship("Clan", back_populates="members")
    player: Mapped["Player"] = relationship("Player")
    extra_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Additional context


class Faction(Base):
    """
    NPC-owned factions that players can join and gain reputation with (Phase 10.3).

    Represents organizations, guilds, religions, or governments in the world.
    Players can gain/lose standing based on actions and quests.
    NPC faction members will have modified behavior based on player standing.
    """

    __tablename__ = "factions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String, nullable=False, server_default="#FFFFFF")
    emblem: Mapped[str | None] = mapped_column(String, nullable=True)
    player_joinable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="1", index=True
    )
    max_members: Mapped[int | None] = mapped_column(Integer, nullable=True)
    require_level: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    created_at: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    npc_members: Mapped[list["FactionNPCMember"]] = relationship(
        "FactionNPCMember", back_populates="faction", cascade="all, delete-orphan"
    )


class FactionNPCMember(Base):
    """
    Links NPC templates to factions for quick O(1) faction lookups.

    Used to determine:
    - Which faction an NPC belongs to
    - Whether an NPC should attack a player based on faction standing
    - NPC dialogue/greeting variations based on player standing
    """

    __tablename__ = "faction_npc_members"

    faction_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("factions.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
        index=True,
    )
    npc_template_id: Mapped[str] = mapped_column(
        String, nullable=False, primary_key=True, index=True
    )

    # Relationships
    faction: Mapped["Faction"] = relationship("Faction", back_populates="npc_members")


# === Phase 17.4: Flora System ===


class FloraInstance(Base):
    """
    Dynamic flora instance - a specific plant or vegetation in the world.

    Flora templates are loaded from YAML, but instances track runtime state
    like harvest cooldowns, quantity, and depletion.
    """

    __tablename__ = "flora_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )

    # State tracking
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    last_harvested_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_harvested_by: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    harvest_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Respawn tracking
    is_depleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0"
    )
    depleted_at: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Spawn tracking
    spawned_at: Mapped[float] = mapped_column(Float, nullable=False)
    is_permanent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0"
    )

