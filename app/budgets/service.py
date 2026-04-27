"""예산 서비스 로직."""

import uuid
from typing import List, Optional, Dict
from datetime import datetime, date
from sqlalchemy import select, delete, func, and_
from sqlalchemy.orm import Session

from app.budgets.models import Budget
from app.transactions.models import Transaction
from app.categories.models import Category
from app.notifications.service import create_notification


def upsert_budget(db: Session, user_id: uuid.UUID, year_month: str, amount: float, category_id: Optional[uuid.UUID] = None) -> Budget:
    """예산을 생성하거나 이미 존재하면 업데이트한다."""
    stmt = select(Budget).where(
        Budget.user_id == user_id,
        Budget.year_month == year_month,
        Budget.category_id == category_id
    )
    budget = db.scalar(stmt)

    if budget:
        budget.amount = amount
        # 예산 금액이 변경되면 알림 상태를 초기화할 수도 있지만, 
        # 여기서는 단순히 금액만 업데이트함.
    else:
        budget = Budget(
            user_id=user_id,
            year_month=year_month,
            amount=amount,
            category_id=category_id
        )
        db.add(budget)
    
    db.commit()
    db.refresh(budget)
    return budget


def delete_budget(db: Session, user_id: uuid.UUID, budget_id: uuid.UUID) -> bool:
    """예산을 삭제한다."""
    stmt = delete(Budget).where(Budget.id == budget_id, Budget.user_id == user_id)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount > 0


def get_budget_usage(db: Session, user_id: uuid.UUID, year_month: str) -> Dict:
    """특정 월의 예산 소진 현황을 조회한다."""
    # 1. 모든 예산 설정 가져오기
    budgets = db.scalars(
        select(Budget).where(Budget.user_id == user_id, Budget.year_month == year_month)
    ).all()

    # 2. 해당 월의 모든 지출(EXPENSE) 거래 가져오기
    # transaction_date가 해당 월인 것들
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
    overall_budget = next((b for b in budgets if b.category_id is None), None)
    category_budgets = [b for b in budgets if b.category_id is not None]

    def format_usage(budget_obj, spent):
        amount = float(budget_obj.amount) if budget_obj else 0.0
        percentage = (spent / amount * 100) if amount > 0 else 0.0
        status = "SAFE"
        if percentage >= 100:
            status = "EXCEEDED"
        elif percentage >= 80:
            status = "WARNING"
        
        return {
            "budget_id": budget_obj.id if budget_obj else None,
            "category_id": budget_obj.category_id if budget_obj else None,
            "budget_amount": amount,
            "spent_amount": spent,
            "usage_percentage": round(percentage, 2),
            "status": status
        }

    # 전체 예산 요약
    overall_data = format_usage(overall_budget, total_spent)
    
    # 카테고리별 예산 요약
    category_data = []
    for b in category_budgets:
        spent = expense_map.get(b.category_id, 0.0)
        item = format_usage(b, spent)
        # 카테고리 이름 추가
        cat = db.get(Category, b.category_id)
        item["category_name"] = cat.name if cat else "Unknown"
        category_data.append(item)

    return {
        "overall": overall_data,
        "categories": category_data
    }


def check_and_notify_budget_threshold(db: Session, user_id: uuid.UUID, transaction_date: date):
    """지출 변경 시 예산 임계값을 확인하고 알림을 생성한다."""
    year_month = transaction_date.strftime("%Y-%m")
    
    # 해당 월의 전체 예산 및 지출 확인
    usage = get_budget_usage(db, user_id, year_month)
    overall = usage["overall"]
    
    if not overall["budget_id"]:
        return

    budget = db.get(Budget, overall["budget_id"])
    if not budget:
        return

    # 100% 초과 확인
    if overall["usage_percentage"] >= 100 and not budget.is_exceeded_notified:
        create_notification(
            db, user_id, "BUDGET_EXCEEDED", 
            f"이번달 예산이 100% 사용되었습니다. (예산: {budget.amount:,.0f}원)"
        )
        budget.is_exceeded_notified = True
        db.commit()
    # 80% 초과 확인
    elif overall["usage_percentage"] >= 80 and not budget.is_warning_notified:
        create_notification(
            db, user_id, "BUDGET_WARNING", 
            "이번달 예산이 80% 사용되었습니다."
        )
        budget.is_warning_notified = True
        db.commit()
