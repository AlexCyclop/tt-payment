from abc import ABC, abstractmethod

from src.application.outbox.i_manager import IOutboxManager
from src.application.payment.i_manager import IPaymentManager


class IUnitOfWork(ABC):
    payment_manager: IPaymentManager
    outbox_manager: IOutboxManager

    async def __aenter__(self) -> "IUnitOfWork":
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, *args, **kwargs
    ) -> None:
        if exc_type:
            await self.rollback()
        else:
            await self.commit()

        await self.close()

    @abstractmethod
    async def commit(self):
        pass

    @abstractmethod
    async def rollback(self):
        pass

    @abstractmethod
    async def close(self):
        pass
