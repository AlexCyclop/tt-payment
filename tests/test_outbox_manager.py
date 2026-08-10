from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from src.application.outbox.enums import OutboxStatusesEnum
from src.core.config import settings
from src.infrastructure.db.managers.outbox import OutboxManager
from tests.factories import make_outbox_entity


async def test_mark_failed_schedules_retry_before_max_attempts(
    db_session: AsyncMock,
) -> None:
    manager = OutboxManager(db_session)
    outbox_uuid = make_outbox_entity().uuid
    now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=UTC)

    await manager.mark_failed(
        outbox_uuid=outbox_uuid,
        attempts=1,
        error="publish failed",
        now=now,
    )

    stmt = db_session.execute.await_args.args[0]
    values = stmt.compile().params
    assert values["status"] == OutboxStatusesEnum.PENDING
    assert values["attempts"] == 1
    assert values["last_error"] == "publish failed"
    assert values["next_retry_at"] == now + timedelta(
        seconds=settings.OUTBOX_RETRY_BASE_DELAY_SECONDS
    )


async def test_mark_failed_marks_terminal_state_at_max_attempts(
    db_session: AsyncMock,
) -> None:
    manager = OutboxManager(db_session)
    outbox_uuid = make_outbox_entity().uuid
    now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=UTC)

    await manager.mark_failed(
        outbox_uuid=outbox_uuid,
        attempts=settings.MAX_OUTBOX_ATTEMPTS,
        error="publish failed",
        now=now,
    )

    stmt = db_session.execute.await_args.args[0]
    values = stmt.compile().params
    assert values["status"] == OutboxStatusesEnum.FAILED
    assert values["next_retry_at"] is None
