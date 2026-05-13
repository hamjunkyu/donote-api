from datetime import datetime
from pydantic import BaseModel, ConfigDict
import uuid
from typing import List, Literal, Optional


class SettlementCreate(BaseModel):
    transaction_id: uuid.UUID
    split_type: Literal["EQUAL", "CUSTOM"]


class ParticipantCreate(BaseModel):
    user_id: uuid.UUID | None = None
    display_name: str
    amount: float = 0


class CustomSplitItem(BaseModel):
    participant_id: uuid.UUID
    amount: float


class CustomSplitRequest(BaseModel):
    splits: List[CustomSplitItem]

class SettlementUpdate(BaseModel):
    split_type: Optional[Literal["EQUAL", "CUSTOM"]] = None


class SettlementResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    creator_id: uuid.UUID
    total_amount: float
    split_type: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)