from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from src.application.i_payment_publisher import IPaymentPublisher
from src.application.i_uow import IUnitOfWork
from src.application.outbox.entity import OutboxEntity
from src.application.outbox.exceptions import MessagePublishingException
from src.core.config import settings


@dataclass(slots=True)
class FailedPublication:
    outbox_uuid: UUID
    attempts: int
    error: str


class OutboxDispatchService:
    def __init__(self, unit_of_work: IUnitOfWork, payment_publisher: IPaymentPublisher):
        self._unit_of_work = unit_of_work
        self._payment_publisher = payment_publisher

    async def dispatch(self) -> dict:
        messages = await self._claim_for_dispatch()
        if not messages:
            return {"selected": 0, "sent": 0, "failed": 0}

        published, failed = await self._publish(messages)
        await self._save_results(published, failed)

        return {
            "selected": len(messages),
            "sent": len(published),
            "failed": len(failed),
        }

    async def _claim_for_dispatch(self) -> list[OutboxEntity]:
        async with self._unit_of_work as session:
            now = self._now()
            messages = await session.outbox_manager.get_for_dispatch(
                now=now, limit=settings.DISPATCH_BATCH_SIZE
            )
            if not messages:
                return []

            await session.outbox_manager.claim_processing(
                [message.uuid for message in messages],
                locked_until=now + timedelta(seconds=settings.CLAIM_RELEASE_SECONDS),
            )

            return messages

    async def _publish(
        self, messages: list[OutboxEntity]
    ) -> tuple[list[UUID], list[FailedPublication]]:
        published: list[UUID] = []
        failed: list[FailedPublication] = []

        for message in messages:
            try:
                await self._payment_publisher.publish_new_payment(
                    message_uuid=message.uuid,
                    message_payload=message.payload,
                )
            except MessagePublishingException as publish_error:
                error = await self._publish_to_dlq(message, publish_error)
                failed.append(
                    FailedPublication(
                        outbox_uuid=message.uuid,
                        attempts=publish_error.attempts,
                        error=error,
                    )
                )
            else:
                published.append(message.uuid)

        return published, failed

    async def _publish_to_dlq(
        self, message: OutboxEntity, publish_error: MessagePublishingException
    ) -> str:
        try:
            await self._payment_publisher.publish_dlq_payment(
                message_uuid=message.uuid,
                message_payload=message.payload,
            )
        except Exception as dlq_error:
            return f"{publish_error.message}; dlq_error={str(dlq_error)[:2000]}"

        return publish_error.message

    async def _save_results(
        self, published: list[UUID], failed: list[FailedPublication]
    ) -> None:
        async with self._unit_of_work as session:
            if published:
                await session.outbox_manager.mark_published(published, now=self._now())

            for failure in failed:
                await session.outbox_manager.mark_failed(
                    failure.outbox_uuid,
                    attempts=failure.attempts,
                    error=failure.error,
                )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
