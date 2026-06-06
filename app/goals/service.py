"""저축 목표 서비스 계층.

Goal 도메인의 CRUD + 적립(Contribution) 기반 진행률 계산 + 상태 자동 판정.
진행률은 명시적 적립(goal_contributions) 합계로만 계산하며, income/expense 거래와 무관하다.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.goals.models import Goal, GoalContribution
from app.goals.schemas import GoalCreate, GoalUpdate, ContributionCreate
from app.notifications.service import create_notification
from app.notifications.constants import NotificationType


def _contribution_sum_subquery():
    """Goal.id 별 적립 합계를 계산하는 correlated subquery."""
    return (
        select(func.coalesce(func.sum(GoalContribution.amount), 0))
        .where(GoalContribution.goal_id == Goal.id)
        .correlate(Goal)
        .scalar_subquery()
    )


def calculate_progress(db: Session, goal: Goal) -> float:
    """해당 목표의 적립 합계(현재 누적 저축액)를 계산한다."""
    total = (
        db.query(func.coalesce(func.sum(GoalContribution.amount), 0))
        .filter(GoalContribution.goal_id == goal.id)
        .scalar()
    )
    return float(total or 0)


def _compute_on_track(goal: Goal, current_amount: float) -> bool | None:
    """현재 적립 페이스로 목표일까지 달성 가능한지. 목표일 없으면 None.

    status(생애주기)와 분리된 '페이스' 지표. 목록·forecast 양쪽에서 사용.
    """
    if not goal.target_date:
        return None
    target = float(goal.target_amount)
    if current_amount >= target:
        return True
    today = datetime.utcnow().date()
    elapsed_days = max((today - goal.created_at.date()).days, 1)
    daily_average = current_amount / elapsed_days
    if daily_average <= 0:
        return None  # 적립 이력이 없어 페이스 판단 불가 (forecast 와 동일하게 미정)
    days_needed = int((target - current_amount) / daily_average) + 1
    return (today + timedelta(days=days_needed)) <= goal.target_date


def _to_goal_dto(goal: Goal, current_amount: float, computed_status: str) -> dict:
    """Goal ORM + 계산 필드를 GoalResponse 매핑용 dict 로 변환."""
    target = float(goal.target_amount)
    progress_percentage = round((current_amount / target * 100) if target > 0 else 0.0, 2)
    remaining_amount = max(target - current_amount, 0)

    return {
        "id": goal.id,
        "user_id": goal.user_id,
        "name": goal.name,
        "target_amount": target,
        "target_date": goal.target_date,
        "description": goal.description,
        "status": computed_status,
        "created_at": goal.created_at,
        "achieved_at": goal.achieved_at,
        "current_amount": current_amount,
        "progress_percentage": progress_percentage,
        "remaining_amount": remaining_amount,
        "on_track": _compute_on_track(goal, current_amount),
    }


def determine_status(goal: Goal, current_amount: float) -> str:
    """생애주기 상태를 판정한다 (IN_PROGRESS/ACHIEVED/EXPIRED/CANCELLED).

    페이스(on_track)는 status 와 분리해 별도로 계산한다.
    created_at(UTC) 기준과 맞추기 위해 today 도 UTC 로 비교한다.
    """
    if goal.status == "CANCELLED":
        return "CANCELLED"

    target = float(goal.target_amount)
    if target <= 0:
        return "ACHIEVED" if current_amount > 0 else "IN_PROGRESS"

    if current_amount / target >= 1.0:
        return "ACHIEVED"

    today = datetime.utcnow().date()
    if goal.target_date and goal.target_date < today:
        return "EXPIRED"

    return "IN_PROGRESS"


def _sync_status(db: Session, goal: Goal, current_amount: float) -> str:
    """계산된 생애주기 상태를 DB 에 반영하고 반환한다 (조회 시점 lazy sync).

    알림은 발생시키지 않는다 (조회는 부수효과 없이). 알림은 적립 변경 시
    check_and_notify_goal 에서만 처리한다.
    """
    computed = determine_status(goal, current_amount)
    if goal.status != computed:
        goal.status = computed
        if computed == "ACHIEVED":
            if not goal.achieved_at:
                goal.achieved_at = datetime.utcnow()
        else:
            goal.achieved_at = None
        db.commit()
        db.refresh(goal)
    return computed


def check_and_notify_goal(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID, commit: bool = True
) -> None:
    """적립 변경(추가/삭제) 후 진행률을 재계산해 마일스톤/달성 알림 + 상태를 갱신한다.

    동시 적립이 같은 목표의 알림 플래그를 동시에 읽어 중복 알림을 보내는 것을
    막기 위해 목표 행을 with_for_update 로 잠근다.
    commit=False 면 호출자가 단일 커밋으로 묶는다.
    """
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .with_for_update()
        .first()
    )
    if not goal or goal.status == "CANCELLED":
        return

    current_amount = calculate_progress(db, goal)
    target = float(goal.target_amount)
    ratio = (current_amount / target) if target > 0 else (1.0 if current_amount > 0 else 0.0)

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
                    db, user_id, NotificationType.GOAL_MILESTONE,
                    f"{goal.name} 목표 {pct}% 달성!", commit=False,
                )
        else:
            if getattr(goal, flag):
                setattr(goal, flag, False)

    if ratio >= 1.0:
        if not goal.is_achieved_notified:
            goal.is_achieved_notified = True
            create_notification(
                db, user_id, NotificationType.GOAL_ACHIEVED,
                f"🎉 목표 달성! {goal.name}", commit=False,
            )
        goal.status = "ACHIEVED"
        if not goal.achieved_at:
            goal.achieved_at = datetime.utcnow()
    else:
        if goal.is_achieved_notified:
            goal.is_achieved_notified = False
        goal.achieved_at = None
        # 달성 아래로 떨어지면 생애주기 상태 재판정 (EXPIRED or IN_PROGRESS)
        goal.status = determine_status(goal, current_amount)

    if commit:
        db.commit()


def create_goal(db: Session, user_id: uuid.UUID, goal_data: GoalCreate) -> dict:
    """새로운 저축 목표를 생성한다."""
    new_goal = Goal(
        user_id=user_id,
        name=goal_data.name,
        target_amount=goal_data.target_amount,
        target_date=goal_data.target_date,
        description=goal_data.description,
        status="IN_PROGRESS",
    )
    db.add(new_goal)
    db.commit()
    db.refresh(new_goal)

    return _to_goal_dto(new_goal, 0.0, determine_status(new_goal, 0.0))


def get_goals(
    db: Session,
    user_id: uuid.UUID,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """사용자의 저축 목표를 최신순으로 조회한다."""
    subq = _contribution_sum_subquery()
    results = (
        db.query(Goal, subq.label("current_amount"))
        .filter(Goal.user_id == user_id)
        .order_by(Goal.created_at.desc(), Goal.id.desc())
        .all()
    )

    goals_list = []
    for goal, cur_amt in results:
        current_amount = float(cur_amt or 0)
        computed_status = _sync_status(db, goal, current_amount)
        dto = _to_goal_dto(goal, current_amount, computed_status)
        if status:
            if computed_status == status:
                goals_list.append(dto)
        else:
            goals_list.append(dto)

    total = len(goals_list)
    items = goals_list[offset:offset + limit]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_goal_by_id(db: Session, goal_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
    """특정 저축 목표를 진행률 포함하여 조회한다."""
    subq = _contribution_sum_subquery()
    result = (
        db.query(Goal, subq.label("current_amount"))
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not result:
        return None

    goal, cur_amt = result
    current_amount = float(cur_amt or 0)
    computed_status = _sync_status(db, goal, current_amount)
    return _to_goal_dto(goal, current_amount, computed_status)


def update_goal(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID, goal_update: GoalUpdate
) -> dict | None:
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

    # target_amount / target_date 변경 시 마일스톤·달성·상태 재평가
    check_and_notify_goal(db, goal.id, user_id, commit=True)
    db.refresh(goal)

    current_amount = calculate_progress(db, goal)
    computed_status = _sync_status(db, goal, current_amount)
    return _to_goal_dto(goal, current_amount, computed_status)


def create_contribution(
    db: Session, goal_id: uuid.UUID, user_id: uuid.UUID, data: ContributionCreate
) -> dict | None:
    """목표에 적립을 추가하고 진행률·알림을 갱신한다."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not goal:
        return None

    contributed_at = data.contributed_at or datetime.utcnow().date()
    contribution = GoalContribution(
        goal_id=goal_id,
        amount=data.amount,
        memo=data.memo,
        contributed_at=contributed_at,
    )
    db.add(contribution)
    db.flush()  # ID 확보. commit 은 알림까지 끝낸 뒤 한 번만.

    check_and_notify_goal(db, goal_id, user_id, commit=False)
    db.commit()
    db.refresh(contribution)

    return {
        "id": contribution.id,
        "amount": float(contribution.amount),
        "memo": contribution.memo,
        "contributed_at": contribution.contributed_at,
        "created_at": contribution.created_at,
    }


def delete_contribution(
    db: Session, goal_id: uuid.UUID, contribution_id: uuid.UUID, user_id: uuid.UUID
) -> bool | None:
    """적립을 삭제하고 진행률·알림 플래그를 재평가한다.

    반환: None=목표 없음, False=적립 없음, True=삭제 성공.
    """
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not goal:
        return None

    contribution = (
        db.query(GoalContribution)
        .filter(
            GoalContribution.id == contribution_id,
            GoalContribution.goal_id == goal_id,
        )
        .first()
    )
    if not contribution:
        return False

    db.delete(contribution)
    db.flush()

    check_and_notify_goal(db, goal_id, user_id, commit=False)
    db.commit()
    return True


def get_goal_progress(db: Session, goal_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
    """특정 목표의 진행률 + 남은 금액 + 남은 기간 + 상태를 종합 조회한다."""
    subq = _contribution_sum_subquery()
    result = (
        db.query(Goal, subq.label("current_amount"))
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
        (goal.target_date - datetime.utcnow().date()).days if goal.target_date else None
    )
    status = _sync_status(db, goal, current_amount)

    return {
        "goal_id": goal.id,
        "target_amount": target,
        "current_amount": current_amount,
        "progress_percentage": round(progress_percentage, 2),
        "remaining_amount": remaining_amount,
        "days_remaining": days_remaining,
        "status": status,
    }


def list_contributions(
    db: Session,
    goal_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> dict | None:
    """목표의 적립 내역을 최신순으로 조회한다."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not goal:
        return None

    query = db.query(GoalContribution).filter(GoalContribution.goal_id == goal_id)
    total = query.count()
    items = (
        query.order_by(
            GoalContribution.contributed_at.desc(), GoalContribution.created_at.desc()
        )
        .limit(limit)
        .offset(offset)
        .all()
    )

    return {"items": items, "total": total, "limit": limit, "offset": offset}


def forecast_completion(db: Session, goal_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
    """현재까지의 적립 페이스로 목표 달성 예상일을 예측한다."""
    subq = _contribution_sum_subquery()
    result = (
        db.query(Goal, subq.label("current_amount"))
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not result:
        return None

    goal, cur_amt = result
    current_amount = float(cur_amt or 0)
    remaining_amount = max(float(goal.target_amount) - current_amount, 0)

    today = datetime.utcnow().date()
    elapsed_days = max((today - goal.created_at.date()).days, 1)
    daily_average = current_amount / elapsed_days

    if daily_average > 0 and remaining_amount > 0:
        days_to_achievement = int(remaining_amount / daily_average) + 1
        forecast_date = today + timedelta(days=days_to_achievement)
    elif remaining_amount == 0:
        days_to_achievement = 0
        forecast_date = today
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


def get_monthly_trend(db: Session, goal_id: uuid.UUID, user_id: uuid.UUID) -> list[dict] | None:
    """목표의 월별 적립액 추이를 시간순으로 조회한다."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not goal:
        return None

    year_month_expr = func.to_char(GoalContribution.contributed_at, "YYYY-MM")
    rows = (
        db.query(
            year_month_expr.label("year_month"),
            func.coalesce(func.sum(GoalContribution.amount), 0).label("amount"),
        )
        .filter(GoalContribution.goal_id == goal_id)
        .group_by(year_month_expr)
        .order_by(year_month_expr.asc())
        .all()
    )

    return [
        {"year_month": row.year_month, "amount": float(row.amount)}
        for row in rows
    ]


def cancel_goal(db: Session, goal_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
    """진행 중(또는 만료)인 목표를 취소 상태(CANCELLED)로 변경한다."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not goal:
        return None

    current_amount = calculate_progress(db, goal)
    computed = determine_status(goal, current_amount)
    if computed in ("ACHIEVED", "CANCELLED"):
        return None

    goal.status = "CANCELLED"
    db.commit()
    db.refresh(goal)

    return _to_goal_dto(goal, current_amount, "CANCELLED")


def reactivate_goal(db: Session, goal_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
    """취소된 목표를 다시 진행 상태로 되돌린다.

    CANCELLED 종료 상태를 해제한 뒤 적립 합계·마감일 기준으로 상태를 재판정한다
    (적립이 목표 이상이면 ACHIEVED, 마감일이 지났으면 EXPIRED, 그 외 IN_PROGRESS).
    취소 시 적립 기록은 보존되므로 재개하면 누적 진행률이 그대로 복원된다.
    반환: None=목표 없음 또는 취소 상태가 아님(재개 불가).
    """
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not goal or goal.status != "CANCELLED":
        return None

    goal.status = "IN_PROGRESS"
    db.flush()
    check_and_notify_goal(db, goal_id, user_id, commit=True)
    db.refresh(goal)

    current_amount = calculate_progress(db, goal)
    computed_status = _sync_status(db, goal, current_amount)
    return _to_goal_dto(goal, current_amount, computed_status)


def delete_goal(db: Session, goal_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
    """저축 목표를 영구 삭제한다 (적립은 FK CASCADE 로 함께 삭제)."""
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not goal:
        return None

    current_amount = calculate_progress(db, goal)
    computed = determine_status(goal, current_amount)
    dto = _to_goal_dto(goal, current_amount, computed)

    db.delete(goal)
    db.commit()
    return dto
