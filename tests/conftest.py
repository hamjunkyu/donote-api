import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.config import settings
from app.main import app
from fastapi.testclient import TestClient

# PostgreSQL 테스트 세션 설정
engine = create_engine(settings.DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    # 테이블이 존재함을 보장
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    """각 테스트 완료 후 변경 사항을 롤백하는 데이터베이스 트랜잭션 피스처."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # SQLAlchemy 2.0 세션 바인딩
    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    """get_db 의존성을 롤백 트랜잭션 세션으로 재정의한 TestClient 피스처."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


from app.auth.dependencies import get_current_user
from app.auth.models import User
import uuid


@pytest.fixture
def test_user(db):
    """테스트용 가상 사용자를 생성합니다."""
    user = User(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hashedpassword",
        name="테스트유저"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_client(client, test_user):
    """인증 흐름을 우회하고 생성된 테스트 사용자(test_user)로 세션을 획득한 클라이언트."""
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)
