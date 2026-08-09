from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.application.payment.entities import PaymentEntity, CreatePaymentRequestDTO
from src.application.payment.enums import PaymentStatusesEnum, WebhookStatusesEnum


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
    ) -> tuple[PaymentEntity, bool]:
        pass

    @abstractmethod
    async def mark_processed(
        self,
        payment_uuid: UUID,
        status: PaymentStatusesEnum,
        processed_at: datetime,
    ) -> None:
        pass

    @abstractmethod
    async def get_for_webhook_retry(
        self, now: datetime, limit: int
    ) -> list[PaymentEntity]:
        pass

    @abstractmethod
    async def claim_webhook_retry(
        self, payment_uuids: list[UUID], locked_until: datetime
    ) -> None:
        pass

    @abstractmethod
    async def update_webhook_delivery(
        self,
        payment_uuid: UUID,
        status: WebhookStatusesEnum,
        attempts: int,
        last_error: str | None,
        next_retry_at: datetime | None,
    ) -> None:
        pass
