"""더치페이 정산 요청/응답 스키마."""

import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SettlementCreate(BaseModel):
    """정산 생성 요청."""
    transaction_id: uuid.UUID
    split_type: Literal["EQUAL", "CUSTOM"]


class ParticipantCreate(BaseModel):
    """참여자 추가 요청. creator 본인은 추가 불가."""
    user_id: uuid.UUID | None = None
    display_name: str = Field(..., min_length=1, max_length=20)
    amount: int = Field(default=0, ge=0)


class CustomSplitItem(BaseModel):
    participant_id: uuid.UUID
    amount: int = Field(..., gt=0)


class CustomSplitRequest(BaseModel):
    splits: List[CustomSplitItem]


class SplitEqualRequest(BaseModel):
    """균등 분배 요청. 특정 참여자 amount 고정 후 나머지 인원 자동 재분배 (creator 포함)."""
    fixed_participant_ids: List[uuid.UUID] = Field(default_factory=list)


class SettlementUpdate(BaseModel):
    split_type: Optional[Literal["EQUAL", "CUSTOM"]] = None


class SettlementResponse(BaseModel):
    """정산 그룹 응답."""
    id: uuid.UUID
    transaction_id: uuid.UUID
    creator_id: uuid.UUID
    total_amount: int
    split_type: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ParticipantResponse(BaseModel):
    """참여자 응답."""
    id: uuid.UUID
    settlement_id: uuid.UUID
    user_id: uuid.UUID | None
    display_name: str
    amount: int
    status: str
    settled_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class BalanceItem(BaseModel):
    """정산 잔액 항목."""
    participant_id: uuid.UUID
    name: str
    amount: int
    status: str


class DebtItem(BaseModel):
    """채무 관계 항목."""
    participant_id: uuid.UUID
    from_name: str = Field(..., alias="from")
    to_name: str = Field(..., alias="to")
    amount: int

    model_config = ConfigDict(populate_by_name=True)


class SettlementDetailResponse(BaseModel):
    """정산 상세 (참여자 포함)."""
    id: uuid.UUID
    transaction_id: uuid.UUID
    creator_id: uuid.UUID
    total_amount: int
    split_type: str
    status: str
    created_at: datetime
    participants: List[ParticipantResponse]


class MessageResponse(BaseModel):
    """단순 메시지 응답."""
    message: str
