from enum import StrEnum


class PaymentCurrenciesEnum(StrEnum):
    USD = "USD"
    EUR = "EUR"
    RUB = "RUB"


class PaymentStatusesEnum(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class WebhookStatusesEnum(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
