from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import Literal

from app.database import get_db
# Temporary auth stub
async def get_current_user():
    return "00000000-0000-0000-0000-000000000001"

from . import schemas, service

router = APIRouter(prefix="/api/statistics", tags=["Statistics"])

@router.get("/summary", response_model=schemas.PeriodSummaryResponse)
def get_summary(
    period: Literal["daily", "weekly", "monthly"] = Query(...),
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from은 date_to보다 이전이어야 합니다")
        
    return service.get_period_summary(db, user_id, period, date_from, date_to)

@router.get("/categories", response_model=schemas.CategoryStatResponse)
def get_categories(
    date_from: date = Query(...),
    date_to: date = Query(...),
    type: Literal["INCOME", "EXPENSE"] = Query(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from은 date_to보다 이전이어야 합니다")
        
    return service.get_category_statistics(db, user_id, date_from, date_to, type)

@router.get("/monthly-report", response_model=schemas.MonthlyReportResponse)
def get_monthly_report(
    month: str = Query(..., description="YYYY-MM 형식"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise HTTPException(status_code=400, detail="month는 'YYYY-MM' 형식이어야 합니다")
        
    return service.get_monthly_report(db, user_id, month)
