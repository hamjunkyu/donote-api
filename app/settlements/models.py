"""더치페이 정산 데이터베이스 모델."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Numeric, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Settlement(Base):
    """거래에 연결된 더치페이 정산 그룹.

    하나의 거래에는 최대 하나의 정산만 연결 가능 (유니크 제약).
    creator는 결제한 사람으로, 비용을 분배하려는 사용자.
    """

    __tablename__ = "settlements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id"), unique=True, nullable=False
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    total_amount: Mapped[float] = mapped_column(
        Numeric(12, 0), nullable=False
    )
    split_type: Mapped[str] = mapped_column(
        SAEnum("EQUAL", "CUSTOM", name="split_type"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        SAEnum(
            "IN_PROGRESS", "COMPLETED", "CANCELLED",
            name="settlement_status",
        ),
        default="IN_PROGRESS",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class SettlementParticipant(Base):
    """더치페이 정산의 개별 참여자.

    user_id가 None이면 비회원 참여자로,
    display_name으로만 추적한다.
    """

    __tablename__ = "settlement_participants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("settlements.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id")
    )
    display_name: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 0), nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum("PENDING", "SETTLED", name="participant_status"),
        default="PENDING",
        nullable=False,
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime)
