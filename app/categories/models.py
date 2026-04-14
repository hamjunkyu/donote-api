"""카테고리 데이터베이스 모델."""

import uuid

from sqlalchemy import String, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Category(Base):
    """거래를 분류하기 위한 카테고리.

    user_id가 None이면 시스템 기본 카테고리 (수정/삭제 불가).
    user_id가 있으면 해당 사용자의 커스텀 카테고리.
    """

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(
        SAEnum("INCOME", "EXPENSE", name="category_type"), nullable=False
    )
