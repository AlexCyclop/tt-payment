# mypy: disable-error-code=call-arg
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

RetryLevel = tuple[str, str, int]


class DBSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="allow", env_prefix="postgres_", env_file=".env"
    )

    HOST: str
    PORT: int
    USER: str
    PASSWORD: str
    DB: str

    @property
    def postgres_url(self):
        return f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DB}"


class RabbitSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="allow", env_prefix="rabbit_", env_file=".env"
    )

    NEW_PAYMENTS_TOPIC: str = "payments.new"

    PAYMENTS_EXCHANGE_NAME: str = "payments"
    PAYMENTS_DLX_EXCHANGE_NAME: str = "payments.dlx"

    PAYMENTS_NEW_QUEUE_NAME: str = "payments.new"
    PAYMENTS_NEW_ROUTING_KEY: str = "payments.new"

    PAYMENTS_RETRY_1_QUEUE_NAME: str = "payments.new.retry.1"
    PAYMENTS_RETRY_1_ROUTING_KEY: str = "payments.new.retry.1"
    PAYMENTS_RETRY_1_DELAY_MS: int = 2000

    PAYMENTS_RETRY_2_QUEUE_NAME: str = "payments.new.retry.2"
    PAYMENTS_RETRY_2_ROUTING_KEY: str = "payments.new.retry.2"
    PAYMENTS_RETRY_2_DELAY_MS: int = 4000

    PAYMENTS_NEW_DLQ_QUEUE_NAME: str = "payments.new.dlq"
    PAYMENTS_NEW_DLQ_ROUTING_KEY: str = "payments.new.dlq"

    HOST: str
    PORT: int
    USER: str
    PASSWORD: str

    @property
    def rabbit_url(self):
        return f"amqp://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/"

    @property
    def retry_levels(self) -> tuple[RetryLevel, ...]:
        """Очереди отложенного ретрая: (имя, routing key, задержка в мс)."""
        return (
            (
                self.PAYMENTS_RETRY_1_QUEUE_NAME,
                self.PAYMENTS_RETRY_1_ROUTING_KEY,
                self.PAYMENTS_RETRY_1_DELAY_MS,
            ),
            (
                self.PAYMENTS_RETRY_2_QUEUE_NAME,
                self.PAYMENTS_RETRY_2_ROUTING_KEY,
                self.PAYMENTS_RETRY_2_DELAY_MS,
            ),
        )


class DispatcherWorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="allow", env_prefix="dispatch_", env_file=".env"
    )

    POLL_INTERVAL_SECONDS: float = 1.0
    ERROR_BACKOFF_SECONDS: float = 3.0


class ConsumerWorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="allow", env_prefix="consumer_", env_file=".env"
    )

    MAX_ATTEMPTS: int = 3
    PREFETCH_COUNT: int = 10


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="allow", env_file=".env")

    db: DBSettings = DBSettings()
    rabbit: RabbitSettings = RabbitSettings()
    dispatcher: DispatcherWorkerSettings = DispatcherWorkerSettings()
    consumer: ConsumerWorkerSettings = ConsumerWorkerSettings()

    API_KEY: str = "123"
    CLAIM_RELEASE_SECONDS: int = 300
    DISPATCH_BATCH_SIZE: int = 100
    MAX_OUTBOX_ATTEMPTS: int = 3

    @property
    def NEW_PAYMENTS_TOPIC(self) -> str:
        return self.rabbit.NEW_PAYMENTS_TOPIC


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
