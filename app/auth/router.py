"""인증 API 엔드포인트.

회원가입, 로그인, 토큰 갱신, 로그아웃, 내 정보 조회, 비밀번호 변경 처리.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import service
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.auth.schemas import (
    SignupRequest,
    LoginRequest,
    RefreshRequest,
    PasswordChangeRequest,
    UserResponse,
    TokenResponse,
    MessageResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """새 사용자 계정을 등록한다.

    Args:
        request: 이메일, 비밀번호, 이름이 포함된 회원가입 데이터.
        db: 데이터베이스 세션.

    Returns:
        생성된 사용자 프로필.

    Raises:
        HTTPException: 이메일이 이미 등록된 경우 409 반환.
    """
    existing_user = service.get_user_by_email(db, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 등록된 이메일입니다",
        )

    user = service.create_user(
        db, request.email, request.password, request.name
    )
    return user


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """사용자를 인증하고 액세스/리프레시 토큰을 발급한다.

    Args:
        request: 로그인 인증 정보 (이메일, 비밀번호).
        db: 데이터베이스 세션.

    Returns:
        액세스 토큰과 리프레시 토큰 쌍.

    Raises:
        HTTPException: 인증 정보가 유효하지 않은 경우 401 반환.
    """
    user = service.authenticate_user(
        db, request.email, request.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 일치하지 않습니다",
        )

    access_token = service.create_access_token(user.id)
    refresh_token = service.create_refresh_token(user.id, db)

    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    """유효한 리프레시 토큰으로 새 토큰 쌍을 발급한다.

    토큰 로테이션 수행: 기존 리프레시 토큰을 삭제하고
    새 액세스/리프레시 토큰 쌍을 발급한다.

    Args:
        request: 사용할 리프레시 토큰.
        db: 데이터베이스 세션.

    Returns:
        새 액세스 토큰과 리프레시 토큰 쌍.

    Raises:
        HTTPException: 리프레시 토큰이 유효하지 않거나
            DB에 없는 경우 401 반환.
    """
    payload = service.verify_token(request.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 Refresh Token입니다",
        )

    db_token = service.get_refresh_token(db, request.refresh_token)
    if db_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 Refresh Token입니다",
        )

    user_id = payload.get("sub")
    service.delete_refresh_token(db, request.refresh_token)

    new_access_token = service.create_access_token(uuid.UUID(user_id))
    new_refresh_token = service.create_refresh_token(
        uuid.UUID(user_id), db
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(request: RefreshRequest, db: Session = Depends(get_db)):
    """리프레시 토큰을 무효화하여 로그아웃한다.

    Args:
        request: 무효화할 리프레시 토큰.
        db: 데이터베이스 세션.

    Returns:
        로그아웃 확인 메시지.
    """
    service.delete_refresh_token(db, request.refresh_token)
    return MessageResponse(message="로그아웃되었습니다")


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    """현재 로그인한 사용자의 프로필을 조회한다.

    Args:
        current_user: 인증된 사용자 (의존성 주입).

    Returns:
        사용자 프로필 정보.
    """
    return current_user


@router.put("/password", response_model=MessageResponse)
def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """현재 사용자의 비밀번호를 변경한다.

    현재 비밀번호를 확인하고, 새 비밀번호로 업데이트한 뒤,
    모든 리프레시 토큰을 무효화하여 재로그인을 강제한다.

    Args:
        request: 현재 비밀번호와 새 비밀번호 데이터.
        current_user: 인증된 사용자 (의존성 주입).
        db: 데이터베이스 세션.

    Returns:
        비밀번호 변경 확인 메시지.

    Raises:
        HTTPException: 현재 비밀번호가 일치하지 않는 경우 400 반환.
    """
    if not service.verify_password(
        request.current_password, current_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 일치하지 않습니다",
        )

    current_user.password_hash = service.hash_password(
        request.new_password
    )
    db.commit()

    service.delete_all_refresh_tokens(db, current_user.id)

    return MessageResponse(
        message="비밀번호가 변경되었습니다. 다시 로그인해주세요."
    )
