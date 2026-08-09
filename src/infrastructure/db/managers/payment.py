from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.payment.entities import PaymentEntity, CreatePaymentRequestDTO
from src.application.payment.enums import PaymentStatusesEnum
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
        )

    async def create(
        self, payment_data: CreatePaymentRequestDTO, idempotency_key: str
    ) -> PaymentEntity:
        if (await self.get_by_idempotency_key(idempotency_key)) is not None:
            raise IdempotencyKeyAlreadyUsedException()

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
        )

        self._session.add(payment)
        await self._session.flush()
        return self._to_entity(payment)

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
