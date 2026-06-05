"""알림 스키마."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.notifications.constants import NotificationType


class NotificationResponse(BaseModel):
    """알림 정보 응답 스키마."""
    id: uuid.UUID
    type: NotificationType
    message: str = Field(max_length=255)
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """단순 메시지 응답."""
    message: str
