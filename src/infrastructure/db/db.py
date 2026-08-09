from sqlalchemy.ext import asyncio
from sqlalchemy.orm import DeclarativeBase

from src.core.config import settings, DBSettings


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, db_settings: DBSettings = settings.db):
        self._engine: asyncio.AsyncEngine = asyncio.create_async_engine(
            db_settings.postgres_url
        )
        self._session_factory = asyncio.async_sessionmaker(
            bind=self._engine, expire_on_commit=False
        )

    @property
    def engine(self) -> asyncio.AsyncEngine:
        return self._engine

    @property
    def session_factory(self) -> asyncio.async_sessionmaker[asyncio.AsyncSession]:
        return self._session_factory
