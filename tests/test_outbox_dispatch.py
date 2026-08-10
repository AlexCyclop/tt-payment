from unittest.mock import AsyncMock

from src.application.outbox.exceptions import (
    MessagePublishingException,
    MessageRejectedException,
)
from src.application.outbox.services.dispatch import OutboxDispatchService
from tests.factories import make_outbox_entity


async def test_broker_outage_never_marks_message_failed(
    unit_of_work: AsyncMock,
    outbox_manager: AsyncMock,
) -> None:
    message = make_outbox_entity(attempts=2)
    outbox_manager.get_for_dispatch = AsyncMock(return_value=[message])

    publisher = AsyncMock()
    publisher.publish_new_payment = AsyncMock(
        side_effect=MessagePublishingException("connection refused")
    )

    service = OutboxDispatchService(unit_of_work, publisher)
    stats = await service.dispatch()

    assert stats["deferred"] == 1
    assert stats["dead_lettered"] == 0
    outbox_manager.mark_failed.assert_not_awaited()
    publisher.publish_dlq_payment.assert_not_awaited()

    reschedule_kwargs = outbox_manager.reschedule.await_args.kwargs
    assert reschedule_kwargs["attempts"] == message.attempts + 1


async def test_broker_outage_defers_the_rest_of_the_batch(
    unit_of_work: AsyncMock,
    outbox_manager: AsyncMock,
) -> None:
    messages = [make_outbox_entity() for _ in range(3)]
    outbox_manager.get_for_dispatch = AsyncMock(return_value=messages)

    publisher = AsyncMock()
    publisher.publish_new_payment = AsyncMock(
        side_effect=MessagePublishingException("connection refused")
    )

    service = OutboxDispatchService(unit_of_work, publisher)
    stats = await service.dispatch()

    assert stats["deferred"] == 3
    assert publisher.publish_new_payment.await_count == 1
    assert outbox_manager.reschedule.await_count == 3


async def test_rejected_message_goes_to_dlq_and_becomes_failed(
    unit_of_work: AsyncMock,
    outbox_manager: AsyncMock,
) -> None:
    message = make_outbox_entity()
    outbox_manager.get_for_dispatch = AsyncMock(return_value=[message])

    publisher = AsyncMock()
    publisher.publish_new_payment = AsyncMock(
        side_effect=MessageRejectedException("unroutable")
    )

    service = OutboxDispatchService(unit_of_work, publisher)
    stats = await service.dispatch()

    assert stats["dead_lettered"] == 1
    assert stats["deferred"] == 0
    publisher.publish_dlq_payment.assert_awaited_once()
    outbox_manager.mark_failed.assert_awaited_once()


async def test_rejected_message_is_deferred_when_dlq_is_unavailable(
    unit_of_work: AsyncMock,
    outbox_manager: AsyncMock,
) -> None:
    message = make_outbox_entity()
    outbox_manager.get_for_dispatch = AsyncMock(return_value=[message])

    publisher = AsyncMock()
    publisher.publish_new_payment = AsyncMock(
        side_effect=MessageRejectedException("unroutable")
    )
    publisher.publish_dlq_payment = AsyncMock(side_effect=OSError("broker is down"))

    service = OutboxDispatchService(unit_of_work, publisher)
    stats = await service.dispatch()

    assert stats["dead_lettered"] == 0
    assert stats["deferred"] == 1
    outbox_manager.mark_failed.assert_not_awaited()
    outbox_manager.reschedule.assert_awaited_once()


async def test_published_messages_are_marked_with_the_claimed_lease(
    unit_of_work: AsyncMock,
    outbox_manager: AsyncMock,
) -> None:
    messages = [make_outbox_entity() for _ in range(2)]
    outbox_manager.get_for_dispatch = AsyncMock(return_value=messages)

    publisher = AsyncMock()
    service = OutboxDispatchService(unit_of_work, publisher)
    stats = await service.dispatch()

    assert stats["sent"] == 2
    claimed_until = outbox_manager.claim_processing.await_args.kwargs["locked_until"]
    assert (
        outbox_manager.mark_published.await_args.kwargs["claimed_until"]
        == claimed_until
    )
