import asyncio
import logging

from sqlalchemy.exc import SQLAlchemyError

from src.core.config import settings
from src.presentation.containers import Container

DISPATCH_ERROR_BACKOFF_SECONDS = 3.0
RETRYABLE_DISPATCH_ERRORS = (SQLAlchemyError, RuntimeError, OSError, TimeoutError)

logger = logging.getLogger(__name__)

container = Container()
message_broker = container.rabbit.broker()
dispatcher = container.dispatch_service()


async def run_outbox_dispatcher() -> None:
    async with message_broker.broker:
        await message_broker.declare_payment_topology()
        logger.info("Outbox dispatcher started")
        while True:
            try:
                stats = await dispatcher.dispatch()
                if stats["selected"] > 0:
                    logger.info(f"Outbox dispatch stats: {stats}")
                await asyncio.sleep(settings.dispatcher.POLL_INTERVAL_SECONDS)
            except RETRYABLE_DISPATCH_ERRORS:
                logger.exception("Outbox dispatcher iteration failed")
                await asyncio.sleep(settings.dispatcher.ERROR_BACKOFF_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_outbox_dispatcher())
