from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.application.outbox.enums import OutboxStatusesEnum


@dataclass
class OutboxEntity:
    uuid: UUID
    topic: str
    payload: dict[str, Any]
    status: OutboxStatusesEnum
    attempts: int
    locked_until: datetime | None
    next_retry_at: datetime | None
    last_error: str | None
    created_at: datetime
    published_at: datetime | None
