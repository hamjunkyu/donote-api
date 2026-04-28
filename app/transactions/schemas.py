from pydantic import BaseModel
from datetime import date, time
from typing import Optional
from uuid import UUID


class TransactionCreate(BaseModel):
    type: str
    amount: float
    category_id: UUID
    description: Optional[str] = None
    transaction_date: date
    transaction_time: Optional[time] = None


class TransactionResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    amount: float
    category_id: UUID
    description: Optional[str]
    transaction_date: date
    transaction_time: Optional[time]

    class Config:
        from_attributes = True


class TransactionUpdate(BaseModel):
    type: Optional[str] = None
    amount: Optional[float] = None
    category_id: Optional[UUID] = None
    description: Optional[str] = None
    transaction_date: Optional[date] = None
    transaction_time: Optional[time] = None 

