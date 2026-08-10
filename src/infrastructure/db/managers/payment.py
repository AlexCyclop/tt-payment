from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.payment.entities import PaymentEntity, CreatePaymentRequestDTO
from src.application.payment.enums import PaymentStatusesEnum, WebhookStatusesEnum
from src.application.payment.exceptions import IdempotencyKeyAlreadyUsedException
from src.application.payment.i_manager import IPaymentManager
from src.infrastructure.db.models.payment import PaymentModel


class PaymentManager(IPaymentManager):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(payment: PaymentModel) -> PaymentEntity:
        return PaymentEntity(
            uuid=payment.uuid,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            metadata=payment.metadata_,
            description=payment.description,
            idempotency_key=payment.idempotency_key,
            webhook_url=payment.webhook_url,
            created_at=payment.created_at,
            processed_at=payment.processed_at,
            webhook_status=payment.webhook_status,
            webhook_attempts=payment.webhook_attempts,
            webhook_last_error=payment.webhook_last_error,
            next_webhook_retry_at=payment.next_webhook_retry_at,
        )

    @staticmethod
    def is_same_payload(existing: PaymentEntity, data: CreatePaymentRequestDTO) -> bool:
        return (
            existing.amount == data.amount
            and existing.currency == data.currency
            and existing.description == data.description
            and existing.metadata == data.metadata
            and existing.webhook_url == data.webhook_url
        )

    async def create(
        self, payment_data: CreatePaymentRequestDTO, idempotency_key: str
    ) -> tuple[PaymentEntity, bool]:
        if (existing := await self.get_by_idempotency_key(idempotency_key)) is not None:
            if not self.is_same_payload(existing, payment_data):
                raise IdempotencyKeyAlreadyUsedException()
            return existing, True

        payment = PaymentModel(
            amount=payment_data.amount,
            currency=payment_data.currency,
            description=payment_data.description,
            metadata_=payment_data.metadata,
            status=PaymentStatusesEnum.PENDING,
            idempotency_key=idempotency_key,
            webhook_url=str(payment_data.webhook_url)
            if payment_data.webhook_url
            else None,
            webhook_status=WebhookStatusesEnum.PENDING
            if payment_data.webhook_url
            else None,
        )

        self._session.add(payment)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            existing = await self.get_by_idempotency_key(idempotency_key)
            if existing is None:
                raise
            if not self.is_same_payload(existing, payment_data):
                raise IdempotencyKeyAlreadyUsedException()
            return existing, True

        return self._to_entity(payment), False

    async def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> PaymentEntity | None:
        payment = await self._session.scalar(
            select(PaymentModel).where(PaymentModel.idempotency_key == idempotency_key)
        )
        return self._to_entity(payment) if payment else None

    async def get_by_id(self, payment_uuid: UUID) -> PaymentEntity | None:
        payment = await self._session.scalar(
            select(PaymentModel).where(PaymentModel.uuid == payment_uuid)
        )
        return self._to_entity(payment) if payment else None

    async def get_by_id_for_update(self, payment_uuid: UUID) -> PaymentEntity | None:
        payment = await self._session.scalar(
            select(PaymentModel)
            .where(PaymentModel.uuid == payment_uuid)
            .with_for_update()
        )
        return self._to_entity(payment) if payment else None

    async def mark_processed(
        self,
        payment_uuid: UUID,
        status: PaymentStatusesEnum,
        processed_at: datetime,
    ) -> None:
        stmt = (
            update(PaymentModel)
            .where(PaymentModel.uuid == payment_uuid)
            .values(status=status, processed_at=processed_at)
        )
        await self._session.execute(stmt)

    async def get_for_webhook_retry(
        self, now: datetime, limit: int
    ) -> list[PaymentEntity]:
        query = (
            select(PaymentModel)
            .where(
                PaymentModel.webhook_status == WebhookStatusesEnum.PENDING,
                PaymentModel.next_webhook_retry_at.is_not(None),
                PaymentModel.next_webhook_retry_at <= now,
            )
            .order_by(PaymentModel.next_webhook_retry_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.scalars(query)
        return [self._to_entity(payment) for payment in result]

    async def claim_webhook_retry(
        self, payment_uuids: list[UUID], locked_until: datetime
    ) -> None:
        stmt = (
            update(PaymentModel)
            .where(PaymentModel.uuid.in_(payment_uuids))
            .values(next_webhook_retry_at=locked_until)
        )
        await self._session.execute(stmt)

    async def update_webhook_delivery(
        self,
        payment_uuid: UUID,
        status: WebhookStatusesEnum,
        attempts: int,
        last_error: str | None,
        next_retry_at: datetime | None,
    ) -> bool:
        stmt = (
            update(PaymentModel)
            .where(
                PaymentModel.uuid == payment_uuid,
                or_(
                    PaymentModel.webhook_status == WebhookStatusesEnum.PENDING,
                    PaymentModel.webhook_status.is_(None),
                ),
            )
            .values(
                webhook_status=status,
                webhook_attempts=attempts,
                webhook_last_error=last_error,
                next_webhook_retry_at=next_retry_at,
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0
