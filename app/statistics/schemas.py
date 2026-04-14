from pydantic import BaseModel
from typing import Literal, List
from uuid import UUID

class PeriodDataItem(BaseModel):
    label: str
    income: int
    expense: int

class PeriodSummaryResponse(BaseModel):
    period: str
    data: List[PeriodDataItem]

class CategoryStatItem(BaseModel):
    category_id: UUID
    name: str
    amount: int
    ratio: float

class CategoryStatResponse(BaseModel):
    total_amount: int
    categories: List[CategoryStatItem]

class TopCategoryItem(BaseModel):
    name: str
    amount: int

class VsLastMonth(BaseModel):
    expense_change: float
    message: str

class MonthlyReportResponse(BaseModel):
    month: str
    total_income: int
    total_expense: int
    net: int
    daily_average_expense: int
    vs_last_month: VsLastMonth
    top_categories: List[TopCategoryItem]
