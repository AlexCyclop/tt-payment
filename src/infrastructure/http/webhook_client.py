import asyncio
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from src.application.i_webhook_client import IWebhookClient, WebhookDeliveryError
from src.core.config import settings


class AiohttpWebhookClient(IWebhookClient):
    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._session_lock = asyncio.Lock()
        self._timeout = ClientTimeout(total=settings.webhook.TIMEOUT_SECONDS)

    async def post(self, url: str, payload: dict[str, Any]) -> None:
        session = await self._get_session()

        try:
            async with session.post(url, json=payload) as response:
                if response.status >= 400:
                    raise WebhookDeliveryError(
                        f"Webhook response status: {response.status}"
                    )
        except TimeoutError as error:
            raise WebhookDeliveryError("Webhook request timed out") from error
        except ClientError as error:
            raise WebhookDeliveryError(f"Webhook request failed: {error}") from error

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def _get_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            async with self._session_lock:
                if self._session is None or self._session.closed:
                    self._session = ClientSession(timeout=self._timeout)

        return self._session
