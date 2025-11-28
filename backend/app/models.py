# backend/app/models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, ForeignKey, JSON


class Base(DeclarativeBase):
    pass


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
    on_exit_effect: Mapped[str | None] = mapped_column(String, nullable=True)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    current_room_id: Mapped[str] = mapped_column(String, ForeignKey("rooms.id"))
    data: Mapped[dict] = mapped_column(JSON, default=dict)  # stats, flags, movement effects, etc.