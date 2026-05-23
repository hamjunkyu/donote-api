"""더치페이 정산 API 라우터.

핵심 디자인:
- Creator NOT in participants (spec 6.3 ①).
- 모든 endpoint 권한 검증 (creator_id == current_user.id).
- COMPLETED 정산 수정 차단, SETTLED 참여자 amount/제거 차단.
- 마지막 SETTLED 시 정산 자동 COMPLETED 전환.
"""

import uuid
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db

from . import schemas, service


router = APIRouter(prefix="/api/settlements", tags=["Settlements"])


@router.get("/", response_model=List[schemas.SettlementResponse])
def list_settlements(
    role: Optional[Literal["creator", "participant"]] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """정산 목록 조회.

    - `role=creator` (default): 본인이 만든 정산
    - `role=participant`: 본인이 참여자로 있는 정산
    """
    return service.get_user_settlements(db, current_user, role=role)


@router.post("/", response_model=schemas.SettlementResponse, status_code=201)
def create_settlement(
    settlement: schemas.SettlementCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """정산 생성. 거래 소유자만 가능. creator는 참여자에 포함되지 않음."""
    new_settlement = service.create_settlement(db, settlement, current_user)
    if not new_settlement:
        raise HTTPException(status_code=404, detail="거래를 찾을 수 없습니다")
    return new_settlement


@router.post(
    "/{settlement_id}/participants",
    response_model=schemas.ParticipantResponse,
    status_code=201,
)
def add_participant(
    settlement_id: uuid.UUID,
    participant: schemas.ParticipantCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """참여자 추가. creator 본인은 추가 불가."""
    result = service.add_participant(db, settlement_id, participant, current_user)
    if not result:
        raise HTTPException(status_code=403, detail="권한이 없거나 정산을 찾을 수 없습니다")
    return result


@router.delete(
    "/{settlement_id}/participants/{participant_id}",
    response_model=schemas.MessageResponse,
)
def remove_participant(
    settlement_id: uuid.UUID,
    participant_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """참여자 제거. SETTLED 참여자는 차단 (revert 먼저)."""
    result = service.remove_participant(db, settlement_id, participant_id, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="참여자를 찾을 수 없습니다")
    return {"message": "참여자가 제거되었습니다"}


@router.post(
    "/{settlement_id}/split/equal",
    response_model=List[schemas.ParticipantResponse],
)
def equal_split(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """균등 분배. per_person = total // (N+1). creator 가 나머지 흡수."""
    result = service.split_equal(db, settlement_id, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="정산을 찾을 수 없습니다")
    return result


@router.post(
    "/{settlement_id}/split/custom",
    response_model=List[schemas.ParticipantResponse],
)
def custom_split(
    settlement_id: uuid.UUID,
    split_data: schemas.CustomSplitRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """직접 분배. 합계 ≤ total 검증."""
    result = service.split_custom(db, settlement_id, split_data, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="정산을 찾을 수 없습니다")
    return result


@router.patch(
    "/{settlement_id}/split/edit",
    response_model=List[schemas.ParticipantResponse],
)
def edit_split(
    settlement_id: uuid.UUID,
    split_data: schemas.CustomSplitRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """split 수정 (split_custom 별칭)."""
    result = service.edit_split(db, settlement_id, split_data, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="정산을 찾을 수 없습니다")
    return result


@router.get(
    "/{settlement_id}/balance",
    response_model=List[schemas.BalanceItem],
)
def view_balance(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """정산 잔액 (참여자별 금액 + 상태)."""
    result = service.get_balance(db, settlement_id, current_user)
    if result is None:
        raise HTTPException(status_code=404, detail="정산을 찾을 수 없습니다")
    return result


@router.get(
    "/{settlement_id}/debts",
    response_model=List[schemas.DebtItem],
)
def get_debts(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """채무 관계 (from → to creator)."""
    result = service.calculate_debts(db, settlement_id, current_user)
    if result is None:
        raise HTTPException(status_code=404, detail="정산을 찾을 수 없습니다")
    return result


@router.patch(
    "/{settlement_id}/complete",
    response_model=schemas.SettlementResponse,
)
def mark_complete(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """정산 전체 완료 처리. 모든 참여자가 SETTLED 여야 함."""
    result = service.mark_settlement_complete(db, settlement_id, current_user)
    if result == "NOT_ALL_SETTLED":
        raise HTTPException(status_code=400, detail="아직 완료되지 않은 참여자가 있습니다")
    if not result:
        raise HTTPException(status_code=404, detail="정산을 찾을 수 없습니다")
    return result


@router.patch(
    "/{settlement_id}/revert",
    response_model=schemas.SettlementResponse,
)
def revert_settlement(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """COMPLETED 정산을 PENDING 으로 복원."""
    result = service.revert_completion(db, settlement_id, current_user)
    if result == "NOT_COMPLETED":
        raise HTTPException(status_code=400, detail="COMPLETED 상태가 아닙니다")
    if not result:
        raise HTTPException(status_code=404, detail="정산을 찾을 수 없습니다")
    return result


@router.patch(
    "/{settlement_id}/cancel",
    response_model=schemas.SettlementResponse,
)
def cancel_settlement(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """정산 취소. status를 CANCELLED로 변경 (기록 보존, 실부담액 계산에서 제외)."""
    result = service.cancel_settlement(db, settlement_id, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="정산을 찾을 수 없습니다")
    return result


@router.patch(
    "/participants/{participant_id}/settle",
    response_model=schemas.ParticipantResponse,
)
def mark_participant_paid(
    participant_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """참여자 SETTLED 처리. 마지막 참여자면 정산 자동 COMPLETED."""
    result = service.mark_participant_settled(db, participant_id, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="참여자를 찾을 수 없거나 권한이 없습니다")
    return result


@router.patch(
    "/participants/{participant_id}/revert",
    response_model=schemas.ParticipantResponse,
)
def revert_participant_settle(
    participant_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """참여자 SETTLED → PENDING 복원. COMPLETED 정산도 자동 PENDING 복귀."""
    result = service.revert_participant(db, participant_id, current_user)
    if result == "NOT_SETTLED":
        raise HTTPException(status_code=400, detail="SETTLED 상태가 아닙니다")
    if not result:
        raise HTTPException(status_code=404, detail="참여자를 찾을 수 없습니다")
    return result


@router.get(
    "/{settlement_id}/participants",
    response_model=List[schemas.ParticipantResponse],
)
def get_participants(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """참여자 목록 조회."""
    result = service.get_participants_status(db, settlement_id, current_user)
    if result is None:
        raise HTTPException(status_code=404, detail="정산을 찾을 수 없습니다")
    return result


@router.get(
    "/{settlement_id}",
    response_model=schemas.SettlementDetailResponse,
)
def view_settlement(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """정산 상세 (참여자 포함)."""
    result = service.get_settlement(db, settlement_id, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="정산을 찾을 수 없습니다")
    return result


@router.patch(
    "/{settlement_id}",
    response_model=schemas.SettlementResponse,
)
def edit_settlement(
    settlement_id: uuid.UUID,
    update_data: schemas.SettlementUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """정산 split_type 변경. COMPLETED 정산은 차단."""
    result = service.update_settlement(db, settlement_id, update_data, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="정산을 찾을 수 없습니다")
    return result


@router.delete(
    "/{settlement_id}",
    response_model=schemas.MessageResponse,
)
def delete_settlement(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """정산 삭제. 참여자는 FK CASCADE로 자동 삭제."""
    result = service.delete_settlement(db, settlement_id, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="정산을 찾을 수 없습니다")
    return {"message": "정산이 삭제되었습니다"}
