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