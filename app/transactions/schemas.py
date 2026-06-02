from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime, time
from typing import Literal, Optional
from uuid import UUID


class TransactionCreate(BaseModel):
    type: Literal["INCOME", "EXPENSE"]
    amount: int = Field(..., gt=0)
    category_id: UUID
    description: Optional[str] = Field(default=None, max_length=500)
    transaction_date: date
    transaction_time: Optional[time] = None


class TransactionResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    amount: int
    actual_amount: int
    category_id: UUID
    category_name: Optional[str]
    description: Optional[str]
    transaction_date: date
    transaction_time: Optional[time]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionUpdate(BaseModel):
    type: Optional[Literal["INCOME", "EXPENSE"]] = None
    amount: Optional[int] = Field(default=None, gt=0)
    category_id: Optional[UUID] = None
    description: Optional[str] = Field(default=None, max_length=500)
    transaction_date: Optional[date] = None
    transaction_time: Optional[time] = None


class MessageResponse(BaseModel):
    message: str
