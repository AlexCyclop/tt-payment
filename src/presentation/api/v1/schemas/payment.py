from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, HttpUrl, Field, field_validator, ConfigDict

from src.application.payment.enums import (
    PaymentCurrenciesEnum,
    PaymentStatusesEnum,
    WebhookStatusesEnum,
)


class CreatePaymentRequestSchema(BaseModel):
    amount: Decimal
    currency: PaymentCurrenciesEnum
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: HttpUrl | None = None

    @field_validator("webhook_url", mode="after")
    @classmethod
    def url_to_str(cls, v: HttpUrl | None) -> str | None:
        return str(v) if v else None


class CreatePaymentResponseSchema(BaseModel):
    uuid: UUID
    status: PaymentStatusesEnum
    created_at: datetime


class GetPaymentResponseSchema(BaseModel):
    uuid: UUID = Field(serialization_alias="payment_id")
    amount: Decimal
    currency: PaymentCurrenciesEnum
    description: str | None
    metadata: dict[str, Any]
    status: PaymentStatusesEnum
    webhook_url: HttpUrl | None
    webhook_status: WebhookStatusesEnum | None
    webhook_attempts: int
    next_webhook_retry_at: datetime | None
    created_at: datetime
    processed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
