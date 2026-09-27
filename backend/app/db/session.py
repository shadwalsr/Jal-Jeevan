"""Async DB session for querying PostGIS from the agents."""
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

def get_async_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

engine = create_async_engine(get_async_db_url(settings.DATABASE_URL), pool_pre_ping=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)
