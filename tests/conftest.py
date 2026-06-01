import pytest
import uuid
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.config import settings
from app.main import app
from app.auth.dependencies import get_current_user
from app.auth.models import User

def create_test_db_if_not_exists():
    """테스트용 데이터베이스가 없으면 postgres 기본 DB에 붙어서 생성해 줍니다."""
    try:
        base_url, db_name = settings.TEST_DATABASE_URL.rsplit('/', 1)
    except ValueError:
        # URL 형식이 예외적인 경우 대비
        return

    default_url = f"{base_url}/postgres"
    default_engine = create_engine(default_url, isolation_level="AUTOCOMMIT")
    
    with default_engine.connect() as conn:
        # pg_database에서 db_name이 있는지 검사
        query = text("SELECT 1 FROM pg_database WHERE datname = :dbname")
        result = conn.execute(query, {"dbname": db_name})
        exists = result.scalar()
        
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            
    default_engine.dispose()


# 테스트 DB 자동 구성
create_test_db_if_not_exists()

# PostgreSQL 테스트 세션 설정
engine = create_engine(settings.TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    # Alembic 마이그레이션 적용
    import os
    os.environ["TEST_DATABASE_URL"] = settings.TEST_DATABASE_URL
    
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.TEST_DATABASE_URL)
    command.upgrade(alembic_cfg, "head")
    
    yield
    # 스키마 drop_all을 제거하여 alembic_version 테이블이 유지되고
    # 다음 테스트 세션 실행 시 upgrade head 스킵 오류가 발생하지 않도록 조치합니다.


@pytest.fixture
def db():
    """각 테스트 완료 후 변경 사항을 롤백하는 데이터베이스 트랜잭션 피스처 (SAVEPOINT 패턴)."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # 중첩 트랜잭션(SAVEPOINT) 시작
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def end_savepoint(session, transaction):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    # SQLAlchemy 세션 바인딩
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
    # client teardown 시 dependency_overrides.clear()가 일괄 수행되므로 별도 pop 생략
