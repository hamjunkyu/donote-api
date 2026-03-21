import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Numeric, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id"), unique=True, nullable=False)
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 0), nullable=False)
    split_type: Mapped[str] = mapped_column(SAEnum("EQUAL", "CUSTOM", name="split_type"), nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum("IN_PROGRESS", "COMPLETED", "CANCELLED", name="settlement_status"),
        default="IN_PROGRESS",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SettlementParticipant(Base):
    __tablename__ = "settlement_participants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    settlement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("settlements.id"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    display_name: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 0), nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum("PENDING", "SETTLED", name="participant_status"),
        default="PENDING",
        nullable=False,
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime)
