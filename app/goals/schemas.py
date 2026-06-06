"""저축 목표 요청/응답 스키마.

API 요청 데이터 검증 및 응답 데이터 직렬화를 위한 Pydantic 모델 정의.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class GoalCreate(BaseModel):
    """저축 목표 생성 요청 스키마."""

    name: str = Field(max_length=100)
    target_amount: float = Field(gt=0)
    target_date: date | None = None
    description: str | None = Field(default=None, max_length=500)


class GoalUpdate(BaseModel):
    """저축 목표 부분 수정 요청 스키마."""

    name: str | None = Field(default=None, max_length=100)
    target_amount: float | None = Field(default=None, gt=0)
    target_date: date | None = None
    description: str | None = Field(default=None, max_length=500)


class GoalResponse(BaseModel):
    """저축 목표 응답 스키마."""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    target_amount: float
    target_date: date | None
    description: str | None
    status: str
    created_at: datetime
    achieved_at: datetime | None
    current_amount: float
    progress_percentage: float
    remaining_amount: float
    on_track: bool | None

    model_config = {"from_attributes": True}

    @field_validator("progress_percentage")
    @classmethod
    def cap_percentage(cls, v: float) -> float:
        return min(v, 100.0)


class ContributionCreate(BaseModel):
    """적립 생성 요청 스키마."""

    amount: float = Field(gt=0)
    memo: str | None = Field(default=None, max_length=200)
    contributed_at: date | None = None


class ContributionResponse(BaseModel):
    """적립 응답 스키마."""

    id: uuid.UUID
    amount: float
    memo: str | None
    contributed_at: date
    created_at: datetime

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

    @field_validator("progress_percentage")
    @classmethod
    def cap_percentage(cls, v: float) -> float:
        return min(v, 100.0)


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
