import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from src.application.i_uow import IUnitOfWork
from src.application.payment.enums import PaymentStatusesEnum

ProcessingState = Literal["processed", "already_processed", "not_found", "failed"]

GATEWAY_MIN_LATENCY_SECONDS = 2
GATEWAY_MAX_LATENCY_SECONDS = 5
GATEWAY_SUCCESS_RATE = 0.9


class PaymentProcessingRetryableError(RuntimeError):
    pass


@dataclass(slots=True)
class PaymentProcessingResult:
    state: ProcessingState
    payment_id: UUID
    webhook_url: str | None = None
    webhook_payload: dict[str, Any] | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _webhook_body(
    payment_id: UUID, status: str, processed_at: datetime | None
) -> dict[str, Any]:
    return {
        "payment_id": str(payment_id),
        "status": status,
        "processed_at": processed_at.isoformat() if processed_at else None,
    }


class PaymentProcessingService:
    def __init__(self, unit_of_work: IUnitOfWork):
        self._unit_of_work = unit_of_work

    async def process_created(
        self,
        payment_id: UUID,
        *,
        final_attempt: bool = False,
    ) -> PaymentProcessingResult:
        await asyncio.sleep(
            random.uniform(GATEWAY_MIN_LATENCY_SECONDS, GATEWAY_MAX_LATENCY_SECONDS)
        )

        async with self._unit_of_work as uow:
            payment = await uow.payment_manager.get_by_id_for_update(payment_id)
            if payment is None:
                return PaymentProcessingResult(state="not_found", payment_id=payment_id)

            if payment.processed_at is not None:
                return PaymentProcessingResult(
                    state="already_processed",
                    payment_id=payment.uuid,
                    webhook_url=payment.webhook_url,
                    webhook_payload=_webhook_body(
                        payment_id=payment.uuid,
                        status=payment.status.value,
                        processed_at=payment.processed_at,
                    ),
                )

            if random.random() >= GATEWAY_SUCCESS_RATE:
                if not final_attempt:
                    raise PaymentProcessingRetryableError(
                        f"Temporary payment processing error for {payment_id}"
                    )

                return await self._finalize(
                    uow=uow,
                    payment_uuid=payment.uuid,
                    webhook_url=payment.webhook_url,
                    status=PaymentStatusesEnum.FAILED,
                    state="failed",
                )

            return await self._finalize(
                uow=uow,
                payment_uuid=payment.uuid,
                webhook_url=payment.webhook_url,
                status=PaymentStatusesEnum.SUCCEEDED,
                state="processed",
            )

    @staticmethod
    async def _finalize(
        uow: IUnitOfWork,
        payment_uuid: UUID,
        webhook_url: str | None,
        status: PaymentStatusesEnum,
        state: ProcessingState,
    ) -> PaymentProcessingResult:
        processed_at = _utc_now()
        await uow.payment_manager.mark_processed(
            payment_uuid=payment_uuid,
            status=status,
            processed_at=processed_at,
        )

        return PaymentProcessingResult(
            state=state,
            payment_id=payment_uuid,
            webhook_url=webhook_url,
            webhook_payload=_webhook_body(
                payment_id=payment_uuid,
                status=status.value,
                processed_at=processed_at,
            ),
        )
