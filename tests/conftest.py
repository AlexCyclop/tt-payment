import os

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
os.environ.setdefault("POSTGRES_DB", "payments_test")
os.environ.setdefault("RABBIT_HOST", "localhost")
os.environ.setdefault("RABBIT_PORT", "5672")
os.environ.setdefault("RABBIT_USER", "guest")
os.environ.setdefault("RABBIT_PASSWORD", "guest")
os.environ.setdefault("API_KEY", "test-api-key")

from unittest.mock import AsyncMock, MagicMock  # noqa: E402

import pytest  # noqa: E402

from src.application.payment.entities import PaymentEntity  # noqa: E402
from tests.factories import make_payment_entity  # noqa: E402


@pytest.fixture
def db_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def payment_manager() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def outbox_manager() -> AsyncMock:
    manager = AsyncMock()
    manager.mark_published = AsyncMock(return_value=1)
    manager.mark_failed = AsyncMock(return_value=1)
    manager.reschedule = AsyncMock(return_value=1)
    return manager


@pytest.fixture
def unit_of_work(payment_manager: AsyncMock, outbox_manager: AsyncMock) -> AsyncMock:
    uow = AsyncMock()
    uow.payment_manager = payment_manager
    uow.outbox_manager = outbox_manager
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    return uow


@pytest.fixture
def payment() -> PaymentEntity:
    return make_payment_entity()
