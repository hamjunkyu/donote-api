"""저축 목표 요청/응답 스키마.

API 요청 데이터 검증 및 응답 데이터 직렬화를 위한 Pydantic 모델 정의.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class GoalCreate(BaseModel):
    """저축 목표 생성 요청 스키마."""

    name: str
    target_amount: float
    target_date: date | None = None
    category_id: uuid.UUID
    description: str | None = None


class GoalUpdate(BaseModel):
    """저축 목표 부분 수정 요청 스키마."""

    name: str | None = None
    target_amount: float | None = None
    target_date: date | None = None
    description: str | None = None


class GoalResponse(BaseModel):
    """저축 목표 응답 스키마."""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    target_amount: float
    target_date: date | None
    category_id: uuid.UUID
    description: str | None
    status: str
    created_at: datetime
    achieved_at: datetime | None

    model_config = {"from_attributes": True}
