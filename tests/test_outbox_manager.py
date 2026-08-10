from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from src.application.outbox.enums import OutboxStatusesEnum
from src.infrastructure.db.managers.outbox import OutboxManager
from tests.factories import make_outbox_entity

NOW = datetime(2026, 8, 9, 12, 0, 0, tzinfo=UTC)
CLAIMED_UNTIL = NOW + timedelta(seconds=300)


async def test_mark_failed_writes_terminal_state(db_session: AsyncMock) -> None:
    manager = OutboxManager(db_session)

    await manager.mark_failed(
        outbox_uuid=make_outbox_entity().uuid,
        attempts=2,
        error="unroutable",
        claimed_until=CLAIMED_UNTIL,
    )

    stmt = db_session.execute.await_args.args[0]
    values = stmt.compile().params
    assert values["status"] == OutboxStatusesEnum.FAILED
    assert values["attempts"] == 2
    assert values["last_error"] == "unroutable"
    assert values["next_retry_at"] is None


async def test_reschedule_returns_message_to_pending(db_session: AsyncMock) -> None:
    manager = OutboxManager(db_session)
    next_retry_at = NOW + timedelta(seconds=4)

    await manager.reschedule(
        outbox_uuid=make_outbox_entity().uuid,
        attempts=2,
        error="broker is down",
        next_retry_at=next_retry_at,
        claimed_until=CLAIMED_UNTIL,
    )

    stmt = db_session.execute.await_args.args[0]
    values = stmt.compile().params
    assert values["status"] == OutboxStatusesEnum.PENDING
    assert values["attempts"] == 2
    assert values["next_retry_at"] == next_retry_at
    assert values["locked_until"] is None


async def test_writes_are_guarded_by_lease_ownership(db_session: AsyncMock) -> None:
    manager = OutboxManager(db_session)

    await manager.reschedule(
        outbox_uuid=make_outbox_entity().uuid,
        attempts=1,
        error="broker is down",
        next_retry_at=NOW,
        claimed_until=CLAIMED_UNTIL,
    )

    stmt = db_session.execute.await_args.args[0]
    where_clause = str(stmt.whereclause)
    assert "locked_until" in where_clause
    assert "status" in where_clause
