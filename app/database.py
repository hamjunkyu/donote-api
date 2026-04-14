"""데이터베이스 엔진, 세션, 베이스 모델 설정."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """모든 SQLAlchemy ORM 모델의 베이스 클래스."""

    pass


def get_db():
    """요청마다 데이터베이스 세션을 제공한다.

    Yields:
        요청 완료 후 자동으로 닫히는 SQLAlchemy 세션 인스턴스.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
