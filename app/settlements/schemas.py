from pydantic import BaseModel
import uuid
from typing import List, Literal
from typing import Optional, Literal


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