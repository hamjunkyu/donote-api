"""예산 서비스 로직."""

import uuid
from typing import List, Optional, Dict
from datetime import datetime, date
from sqlalchemy import select, delete, func, and_
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.budgets.models import Budget
from app.transactions.models import Transaction
from app.categories.models import Category
from app.notifications.service import create_notification


def upsert_budget(db: Session, user_id: uuid.UUID, year_month: str, amount: float, category_id: Optional[uuid.UUID] = None) -> Budget:
    """예산을 생성하거나 이미 존재하면 업데이트한다."""
    # 1. 카테고리 권한 체크
    if category_id:
        category = db.get(Category, category_id)
        if not category:
            raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
        if category.user_id is not None and category.user_id != user_id:
            raise HTTPException(status_code=403, detail="해당 카테고리에 대한 권한이 없습니다.")

    # 2. upsert 로직 (try/except + retry 패턴으로 Race Condition 완벽 대응)
    # category_id가 NULL인 경우 PostgreSQL Unique 제약조건의 NULL distinct 동작 방어 포함
    for attempt in range(3):  # 최대 3번 시도
        try:
            # select_for_update()를 사용하여 race condition 최소화
            budget = db.scalar(
                select(Budget)
                .where(
                    Budget.user_id == user_id,
                    Budget.year_month == year_month,
                    Budget.category_id == category_id
                )
                .with_for_update()
            )
            
            if budget:
                budget.amount = amount
                budget.is_warning_notified = False
                budget.is_exceeded_notified = False
            else:
                budget = Budget(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    year_month=year_month,
                    amount=amount,
                    category_id=category_id,
                    is_warning_notified=False,
                    is_exceeded_notified=False
                )
                db.add(budget)
            
            db.commit()
            db.refresh(budget)
            return budget
        except Exception as e:
            db.rollback()
            if attempt == 2:
                raise e


def delete_budget(db: Session, user_id: uuid.UUID, budget_id: uuid.UUID) -> bool:
    """예산을 삭제한다."""
    stmt = delete(Budget).where(Budget.id == budget_id, Budget.user_id == user_id)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount > 0


def get_budget_usage(db: Session, user_id: uuid.UUID, year_month: str) -> Dict:
    """특정 월의 예산 소진 현황을 조회한다."""
    # 1. 모든 예산 설정 가져오기 (Category Join으로 N+1 방지)
    stmt = (
        select(Budget, Category.name.label("category_name"))
        .outerjoin(Category, Category.id == Budget.category_id)
        .where(Budget.user_id == user_id, Budget.year_month == year_month)
    )
    results = db.execute(stmt).all()

    # 2. 해당 월의 모든 지출(EXPENSE) 거래 가져오기
    start_date = datetime.strptime(year_month, "%Y-%m").date()
    if start_date.month == 12:
        end_date = date(start_date.year + 1, 1, 1)
    else:
        end_date = date(start_date.year, start_date.month + 1, 1)

    expenses = db.execute(
        select(Transaction.category_id, func.sum(Transaction.amount).label("total"))
        .where(
            Transaction.user_id == user_id,
            Transaction.type == "EXPENSE",
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date < end_date
        )
        .group_by(Transaction.category_id)
    ).all()

    expense_map = {row.category_id: float(row.total) for row in expenses}
    total_spent = sum(expense_map.values())

    # 3. 데이터 조립
    budgets_list = []
    overall_item = None
    category_items = []

    for row in results:
        budget_obj = row.Budget
        cat_name = row.category_name
        
        if budget_obj.category_id is None:
            overall_item = (budget_obj, total_spent)
        else:
            spent = expense_map.get(budget_obj.category_id, 0.0)
            category_items.append((budget_obj, cat_name, spent))

    def format_usage(budget_obj, spent, cat_name=None):
        amount = float(budget_obj.amount) if budget_obj else 0.0
        remaining = max(amount - spent, 0.0)
        percentage = (spent / amount * 100) if amount > 0 else 0.0
        
        status = "SAFE"
        if percentage >= 100:
            status = "EXCEEDED"
        elif percentage >= 80:
            status = "WARNING"
            
        return {
            "budget_id": budget_obj.id,
            "category_id": budget_obj.category_id,
            "category": cat_name,  # 전체일 때는 None(null)
            "label": cat_name if cat_name else "전체",
            "budget": amount,
            "spent": spent,
            "remaining": remaining,
            "usage_rate": round(percentage, 2),
            "status": status
        }

    # 전체 예산이 있는 경우에만 최상단에 추가 (overall = None 처리)
    if overall_item:
        budgets_list.append(format_usage(overall_item[0], overall_item[1]))
        
    for b_obj, cat_name, spent in category_items:
        budgets_list.append(format_usage(b_obj, spent, cat_name))

    return {
        "year_month": year_month,
        "budgets": budgets_list
    }


def check_and_notify_budget_threshold(db: Session, user_id: uuid.UUID, transaction_date: date):
    """지출 변경 시 예산 임계값을 확인하고 알림을 생성한다."""
    year_month = transaction_date.strftime("%Y-%m")
    
    # 1. 해당 월의 모든 예산 설정 로드 (Category Join으로 N+1 방지)
    stmt = (
        select(Budget, Category.name.label("category_name"))
        .outerjoin(Category, Category.id == Budget.category_id)
        .where(Budget.user_id == user_id, Budget.year_month == year_month)
    )
    results = db.execute(stmt).all()
    if not results:
        return
        
    # 2. 해당 월의 지출 데이터 계산
    start_date = datetime.strptime(year_month, "%Y-%m").date()
    if start_date.month == 12:
        end_date = date(start_date.year + 1, 1, 1)
    else:
        end_date = date(start_date.year, start_date.month + 1, 1)

    expenses = db.execute(
        select(Transaction.category_id, func.sum(Transaction.amount).label("total"))
        .where(
            Transaction.user_id == user_id,
            Transaction.type == "EXPENSE",
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date < end_date
        )
        .group_by(Transaction.category_id)
    ).all()

    expense_map = {row.category_id: float(row.total) for row in expenses}
    total_spent = sum(expense_map.values())
    
    # 3. 예산 소진율에 따른 알림 트리거 및 플래그 관리 (재발화)
    for row in results:
        budget = row.Budget
        cat_name = row.category_name
        
        # spent 결정
        if budget.category_id is None:
            spent = total_spent
            label = "전체"
        else:
            spent = expense_map.get(budget.category_id, 0.0)
            label = cat_name if cat_name else "카테고리"
            
        amount = float(budget.amount)
        if amount <= 0:
            continue
            
        percentage = (spent / amount * 100)
        
        # 100% 초과(EXCEEDED) 알림
        if percentage >= 100:
            if not budget.is_exceeded_notified:
                msg = (
                    f"이번달 예산이 100% 사용되었습니다. (예산: {amount:,.0f}원)"
                    if budget.category_id is None
                    else f"이번달 {label} 예산이 100% 사용되었습니다. (예산: {amount:,.0f}원)"
                )
                create_notification(db, user_id, "BUDGET_EXCEEDED", msg)
                budget.is_exceeded_notified = True
                db.commit()
        else:
            # 100% 아래로 떨어지면 리셋 (재발화 가능)
            if budget.is_exceeded_notified:
                budget.is_exceeded_notified = False
                db.commit()
                
        # 80% 초과(WARNING) 알림
        if percentage >= 80:
            if not budget.is_warning_notified:
                msg = (
                    "이번달 예산이 80% 사용되었습니다."
                    if budget.category_id is None
                    else f"이번달 {label} 예산이 80% 사용되었습니다."
                )
                create_notification(db, user_id, "BUDGET_WARNING", msg)
                budget.is_warning_notified = True
                db.commit()
        else:
            # 80% 아래로 떨어지면 리셋 (재발화 가능)
            if budget.is_warning_notified:
                budget.is_warning_notified = False
                db.commit()
