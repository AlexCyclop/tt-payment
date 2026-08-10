from datetime import datetime
from typing import Any
from uuid import UUID


def build_webhook_payload(
    payment_id: UUID,
    status: str,
    processed_at: datetime | None,
) -> dict[str, Any]:
    return {
        "delivery_id": str(payment_id),
        "payment_id": str(payment_id),
        "status": status,
        "processed_at": processed_at.isoformat() if processed_at else None,
    }
