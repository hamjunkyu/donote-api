"""저축 목표 API 라우터."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.shared.schemas import PaginatedResponse
from app.goals import schemas, service


router = APIRouter(prefix="/api/goals", tags=["Goals"])


def _map_goal_response(goal_dto: dict) -> schemas.GoalResponse:
    """service 의 dict DTO 를 schemas.GoalResponse 로 변환."""
    return schemas.GoalResponse(
        id=goal_dto["id"],
        user_id=goal_dto["user_id"],
        name=goal_dto["name"],
        target_amount=goal_dto["target_amount"],
        target_date=goal_dto["target_date"],
        description=goal_dto["description"],
        status=goal_dto["status"],
        created_at=goal_dto["created_at"],
        achieved_at=goal_dto["achieved_at"],
        current_amount=goal_dto["current_amount"],
        progress_percentage=goal_dto["progress_percentage"],
        remaining_amount=goal_dto["remaining_amount"],
        on_track=goal_dto["on_track"],
    )


@router.post("/", response_model=schemas.GoalResponse, status_code=201)
def create_goal(
    goal: schemas.GoalCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """새로운 저축 목표 생성."""
    new_goal = service.create_goal(db, current_user.id, goal)
    return _map_goal_response(new_goal)


@router.get("/", response_model=PaginatedResponse[schemas.GoalResponse])
def get_goals(
    status: Literal["IN_PROGRESS", "ACHIEVED", "EXPIRED", "CANCELLED"] | None = Query(
        default=None,
        description="목표 상태 필터 (IN_PROGRESS/ACHIEVED/EXPIRED/CANCELLED)",
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """저축 목표 조회. status 파라미터로 생애주기 상태별 필터링 가능."""
    res = service.get_goals(db, current_user.id, status, limit, offset)
    res["items"] = [_map_goal_response(g) for g in res["items"]]
    return res


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


@router.post(
    "/{goal_id}/contributions",
    response_model=schemas.ContributionResponse,
    status_code=201,
)
def add_contribution(
    goal_id: uuid.UUID,
    contribution: schemas.ContributionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """목표에 적립을 추가한다 (진행률·마일스톤·달성 알림 자동 갱신)."""
    result = service.create_contribution(db, goal_id, current_user.id, contribution)
    if result is None:
        raise HTTPException(status_code=404, detail="목표를 찾을 수 없습니다")
    return result


@router.get(
    "/{goal_id}/contributions",
    response_model=PaginatedResponse[schemas.ContributionResponse],
)
def get_contributions(
    goal_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """목표의 적립 내역을 최신순으로 조회."""
    res = service.list_contributions(db, goal_id, current_user.id, limit, offset)
    if res is None:
        raise HTTPException(status_code=404, detail="목표를 찾을 수 없습니다")
    return res


@router.delete(
    "/{goal_id}/contributions/{contribution_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
def remove_contribution(
    goal_id: uuid.UUID,
    contribution_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """적립을 취소(삭제)하고 진행률을 재평가한다."""
    result = service.delete_contribution(db, goal_id, contribution_id, current_user.id)
    if result is None:
        raise HTTPException(status_code=404, detail="목표를 찾을 수 없습니다")
    if result is False:
        raise HTTPException(status_code=404, detail="적립 내역을 찾을 수 없습니다")
    return None


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
    """저축 목표 월별 적립액 추이 조회."""
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
            detail="목표를 찾을 수 없거나 취소할 수 없는 상태입니다",
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
