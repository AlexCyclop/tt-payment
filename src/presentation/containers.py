from dependency_injector import containers, providers

from src.application.i_payment_publisher import IPaymentPublisher
from src.application.i_uow import IUnitOfWork
from src.application.i_webhook_client import IWebhookClient
from src.application.outbox.services.dispatch import OutboxDispatchService
from src.application.payment.services.payment import PaymentService
from src.application.payment.services.payment_processing import PaymentProcessingService
from src.application.webhook.services.webhook_delivery import WebhookDeliveryService
from src.application.webhook.services.webhook_retry import WebhookRetryService
from src.infrastructure.db.db import Database
from src.infrastructure.db.uow import UnitOfWork
from src.infrastructure.http.webhook_client import AiohttpWebhookClient
from src.infrastructure.rabbit.message_broker import MessageBroker
from src.infrastructure.rabbit.payment_consumer import PaymentConsumer
from src.infrastructure.rabbit.payment_publisher import PaymentPublisher


class DBContainer(containers.DeclarativeContainer):
    db: providers.Singleton[Database] = providers.Singleton(Database)
    uow: providers.Factory[IUnitOfWork] = providers.Factory(
        UnitOfWork, session_factory=db.provided.session_factory
    )


class RabbitContainer(containers.DeclarativeContainer):
    broker: providers.Singleton[MessageBroker] = providers.Singleton(MessageBroker)
    publisher: providers.Singleton[IPaymentPublisher] = providers.Singleton(
        PaymentPublisher, message_broker=broker
    )


class Container(containers.DeclarativeContainer):
    db: providers.Container[DBContainer] = providers.Container(DBContainer)
    rabbit: providers.Container[RabbitContainer] = providers.Container(RabbitContainer)

    payment_service: providers.Factory[PaymentService] = providers.Factory(
        PaymentService, unit_of_work=db.uow
    )
    dispatch_service: providers.Factory[OutboxDispatchService] = providers.Factory(
        OutboxDispatchService, unit_of_work=db.uow, payment_publisher=rabbit.publisher
    )

    payment_processing_service: providers.Factory[PaymentProcessingService] = (
        providers.Factory(
            PaymentProcessingService,
            unit_of_work=db.uow,
        )
    )
    webhook_client: providers.Singleton[IWebhookClient] = providers.Singleton(
        AiohttpWebhookClient
    )
    webhook_delivery_service: providers.Factory[WebhookDeliveryService] = (
        providers.Factory(
            WebhookDeliveryService,
            unit_of_work=db.uow,
            webhook_client=webhook_client,
            payment_publisher=rabbit.publisher,
        )
    )
    webhook_retry_service: providers.Factory[WebhookRetryService] = providers.Factory(
        WebhookRetryService,
        unit_of_work=db.uow,
        delivery_service_factory=webhook_delivery_service.provider,
    )
    payment_consumer: providers.Singleton[PaymentConsumer] = providers.Singleton(
        PaymentConsumer,
        message_broker=rabbit.broker,
        processing_service_factory=payment_processing_service.provider,
        webhook_delivery_service_factory=webhook_delivery_service.provider,
        payment_publisher=rabbit.publisher,
    )
