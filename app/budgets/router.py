from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import uuid
from datetime import datetime

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.budgets import schemas, service

router = APIRouter(prefix="/api/budgets", tags=["Budgets"])


@router.post("", response_model=schemas.BudgetResponse)
def set_budget(
    budget_in: schemas.BudgetCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """예산을 설정하거나 업데이트한다."""
    return service.upsert_budget(
        db, current_user.id, budget_in.year_month, budget_in.amount, budget_in.category_id
    )


@router.get("/{year_month}", response_model=schemas.BudgetSummaryResponse)
def get_budget_usage(
    year_month: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """특정 월의 예산 요약 및 소진율을 조회한다."""
    try:
        datetime.strptime(year_month, "%Y-%m")
    except ValueError:
        raise HTTPException(status_code=400, detail="year_month는 'YYYY-MM' 형식이어야 합니다.")
    
    return service.get_budget_usage(db, current_user.id, year_month)


@router.delete("/{budget_id}")
def delete_budget(
    budget_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """설정된 예산을 삭제한다."""
    success = service.delete_budget(db, current_user.id, budget_id)
    if not success:
        raise HTTPException(status_code=404, detail="예산을 찾을 수 없습니다.")
    return {"message": "예산이 삭제되었습니다."}
