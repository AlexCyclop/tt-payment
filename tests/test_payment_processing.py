from unittest.mock import AsyncMock, patch

from src.application.payment.enums import PaymentStatusesEnum
from src.application.payment.services.payment_processing import PaymentProcessingService
from tests.factories import DEFAULT_PROCESSED_AT, make_payment_entity


async def test_already_processed_does_not_schedule_webhook(
    unit_of_work: AsyncMock,
    payment_manager: AsyncMock,
) -> None:
    payment = make_payment_entity(
        status=PaymentStatusesEnum.SUCCEEDED,
        processed_at=DEFAULT_PROCESSED_AT,
    )
    payment_manager.get_by_id_for_update = AsyncMock(return_value=payment)

    service = PaymentProcessingService(unit_of_work=unit_of_work)

    with patch(
        "src.application.payment.services.payment_processing.asyncio.sleep",
        new=AsyncMock(),
    ):
        result = await service.process_created(payment.uuid)

    assert result.state == "already_processed"
    assert result.webhook_url is None
    assert result.webhook_payload is None
