"""저축 목표 API 라우터."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.goals import schemas, service


router = APIRouter(prefix="/api/goals", tags=["Goals"])


def _map_goal_response(goal_dto: dict) -> schemas.GoalResponse:
    """10번 피드백: service로부터 dynamic attribute가 부착된 ORM 대신 정밀 가공된 DTO를 건네받아,
    schemas.GoalResponse 객체로 안전하고 정적으로 빌드하여 반환합니다."""
    return schemas.GoalResponse(
        id=goal_dto["id"],
        user_id=goal_dto["user_id"],
        name=goal_dto["name"],
        target_amount=goal_dto["target_amount"],
        target_date=goal_dto["target_date"],
        category_id=goal_dto["category_id"],
        description=goal_dto["description"],
        status=goal_dto["status"],
        created_at=goal_dto["created_at"],
        achieved_at=goal_dto["achieved_at"],
        current_amount=goal_dto["current_amount"],
        progress_percentage=goal_dto["progress_percentage"],
        remaining_amount=goal_dto["remaining_amount"],
    )


@router.post("/", response_model=schemas.GoalResponse, status_code=201)
def create_goal(
    goal: schemas.GoalCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """새로운 저축 목표 생성."""
    new_goal = service.create_goal(db, current_user.id, goal)

    if not new_goal:
        raise HTTPException(
            status_code=400,
            detail="유효하지 않거나 권한이 없는 카테고리입니다",
        )

    return _map_goal_response(new_goal)


@router.get("/", response_model=list[schemas.GoalResponse])
def get_goals(
    status: Literal["ACHIEVED", "EXPIRED", "CANCELLED", "ON_TRACK", "BEHIND"] | None = Query(
        default=None,
        description="목표 상태 필터 (ACHIEVED/EXPIRED/CANCELLED/ON_TRACK/BEHIND)",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """저축 목표 조회. status 파라미터로 상태별 필터링 가능 (예: 달성 내역은 status=ACHIEVED, 뒤처짐은 status=BEHIND)."""
    goals = service.get_goals(db, current_user.id, status)
    return [_map_goal_response(g) for g in goals]


@router.get("/{goal_id}", response_model=schemas.GoalResponse)
def get_goal(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """특정 저축 목표 상세 조회."""
    goal = service.get_goal_by_id(db, goal_id, current_user.id)

    if not goal:
        raise HTTPException(status_code=404, detail="목표를 찾을 수 없습니다")

    return _map_goal_response(goal)


@router.get("/{goal_id}/progress", response_model=schemas.GoalProgressResponse)
def get_goal_progress(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """저축 목표 진행률 조회 (진행률, 남은 금액, 남은 기간, 상태)."""
    progress = service.get_goal_progress(db, goal_id, current_user.id)

    if not progress:
        raise HTTPException(status_code=404, detail="목표를 찾을 수 없습니다")

    return progress


@router.get(
    "/{goal_id}/transactions",
    response_model=list[schemas.ContributingTransactionResponse],
)
def get_goal_transactions(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """저축 목표 달성에 기여한 거래 내역을 시간순으로 조회."""
    transactions = service.get_contributing_transactions(
        db, goal_id, current_user.id
    )

    if transactions is None:
        raise HTTPException(status_code=404, detail="목표를 찾을 수 없습니다")

    return transactions


@router.get("/{goal_id}/forecast", response_model=schemas.GoalForecastResponse)
def get_goal_forecast(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """저축 목표 예상 달성일 조회."""
    forecast = service.forecast_completion(db, goal_id, current_user.id)

    if not forecast:
        raise HTTPException(status_code=404, detail="목표를 찾을 수 없습니다")

    return forecast


@router.get(
    "/{goal_id}/monthly-trend",
    response_model=schemas.GoalMonthlyTrendResponse,
)
def get_goal_monthly_trend(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """저축 목표 월별 저축액 추이 조회."""
    trend = service.get_monthly_trend(db, goal_id, current_user.id)

    if trend is None:
        raise HTTPException(status_code=404, detail="목표를 찾을 수 없습니다")

    return {"goal_id": goal_id, "trend": trend}


@router.patch("/{goal_id}/cancel", response_model=schemas.GoalResponse)
def cancel_goal(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """진행 중인 저축 목표를 취소 상태로 변경 (삭제와 달리 기록 보존)."""
    goal = service.cancel_goal(db, goal_id, current_user.id)

    if not goal:
        raise HTTPException(
            status_code=404,
            detail="목표를 찾을 수 없거나 진행 중이 아닙니다",
        )

    return _map_goal_response(goal)


@router.patch("/{goal_id}", response_model=schemas.GoalResponse)
def update_goal(
    goal_id: uuid.UUID,
    goal_update: schemas.GoalUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """저축 목표 부분 수정."""
    goal = service.update_goal(db, goal_id, current_user.id, goal_update)

    if not goal:
        raise HTTPException(status_code=404, detail="목표를 찾을 수 없습니다")

    return _map_goal_response(goal)


@router.delete("/{goal_id}")
def delete_goal(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """저축 목표 영구 삭제."""
    goal = service.delete_goal(db, goal_id, current_user.id)

    if not goal:
        raise HTTPException(status_code=404, detail="목표를 찾을 수 없습니다")

    return {"message": "목표가 성공적으로 삭제되었습니다"}
