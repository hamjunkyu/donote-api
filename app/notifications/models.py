"""알림 데이터베이스 모델."""

import uuid
from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Notification(Base):
    """사용자에게 발송되는 알림 기록."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # 예: "BUDGET_WARNING", "BUDGET_EXCEEDED"
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
