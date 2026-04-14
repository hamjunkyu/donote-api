"""인증 서비스 계층.

비밀번호 해싱, JWT 토큰 관리, 사용자 CRUD 처리.
"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.config import settings
from app.auth.models import User, RefreshToken


def hash_password(password: str) -> str:
    """평문 비밀번호를 bcrypt로 해싱한다.

    Args:
        password: 해싱할 평문 비밀번호.

    Returns:
        bcrypt 해싱된 비밀번호 문자열.
    """
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """평문 비밀번호와 bcrypt 해시를 비교 검증한다.

    Args:
        plain_password: 검증할 평문 비밀번호.
        hashed_password: 비교 대상 bcrypt 해시.

    Returns:
        일치하면 True, 불일치하면 False.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(user_id: uuid.UUID) -> str:
    """단기 JWT 액세스 토큰을 생성한다.

    Args:
        user_id: 토큰을 생성할 사용자의 UUID.

    Returns:
        인코딩된 JWT 액세스 토큰 문자열.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id: uuid.UUID, db: Session) -> str:
    """장기 JWT 리프레시 토큰을 생성하고 DB에 저장한다.

    Args:
        user_id: 토큰을 생성할 사용자의 UUID.
        db: 데이터베이스 세션.

    Returns:
        인코딩된 JWT 리프레시 토큰 문자열.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    db_token = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expire,
    )
    db.add(db_token)
    db.commit()

    return token


def verify_token(token: str) -> dict | None:
    """JWT 토큰을 디코딩하고 검증한다.

    Args:
        token: 검증할 JWT 토큰 문자열.

    Returns:
        유효하면 디코딩된 payload dict, 무효하면 None.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=["HS256"]
        )
        return payload
    except JWTError:
        return None


def get_user_by_email(db: Session, email: str) -> User | None:
    """이메일로 사용자를 조회한다.

    Args:
        db: 데이터베이스 세션.
        email: 검색할 이메일 주소.

    Returns:
        사용자 객체. 없으면 None.
    """
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """UUID로 사용자를 조회한다.

    Args:
        db: 데이터베이스 세션.
        user_id: 검색할 사용자 UUID.

    Returns:
        사용자 객체. 없으면 None.
    """
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, email: str, password: str, name: str) -> User:
    """비밀번호를 해싱하여 새 사용자를 생성한다.

    Args:
        db: 데이터베이스 세션.
        email: 사용자 이메일 주소.
        password: 평문 비밀번호 (해싱 후 저장).
        name: 사용자 표시 이름.

    Returns:
        생성된 사용자 객체.
    """
    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(
    db: Session, email: str, password: str
) -> User | None:
    """이메일과 비밀번호로 사용자를 인증한다.

    Args:
        db: 데이터베이스 세션.
        email: 사용자 이메일 주소.
        password: 검증할 평문 비밀번호.

    Returns:
        인증 성공 시 사용자 객체, 실패 시 None.
    """
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_refresh_token(db: Session, token: str) -> RefreshToken | None:
    """DB에서 리프레시 토큰 레코드를 조회한다.

    Args:
        db: 데이터베이스 세션.
        token: JWT 리프레시 토큰 문자열.

    Returns:
        리프레시 토큰 객체. 없으면 None.
    """
    return db.query(RefreshToken).filter(
        RefreshToken.token == token
    ).first()


def delete_refresh_token(db: Session, token: str) -> None:
    """DB에서 단일 리프레시 토큰을 삭제한다.

    Args:
        db: 데이터베이스 세션.
        token: 삭제할 JWT 리프레시 토큰 문자열.
    """
    db.query(RefreshToken).filter(
        RefreshToken.token == token
    ).delete()
    db.commit()


def delete_all_refresh_tokens(db: Session, user_id: uuid.UUID) -> None:
    """사용자의 모든 리프레시 토큰을 삭제한다.

    비밀번호 변경 시 모든 기기에서 재로그인을 강제하기 위해 사용.

    Args:
        db: 데이터베이스 세션.
        user_id: 토큰을 삭제할 사용자의 UUID.
    """
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id
    ).delete()
    db.commit()
