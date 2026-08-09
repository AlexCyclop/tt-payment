from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from src.application.i_uow import IUnitOfWork
from src.application.payment.entities import PaymentEntity
from src.application.webhook.payload import build_webhook_payload
from src.application.webhook.services.webhook_delivery import (
    DeliveryStatus,
    WebhookDeliveryService,
)
from src.core.config import settings


class WebhookRetryService:
    def __init__(
        self,
        unit_of_work: IUnitOfWork,
        delivery_service_factory: Callable[[], WebhookDeliveryService],
    ):
        self._unit_of_work = unit_of_work
        self._delivery_service_factory = delivery_service_factory

    async def retry_pending(self) -> dict:
        payments = await self._claim_for_retry()
        if not payments:
            return {"selected": 0, "delivered": 0, "scheduled": 0, "failed": 0}

        delivered = 0
        scheduled = 0
        failed = 0

        for payment in payments:
            status = await self._deliver(payment)

            if status == "delivered":
                delivered += 1
            elif status == "scheduled":
                scheduled += 1
            else:
                failed += 1

        return {
            "selected": len(payments),
            "delivered": delivered,
            "scheduled": scheduled,
            "failed": failed,
        }

    async def _claim_for_retry(self) -> list[PaymentEntity]:
        async with self._unit_of_work as uow:
            now = self._now()
            payments = await uow.payment_manager.get_for_webhook_retry(
                now=now, limit=settings.webhook.RETRY_BATCH_SIZE
            )
            if not payments:
                return []

            await uow.payment_manager.claim_webhook_retry(
                [payment.uuid for payment in payments],
                locked_until=now
                + timedelta(seconds=settings.webhook.RETRY_CLAIM_SECONDS),
            )

            return payments

    async def _deliver(self, payment: PaymentEntity) -> DeliveryStatus:
        return await self._delivery_service_factory().deliver(
            payment_uuid=payment.uuid,
            webhook_url=payment.webhook_url,
            payload=build_webhook_payload(
                payment_id=payment.uuid,
                status=payment.status.value,
                processed_at=payment.processed_at,
            ),
            attempt=payment.webhook_attempts + 1,
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
