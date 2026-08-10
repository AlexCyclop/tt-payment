from typing import Any
from uuid import UUID

from aiormq import AMQPError

from src.application.i_payment_publisher import IPaymentPublisher
from src.application.outbox.exceptions import (
    MessagePublishingException,
    MessageRejectedException,
)
from src.core.config import settings
from src.infrastructure.rabbit.message_broker import MessageBroker

TRANSPORT_ERRORS = (AMQPError, ConnectionError, TimeoutError)


class PaymentPublisher(IPaymentPublisher):
    def __init__(self, message_broker: MessageBroker) -> None:
        self._message_broker = message_broker

    async def publish_new_payment(
        self, message_uuid: UUID, message_payload: dict
    ) -> None:
        try:
            await self._message_broker.broker.publish(
                message=message_payload,
                exchange=self._message_broker.payment_exchange,
                routing_key=settings.rabbit.PAYMENTS_NEW_ROUTING_KEY,
                message_id=str(message_uuid),
                persist=True,
                mandatory=True,
            )
        except TRANSPORT_ERRORS as error:
            raise MessagePublishingException(str(error)[:2000]) from error
        except Exception as error:
            raise MessageRejectedException(str(error)[:2000]) from error

    async def publish_payment_retry(
        self,
        message_uuid: UUID | None,
        message_payload: dict,
        retry_level: int,
        headers: dict[str, Any] | None = None,
    ) -> None:
        retry_levels = settings.rabbit.retry_levels
        if not 1 <= retry_level <= len(retry_levels):
            raise ValueError(f"Unknown retry level: {retry_level}")

        _queue_name, routing_key, _delay_ms = retry_levels[retry_level - 1]

        await self._message_broker.broker.publish(
            message=message_payload,
            exchange=self._message_broker.payment_dlx_exchange,
            routing_key=routing_key,
            message_id=str(message_uuid) if message_uuid else None,
            headers=headers,
            persist=True,
            mandatory=True,
        )

    async def publish_dlq_payment(
        self,
        message_uuid: UUID | None,
        message_payload: dict,
        headers: dict[str, Any] | None = None,
    ) -> None:
        await self._message_broker.broker.publish(
            message=message_payload,
            exchange=self._message_broker.payment_dlx_exchange,
            routing_key=settings.rabbit.PAYMENTS_NEW_DLQ_ROUTING_KEY,
            message_id=str(message_uuid) if message_uuid else None,
            headers=headers,
            persist=True,
            mandatory=True,
        )
