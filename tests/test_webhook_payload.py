from datetime import UTC, datetime
from uuid import uuid4

from src.application.webhook.payload import build_webhook_payload


def test_build_webhook_payload_includes_delivery_id() -> None:
    payment_id = uuid4()
    processed_at = datetime(2026, 8, 9, 12, 0, 0, tzinfo=UTC)

    payload = build_webhook_payload(
        payment_id=payment_id,
        status="succeeded",
        processed_at=processed_at,
    )

    assert payload["delivery_id"] == str(payment_id)
    assert payload["payment_id"] == str(payment_id)
    assert payload["status"] == "succeeded"
    assert payload["processed_at"] == processed_at.isoformat()
