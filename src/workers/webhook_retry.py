import asyncio
import logging

from sqlalchemy.exc import SQLAlchemyError

from src.core.config import settings
from src.presentation.containers import Container

RETRYABLE_WEBHOOK_RETRY_ERRORS = (SQLAlchemyError, RuntimeError, OSError, TimeoutError)

logger = logging.getLogger(__name__)

container = Container()
message_broker = container.rabbit.broker()
webhook_client = container.webhook_client()
retry_service = container.webhook_retry_service()


async def run_webhook_retry() -> None:
    async with message_broker.broker:
        await message_broker.declare_payment_topology()
        logger.info("Webhook retry worker started")
        try:
            while True:
                try:
                    stats = await retry_service.retry_pending()
                    if stats["selected"] > 0:
                        logger.info(f"Webhook retry stats: {stats}")
                    await asyncio.sleep(settings.webhook.RETRY_POLL_INTERVAL_SECONDS)
                except RETRYABLE_WEBHOOK_RETRY_ERRORS:
                    logger.exception("Webhook retry iteration failed")
                    await asyncio.sleep(settings.webhook.RETRY_ERROR_BACKOFF_SECONDS)
        finally:
            await webhook_client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_webhook_retry())
