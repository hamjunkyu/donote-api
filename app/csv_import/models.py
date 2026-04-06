"""CSV 가져오기 데이터베이스 모델."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImportHash(Base):
    """CSV 중복 가져오기 방지를 위한 해시 레코드.

    CSV 파일의 각 행에서 user_id, 날짜, 금액, 메모, 행 번호를
    기반으로 SHA256 해시를 생성한다.
    동일 해시가 이미 존재하면 중복으로 판단하여 건너뛴다.
    """

    __tablename__ = "import_hashes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
