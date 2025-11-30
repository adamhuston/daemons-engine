from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.orm import declarative_base

# SQLite database URL
DATABASE_URL = "sqlite+aiosqlite:///./dungeon.db"  # dungeon.db will live in backend/

# Create async SQLAlchemy engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # True if you want to see SQL
    future=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
)

# Base class for models
Base = declarative_base()


# Dependency to get async DB session
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
