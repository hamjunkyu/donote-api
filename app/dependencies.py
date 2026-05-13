# app/dependencies.py
import uuid
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db

# 1. OAuth2 스키마 정의 (나중에 실제 로그인 연동 시 사용)
# tokenUrl은 실제 로그인 엔드포인트 경로에 맞춰 설정합니다.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)

# 2. 테스트용 임시 유저 클래스
class MockUser:
    def __init__(self):
        # 고정된 UUID를 사용하여 테스트 데이터의 일관성을 유지합니다.
        # 필요 시 실제 DB에 존재하는 유저 ID로 변경 가능합니다.
        self.id = uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")
        self.email = "test@example.com"

def get_current_user(
    db: Session = Depends(get_db)
    # token: str = Depends(oauth2_scheme)  <-- 401 에러 방지를 위해 주석 처리
):
    """
    현재 접속한 유저 정보를 반환하는 의존성 함수.
    개발 단계에서는 인증 절차를 생략하고 항상 MockUser를 반환합니다.
    """
    
    # [TODO] 실제 운영 환경 배포 시 아래 로직으로 전환하십시오:
    # 1. token에서 payload를 디코딩 (JWT)
    # 2. payload의 user_id로 DB에서 유저 조회
    # 3. 유저가 없으면 401 Raise
    
    return MockUser()