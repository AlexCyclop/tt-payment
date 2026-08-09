from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

ATTEMPT_HEADER = "x-attempt"
ERROR_HEADER = "x-error"
SOURCE_HEADER = "x-source"


class IPaymentPublisher(ABC):
    @abstractmethod
    async def publish_new_payment(
        self, message_uuid: UUID, message_payload: dict
    ) -> None:
        pass

    @abstractmethod
    async def publish_payment_retry(
        self,
        message_uuid: UUID | None,
        message_payload: dict,
        retry_level: int,
        headers: dict[str, Any] | None = None,
    ) -> None:
        pass

    @abstractmethod
    async def publish_dlq_payment(
        self,
        message_uuid: UUID | None,
        message_payload: dict,
        headers: dict[str, Any] | None = None,
    ) -> None:
        pass
