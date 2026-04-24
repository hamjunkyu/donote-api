from pydantic import BaseModel
import uuid


class SettlementCreate(BaseModel):
    transaction_id: uuid.UUID
    split_type: str  # "EQUAL" or "CUSTOM"


class ParticipantCreate(BaseModel):
    user_id: uuid.UUID | None = None
    display_name: str
    amount: float

