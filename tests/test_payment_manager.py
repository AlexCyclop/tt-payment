from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from src.application.payment.exceptions import IdempotencyKeyAlreadyUsedException
from src.infrastructure.db.managers.payment import PaymentManager
from tests.factories import make_payment_entity, make_payment_request


def test_is_same_payload_matches_equivalent_request() -> None:
    existing = make_payment_entity()
    request = make_payment_request()

    assert PaymentManager.is_same_payload(existing, request) is True


def test_is_same_payload_detects_different_amount() -> None:
    existing = make_payment_entity()
    request = make_payment_request(amount=Decimal("200.00"))

    assert PaymentManager.is_same_payload(existing, request) is False


async def test_create_reruns_lookup_after_integrity_error(
    db_session: AsyncMock,
) -> None:
    manager = PaymentManager(db_session)
    request = make_payment_request()
    existing = make_payment_entity(idempotency_key="race-key")

    manager.get_by_idempotency_key = AsyncMock(side_effect=[None, existing])  # type: ignore[method-assign]
    db_session.flush = AsyncMock(
        side_effect=IntegrityError("insert", {}, Exception("duplicate key"))
    )

    entity, existed = await manager.create(request, "race-key")

    assert existed is True
    assert entity is existing
    db_session.rollback.assert_awaited_once()
    assert manager.get_by_idempotency_key.await_count == 2


async def test_create_raises_conflict_when_payload_differs_after_integrity_error(
    db_session: AsyncMock,
) -> None:
    manager = PaymentManager(db_session)
    request = make_payment_request(amount=Decimal("200.00"))
    existing = make_payment_entity(idempotency_key="race-key")

    manager.get_by_idempotency_key = AsyncMock(side_effect=[None, existing])  # type: ignore[method-assign]
    db_session.flush = AsyncMock(
        side_effect=IntegrityError("insert", {}, Exception("duplicate key"))
    )

    with pytest.raises(IdempotencyKeyAlreadyUsedException):
        await manager.create(request, "race-key")
