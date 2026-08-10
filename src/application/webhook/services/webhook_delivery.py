import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from src.application.i_payment_publisher import (
    ERROR_HEADER,
    SOURCE_HEADER,
    IPaymentPublisher,
)
from src.application.i_uow import IUnitOfWork
from src.application.i_webhook_client import IWebhookClient, WebhookDeliveryError
from src.application.payment.enums import WebhookStatusesEnum
from src.core.config import settings

logger = logging.getLogger(__name__)

WEBHOOK_SOURCE = "webhook"

DeliveryStatus = Literal[
    "delivered", "skipped", "scheduled", "dlq_published", "dlq_publish_failed"
]


class WebhookDeliveryService:
    def __init__(
        self,
        unit_of_work: IUnitOfWork,
        webhook_client: IWebhookClient,
        payment_publisher: IPaymentPublisher,
    ):
        self._unit_of_work = unit_of_work
        self._webhook_client = webhook_client
        self._payment_publisher = payment_publisher
        self._max_attempts = settings.webhook.MAX_ATTEMPTS

    async def deliver(
        self,
        payment_uuid: UUID,
        webhook_url: str | None,
        payload: dict[str, Any],
        attempt: int = 1,
    ) -> DeliveryStatus:
        if not webhook_url:
            logger.info(
                "Webhook URL is empty, payment %s completed without callback",
                payment_uuid,
            )
            return "skipped"

        async with self._unit_of_work as uow:
            payment = await uow.payment_manager.get_by_id(payment_uuid)
            if payment is None:
                logger.warning(
                    "Payment %s not found for webhook delivery", payment_uuid
                )
                return "skipped"
            if payment.webhook_status in (
                WebhookStatusesEnum.DELIVERED,
                WebhookStatusesEnum.FAILED,
            ):
                logger.info(
                    "Webhook for payment %s already in terminal state %s, skipping",
                    payment_uuid,
                    payment.webhook_status,
                )
                return "skipped"

        try:
            await self._webhook_client.post(webhook_url, payload)
        except WebhookDeliveryError as error:
            return await self._handle_failure(payment_uuid, payload, attempt, error)

        await self._save(
            payment_uuid,
            status=WebhookStatusesEnum.DELIVERED,
            attempts=attempt,
            last_error=None,
            next_retry_at=None,
        )
        logger.info(
            "Webhook for payment %s delivered on attempt %s", payment_uuid, attempt
        )

        return "delivered"

    async def _handle_failure(
        self,
        payment_uuid: UUID,
        payload: dict[str, Any],
        attempt: int,
        error: WebhookDeliveryError,
    ) -> DeliveryStatus:
        if attempt >= self._max_attempts:
            await self._save(
                payment_uuid,
                status=WebhookStatusesEnum.FAILED,
                attempts=attempt,
                last_error=str(error)[:2000],
                next_retry_at=None,
            )
            return await self._to_dlq(payment_uuid, payload, attempt, error)

        delay_seconds = self._delay_for(attempt)
        await self._save(
            payment_uuid,
            status=WebhookStatusesEnum.PENDING,
            attempts=attempt,
            last_error=str(error)[:2000],
            next_retry_at=self._now() + timedelta(seconds=delay_seconds),
        )
        logger.warning(
            "Webhook attempt %s/%s for payment %s failed, next try in %ss: %s",
            attempt,
            self._max_attempts,
            payment_uuid,
            delay_seconds,
            error,
        )

        return "scheduled"

    @staticmethod
    def _delay_for(attempt: int) -> int:
        return settings.webhook.BASE_DELAY_SECONDS * 2 ** (attempt - 1)

    async def _save(
        self,
        payment_uuid: UUID,
        status: WebhookStatusesEnum,
        attempts: int,
        last_error: str | None,
        next_retry_at: datetime | None,
    ) -> bool:
        async with self._unit_of_work as uow:
            updated = await uow.payment_manager.update_webhook_delivery(
                payment_uuid=payment_uuid,
                status=status,
                attempts=attempts,
                last_error=last_error,
                next_retry_at=next_retry_at,
            )
        if not updated:
            logger.warning(
                "Webhook delivery state for payment %s was not updated "
                "(likely already in terminal state)",
                payment_uuid,
            )
        return updated

    async def _to_dlq(
        self,
        payment_uuid: UUID,
        payload: dict[str, Any],
        attempt: int,
        error: WebhookDeliveryError,
    ) -> DeliveryStatus:
        logger.error(
            "Webhook delivery failed for payment %s after %s attempts: %s",
            payment_uuid,
            attempt,
            error,
        )

        try:
            await self._payment_publisher.publish_dlq_payment(
                message_uuid=payment_uuid,
                message_payload=payload,
                headers={
                    ERROR_HEADER: f"webhook_failed: {error}"[:2000],
                    SOURCE_HEADER: WEBHOOK_SOURCE,
                },
            )
        except Exception:
            logger.exception("DLQ publish failed for payment %s", payment_uuid)
            return "dlq_publish_failed"

        return "dlq_published"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
