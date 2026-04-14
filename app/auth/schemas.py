"""인증 요청/응답 스키마.

API 요청 데이터 검증 및 응답 데이터 직렬화를 위한 Pydantic 모델 정의.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class SignupRequest(BaseModel):
    """회원가입 요청 스키마."""

    email: EmailStr
    password: str
    password_confirm: str
    name: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """비밀번호 최소 요구사항 검증."""
        if len(v) < 8:
            raise ValueError("비밀번호는 최소 8자 이상이어야 합니다")
        has_letter = any(c.isalpha() for c in v)
        has_digit = any(c.isdigit() for c in v)
        if not (has_letter and has_digit):
            raise ValueError(
                "비밀번호는 영문과 숫자를 모두 포함해야 합니다"
            )
        return v

    @field_validator("password_confirm")
    @classmethod
    def validate_password_confirm(cls, v: str, info) -> str:
        """비밀번호 확인 일치 여부 검증."""
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("비밀번호가 일치하지 않습니다")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """이름 길이 검증 (2~20자)."""
        if len(v) < 2 or len(v) > 20:
            raise ValueError("이름은 2~20자여야 합니다")
        return v


class LoginRequest(BaseModel):
    """로그인 요청 스키마."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """토큰 갱신 및 로그아웃 요청 스키마."""

    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """비밀번호 변경 요청 스키마."""

    current_password: str
    new_password: str
    new_password_confirm: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """새 비밀번호 최소 요구사항 검증."""
        if len(v) < 8:
            raise ValueError("비밀번호는 최소 8자 이상이어야 합니다")
        has_letter = any(c.isalpha() for c in v)
        has_digit = any(c.isdigit() for c in v)
        if not (has_letter and has_digit):
            raise ValueError(
                "비밀번호는 영문과 숫자를 모두 포함해야 합니다"
            )
        return v

    @field_validator("new_password_confirm")
    @classmethod
    def validate_new_password_confirm(cls, v: str, info) -> str:
        """새 비밀번호 확인 일치 여부 검증."""
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("새 비밀번호가 일치하지 않습니다")
        return v


class UserResponse(BaseModel):
    """사용자 프로필 응답 스키마."""

    id: uuid.UUID
    email: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """인증 토큰 응답 스키마."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    """단순 확인 메시지 응답 스키마."""

    message: str
