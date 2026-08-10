import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from src.application.i_payment_publisher import IPaymentPublisher
from src.application.i_uow import IUnitOfWork
from src.application.outbox.entity import OutboxEntity
from src.application.outbox.exceptions import (
    MessagePublishingException,
    MessageRejectedException,
)
from src.core.config import settings

logger = logging.getLogger(__name__)

MAX_BACKOFF_EXPONENT = 16


@dataclass(slots=True)
class OutboxFailure:
    outbox_uuid: UUID
    attempts: int
    error: str


@dataclass(slots=True)
class DispatchResult:
    published: list[UUID]
    dead_lettered: list[OutboxFailure]
    deferred: list[OutboxFailure]


class OutboxDispatchService:
    def __init__(self, unit_of_work: IUnitOfWork, payment_publisher: IPaymentPublisher):
        self._unit_of_work = unit_of_work
        self._payment_publisher = payment_publisher

    async def dispatch(self) -> dict:
        claim = await self._claim_for_dispatch()
        if claim is None:
            return {"selected": 0, "sent": 0, "dead_lettered": 0, "deferred": 0}

        messages, claimed_until = claim
        result = await self._publish(messages)
        await self._save_results(result, claimed_until)

        return {
            "selected": len(messages),
            "sent": len(result.published),
            "dead_lettered": len(result.dead_lettered),
            "deferred": len(result.deferred),
        }

    async def _claim_for_dispatch(
        self,
    ) -> tuple[list[OutboxEntity], datetime] | None:
        async with self._unit_of_work as session:
            now = self._now()
            messages = await session.outbox_manager.get_for_dispatch(
                now=now, limit=settings.DISPATCH_BATCH_SIZE
            )
            if not messages:
                return None

            claimed_until = now + timedelta(seconds=settings.CLAIM_RELEASE_SECONDS)
            await session.outbox_manager.claim_processing(
                [message.uuid for message in messages],
                locked_until=claimed_until,
            )

            return messages, claimed_until

    async def _publish(self, messages: list[OutboxEntity]) -> DispatchResult:
        result = DispatchResult(published=[], dead_lettered=[], deferred=[])

        for index, message in enumerate(messages):
            try:
                await self._payment_publisher.publish_new_payment(
                    message_uuid=message.uuid,
                    message_payload=message.payload,
                )
            except MessagePublishingException as error:
                remaining = messages[index:]
                logger.warning(
                    "Broker is unavailable, deferring %s outbox messages: %s",
                    len(remaining),
                    error.message,
                )
                result.deferred.extend(
                    self._as_failure(deferred_message, error.message)
                    for deferred_message in remaining
                )
                break
            except MessageRejectedException as error:
                if await self._publish_to_dlq(message):
                    result.dead_lettered.append(
                        self._as_failure(message, error.message)
                    )
                else:
                    result.deferred.append(
                        self._as_failure(
                            message, f"{error.message}; dlq is unavailable too"
                        )
                    )
            else:
                result.published.append(message.uuid)

        return result

    async def _publish_to_dlq(self, message: OutboxEntity) -> bool:
        try:
            await self._payment_publisher.publish_dlq_payment(
                message_uuid=message.uuid,
                message_payload=message.payload,
            )
        except Exception:
            logger.exception("DLQ publish failed for outbox message %s", message.uuid)
            return False

        return True

    async def _save_results(
        self, result: DispatchResult, claimed_until: datetime
    ) -> None:
        now = self._now()

        async with self._unit_of_work as session:
            if result.published:
                updated = await session.outbox_manager.mark_published(
                    result.published, now=now, claimed_until=claimed_until
                )
                self._warn_on_lost_lease(updated, len(result.published))

            for failure in result.dead_lettered:
                updated = await session.outbox_manager.mark_failed(
                    failure.outbox_uuid,
                    attempts=failure.attempts,
                    error=failure.error,
                    claimed_until=claimed_until,
                )
                self._warn_on_lost_lease(updated, 1)

            for failure in result.deferred:
                self._log_deferred(failure)
                updated = await session.outbox_manager.reschedule(
                    failure.outbox_uuid,
                    attempts=failure.attempts,
                    error=failure.error,
                    next_retry_at=now
                    + timedelta(seconds=self._retry_delay(failure.attempts)),
                    claimed_until=claimed_until,
                )
                self._warn_on_lost_lease(updated, 1)

    @staticmethod
    def _as_failure(message: OutboxEntity, error: str) -> OutboxFailure:
        return OutboxFailure(
            outbox_uuid=message.uuid,
            attempts=message.attempts + 1,
            error=error[:2000],
        )

    @staticmethod
    def _retry_delay(attempts: int) -> int:
        exponent = min(attempts - 1, MAX_BACKOFF_EXPONENT)
        delay = settings.OUTBOX_RETRY_BASE_DELAY_SECONDS * 2**exponent

        return min(delay, settings.OUTBOX_MAX_RETRY_DELAY_SECONDS)

    @staticmethod
    def _log_deferred(failure: OutboxFailure) -> None:
        if failure.attempts >= settings.MAX_OUTBOX_ATTEMPTS:
            logger.error(
                "Outbox message %s is still undelivered after %s attempts: %s",
                failure.outbox_uuid,
                failure.attempts,
                failure.error,
            )

    @staticmethod
    def _warn_on_lost_lease(updated: int, expected: int) -> None:
        if updated < expected:
            logger.warning(
                "Outbox lease was lost for %s of %s messages, "
                "their state is owned by another dispatcher",
                expected - updated,
                expected,
            )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
