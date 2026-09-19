from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Engine async único por proceso. Se crea al primer uso, no al importar."""
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Dependencia de FastAPI: una sesión por petición, cerrada al terminar."""
    async with get_sessionmaker()() as session:
        yield session
