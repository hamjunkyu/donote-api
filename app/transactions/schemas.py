from pydantic import BaseModel, Field
from datetime import date, time, datetime
from typing import Optional, Literal
from uuid import UUID


class TransactionCreate(BaseModel):
    type: Literal["INCOME", "EXPENSE"]
    amount: int = Field(gt=0)
    category_id: UUID
    description: Optional[str] = Field(default=None, max_length=500)
    transaction_date: date
    transaction_time: Optional[time] = None


class TransactionUpdate(BaseModel):
    type: Optional[Literal["INCOME", "EXPENSE"]] = None
    amount: Optional[int] = Field(default=None, gt=0)
    category_id: Optional[UUID] = None
    description: Optional[str] = Field(default=None, max_length=500)
    transaction_date: Optional[date] = None
    transaction_time: Optional[time] = None


class TransactionResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: Literal["INCOME", "EXPENSE"]
    amount: int
    category_id: UUID
    category_name: str
    description: Optional[str] = None
    transaction_date: date
    transaction_time: Optional[time]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True