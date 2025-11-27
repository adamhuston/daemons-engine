from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# SQLite database URL
DATABASE_URL = "sqlite+aiosqlite:///./dungeon.db"  # game.db will live in backend/

# Create SQLAlchemy engine

engine = create_async_engine(
    DATABASE_URL,
    echo=False,      # True if you want to see SQL
    future=True,
)


AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
)

async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session