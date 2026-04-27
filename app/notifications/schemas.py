"""알림 스키마."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    """알림 정보 응답 스키마."""
    id: uuid.UUID
    type: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
