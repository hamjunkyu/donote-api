"""저축 목표 데이터베이스 모델."""

import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, Numeric, ForeignKey, Date, DateTime, Enum as SAEnum, CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Goal(Base):
    """사용자의 저축 목표.

    진행률은 연결된 적립(GoalContribution) 합계로 계산한다.
    상태 ENUM:
      - IN_PROGRESS: 진행 중
      - ACHIEVED: 목표 금액 달성
      - EXPIRED: 목표일 경과 + 미달성
      - CANCELLED: 사용자가 취소
    """

    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_amount: Mapped[float] = mapped_column(Numeric(12, 0), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        SAEnum(
            "IN_PROGRESS", "ACHIEVED", "EXPIRED", "CANCELLED",
            name="goal_status",
        ),
        default="IN_PROGRESS",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_25_notified: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_50_notified: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_75_notified: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_achieved_notified: Mapped[bool] = mapped_column(default=False, nullable=False)


class GoalContribution(Base):
    """저축 목표에 대한 명시적 적립 기록.

    사용자가 "이 목표에 N원 모았다"를 직접 기록한다 (income/expense 와 무관).
    진행률 = 해당 목표의 적립 합계.
    """

    __tablename__ = "goal_contributions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_goal_contribution_amount_gt_zero"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 0), nullable=False)
    memo: Mapped[str | None] = mapped_column(String(200))
    contributed_at: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
