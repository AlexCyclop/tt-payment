from faststream.rabbit import RabbitBroker, RabbitExchange, RabbitQueue

from src.core.config import settings


class MessageBroker:
    def __init__(self) -> None:
        self.broker = RabbitBroker(settings.rabbit.rabbit_url)

        self.payment_exchange = RabbitExchange(
            settings.rabbit.PAYMENTS_EXCHANGE_NAME,
            durable=True,
        )
        self.payment_dlx_exchange = RabbitExchange(
            settings.rabbit.PAYMENTS_DLX_EXCHANGE_NAME,
            durable=True,
        )

        self.payment_queue = RabbitQueue(
            name=settings.rabbit.PAYMENTS_NEW_QUEUE_NAME,
            durable=True,
            routing_key=settings.rabbit.PAYMENTS_NEW_ROUTING_KEY,
            arguments={
                "x-dead-letter-exchange": settings.rabbit.PAYMENTS_DLX_EXCHANGE_NAME,
                "x-dead-letter-routing-key": settings.rabbit.PAYMENTS_NEW_DLQ_ROUTING_KEY,
            },
        )

        self.payment_retry_queues = tuple(
            RabbitQueue(
                name=queue_name,
                durable=True,
                routing_key=routing_key,
                arguments={
                    "x-message-ttl": delay_ms,
                    "x-dead-letter-exchange": settings.rabbit.PAYMENTS_EXCHANGE_NAME,
                    "x-dead-letter-routing-key": settings.rabbit.PAYMENTS_NEW_ROUTING_KEY,
                },
            )
            for queue_name, routing_key, delay_ms in settings.rabbit.retry_levels
        )

        self.payment_dlq_queue = RabbitQueue(
            name=settings.rabbit.PAYMENTS_NEW_DLQ_QUEUE_NAME,
            durable=True,
            routing_key=settings.rabbit.PAYMENTS_NEW_DLQ_ROUTING_KEY,
        )

    async def declare_payment_topology(self) -> None:
        payment_exchange = await self.broker.declare_exchange(self.payment_exchange)
        dlx_exchange = await self.broker.declare_exchange(self.payment_dlx_exchange)

        payment_queue = await self.broker.declare_queue(self.payment_queue)
        await payment_queue.bind(
            payment_exchange,
            routing_key=settings.rabbit.PAYMENTS_NEW_ROUTING_KEY,
        )

        for queue_schema, (_, routing_key, _delay_ms) in zip(
            self.payment_retry_queues, settings.rabbit.retry_levels, strict=True
        ):
            retry_queue = await self.broker.declare_queue(queue_schema)
            await retry_queue.bind(dlx_exchange, routing_key=routing_key)

        dlq_queue = await self.broker.declare_queue(self.payment_dlq_queue)
        await dlq_queue.bind(
            dlx_exchange,
            routing_key=settings.rabbit.PAYMENTS_NEW_DLQ_ROUTING_KEY,
        )
