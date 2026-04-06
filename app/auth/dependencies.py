"""인증 의존성 (FastAPI 의존성 주입).

다른 라우터에서 현재 로그인한 사용자를 식별하기 위한
get_current_user 의존성을 제공한다.
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.service import verify_token, get_user_by_id
from app.auth.models import User

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Authorization 헤더에서 현재 사용자를 추출하고 검증한다.

    요청 헤더의 Bearer 토큰을 파싱하여 유효한 액세스 토큰인지
    검증하고, 해당 사용자를 반환한다.

    Args:
        credentials: 요청 헤더의 HTTP Bearer 인증 정보.
        db: 데이터베이스 세션.

    Returns:
        인증된 사용자 객체.

    Raises:
        HTTPException: 토큰이 유효하지 않거나 만료됐거나
            사용자를 찾을 수 없는 경우 401 반환.
    """
    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access Token이 아닙니다",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
        )

    user = get_user_by_id(db, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다",
        )

    return user
