import logging

from faststream import FastStream

from src.presentation.containers import Container

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

container = Container()
message_broker = container.rabbit.broker()
webhook_client = container.webhook_client()

consumer = container.payment_consumer()

app = FastStream(message_broker.broker)


@app.on_startup
async def declare_topology() -> None:
    await message_broker.broker.connect()
    await message_broker.declare_payment_topology()
    logger.info("Payment consumer topology declared")


@app.on_shutdown
async def close_webhook_client() -> None:
    await webhook_client.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(app.run())
