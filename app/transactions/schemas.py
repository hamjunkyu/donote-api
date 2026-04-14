from pydantic import BaseModel
from datetime import date, time
from uuid import UUID


class TransactionCreate(BaseModel):
    type: str
    amount: float
    category_id: UUID
    description: str | None = None
    transaction_date: date
    transaction_time: time | None = None


class TransactionResponse(BaseModel):
    id: UUID
    type: str
    amount: float
    category_id: UUID
    description: str | None
    transaction_date: date

    class Config:
        from_attributes = True
