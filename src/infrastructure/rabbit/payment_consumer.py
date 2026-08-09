import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from faststream import AckPolicy
from faststream.rabbit import Channel, RabbitMessage

from src.application.i_payment_publisher import IPaymentPublisher
from src.application.payment.services.payment_processing import (
    PaymentProcessingRetryableError,
    PaymentProcessingService,
)
from src.application.webhook.services.webhook_delivery import WebhookDeliveryService
from src.core.config import settings
from src.infrastructure.rabbit.message_broker import MessageBroker

logger = logging.getLogger(__name__)

ATTEMPT_HEADER = "x-attempt"
ERROR_HEADER = "x-error"


class PaymentConsumer:
    def __init__(
        self,
        message_broker: MessageBroker,
        processing_service_factory: Callable[[], PaymentProcessingService],
        webhook_delivery_service: WebhookDeliveryService,
        payment_publisher: IPaymentPublisher,
    ) -> None:
        self._broker = message_broker.broker
        self._payment_queue = message_broker.payment_queue
        self._payment_exchange = message_broker.payment_exchange
        self._processing_service_factory = processing_service_factory
        self._webhook_delivery_service = webhook_delivery_service
        self._payment_publisher = payment_publisher
        self._max_attempts = settings.consumer.MAX_ATTEMPTS

        self._register_subscribers()

    def _register_subscribers(self) -> None:
        self._broker.subscriber(
            self._payment_queue,
            self._payment_exchange,
            channel=Channel(prefetch_count=settings.consumer.PREFETCH_COUNT),
            ack_policy=AckPolicy.MANUAL,
        )(self._consume_payment)

    async def _consume_payment(self, payload: Any, message: RabbitMessage) -> None:
        attempt = self._attempt_number(message)
        payment_id = self._extract_payment_id(payload)

        if payment_id is None:
            logger.error(
                "Unprocessable payment message %s: %r", message.message_id, payload
            )
            await self._to_dlq(message, payload, reason="invalid_payload")
            return

        is_final_attempt = attempt >= self._max_attempts

        try:
            result = await self._processing_service_factory().process_created(
                payment_id,
                final_attempt=is_final_attempt,
            )
        except PaymentProcessingRetryableError as error:
            logger.warning(
                "Payment %s processing failed on attempt %s/%s: %s",
                payment_id,
                attempt,
                self._max_attempts,
                error,
            )
            await self._retry_or_dlq(message, payload, attempt, reason=str(error))
            return
        except Exception as error:
            logger.exception("Unexpected error while processing payment %s", payment_id)
            await self._retry_or_dlq(message, payload, attempt, reason=repr(error))
            return

        if result.state == "not_found":
            logger.error("Payment %s not found, sending message to DLQ", payment_id)
            await self._to_dlq(message, payload, reason="payment_not_found")
            return

        logger.info("Payment %s processing result: %s", payment_id, result.state)

        delivery_status = await self._webhook_delivery_service.deliver(
            payment_uuid=result.payment_id,
            webhook_url=result.webhook_url,
            payload=result.webhook_payload or {},
        )
        logger.info("Payment %s webhook delivery: %s", payment_id, delivery_status)

        await message.ack()

    async def _retry_or_dlq(
        self,
        message: RabbitMessage,
        payload: Any,
        attempt: int,
        reason: str,
    ) -> None:
        if attempt >= self._max_attempts:
            await self._to_dlq(message, payload, reason=reason, attempt=attempt)
            return

        try:
            await self._payment_publisher.publish_payment_retry(
                message_uuid=self._message_uuid(message),
                message_payload=payload,
                retry_level=attempt,
                headers={ATTEMPT_HEADER: attempt + 1, ERROR_HEADER: reason[:2000]},
            )
        except Exception:
            logger.exception(
                "Failed to schedule retry for message %s", message.message_id
            )
            await message.nack(requeue=True)
            return

        await message.ack()

    async def _to_dlq(
        self,
        message: RabbitMessage,
        payload: Any,
        reason: str,
        attempt: int | None = None,
    ) -> None:
        headers: dict[str, Any] = {ERROR_HEADER: reason[:2000]}
        if attempt is not None:
            headers[ATTEMPT_HEADER] = attempt

        try:
            await self._payment_publisher.publish_dlq_payment(
                message_uuid=self._message_uuid(message),
                message_payload=payload,
                headers=headers,
            )
        except Exception:
            logger.exception("Failed to publish message %s to DLQ", message.message_id)
            await message.nack(requeue=True)
            return

        logger.error("Message %s moved to DLQ: %s", message.message_id, reason)
        await message.ack()

    def _attempt_number(self, message: RabbitMessage) -> int:
        raw_attempt = (message.headers or {}).get(ATTEMPT_HEADER)
        if raw_attempt is None:
            return 1

        try:
            attempt = int(raw_attempt)
        except (TypeError, ValueError):
            return 1

        return min(max(attempt, 1), self._max_attempts)

    @staticmethod
    def _extract_payment_id(payload: Any) -> UUID | None:
        if not isinstance(payload, dict):
            return None

        try:
            return UUID(str(payload["payment_id"]))
        except (KeyError, ValueError):
            return None

    @staticmethod
    def _message_uuid(message: RabbitMessage) -> UUID | None:
        try:
            return UUID(str(message.message_id))
        except (TypeError, ValueError):
            return None
