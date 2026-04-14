"""예산 데이터베이스 모델."""

import uuid

from sqlalchemy import String, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Budget(Base):
    """월별 예산 한도 (전체 또는 카테고리별).

    category_id가 None이면 해당 월의 전체 예산.
    유니크 제약으로 같은 사용자/연월/카테고리 조합의
    중복 예산 생성을 방지한다.
    """

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "year_month", "category_id",
            name="uq_budget_user_month_category",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id")
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 0), nullable=False)
