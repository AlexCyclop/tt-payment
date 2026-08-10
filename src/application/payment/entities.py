from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.application.payment.enums import (
    PaymentCurrenciesEnum,
    PaymentStatusesEnum,
    WebhookStatusesEnum,
)


@dataclass
class PaymentEntity:
    uuid: UUID
    amount: Decimal
    currency: PaymentCurrenciesEnum
    description: str | None
    metadata: dict[str, Any]
    status: PaymentStatusesEnum
    idempotency_key: str
    webhook_url: str | None
    created_at: datetime
    processed_at: datetime | None
    webhook_status: WebhookStatusesEnum | None = None
    webhook_attempts: int = 0
    webhook_last_error: str | None = None
    next_webhook_retry_at: datetime | None = None


@dataclass
class CreatePaymentRequestDTO:
    amount: Decimal
    currency: PaymentCurrenciesEnum
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    webhook_url: str | None = None
