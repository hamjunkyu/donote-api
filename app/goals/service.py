"""저축 목표 서비스 계층.

Goal 도메인의 CRUD + 진행률 계산 + 상태 자동 판정 비즈니스 로직 처리.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.categories.models import Category
from app.goals.models import Goal
from app.goals.schemas import GoalCreate, GoalUpdate
from app.transactions.models import Transaction


def create_goal(
    db: Session, user_id: uuid.UUID, goal_data: GoalCreate
) -> Goal | None:
    """새로운 저축 목표를 생성한다.

    Args:
        db: 데이터베이스 세션.
        user_id: 목표 소유자 ID.
        goal_data: 생성 요청 데이터.

    Returns:
        생성된 Goal 객체. 카테고리 검증 실패 시 None.
    """
    category = (
        db.query(Category)
        .filter(
            Category.id == goal_data.category_id,
            (Category.user_id == None) | (Category.user_id == user_id),
        )
        .first()
    )
    if not category:
        return None

    new_goal = Goal(
        user_id=user_id,
        name=goal_data.name,
        target_amount=goal_data.target_amount,
        target_date=goal_data.target_date,
        category_id=goal_data.category_id,
        description=goal_data.description,
    )

    db.add(new_goal)
    db.commit()
    db.refresh(new_goal)

    return new_goal


def get_goals(db: Session, user_id: uuid.UUID) -> list[Goal]:
    """사용자의 모든 저축 목표를 최신순으로 조회한다."""
    return (
        db.query(Goal)
        .filter(Goal.user_id == user_id)
        .order_by(Goal.created_at.desc())
        .all()
    )


def get_goal_by_id(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID
) -> Goal | None:
    """특정 저축 목표를 조회한다."""
    return (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )


def update_goal(
    db: Session,
    goal_id: uuid.UUID,
    user_id: uuid.UUID,
    goal_update: GoalUpdate,
) -> Goal | None:
    """저축 목표 정보를 부분 수정한다."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )

    if not goal:
        return None

    if goal_update.name is not None:
        goal.name = goal_update.name
    if goal_update.target_amount is not None:
        goal.target_amount = goal_update.target_amount
    if goal_update.target_date is not None:
        goal.target_date = goal_update.target_date
    if goal_update.description is not None:
        goal.description = goal_update.description

    db.commit()
    db.refresh(goal)

    return goal


def calculate_progress(db: Session, goal: Goal) -> float:
    """연결 카테고리의 EXPENSE 거래 합계로 현재 누적 저축액을 계산한다.

    Args:
        db: 데이터베이스 세션.
        goal: 저축 목표 객체.

    Returns:
        목표 생성 후 누적된 EXPENSE 거래 합계.
    """
    total = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.user_id == goal.user_id,
            Transaction.category_id == goal.category_id,
            Transaction.type == "EXPENSE",
            Transaction.created_at >= goal.created_at,
        )
        .scalar()
    )
    return float(total or 0)


def determine_status(goal: Goal, current_amount: float) -> str:
    """진행률과 시간 경과율을 비교하여 목표 상태를 판정한다.

    상태:
      - ACHIEVED: 진행률 100% 이상
      - EXPIRED: 달성일 경과 + 미달성
      - ON_TRACK: 시간 경과율 ≤ 진행률 (계획대로 진행 중)
      - BEHIND: 시간 경과율 > 진행률 (뒤처짐)
    CANCELLED 상태는 그대로 유지한다.
    """
    if goal.status == "CANCELLED":
        return "CANCELLED"

    progress_ratio = current_amount / float(goal.target_amount)

    if progress_ratio >= 1.0:
        return "ACHIEVED"

    if goal.target_date and goal.target_date < date.today():
        return "EXPIRED"

    if not goal.target_date:
        return "ON_TRACK"

    total_days = (goal.target_date - goal.created_at.date()).days
    elapsed_days = (date.today() - goal.created_at.date()).days

    if total_days <= 0:
        return "ON_TRACK"

    time_ratio = elapsed_days / total_days

    if progress_ratio >= time_ratio:
        return "ON_TRACK"
    return "BEHIND"


def get_goal_progress(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID
) -> dict | None:
    """특정 목표의 진행률 + 남은 금액 + 남은 기간 + 상태를 종합 조회한다."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not goal:
        return None

    current_amount = calculate_progress(db, goal)
    progress_percentage = (current_amount / float(goal.target_amount)) * 100
    remaining_amount = max(float(goal.target_amount) - current_amount, 0)
    days_remaining = (
        (goal.target_date - date.today()).days if goal.target_date else None
    )
    status = determine_status(goal, current_amount)

    if goal.status != status:
        goal.status = status
        if status == "ACHIEVED" and not goal.achieved_at:
            goal.achieved_at = datetime.utcnow()
        db.commit()
        db.refresh(goal)

    return {
        "goal_id": goal.id,
        "target_amount": float(goal.target_amount),
        "current_amount": current_amount,
        "progress_percentage": round(progress_percentage, 2),
        "remaining_amount": remaining_amount,
        "days_remaining": days_remaining,
        "status": status,
    }


def delete_goal(db: Session, goal_id: uuid.UUID, user_id: uuid.UUID) -> Goal | None:
    """저축 목표를 영구 삭제한다."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )

    if not goal:
        return None

    db.delete(goal)
    db.commit()

    return goal
