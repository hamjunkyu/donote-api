"""거래 데이터베이스 모델."""

import uuid
from datetime import datetime, date, time

from sqlalchemy import (
    String, Date, Time, DateTime, Numeric, Enum as SAEnum, ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Transaction(Base):
    """수입 또는 지출 거래 기록."""

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(
        SAEnum("INCOME", "EXPENSE", name="transaction_type"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 0), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(500))
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_time: Mapped[time | None] = mapped_column(Time)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
