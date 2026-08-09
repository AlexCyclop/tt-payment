"""initial payments and outbox tables

Revision ID: 0001
Revises:
Create Date: 2026-08-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "currency",
            sa.Enum("USD", "EUR", "RUB", name="currency"),
            nullable=False,
        ),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "succeeded", "failed", name="status"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("webhook_url", sa.String(2048), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("uuid"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_payments_created_at", "payments", ["created_at"])

    op.create_table(
        "outbox",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic", sa.String(120), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "processing", "published", "failed", name="outbox_status"
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("uuid"),
    )
    op.create_index(
        "ix_outbox_dispatch", "outbox", ["status", "next_retry_at", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_dispatch", table_name="outbox")
    op.drop_table("outbox")

    op.drop_index("ix_payments_created_at", table_name="payments")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_table("payments")

    sa.Enum(name="outbox_status").drop(op.get_bind())
    sa.Enum(name="status").drop(op.get_bind())
    sa.Enum(name="currency").drop(op.get_bind())
