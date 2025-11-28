# backend/app/models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, ForeignKey, JSON, Integer, Float, Text, MetaData


# Naming convention for constraints (required for batch migrations)
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    room_type: Mapped[str] = mapped_column(String, nullable=False, server_default="ethereal")
    
    # Link to area (nullable - rooms can exist without areas)
    area_id: Mapped[str | None] = mapped_column(String, ForeignKey("areas.id"), nullable=True)

    north_id: Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)
    south_id: Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)
    east_id:  Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)
    west_id:  Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)
    up_id:    Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)
    down_id:  Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)
    
    # Movement effects
    on_enter_effect: Mapped[str | None] = mapped_column(String, nullable=True)
    on_exit_effect: Mapped[str | None] = mapped_column(String, nullable=True)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    current_room_id: Mapped[str] = mapped_column(String, ForeignKey("rooms.id"))
    
    # Character class/archetype
    character_class: Mapped[str] = mapped_column(String, nullable=False, server_default="adventurer")
    level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    experience: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    
    # Base stats (primary attributes)
    strength: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    dexterity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    intelligence: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    vitality: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    
    # Derived stats (combat/survival)
    max_health: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    current_health: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    armor_class: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    max_energy: Mapped[int] = mapped_column(Integer, nullable=False, server_default="50")
    current_energy: Mapped[int] = mapped_column(Integer, nullable=False, server_default="50")

    # Misc data (flags, temporary effects, etc.)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


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
    time_scale: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")
    starting_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    starting_hour: Mapped[int] = mapped_column(Integer, nullable=False, server_default="6")
    starting_minute: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    
    # Environmental properties
    biome: Mapped[str] = mapped_column(String, nullable=False, server_default="ethereal")
    climate: Mapped[str] = mapped_column(String, nullable=False, server_default="mild")
    ambient_lighting: Mapped[str] = mapped_column(String, nullable=False, server_default="normal")
    weather_profile: Mapped[str] = mapped_column(String, nullable=False, server_default="clear")
    
    # Gameplay properties
    danger_level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    magic_intensity: Mapped[str] = mapped_column(String, nullable=False, server_default="low")
    default_respawn_time: Mapped[int] = mapped_column(Integer, nullable=False, server_default="300")  # seconds
    
    # Atmospheric details
    ambient_sound: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Time phase flavor text (stored as JSON)
    # Format: {"dawn": "text", "morning": "text", ...}
    time_phases: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Entry points (stored as JSON array of room IDs)
    entry_points: Mapped[list] = mapped_column(JSON, default=list)


class ItemTemplate(Base):
    """Static item definition - the blueprint for all instances of this item type."""
    __tablename__ = "item_templates"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g., "item_rusty_sword"
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Item categorization
    item_type: Mapped[str] = mapped_column(String, nullable=False)  # "weapon", "armor", "consumable", "container", "quest", "junk"
    item_subtype: Mapped[str | None] = mapped_column(String, nullable=True)  # "sword", "potion", "helmet", etc.
    
    # Equipment properties
    equipment_slot: Mapped[str | None] = mapped_column(String, nullable=True)  # "weapon", "head", "chest", "hands", "legs", "feet", "neck", "ring", "back"
    
    # Stat modifiers (JSON: {"strength": 2, "armor_class": 5})
    stat_modifiers: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Physical properties
    weight: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")
    max_stack_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")  # 1 = unique, >1 = stackable
    
    # Durability system
    has_durability: Mapped[bool] = mapped_column(Integer, nullable=False, server_default="0")  # SQLite uses 0/1 for bool
    max_durability: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null if has_durability=False
    
    # Container properties
    is_container: Mapped[bool] = mapped_column(Integer, nullable=False, server_default="0")
    container_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)  # max items or weight
    container_type: Mapped[str | None] = mapped_column(String, nullable=True)  # "weight_based", "slot_based"
    
    # Consumable properties
    is_consumable: Mapped[bool] = mapped_column(Integer, nullable=False, server_default="0")
    consume_effect: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Effect applied on consumption
    
    # Weapon combat stats (only used when item_type="weapon")
    damage_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    damage_max: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    attack_speed: Mapped[float] = mapped_column(Float, nullable=False, server_default="2.0")  # seconds per swing
    damage_type: Mapped[str] = mapped_column(String, nullable=False, server_default="physical")  # physical, magic, fire, etc.
    
    # Flavor and metadata
    flavor_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    rarity: Mapped[str] = mapped_column(String, nullable=False, server_default="common")  # "common", "uncommon", "rare", "epic", "legendary"
    value: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")  # Gold value
    
    # Special flags (JSON: {"quest_item": true, "no_drop": true})
    flags: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Keywords for searching (JSON array: ["backpack", "pack", "bag"])
    keywords: Mapped[list] = mapped_column(JSON, default=list)


class ItemInstance(Base):
    """Dynamic item instance - a specific occurrence of an item in the world."""
    __tablename__ = "item_instances"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID
    template_id: Mapped[str] = mapped_column(String, ForeignKey("item_templates.id"), nullable=False)
    
    # Location (one of these must be set)
    room_id: Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)  # On ground in room
    player_id: Mapped[str | None] = mapped_column(String, ForeignKey("players.id"), nullable=True)  # In player inventory
    container_id: Mapped[str | None] = mapped_column(String, ForeignKey("item_instances.id"), nullable=True)  # Inside another item
    
    # Instance state
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")  # Stack size
    current_durability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Equipped state (null = not equipped, slot name if equipped)
    equipped_slot: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Custom instance data (JSON: unique flags, enchantments, etc.)
    instance_data: Mapped[dict] = mapped_column(JSON, default=dict)


class PlayerInventory(Base):
    """Player inventory metadata - capacity, organization, etc."""
    __tablename__ = "player_inventories"
    
    player_id: Mapped[str] = mapped_column(String, ForeignKey("players.id"), primary_key=True)
    
    # Capacity limits
    max_weight: Mapped[float] = mapped_column(Float, nullable=False, server_default="100.0")
    max_slots: Mapped[int] = mapped_column(Integer, nullable=False, server_default="20")
    
    # Current usage (denormalized for quick checks)
    current_weight: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    current_slots: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class NpcTemplate(Base):
    """Static NPC definition - blueprint for all instances of this NPC type."""
    __tablename__ = "npc_templates"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g., "npc_goblin_warrior"
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # NPC categorization
    npc_type: Mapped[str] = mapped_column(String, nullable=False, server_default="hostile")  # "hostile", "neutral", "friendly", "merchant"
    
    # Base stats (combat-ready for Phase 4.5)
    level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    max_health: Mapped[int] = mapped_column(Integer, nullable=False, server_default="50")
    armor_class: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    
    # Primary attributes
    strength: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    dexterity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    intelligence: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    
    # Combat properties (for Phase 4.5)
    attack_damage_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    attack_damage_max: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    attack_speed: Mapped[float] = mapped_column(Float, nullable=False, server_default="3.0")  # seconds between attacks
    experience_reward: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    
    # AI behavior flags (JSON: {"wanders": true, "flees_at_health_percent": 20, "aggro_on_sight": true})
    behavior: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Loot table (JSON array for Phase 4.5: [{"template_id": "...", "chance": 0.5, "quantity": [1, 3]}])
    loot_table: Mapped[list] = mapped_column(JSON, default=list)
    
    # Flavor and metadata
    idle_messages: Mapped[list] = mapped_column(JSON, default=list)  # Random messages NPC says when idle
    keywords: Mapped[list] = mapped_column(JSON, default=list)  # For targeting: ["goblin", "warrior"]


class NpcInstance(Base):
    """Dynamic NPC instance - a specific NPC in the world."""
    __tablename__ = "npc_instances"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID
    template_id: Mapped[str] = mapped_column(String, ForeignKey("npc_templates.id"), nullable=False)
    
    # Location
    room_id: Mapped[str] = mapped_column(String, ForeignKey("rooms.id"), nullable=False)
    spawn_room_id: Mapped[str] = mapped_column(String, ForeignKey("rooms.id"), nullable=False)  # Where to respawn
    
    # Instance state
    current_health: Mapped[int] = mapped_column(Integer, nullable=False)
    is_alive: Mapped[bool] = mapped_column(Integer, nullable=False, server_default="1")  # SQLite uses 0/1
    
    # Respawn tracking
    # If set, overrides area default. Use -1 to disable respawn entirely.
    respawn_time: Mapped[int | None] = mapped_column(Integer, nullable=True)  # seconds, NULL = use area default
    last_killed_at: Mapped[float | None] = mapped_column(Float, nullable=True)  # Unix timestamp
    
    # Instance-specific overrides (JSON: custom name, modified stats, etc.)
    instance_data: Mapped[dict] = mapped_column(JSON, default=dict)