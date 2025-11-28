# backend/app/models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, ForeignKey, JSON, Integer, MetaData


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

    north_id: Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)
    south_id: Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)
    east_id:  Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)
    west_id:  Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)
    up_id:    Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)
    down_id:  Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)
    
    # Movement effects
    on_enter_effect: Mapped[str | None] = mapped_column(String, nullable=True)
    on_exit_effect: Mapped[str | None] = mapped_column(String, ForeignKey("rooms.id"), nullable=True)


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