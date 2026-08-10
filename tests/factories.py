from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from src.application.outbox.entity import OutboxEntity
from src.application.outbox.enums import OutboxStatusesEnum
from src.application.payment.entities import CreatePaymentRequestDTO, PaymentEntity
from src.application.payment.enums import (
    PaymentCurrenciesEnum,
    PaymentStatusesEnum,
    WebhookStatusesEnum,
)

DEFAULT_CREATED_AT = datetime(2026, 8, 9, 12, 0, 0, tzinfo=UTC)
DEFAULT_PROCESSED_AT = datetime(2026, 8, 9, 12, 0, 4, tzinfo=UTC)
DEFAULT_WEBHOOK_URL = "https://example.com/hook"
DEFAULT_AMOUNT = Decimal("100.00")
DEFAULT_DESCRIPTION = "test"
DEFAULT_METADATA: dict[str, Any] = {"source": "web"}
DEFAULT_IDEMPOTENCY_KEY = "key-1"


def make_payment_request(
    *,
    amount: Decimal = DEFAULT_AMOUNT,
    currency: PaymentCurrenciesEnum = PaymentCurrenciesEnum.RUB,
    description: str | None = DEFAULT_DESCRIPTION,
    metadata: dict[str, Any] | None = None,
    webhook_url: str | None = DEFAULT_WEBHOOK_URL,
) -> CreatePaymentRequestDTO:
    return CreatePaymentRequestDTO(
        amount=amount,
        currency=currency,
        description=description,
        metadata=dict(DEFAULT_METADATA) if metadata is None else metadata,
        webhook_url=webhook_url,
    )


def make_payment_entity(
    *,
    uuid: UUID | None = None,
    amount: Decimal = DEFAULT_AMOUNT,
    currency: PaymentCurrenciesEnum = PaymentCurrenciesEnum.RUB,
    description: str | None = DEFAULT_DESCRIPTION,
    metadata: dict[str, Any] | None = None,
    status: PaymentStatusesEnum = PaymentStatusesEnum.PENDING,
    idempotency_key: str = DEFAULT_IDEMPOTENCY_KEY,
    webhook_url: str | None = DEFAULT_WEBHOOK_URL,
    created_at: datetime = DEFAULT_CREATED_AT,
    processed_at: datetime | None = None,
    webhook_status: WebhookStatusesEnum | None = None,
    webhook_attempts: int = 0,
    webhook_last_error: str | None = None,
    next_webhook_retry_at: datetime | None = None,
) -> PaymentEntity:
    return PaymentEntity(
        uuid=uuid4() if uuid is None else uuid,
        amount=amount,
        currency=currency,
        description=description,
        metadata=dict(DEFAULT_METADATA) if metadata is None else metadata,
        status=status,
        idempotency_key=idempotency_key,
        webhook_url=webhook_url,
        created_at=created_at,
        processed_at=processed_at,
        webhook_status=webhook_status,
        webhook_attempts=webhook_attempts,
        webhook_last_error=webhook_last_error,
        next_webhook_retry_at=next_webhook_retry_at,
    )


def make_outbox_entity(
    *,
    uuid: UUID | None = None,
    topic: str = "payments.new",
    payload: dict[str, Any] | None = None,
    status: OutboxStatusesEnum = OutboxStatusesEnum.PENDING,
    attempts: int = 0,
    locked_until: datetime | None = None,
    next_retry_at: datetime | None = None,
    last_error: str | None = None,
    created_at: datetime = DEFAULT_CREATED_AT,
    published_at: datetime | None = None,
) -> OutboxEntity:
    outbox_uuid = uuid4() if uuid is None else uuid

    return OutboxEntity(
        uuid=outbox_uuid,
        topic=topic,
        payload={"payment_id": str(outbox_uuid)} if payload is None else payload,
        status=status,
        attempts=attempts,
        locked_until=locked_until,
        next_retry_at=next_retry_at,
        last_error=last_error,
        created_at=created_at,
        published_at=published_at,
    )
