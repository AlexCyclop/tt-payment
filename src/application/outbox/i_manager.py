from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.application.outbox.entity import OutboxEntity


class IOutboxManager(ABC):
    @abstractmethod
    async def create(self, payment_uuid: UUID, idempotency_key: str) -> None:
        pass

    @abstractmethod
    async def get_for_dispatch(self, now: datetime, limit: int) -> list[OutboxEntity]:
        pass

    @abstractmethod
    async def claim_processing(
        self, outbox_uuids: list[UUID], locked_until: datetime
    ) -> None:
        pass

    @abstractmethod
    async def mark_published(self, outbox_uuid: UUID, now: datetime) -> None:
        pass

    @abstractmethod
    async def mark_failed(self, outbox_uuid: UUID, attempts: int, error: str) -> None:
        pass
