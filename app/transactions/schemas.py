from pydantic import BaseModel
from datetime import datetime
import uuid


class TransactionCreate(BaseModel):
    amount: float
    category_id: uuid.UUID   # REQUIRED (matches your model)
    description: str


class TransactionResponse(BaseModel):
    id: uuid.UUID
    amount: float
    description: str
    created_at: datetime

    class Config:
        from_attributes = True

        