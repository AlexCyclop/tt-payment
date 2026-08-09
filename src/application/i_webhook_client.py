from abc import ABC, abstractmethod
from typing import Any


class WebhookDeliveryError(RuntimeError):
    pass


class IWebhookClient(ABC):
    @abstractmethod
    async def post(self, url: str, payload: dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass
