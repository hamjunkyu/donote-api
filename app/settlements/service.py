"""더치페이 정산 비즈니스 로직.

핵심 디자인 결정:
- Creator NOT in participants (spec 6.3 ①). 본인 몫은 implicit (total - SUM(participants.amount)).
- split_equal: per_person = total // (N+1). 나머지는 creator 가 흡수.
- SettlementParticipant.amount는 정수 (Numeric(12,0)).
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


def _validate_creator_share(db: Session, settlement_id, exclude_participant_id=None) -> None:
    """내 몫 ≥ 0 검증. settlement.total_amount >= SUM(participants.amount)."""
    settlement = db.query(models.Settlement).filter(
        models.Settlement.id == settlement_id
    ).first()
    if not settlement:
        return

    query = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
    )
    if exclude_participant_id:
        query = query.filter(models.SettlementParticipant.id != exclude_participant_id)

    total_participants = sum(int(p.amount) for p in query.all())
    if total_participants > int(settlement.total_amount):
        raise HTTPException(
            status_code=400,
            detail=f"참여자 합계({total_participants})가 총액({int(settlement.total_amount)})을 초과합니다",
        )


def create_settlement(db: Session, settlement: schemas.SettlementCreate, current_user) -> Optional[models.Settlement]:
    """정산 생성. creator는 참여자로 추가하지 않음 (spec)."""
    transaction = db.query(transaction_models.Transaction).filter(
        transaction_models.Transaction.id == settlement.transaction_id,
        transaction_models.Transaction.user_id == current_user.id,
    ).first()

    if not transaction:
        return None

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

    # 내 몫 검증 (새 참여자 amount 포함)
    _validate_creator_share(db, settlement_id)

    db.commit()
    db.refresh(new_participant)

    # 회원 참여자에게 알림 발생 (D2 백엔드 부분)
    if participant.user_id is not None:
        create_notification(
            db,
            participant.user_id,
            "SETTLEMENT_REQUEST",
            f"{current_user.name}님이 {participant.amount:,}원 정산을 요청했습니다",
        )

    return new_participant


def split_equal(db: Session, settlement_id, current_user) -> Optional[list]:
    """균등 분배. per_person = total // (N+1). creator 가 나머지 흡수."""
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

    # SETTLED 참여자는 수정 차단 (재분배 영향)
    if any(p.status == "SETTLED" for p in participants):
        raise HTTPException(
            status_code=400,
            detail="SETTLED 참여자가 있어 재분배 불가. revert 후 다시 시도하세요",
        )

    total = int(settlement.total_amount)
    n_total = len(participants) + 1  # creator 포함
    per_person = total // n_total

    for p in participants:
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

    # 내 몫 ≥ 0 검증
    total_participants = sum(int(p.amount) for p in participants)
    if total_participants > int(settlement.total_amount):
        raise HTTPException(
            status_code=400,
            detail=f"참여자 합계({total_participants})가 총액({int(settlement.total_amount)})을 초과합니다",
        )

    settlement.split_type = "CUSTOM"

    db.commit()
    return participants


def edit_split(
    db: Session, settlement_id, split_data: schemas.CustomSplitRequest, current_user
) -> Optional[list]:
    """split_custom 별칭. PATCH /split/edit 호환."""
    return split_custom(db, settlement_id, split_data, current_user)


def get_balance(db: Session, settlement_id, current_user) -> Optional[list]:
    """본인 정산의 잔액 항목 조회. 권한 검증 포함."""
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

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
    """채무 관계 계산. creator name 은 User 테이블에서 직접 조회 (Decision A: creator는 participants에 없음)."""
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    # creator name 조회
    creator_user = db.query(User).filter(User.id == settlement.creator_id).first()
    creator_name = creator_user.name if creator_user else "creator"

    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
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
    """정산 전체 완료 처리. 빈 참여자 / 미완료 참여자 가드."""
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

    settlement.status = "COMPLETED"

    db.commit()
    db.refresh(settlement)

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


def mark_participant_settled(db: Session, participant_id, current_user):
    """참여자 SETTLED 처리. 마지막 SETTLED 시 정산 자동 COMPLETED."""
    participant = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.id == participant_id
    ).first()

    if not participant:
        return None

    settlement = db.query(models.Settlement).filter(
        models.Settlement.id == participant.settlement_id
    ).first()

    if not settlement or settlement.creator_id != current_user.id:
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

    if all_participants and all(p.status == "SETTLED" for p in all_participants):
        settlement.status = "COMPLETED"

    db.commit()
    db.refresh(participant)

    return participant


def revert_participant(db: Session, participant_id, current_user):
    """참여자 SETTLED → PENDING 복원."""
    participant = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.id == participant_id
    ).first()

    if not participant:
        return None

    settlement = db.query(models.Settlement).filter(
        models.Settlement.id == participant.settlement_id
    ).first()

    if not settlement or settlement.creator_id != current_user.id:
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
    """정산 삭제. CASCADE로 참여자 자동 삭제."""
    settlement = _get_owned_settlement(db, settlement_id, current_user)
    if not settlement:
        return None

    db.delete(settlement)
    db.commit()

    return settlement


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
