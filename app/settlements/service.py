"""더치페이 정산 비즈니스 로직.

핵심 동작:
- Creator 는 SettlementParticipant 테이블에 추가하지 않음. 본인 몫은 implicit (total - SUM(participants.amount)).
- split_equal: per_person = total // (N+1). 나머지는 creator 가 흡수.
- SettlementParticipant.amount 는 정수 (Numeric(12,0)).
- 모든 권한 검증: settlement.creator_id == current_user.id.
- COMPLETED 정산은 모든 수정 차단. SETTLED 참여자는 amount/제거 차단 (revert 먼저).
- 자동 COMPLETED: 마지막 참여자 SETTLED 시 settlement.status 자동 변경.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.models import User
from app.notifications.service import create_notification
from app.transactions import models as transaction_models

from . import models, schemas


def _get_owned_settlement(db: Session, settlement_id, current_user) -> Optional[models.Settlement]:
    """본인 소유 정산 조회 (권한 검증 포함)."""
    return db.query(models.Settlement).filter(
        models.Settlement.id == settlement_id,
        models.Settlement.creator_id == current_user.id,
    ).first()


def _ensure_modifiable(settlement: models.Settlement) -> None:
    """COMPLETED 정산 수정 차단."""
    if settlement.status == "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="완료된 정산은 수정할 수 없습니다",
        )
    if settlement.status == "CANCELLED":
        raise HTTPException(
            status_code=400,
            detail="취소된 정산은 수정할 수 없습니다",
        )


def _validate_creator_share(db: Session, settlement_id) -> None:
    """내 몫 ≥ 0 검증. settlement.total_amount >= SUM(participants.amount)."""
    settlement = db.query(models.Settlement).filter(
        models.Settlement.id == settlement_id
    ).first()
    if not settlement:
        return

    total_participants = sum(
        int(p.amount)
        for p in db.query(models.SettlementParticipant).filter(
            models.SettlementParticipant.settlement_id == settlement_id
        ).all()
    )
    if total_participants > int(settlement.total_amount):
        raise HTTPException(
            status_code=400,
            detail=f"참여자 합계({total_participants})가 총액({int(settlement.total_amount)})을 초과합니다",
        )


def create_settlement(db: Session, settlement: schemas.SettlementCreate, current_user) -> Optional[models.Settlement]:
    """정산 생성. creator는 참여자로 추가하지 않음."""
    transaction = db.query(transaction_models.Transaction).filter(
        transaction_models.Transaction.id == settlement.transaction_id,
        transaction_models.Transaction.user_id == current_user.id,
    ).first()

    if not transaction:
        return None

    if transaction.type != "EXPENSE":
        raise HTTPException(
            status_code=400,
            detail="지출(EXPENSE) 거래만 정산 생성 가능합니다",
        )

    # 이미 정산 있는지 체크 (Settlement.transaction_id 는 UNIQUE)
    existing = db.query(models.Settlement).filter(
        models.Settlement.transaction_id == transaction.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="이 거래에 이미 정산이 존재합니다",
        )

    db_settlement = models.Settlement(
        transaction_id=transaction.id,
        creator_id=current_user.id,
        total_amount=transaction.amount,
        split_type=settlement.split_type,
    )

    db.add(db_settlement)
    db.commit()
    db.refresh(db_settlement)

    return db_settlement


def add_participant(
    db: Session, settlement_id, participant: schemas.ParticipantCreate, current_user
) -> Optional[models.SettlementParticipant]:
    """참여자 추가. creator 본인 추가 불가, 회원 중복 불가, 내 몫 ≥ 0 검증."""
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    _ensure_modifiable(settlement)

    # 본인 추가 불가
    if participant.user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="본인을 참여자로 추가할 수 없습니다 (creator 몫은 자동 계산됨)",
        )

    # 같은 user_id 중복 추가 불가 (회원만 체크 — 비회원은 display_name 중복 허용)
    if participant.user_id is not None:
        existing = db.query(models.SettlementParticipant).filter(
            models.SettlementParticipant.settlement_id == settlement_id,
            models.SettlementParticipant.user_id == participant.user_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="이미 추가된 참여자입니다",
            )

    new_participant = models.SettlementParticipant(
        settlement_id=settlement_id,
        user_id=participant.user_id,
        display_name=participant.display_name,
        amount=participant.amount,
    )

    db.add(new_participant)
    db.flush()  # ID 확보

    # 내 몫 검증 (새 참여자 amount 포함). 실패 시 flush 된 참여자를 롤백한다.
    try:
        _validate_creator_share(db, settlement_id)
    except HTTPException:
        db.rollback()
        raise

    db.commit()
    db.refresh(new_participant)

    # 회원 참여자에게 알림 발생
    # amount=0 인 경우 (split 전 임시 추가) 금액 미정 메시지로 분기
    if participant.user_id is not None:
        if participant.amount > 0:
            message = f"{current_user.name}님이 {participant.amount:,}원 정산을 요청했습니다"
        else:
            message = f"{current_user.name}님이 정산에 추가했습니다 (금액 확정 대기)"
        create_notification(
            db,
            participant.user_id,
            "SETTLEMENT_REQUEST",
            message,
        )

    return new_participant


def split_equal(
    db: Session,
    settlement_id,
    current_user,
    fixed_participant_ids: Optional[list] = None,
) -> Optional[list]:
    """균등 분배. per_person = total // (N+1). creator 가 나머지 흡수.

    fixed_participant_ids 지정 시 해당 참여자는 금액 유지,
    나머지 인원이 잔여 금액을 균등 재분배 (creator 포함).
    """
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    _ensure_modifiable(settlement)

    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
    ).all()

    if not participants:
        raise HTTPException(
            status_code=400,
            detail="참여자가 없습니다",
        )

    # SETTLED 참여자는 수정 차단 (재분배 영향). 단, 고정 참여자에 포함된 경우는 OK (금액 유지)
    fixed_set = set(fixed_participant_ids or [])
    settled_unfixed = [p for p in participants if p.status == "SETTLED" and p.id not in fixed_set]
    if settled_unfixed:
        raise HTTPException(
            status_code=400,
            detail="SETTLED 참여자가 있어 재분배 불가. revert 후 다시 시도하세요",
        )

    total = int(settlement.total_amount)

    # 고정 참여자 합계 + 나머지 인원 재분배
    fixed = [p for p in participants if p.id in fixed_set]
    remaining = [p for p in participants if p.id not in fixed_set]

    fixed_total = sum(int(p.amount) for p in fixed)
    remaining_pool = total - fixed_total

    if remaining_pool < 0:
        raise HTTPException(
            status_code=400,
            detail=f"고정 참여자 합계({fixed_total})가 총액({total})을 초과합니다",
        )

    n_remaining = len(remaining) + 1  # creator 포함
    per_person = remaining_pool // n_remaining if n_remaining > 0 else 0

    for p in remaining:
        p.amount = per_person

    settlement.split_type = "EQUAL"

    db.commit()
    return participants


def split_custom(
    db: Session, settlement_id, split_data: schemas.CustomSplitRequest, current_user
) -> Optional[list]:
    """직접 분배. 합계 ≤ total. SETTLED 참여자 수정 차단."""
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    _ensure_modifiable(settlement)

    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
    ).all()

    if not participants:
        raise HTTPException(
            status_code=400,
            detail="참여자가 없습니다",
        )

    participant_map = {p.id: p for p in participants}

    # SETTLED 참여자 amount 변경 시도 차단
    for item in split_data.splits:
        target = participant_map.get(item.participant_id)
        if not target:
            raise HTTPException(
                status_code=400,
                detail=f"존재하지 않는 참여자: {item.participant_id}",
            )
        if target.status == "SETTLED" and int(target.amount) != item.amount:
            raise HTTPException(
                status_code=400,
                detail="SETTLED 참여자의 amount는 수정할 수 없습니다. revert 후 시도하세요",
            )

    # amount 적용
    for item in split_data.splits:
        participant_map[item.participant_id].amount = item.amount

    db.flush()

    # 내 몫 ≥ 0 검증 (헬퍼 사용으로 중복 제거)
    _validate_creator_share(db, settlement_id)

    settlement.split_type = "CUSTOM"

    db.commit()
    return participants


def edit_split(
    db: Session, settlement_id, split_data: schemas.CustomSplitRequest, current_user
) -> Optional[list]:
    """split_custom 별칭. PATCH /split/edit 호환."""
    return split_custom(db, settlement_id, split_data, current_user)


def get_balance(db: Session, settlement_id, current_user) -> Optional[list]:
    """본인 정산의 잔액 항목 조회. CANCELLED 정산은 빈 배열 반환 (실부담액 계산에서 제외)."""
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    if settlement.status == "CANCELLED":
        return []

    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
    ).all()

    return [
        {
            "participant_id": p.id,
            "name": p.display_name,
            "amount": int(p.amount),
            "status": p.status,
        }
        for p in participants
    ]


def calculate_debts(db: Session, settlement_id, current_user) -> Optional[list]:
    """채무 관계 (미수금) 계산. PENDING 참여자만 반환 (SETTLED 는 이미 송금받음 → 미수금 아님).

    CANCELLED 정산은 빈 배열 (실부담액 계산에서 제외).
    creator name 은 User 테이블에서 직접 조회 (creator는 participants에 없음).
    """
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    if settlement.status == "CANCELLED":
        return []

    # creator name 조회
    creator_user = db.query(User).filter(User.id == settlement.creator_id).first()
    creator_name = creator_user.name if creator_user else "creator"

    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id,
        models.SettlementParticipant.status == "PENDING",
    ).all()

    return [
        {
            "participant_id": p.id,
            "from": p.display_name,
            "to": creator_name,
            "amount": int(p.amount),
        }
        for p in participants
    ]


def mark_settlement_complete(db: Session, settlement_id, current_user):
    """정산 전체 완료 처리. 빈 참여자 / 미완료 참여자 가드. creator에게 COMPLETED 알림."""
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
    ).all()

    if not participants:
        raise HTTPException(
            status_code=400,
            detail="참여자가 없습니다",
        )

    if any(p.status != "SETTLED" for p in participants):
        return "NOT_ALL_SETTLED"

    was_already_completed = settlement.status == "COMPLETED"
    settlement.status = "COMPLETED"

    db.commit()
    db.refresh(settlement)

    if not was_already_completed:
        create_notification(
            db,
            settlement.creator_id,
            "SETTLEMENT_COMPLETED",
            f"정산이 완료되었습니다 ({int(settlement.total_amount):,}원)",
        )

    return settlement


def revert_completion(db: Session, settlement_id, current_user):
    """COMPLETED → PENDING 복원."""
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    if settlement.status != "COMPLETED":
        return "NOT_COMPLETED"

    settlement.status = "PENDING"

    db.commit()
    db.refresh(settlement)

    return settlement


def mark_participant_settled(db: Session, settlement_id, participant_id, current_user):
    """참여자 SETTLED 처리. creator 또는 회원 참여자 본인이 호출 가능. 마지막 SETTLED 시 정산 자동 COMPLETED."""
    participant = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.id == participant_id,
        models.SettlementParticipant.settlement_id == settlement_id,
    ).first()

    if not participant:
        return None

    settlement = db.query(models.Settlement).filter(
        models.Settlement.id == settlement_id
    ).first()

    if not settlement:
        return None

    is_creator = settlement.creator_id == current_user.id
    is_participant_self = participant.user_id == current_user.id
    if not is_creator and not is_participant_self:
        return None

    if settlement.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"{settlement.status} 정산의 참여자는 수정할 수 없습니다",
        )

    participant.status = "SETTLED"
    participant.settled_at = datetime.utcnow()
    db.flush()

    # 모든 참여자 SETTLED 인지 체크 → 자동 COMPLETED
    all_participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement.id
    ).all()

    auto_completed = False
    if all_participants and all(p.status == "SETTLED" for p in all_participants):
        settlement.status = "COMPLETED"
        auto_completed = True

    db.commit()
    db.refresh(participant)

    if auto_completed:
        create_notification(
            db,
            settlement.creator_id,
            "SETTLEMENT_COMPLETED",
            f"정산이 완료되었습니다 ({int(settlement.total_amount):,}원)",
        )

    return participant


def revert_participant(db: Session, settlement_id, participant_id, current_user):
    """참여자 SETTLED → PENDING 복원. creator 또는 회원 참여자 본인이 호출 가능."""
    participant = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.id == participant_id,
        models.SettlementParticipant.settlement_id == settlement_id,
    ).first()

    if not participant:
        return None

    settlement = db.query(models.Settlement).filter(
        models.Settlement.id == settlement_id
    ).first()

    if not settlement:
        return None

    is_creator = settlement.creator_id == current_user.id
    is_participant_self = participant.user_id == current_user.id
    if not is_creator and not is_participant_self:
        return None

    if participant.status != "SETTLED":
        return "NOT_SETTLED"

    participant.status = "PENDING"
    participant.settled_at = None

    # 정산이 COMPLETED 였으면 PENDING 으로 복귀
    if settlement.status == "COMPLETED":
        settlement.status = "PENDING"

    db.commit()
    db.refresh(participant)

    return participant


def get_participants_status(db: Session, settlement_id, current_user):
    """본인 정산의 참여자 목록 조회. 권한 검증 포함."""
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
    ).all()

    return participants


def remove_participant(db: Session, settlement_id, participant_id, current_user):
    """참여자 제거. SETTLED 참여자는 차단."""
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    _ensure_modifiable(settlement)

    participant = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.id == participant_id,
        models.SettlementParticipant.settlement_id == settlement_id,
    ).first()

    if not participant:
        return None

    if participant.status == "SETTLED":
        raise HTTPException(
            status_code=400,
            detail="송금 완료된 참여자는 제거할 수 없습니다. revert 후 시도하세요",
        )

    db.delete(participant)
    db.commit()

    return True


def get_settlement(db: Session, settlement_id, current_user):
    """본인 정산 상세 조회. 권한 검증 포함."""
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
    ).all()

    return {
        "id": settlement.id,
        "transaction_id": settlement.transaction_id,
        "creator_id": settlement.creator_id,
        "total_amount": int(settlement.total_amount),
        "split_type": settlement.split_type,
        "status": settlement.status,
        "created_at": settlement.created_at,
        "participants": participants,
    }


def update_settlement(
    db: Session, settlement_id, update_data: schemas.SettlementUpdate, current_user
):
    """정산 split_type 변경. COMPLETED 정산은 차단."""
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    _ensure_modifiable(settlement)

    if update_data.split_type is not None:
        settlement.split_type = update_data.split_type

    db.commit()
    db.refresh(settlement)

    return settlement


def delete_settlement(db: Session, settlement_id, current_user):
    """정산 삭제. COMPLETED 정산은 차단 (revert 먼저). CASCADE로 참여자 자동 삭제."""
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    if settlement.status == "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="완료된 정산은 삭제할 수 없습니다. revert 후 시도하세요",
        )

    db.delete(settlement)
    db.commit()

    return settlement


def cancel_settlement(db: Session, settlement_id, current_user):
    """정산 취소. status를 CANCELLED로 변경 + 모든 참여자 상태 초기화 (PENDING + settled_at NULL).

    기록 보존, 실부담액 계산에서 제외.
    COMPLETED 정산은 차단 (revert 먼저).
    """
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    if settlement.status == "CANCELLED":
        return settlement

    if settlement.status == "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="완료된 정산은 취소할 수 없습니다. revert 후 시도하세요",
        )

    settlement.status = "CANCELLED"

    # 모든 참여자 상태 초기화 (PENDING + settled_at NULL)
    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
    ).all()
    for p in participants:
        p.status = "PENDING"
        p.settled_at = None

    db.commit()
    db.refresh(settlement)

    return settlement


def get_active_settlement_by_transaction(db: Session, transaction_id):
    """거래에 연결된 비-CANCELLED 정산 조회 (없으면 None)."""
    return db.query(models.Settlement).filter(
        models.Settlement.transaction_id == transaction_id,
        models.Settlement.status != "CANCELLED",
    ).first()


def update_settlement_total(db: Session, transaction_id, new_amount: int) -> None:
    """거래 amount 변경 시 연결된 정산의 total + 참여자 amount 재분배.

    CANCELLED 정산은 무시. COMPLETED 정산은 차단 (revert 먼저).
    SETTLED 참여자 amount는 유지 (송금 완료 사실 보존).
    EQUAL: 미정산 참여자 + creator 가 잔여 금액 균등 재분배.
    CUSTOM: 미정산 참여자 amount 0으로 초기화 (사용자 재입력 필요).
    재분배 후 creator 몫 < 0 이면 400.
    """
    settlement = get_active_settlement_by_transaction(db, transaction_id)
    if not settlement:
        return

    if settlement.status == "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="완료된 정산이 연결된 거래는 금액을 변경할 수 없습니다. revert 후 시도하세요",
        )

    settlement.total_amount = new_amount

    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement.id
    ).all()

    if settlement.split_type == "EQUAL":
        settled_total = sum(int(p.amount) for p in participants if p.status == "SETTLED")
        non_settled = [p for p in participants if p.status != "SETTLED"]
        remaining_pool = new_amount - settled_total
        if remaining_pool < 0:
            raise HTTPException(
                status_code=400,
                detail="이미 정산된 금액보다 작게 변경할 수 없습니다",
            )
        n_remaining = len(non_settled) + 1  # creator 포함
        per_person = remaining_pool // n_remaining
        for p in non_settled:
            p.amount = per_person
    else:  # CUSTOM
        for p in participants:
            if p.status != "SETTLED":
                p.amount = 0

    db.flush()
    _validate_creator_share(db, settlement.id)


def get_user_settlements(db: Session, current_user, role: Optional[str] = None):
    """사용자 정산 목록 조회.

    role=None or "creator": 본인이 만든 정산 (default)
    role="participant": 본인이 참여자로 들어있는 정산
    """
    if role == "participant":
        # SettlementParticipant.user_id == current_user.id 인 정산
        return (
            db.query(models.Settlement)
            .join(
                models.SettlementParticipant,
                models.SettlementParticipant.settlement_id == models.Settlement.id,
            )
            .filter(models.SettlementParticipant.user_id == current_user.id)
            .order_by(models.Settlement.created_at.desc())
            .all()
        )

    # default: creator
    return (
        db.query(models.Settlement)
        .filter(models.Settlement.creator_id == current_user.id)
        .order_by(models.Settlement.created_at.desc())
        .all()
    )
