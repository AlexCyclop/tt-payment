from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.application.payment.enums import PaymentCurrenciesEnum, PaymentStatusesEnum


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


@dataclass
class CreatePaymentRequestDTO:
    amount: Decimal
    currency: PaymentCurrenciesEnum
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    webhook_url: str | None = None


@dataclass
class CreatePaymentResponseDTO:
    uuid: UUID
    status: PaymentStatusesEnum
    created_at: datetime
