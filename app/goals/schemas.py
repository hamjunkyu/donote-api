"""저축 목표 요청/응답 스키마.

API 요청 데이터 검증 및 응답 데이터 직렬화를 위한 Pydantic 모델 정의.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    """저축 목표 생성 요청 스키마."""

    name: str
    target_amount: float = Field(gt=0)
    target_date: date | None = None
    category_id: uuid.UUID
    description: str | None = None


class GoalUpdate(BaseModel):
    """저축 목표 부분 수정 요청 스키마."""

    name: str | None = None
    target_amount: float | None = Field(default=None, gt=0)
    target_date: date | None = None
    category_id: uuid.UUID | None = None
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
    current_amount: float
    progress_percentage: float
    remaining_amount: float

    model_config = {"from_attributes": True}


class GoalProgressResponse(BaseModel):
    """저축 목표 진행률 응답 스키마."""

    goal_id: uuid.UUID
    target_amount: float
    current_amount: float
    progress_percentage: float
    remaining_amount: float
    days_remaining: int | None
    status: str


class ContributingTransactionResponse(BaseModel):
    """저축 목표 기여 거래 응답 스키마."""

    id: uuid.UUID
    amount: float
    description: str | None
    transaction_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class GoalForecastResponse(BaseModel):
    """저축 목표 예상 달성일 응답 스키마."""

    goal_id: uuid.UUID
    current_amount: float
    target_amount: float
    remaining_amount: float
    daily_average: float
    days_to_achievement: int | None
    forecast_date: date | None
    on_track: bool | None


class MonthlyTrendItem(BaseModel):
    """월별 저축액 단일 항목."""

    year_month: str
    amount: float


class GoalMonthlyTrendResponse(BaseModel):
    """저축 목표 월별 저축 추이 응답 스키마."""

    goal_id: uuid.UUID
    trend: list[MonthlyTrendItem]
