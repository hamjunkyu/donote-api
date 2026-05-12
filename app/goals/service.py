"""저축 목표 서비스 계층.

Goal 도메인의 CRUD + 진행률 계산 + 상태 자동 판정 비즈니스 로직 처리.
"""

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.categories.models import Category
from app.goals.models import Goal
from app.goals.schemas import GoalCreate, GoalUpdate
from app.notifications.service import create_notification
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


def get_contributing_transactions(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID
) -> list[Transaction] | None:
    """저축 목표 달성에 기여한 거래(연결 카테고리의 EXPENSE)를 시간순으로 조회한다."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not goal:
        return None

    return (
        db.query(Transaction)
        .filter(
            Transaction.user_id == goal.user_id,
            Transaction.category_id == goal.category_id,
            Transaction.type == "EXPENSE",
            Transaction.created_at >= goal.created_at,
        )
        .order_by(Transaction.created_at.asc())
        .all()
    )


def forecast_completion(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID
) -> dict | None:
    """현재까지의 저축 페이스로 목표 달성 예상일을 예측한다.

    일평균 저축액 = 현재 누적 / 경과 일수
    예상 달성일 = 오늘 + (남은 금액 / 일평균)
    """
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not goal:
        return None

    current_amount = calculate_progress(db, goal)
    remaining_amount = max(float(goal.target_amount) - current_amount, 0)

    elapsed_days = max((date.today() - goal.created_at.date()).days, 1)
    daily_average = current_amount / elapsed_days

    if daily_average > 0 and remaining_amount > 0:
        days_to_achievement = int(remaining_amount / daily_average) + 1
        forecast_date = date.today() + timedelta(days=days_to_achievement)
    elif remaining_amount == 0:
        days_to_achievement = 0
        forecast_date = date.today()
    else:
        days_to_achievement = None
        forecast_date = None

    on_track = None
    if goal.target_date and forecast_date:
        on_track = forecast_date <= goal.target_date

    return {
        "goal_id": goal.id,
        "current_amount": current_amount,
        "target_amount": float(goal.target_amount),
        "remaining_amount": remaining_amount,
        "daily_average": round(daily_average, 2),
        "days_to_achievement": days_to_achievement,
        "forecast_date": forecast_date,
        "on_track": on_track,
    }


def check_and_notify_goal_achievement(
    db: Session, user_id: uuid.UUID, category_id: uuid.UUID
) -> None:
    """거래 생성/수정 시 호출되어 해당 카테고리에 연결된 목표의 달성 여부를 확인하고
    100% 도달 시 ACHIEVED 상태로 변경하고 알림을 생성한다.
    """
    goals = (
        db.query(Goal)
        .filter(
            Goal.user_id == user_id,
            Goal.category_id == category_id,
            Goal.status == "IN_PROGRESS",
        )
        .all()
    )

    for goal in goals:
        current_amount = calculate_progress(db, goal)
        if current_amount >= float(goal.target_amount):
            goal.status = "ACHIEVED"
            goal.achieved_at = datetime.utcnow()
            create_notification(
                db,
                user_id,
                "GOAL_ACHIEVED",
                f"🎉 목표 달성! {goal.name}",
            )

    db.commit()


def cancel_goal(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID
) -> Goal | None:
    """진행 중인 저축 목표를 취소 상태(CANCELLED)로 변경한다.

    삭제와 달리 기록은 보존되며, 이미 ACHIEVED/EXPIRED/CANCELLED 상태인 경우 None을 반환.
    """
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )

    if not goal:
        return None

    if goal.status != "IN_PROGRESS":
        return None

    goal.status = "CANCELLED"
    db.commit()
    db.refresh(goal)

    return goal


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
