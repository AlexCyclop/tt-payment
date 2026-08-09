from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.application.payment.entities import PaymentEntity, CreatePaymentRequestDTO
from src.application.payment.enums import PaymentStatusesEnum


class IPaymentManager(ABC):
    @abstractmethod
    async def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> PaymentEntity | None:
        pass

    @abstractmethod
    async def get_by_id(self, payment_uuid: UUID) -> PaymentEntity | None:
        pass

    @abstractmethod
    async def get_by_id_for_update(self, payment_uuid: UUID) -> PaymentEntity | None:
        pass

    @abstractmethod
    async def create(
        self, payment_data: CreatePaymentRequestDTO, idempotency_key: str
    ) -> PaymentEntity:
        pass

    @abstractmethod
    async def mark_processed(
        self,
        payment_uuid: UUID,
        status: PaymentStatusesEnum,
        processed_at: datetime,
    ) -> None:
        pass
