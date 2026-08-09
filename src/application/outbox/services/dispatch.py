from datetime import timedelta, datetime, UTC

from src.application.i_payment_publisher import IPaymentPublisher
from src.application.i_uow import IUnitOfWork
from src.application.outbox.entity import OutboxEntity
from src.application.outbox.exceptions import MessagePublishingException
from src.core.config import settings


class OutboxDispatchService:
    def __init__(self, unit_of_work: IUnitOfWork, payment_publisher: IPaymentPublisher):
        self._unit_of_work = unit_of_work
        self._payment_publisher = payment_publisher

    async def dispatch(self) -> dict:
        async with self._unit_of_work as session:
            messages = await self._claim_for_dispatch(session)
            return await self._publish(session, messages)

    async def _claim_for_dispatch(self, session) -> list[OutboxEntity]:

        now = self._now()
        messages = await session.outbox_manager.get_for_dispatch(
            now=now, limit=settings.DISPATCH_BATCH_SIZE
        )

        await session.outbox_manager.claim_processing(
            [message.uuid for message in messages],
            locked_until=now + timedelta(seconds=settings.CLAIM_RELEASE_SECONDS),
        )

        return messages

    async def _publish(self, session, messages: list[OutboxEntity]) -> dict:
        failed_count = 0
        sent_count = 0
        for message in messages:
            try:
                await self._payment_publisher.publish_new_payment(
                    message_uuid=message.uuid,
                    message_payload=message.payload,
                )

            except MessagePublishingException as publish_error:
                await session.outbox_manager.mark_failed(
                    message.uuid,
                    attempts=publish_error.attempts,
                    error=publish_error.message,
                )
                failed_count += 1
                try:
                    await self._payment_publisher.publish_dlq_payment(
                        message_uuid=message.uuid,
                        message_payload=message.payload,
                    )
                except Exception as dlq_error:
                    message.last_error = (
                        f"{publish_error.message}; dlq_error={str(dlq_error)[:2000]}"
                    )

            else:
                await session.outbox_manager.mark_published(
                    message.uuid, now=self._now()
                )
                sent_count += 1

        return {"selected": len(messages), "sent": sent_count, "failed": failed_count}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
