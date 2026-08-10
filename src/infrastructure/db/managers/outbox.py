from datetime import datetime
from uuid import UUID

from sqlalchemy import select, or_, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.outbox.entity import OutboxEntity
from src.application.outbox.enums import OutboxStatusesEnum
from src.application.outbox.i_manager import IOutboxManager
from src.core.config import settings
from src.infrastructure.db.models.outbox import OutboxModel


class OutboxManager(IOutboxManager):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(outbox: OutboxModel) -> OutboxEntity:
        return OutboxEntity(
            uuid=outbox.uuid,
            topic=outbox.topic,
            payload=outbox.payload,
            status=outbox.status,
            attempts=outbox.attempts,
            locked_until=outbox.locked_until,
            next_retry_at=outbox.next_retry_at,
            last_error=outbox.last_error,
            created_at=outbox.created_at,
            published_at=outbox.published_at,
        )

    async def create(self, payment_uuid: UUID, idempotency_key: str) -> None:
        outbox = OutboxModel(
            topic=settings.rabbit.NEW_PAYMENTS_TOPIC,
            payload={
                "payment_id": str(payment_uuid),
                "idempotency_key": idempotency_key,
            },
            status=OutboxStatusesEnum.PENDING,
        )

        self._session.add(outbox)
        await self._session.flush()

    async def get_for_dispatch(self, now: datetime, limit: int) -> list[OutboxEntity]:
        query = (
            select(OutboxModel)
            .where(
                or_(
                    OutboxModel.status == OutboxStatusesEnum.PENDING,
                    and_(
                        OutboxModel.status == OutboxStatusesEnum.PROCESSING,
                        OutboxModel.locked_until <= now,
                    ),
                )
            )
            .where(
                or_(
                    OutboxModel.next_retry_at.is_(None),
                    OutboxModel.next_retry_at <= now,
                )
            )
            .where(OutboxModel.topic == settings.NEW_PAYMENTS_TOPIC)
            .order_by(OutboxModel.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.scalars(query)
        return [self._to_entity(outbox) for outbox in result]

    async def claim_processing(
        self, outbox_uuid: list[UUID], locked_until: datetime
    ) -> None:
        stmt = (
            update(OutboxModel)
            .where(OutboxModel.uuid.in_(outbox_uuid))
            .values(
                status=OutboxStatusesEnum.PROCESSING,
                locked_until=locked_until,
            )
        )
        await self._session.execute(stmt)

    def _owned(self, outbox_uuid: UUID, claimed_until: datetime):
        return and_(
            OutboxModel.uuid == outbox_uuid,
            OutboxModel.status == OutboxStatusesEnum.PROCESSING,
            OutboxModel.locked_until == claimed_until,
        )

    async def mark_published(
        self, outbox_uuids: list[UUID], now: datetime, claimed_until: datetime
    ) -> int:
        stmt = (
            update(OutboxModel)
            .where(
                OutboxModel.uuid.in_(outbox_uuids),
                OutboxModel.status == OutboxStatusesEnum.PROCESSING,
                OutboxModel.locked_until == claimed_until,
            )
            .values(
                status=OutboxStatusesEnum.PUBLISHED,
                published_at=now,
                locked_until=None,
                next_retry_at=None,
                last_error=None,
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount

    async def mark_failed(
        self, outbox_uuid: UUID, attempts: int, error: str, claimed_until: datetime
    ) -> int:
        stmt = (
            update(OutboxModel)
            .where(self._owned(outbox_uuid, claimed_until))
            .values(
                status=OutboxStatusesEnum.FAILED,
                attempts=attempts,
                last_error=error,
                locked_until=None,
                next_retry_at=None,
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount

    async def reschedule(
        self,
        outbox_uuid: UUID,
        attempts: int,
        error: str,
        next_retry_at: datetime,
        claimed_until: datetime,
    ) -> int:
        stmt = (
            update(OutboxModel)
            .where(self._owned(outbox_uuid, claimed_until))
            .values(
                status=OutboxStatusesEnum.PENDING,
                attempts=attempts,
                last_error=error,
                locked_until=None,
                next_retry_at=next_retry_at,
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount
