"""예산 스키마."""

import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BudgetBase(BaseModel):
    year_month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    amount: float = Field(..., ge=0)
    category_id: Optional[uuid.UUID] = None


class BudgetCreate(BudgetBase):
    pass


class BudgetResponse(BudgetBase):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class BudgetUsageResponse(BaseModel):
    """예산 소진 현황 응답 스키마."""
    budget_id: Optional[uuid.UUID] = None
    category_id: Optional[uuid.UUID] = None
    category_name: Optional[str] = None
    budget_amount: float
    spent_amount: float
    usage_percentage: float
    status: str  # "SAFE", "WARNING", "EXCEEDED"

    model_config = ConfigDict(from_attributes=True)


class BudgetSummaryResponse(BaseModel):
    """전체 및 카테고리별 예산 요약."""
    overall: BudgetUsageResponse
    categories: List[BudgetUsageResponse]
