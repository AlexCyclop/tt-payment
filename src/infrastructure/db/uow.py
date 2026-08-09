from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.i_uow import IUnitOfWork
from src.infrastructure.db.managers.outbox import OutboxManager
from src.infrastructure.db.managers.payment import PaymentManager


class UnitOfWork(IUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> IUnitOfWork:
        self._session = self._session_factory()

        self.payment_manager = PaymentManager(session=self._session)
        self.outbox_manager = OutboxManager(session=self._session)

        return await super().__aenter__()

    async def commit(self):
        await self._session.commit()

    async def rollback(self):
        await self._session.rollback()

    async def close(self):
        await self._session.close()
