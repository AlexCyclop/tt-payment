from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.application.payment.enums import (
    PaymentCurrenciesEnum,
    PaymentStatusesEnum,
    WebhookStatusesEnum,
)
from src.infrastructure.db.db import Base


class PaymentModel(Base):
    __tablename__ = "payments"
    uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    currency: Mapped[PaymentCurrenciesEnum] = mapped_column(
        SQLEnum(
            PaymentCurrenciesEnum,
            name="currency",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    status: Mapped[PaymentStatusesEnum] = mapped_column(
        SQLEnum(
            PaymentStatusesEnum,
            name="status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=PaymentStatusesEnum.PENDING,
        server_default=PaymentStatusesEnum.PENDING.value,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )
    webhook_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    webhook_status: Mapped[WebhookStatusesEnum | None] = mapped_column(
        SQLEnum(
            WebhookStatusesEnum,
            name="webhook_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=True,
    )
    webhook_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    webhook_last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    next_webhook_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    __table_args__ = (
        Index("ix_payments_status", "status"),
        Index("ix_payments_created_at", "created_at"),
        Index("ix_payments_webhook_retry", "webhook_status", "next_webhook_retry_at"),
    )
