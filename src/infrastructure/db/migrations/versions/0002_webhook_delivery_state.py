"""webhook delivery state on payments

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WEBHOOK_STATUS_VALUES = ("pending", "delivered", "failed")


def upgrade() -> None:
    postgresql.ENUM(*WEBHOOK_STATUS_VALUES, name="webhook_status").create(
        op.get_bind(), checkfirst=True
    )

    op.add_column(
        "payments",
        sa.Column(
            "webhook_status",
            postgresql.ENUM(
                *WEBHOOK_STATUS_VALUES, name="webhook_status", create_type=False
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "payments",
        sa.Column("webhook_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("payments", sa.Column("webhook_last_error", sa.Text(), nullable=True))
    op.add_column(
        "payments",
        sa.Column("next_webhook_retry_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_payments_webhook_retry",
        "payments",
        ["webhook_status", "next_webhook_retry_at"],
    )

    op.execute(
        "UPDATE payments SET webhook_status = 'pending' WHERE webhook_url IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_payments_webhook_retry", table_name="payments")
    op.drop_column("payments", "next_webhook_retry_at")
    op.drop_column("payments", "webhook_last_error")
    op.drop_column("payments", "webhook_attempts")
    op.drop_column("payments", "webhook_status")

    postgresql.ENUM(name="webhook_status").drop(op.get_bind(), checkfirst=True)
