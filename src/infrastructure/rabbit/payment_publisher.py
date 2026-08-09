import asyncio
from typing import Any
from uuid import UUID

from aiormq import AMQPError

from src.application.i_payment_publisher import IPaymentPublisher
from src.application.outbox.exceptions import MessagePublishingException
from src.core.config import settings
from src.infrastructure.rabbit.message_broker import MessageBroker


class PaymentPublisher(IPaymentPublisher):
    def __init__(self, message_broker: MessageBroker) -> None:
        self._message_broker = message_broker
        self._max_retries = settings.MAX_OUTBOX_ATTEMPTS

    async def publish_new_payment(
        self, message_uuid: UUID, message_payload: dict
    ) -> None:
        delay = 1

        for attempt in range(1, self._max_retries + 1):
            try:
                await self._message_broker.broker.publish(
                    message=message_payload,
                    exchange=self._message_broker.payment_exchange,
                    routing_key=settings.rabbit.PAYMENTS_NEW_ROUTING_KEY,
                    message_id=str(message_uuid),
                    persist=True,
                    mandatory=True,
                )

            except (AMQPError, ConnectionError, TimeoutError) as error:
                if attempt == self._max_retries:
                    error_text = str(error)[:2000]
                    raise MessagePublishingException(attempt, error_text) from error

                await asyncio.sleep(delay)
                delay *= 2

            except Exception as error:
                error_text = str(error)[:2000]
                raise MessagePublishingException(attempt, error_text) from error

            else:
                return

    async def publish_payment_retry(
        self,
        message_uuid: UUID | None,
        message_payload: dict,
        retry_level: int,
        headers: dict[str, Any] | None = None,
    ) -> None:
        """Кладёт сообщение в очередь отложенного ретрая соответствующего уровня.

        retry_level нумеруется с единицы; уровни описаны в RabbitSettings.retry_levels.
        """
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
