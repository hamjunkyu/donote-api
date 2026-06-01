"""저축 목표 서비스 계층.

Goal 도메인의 CRUD + 진행률 계산 + 상태 자동 판정 비즈니스 로직 처리.
"""

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.categories.models import Category
from app.goals.models import Goal
from app.goals.schemas import GoalCreate, GoalUpdate
from app.notifications.service import create_notification
from app.transactions.models import Transaction


# DB persist 대상 status (ON_TRACK/BEHIND 는 computed-only)
PERSIST_STATES = {"IN_PROGRESS", "ACHIEVED", "EXPIRED", "CANCELLED"}


def _goal_progress_subquery():
    """Goal.id 별 current_amount를 계산하는 correlated subquery."""
    return (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(
            Transaction.user_id == Goal.user_id,
            Transaction.category_id == Goal.category_id,
            Transaction.type == "EXPENSE",
            Transaction.created_at >= Goal.created_at,
        )
        .correlate(Goal)
        .scalar_subquery()
    )


def _to_goal_dto(goal: Goal, current_amount: float, computed_status: str) -> dict:
    """Goal ORM 객체 + 계산된 필드를 GoalResponse 매핑용 dict 로 변환."""
    target = float(goal.target_amount)
    progress_percentage = round((current_amount / target * 100) if target > 0 else 0.0, 2)
    remaining_amount = max(target - current_amount, 0)

    return {
        "id": goal.id,
        "user_id": goal.user_id,
        "name": goal.name,
        "target_amount": target,
        "target_date": goal.target_date,
        "category_id": goal.category_id,
        "description": goal.description,
        "status": computed_status,
        "created_at": goal.created_at,
        "achieved_at": goal.achieved_at,
        "current_amount": current_amount,
        "progress_percentage": progress_percentage,
        "remaining_amount": remaining_amount,
    }


def create_goal(
    db: Session, user_id: uuid.UUID, goal_data: GoalCreate
) -> dict | None:
    """새로운 저축 목표를 생성한다."""
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
        status="IN_PROGRESS",
    )

    db.add(new_goal)
    db.commit()
    db.refresh(new_goal)

    current_amount = 0.0
    computed_status = determine_status(new_goal, current_amount)

    return _to_goal_dto(new_goal, current_amount, computed_status)


def get_goals(
    db: Session,
    user_id: uuid.UUID,
    status: str | None = None,
    category_id: uuid.UUID | None = None,
    limit: int = 20,
    offset: int = 0
) -> dict:
    """사용자의 저축 목표를 최신순으로 조회한다."""
    progress_subq = _goal_progress_subquery()
    query = (
        db.query(Goal, progress_subq.label("current_amount"))
        .filter(Goal.user_id == user_id)
    )

    if category_id is not None:
        query = query.filter(Goal.category_id == category_id)

    query = query.order_by(Goal.created_at.desc(), Goal.id.desc())

    results = query.all()
    goals_list = []
    for goal, cur_amt in results:
        current_amount = float(cur_amt or 0)
        computed_status = determine_status(goal, current_amount)

        if computed_status in PERSIST_STATES and goal.status != computed_status:
            goal.status = computed_status
            if computed_status == "ACHIEVED" and not goal.achieved_at:
                goal.achieved_at = datetime.utcnow()
            db.commit()
            db.refresh(goal)

        dto = _to_goal_dto(goal, current_amount, computed_status)

        if status:
            if computed_status == status:
                goals_list.append(dto)
        else:
            goals_list.append(dto)

    total = len(goals_list)
    items = goals_list[offset:offset+limit]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }


def get_goal_by_id(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID
) -> dict | None:
    """특정 저축 목표를 조회하며 진행률 및 계산된 필드들을 포함시킵니다."""
    progress_subq = _goal_progress_subquery()
    result = (
        db.query(Goal, progress_subq.label("current_amount"))
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not result:
        return None

    goal, cur_amt = result
    current_amount = float(cur_amt or 0)
    computed_status = determine_status(goal, current_amount)

    if computed_status in PERSIST_STATES and goal.status != computed_status:
        goal.status = computed_status
        if computed_status == "ACHIEVED" and not goal.achieved_at:
            goal.achieved_at = datetime.utcnow()
        db.commit()
        db.refresh(goal)

    return _to_goal_dto(goal, current_amount, computed_status)


def update_goal(
    db: Session,
    goal_id: uuid.UUID,
    user_id: uuid.UUID,
    goal_update: GoalUpdate,
) -> dict | None:
    """저축 목표 정보를 부분 수정한다."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )

    if not goal:
        return None

    if goal_update.category_id is not None:
        category = (
            db.query(Category)
            .filter(
                Category.id == goal_update.category_id,
                (Category.user_id == None) | (Category.user_id == user_id),
            )
            .first()
        )
        if not category:
            return None
        goal.category_id = goal_update.category_id

    if goal_update.name is not None:
        goal.name = goal_update.name

    amount_changed = False
    date_changed = False

    if goal_update.target_amount is not None:
        if float(goal.target_amount) != float(goal_update.target_amount):
            goal.target_amount = goal_update.target_amount
            amount_changed = True

    if goal_update.target_date is not None:
        if goal.target_date != goal_update.target_date:
            goal.target_date = goal_update.target_date
            date_changed = True

    if goal_update.description is not None:
        goal.description = goal_update.description

    db.commit()
    db.refresh(goal)

    # target_amount / target_date 변경 시 마일스톤 flag reset + status 재평가
    current_amount = calculate_progress(db, goal)

    if amount_changed or date_changed:
        target = float(goal.target_amount)
        if target > 0:
            ratio = current_amount / target

            # (a) target_amount 변경 시 진행 비율 하락에 맞춰 마일스톤 플래그 리셋
            goal.is_25_notified = ratio >= 0.25
            goal.is_50_notified = ratio >= 0.50
            goal.is_75_notified = ratio >= 0.75

            if ratio >= 1.0:
                if not goal.is_achieved_notified:
                    goal.status = "ACHIEVED"
                    goal.achieved_at = datetime.utcnow()
                    goal.is_achieved_notified = True
            else:
                if goal.is_achieved_notified:
                    goal.status = "IN_PROGRESS"
                    goal.achieved_at = None
                    goal.is_achieved_notified = False

        # (b) target_date 변경 시 status 재평가 (EXPIRED 상태 연장/복구 등 대응)
        computed_status = determine_status(goal, current_amount)
        if computed_status in PERSIST_STATES and goal.status != computed_status:
            goal.status = computed_status
            if computed_status == "ACHIEVED" and not goal.achieved_at:
                goal.achieved_at = datetime.utcnow()
            elif computed_status != "ACHIEVED":
                goal.achieved_at = None

        db.commit()
        db.refresh(goal)

    current_amount = calculate_progress(db, goal)
    computed_status = determine_status(goal, current_amount)

    return _to_goal_dto(goal, current_amount, computed_status)


def calculate_progress(db: Session, goal: Goal) -> float:
    """연결 카테고리의 EXPENSE 거래 합계로 현재 누적 저축액을 계산한다."""
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
    """진행률과 시간 경과율을 비교하여 목표 상태를 판정한다."""
    if goal.status == "CANCELLED":
        return "CANCELLED"

    target = float(goal.target_amount)
    if target <= 0:
        return "ACHIEVED" if current_amount > 0 else "IN_PROGRESS"

    progress_ratio = current_amount / target

    if progress_ratio >= 1.0:
        return "ACHIEVED"

    if goal.target_date and goal.target_date < date.today():
        return "EXPIRED"

    if not goal.target_date:
        return "ON_TRACK"

    total_days = (goal.target_date - goal.created_at.date()).days
    elapsed_days = (date.today() - goal.created_at.date()).days

    if total_days <= 0:
        return "BEHIND"

    time_ratio = elapsed_days / total_days

    if progress_ratio >= time_ratio:
        return "ON_TRACK"
    return "BEHIND"


def get_goal_progress(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID
) -> dict | None:
    """특정 목표의 진행률 + 남은 금액 + 남은 기간 + 상태를 종합 조회한다."""
    progress_subq = _goal_progress_subquery()
    result = (
        db.query(Goal, progress_subq.label("current_amount"))
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not result:
        return None

    goal, cur_amt = result
    current_amount = float(cur_amt or 0)
    target = float(goal.target_amount)
    progress_percentage = (current_amount / target * 100) if target > 0 else 0.0
    remaining_amount = max(target - current_amount, 0)
    days_remaining = (
        (goal.target_date - date.today()).days if goal.target_date else None
    )
    status = determine_status(goal, current_amount)

    if status in PERSIST_STATES and goal.status != status:
        goal.status = status
        if status == "ACHIEVED" and not goal.achieved_at:
            goal.achieved_at = datetime.utcnow()
        elif status == "IN_PROGRESS":
            # get_goal_progress는 외부 노출용이므로 status는 유지하되 internal state sync용
            goal.achieved_at = None
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
    db: Session,
    goal_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0
) -> dict | None:
    """저축 목표 달성에 기여한 거래(연결 카테고리의 EXPENSE)를 시간순으로 조회한다."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not goal:
        return None

    query = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == goal.user_id,
            Transaction.category_id == goal.category_id,
            Transaction.type == "EXPENSE",
            Transaction.created_at >= goal.created_at,
        )
    )

    total = query.count()

    items = (
        query.order_by(Transaction.created_at.asc(), Transaction.id.asc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }


def forecast_completion(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID
) -> dict | None:
    """현재까지의 저축 페이스로 목표 달성 예상일을 예측한다."""
    progress_subq = _goal_progress_subquery()
    result = (
        db.query(Goal, progress_subq.label("current_amount"))
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not result:
        return None

    goal, cur_amt = result
    current_amount = float(cur_amt or 0)
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


def get_monthly_trend(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID
) -> list[dict] | None:
    """저축 목표의 월별 저축액 추이를 시간순으로 조회한다."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not goal:
        return None

    year_month_expr = func.to_char(Transaction.transaction_date, "YYYY-MM")

    rows = (
        db.query(
            year_month_expr.label("year_month"),
            func.coalesce(func.sum(Transaction.amount), 0).label("amount"),
        )
        .filter(
            Transaction.user_id == goal.user_id,
            Transaction.category_id == goal.category_id,
            Transaction.type == "EXPENSE",
            Transaction.created_at >= goal.created_at,
        )
        .group_by(year_month_expr)
        .order_by(year_month_expr.asc())
        .all()
    )

    return [
        {"year_month": row.year_month, "amount": float(row.amount)}
        for row in rows
    ]


def check_and_notify_goal_achievement(
    db: Session, user_id: uuid.UUID, category_id: uuid.UUID
) -> None:
    """거래 생성/수정/삭제 시 호출되어 해당 카테고리에 연결된 목표의 진행 상태를 확인하고,
    마일스톤 및 최종 달성 알림을 처리하고 상태를 갱신합니다.
    """
    progress_subq = _goal_progress_subquery()
    goals_with_progress = (
        db.query(Goal, progress_subq.label("current_amount"))
        .filter(
            Goal.user_id == user_id,
            Goal.category_id == category_id,
            Goal.status.in_(["IN_PROGRESS", "ACHIEVED"]),
        )
        .all()
    )

    for goal, cur_amt in goals_with_progress:
        current_amount = float(cur_amt or 0)
        target = float(goal.target_amount)
        if target <= 0:
            continue

        ratio = current_amount / target

        for threshold, flag in [
            (0.25, "is_25_notified"),
            (0.5, "is_50_notified"),
            (0.75, "is_75_notified"),
        ]:
            pct = int(threshold * 100)
            if ratio >= threshold:
                if not getattr(goal, flag):
                    setattr(goal, flag, True)
                    create_notification(
                        db,
                        user_id,
                        "GOAL_MILESTONE",
                        f"{goal.name} 목표 {pct}% 달성!",
                    )
            else:
                if getattr(goal, flag):
                    setattr(goal, flag, False)

        if ratio >= 1.0:
            if not goal.is_achieved_notified:
                goal.status = "ACHIEVED"
                goal.achieved_at = datetime.utcnow()
                goal.is_achieved_notified = True
                create_notification(
                    db,
                    user_id,
                    "GOAL_ACHIEVED",
                    f"🎉 목표 달성! {goal.name}",
                )
        else:
            if goal.is_achieved_notified:
                goal.status = "IN_PROGRESS"
                goal.achieved_at = None
                goal.is_achieved_notified = False

    db.commit()


def cancel_goal(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID
) -> dict | None:
    """진행 중인 저축 목표를 취소 상태(CANCELLED)로 변경한다."""
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

    current_amount = calculate_progress(db, goal)
    computed_status = determine_status(goal, current_amount)

    return _to_goal_dto(goal, current_amount, computed_status)


def delete_goal(db: Session, goal_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
    """저축 목표를 영구 삭제한다."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )

    if not goal:
        return None

    # 반환할 최종 데이터 구성
    current_amount = calculate_progress(db, goal)
    computed_status = determine_status(goal, current_amount)
    dto = _to_goal_dto(goal, current_amount, computed_status)

    db.delete(goal)
    db.commit()

    return dto
