from uuid import UUID

from src.application.i_uow import IUnitOfWork
from src.application.payment.entities import PaymentEntity, CreatePaymentRequestDTO


class PaymentService:
    def __init__(self, unit_of_work: IUnitOfWork):
        self._unit_of_work = unit_of_work

    async def create_payment(
        self, data: CreatePaymentRequestDTO, idempotency_key: str
    ) -> PaymentEntity:
        async with self._unit_of_work as session:
            created_payment = await session.payment_manager.create(
                data, idempotency_key
            )

            await session.outbox_manager.create(
                payment_uuid=created_payment.uuid, idempotency_key=idempotency_key
            )

            return created_payment

    async def get_payment(self, payment_id: UUID) -> PaymentEntity | None:
        async with self._unit_of_work as session:
            return await session.payment_manager.get_by_id(payment_id)
