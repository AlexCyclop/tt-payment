from unittest.mock import AsyncMock, MagicMock

from src.application.payment.enums import PaymentStatusesEnum, WebhookStatusesEnum
from src.application.webhook.services.webhook_delivery import WebhookDeliveryService
from tests.factories import DEFAULT_PROCESSED_AT, make_payment_entity


async def test_deliver_skips_terminal_webhook_status(
    unit_of_work: AsyncMock,
    payment_manager: AsyncMock,
) -> None:
    payment = make_payment_entity(
        status=PaymentStatusesEnum.SUCCEEDED,
        processed_at=DEFAULT_PROCESSED_AT,
        webhook_status=WebhookStatusesEnum.DELIVERED,
        webhook_attempts=1,
    )
    payment_manager.get_by_id = AsyncMock(return_value=payment)

    webhook_client = AsyncMock()
    service = WebhookDeliveryService(unit_of_work, webhook_client, MagicMock())

    status = await service.deliver(
        payment_uuid=payment.uuid,
        webhook_url=payment.webhook_url,
        payload={"payment_id": str(payment.uuid)},
    )

    assert status == "skipped"
    webhook_client.post.assert_not_called()
