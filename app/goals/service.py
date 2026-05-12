"""저축 목표 서비스 계층.

Goal 도메인의 CRUD 비즈니스 로직 처리.
"""

import uuid

from sqlalchemy.orm import Session

from app.categories.models import Category
from app.goals.models import Goal
from app.goals.schemas import GoalCreate, GoalUpdate
from app.transactions.models import Transaction
from app.notifications.service import create_notification
from sqlalchemy import func
from datetime import datetime

def _attach_current_amount(db: Session, goal: Goal) -> Goal:
    if not goal:
        return goal
    total = db.query(func.sum(Transaction.amount)).filter(
        Transaction.category_id == goal.category_id,
        Transaction.user_id == goal.user_id
    ).scalar()
    goal.current_amount = float(total or 0.0)
    return goal

def check_and_notify_goal_achievement(db: Session, user_id: uuid.UUID, category_id: uuid.UUID):
    # Find active goals for this category
    goals = db.query(Goal).filter(
        Goal.user_id == user_id,
        Goal.category_id == category_id,
        Goal.status == "IN_PROGRESS"
    ).all()
    
    for goal in goals:
        _attach_current_amount(db, goal)
        if goal.current_amount >= goal.target_amount:
            goal.status = "ACHIEVED"
            goal.achieved_at = datetime.utcnow()
            create_notification(
                db, user_id, "GOAL_ACHIEVED",
                f"🎉 목표 달성! {goal.name}"
            )
    db.commit()


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

    return _attach_current_amount(db, new_goal)


def get_goals(db: Session, user_id: uuid.UUID) -> list[Goal]:
    """사용자의 모든 저축 목표를 최신순으로 조회한다."""
    goals = (
        db.query(Goal)
        .filter(Goal.user_id == user_id)
        .order_by(Goal.created_at.desc())
        .all()
    )
    for g in goals:
        _attach_current_amount(db, g)
    return goals


def get_goal_by_id(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID
) -> Goal | None:
    """특정 저축 목표를 조회한다."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    return _attach_current_amount(db, goal)


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

    return _attach_current_amount(db, goal)


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
