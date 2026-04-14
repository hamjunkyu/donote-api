from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc, case
from app.transactions.models import Transaction
from app.settlements.models import Settlement, SettlementParticipant
from app.categories.models import Category
import calendar
from datetime import date

def _actual_amount_subquery():
    """
    거래의 실부담액을 계산하는 서브쿼리.
    """
    participant_sum = (
        select(func.coalesce(func.sum(SettlementParticipant.amount), 0))
        .join(Settlement, Settlement.id == SettlementParticipant.settlement_id)
        .where(
            Settlement.transaction_id == Transaction.id,
            Settlement.status != "CANCELLED",
        )
        .correlate(Transaction)
        .scalar_subquery()
    )
    return (Transaction.amount - participant_sum).label("actual_amount")

def get_period_summary(db: Session, user_id: str, period: str, date_from: date, date_to: date):
    if period == "daily":
        group_expr = func.to_char(Transaction.transaction_date, 'YYYY-MM-DD')
    elif period == "weekly":
        group_expr = func.to_char(func.date_trunc('week', Transaction.transaction_date), 'YYYY-"W"IW')
    elif period == "monthly":
        group_expr = func.to_char(Transaction.transaction_date, 'YYYY-MM')
    else:
        group_expr = func.to_char(Transaction.transaction_date, 'YYYY-MM-DD')
        
    actual_amount_expr = _actual_amount_subquery()
    
    income_expr = func.sum(
        case(
            (Transaction.type == 'INCOME', actual_amount_expr),
            else_=0
        )
    )
    
    expense_expr = func.sum(
        case(
            (Transaction.type == 'EXPENSE', actual_amount_expr),
            else_=0
        )
    )
    
    query = (
        select(
            group_expr.label("label"),
            func.coalesce(income_expr, 0).label("income"),
            func.coalesce(expense_expr, 0).label("expense")
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= date_from,
            Transaction.transaction_date <= date_to
        )
        .group_by(group_expr)
        .order_by(group_expr)
    )
    
    results = db.execute(query).fetchall()
    
    data = []
    for row in results:
        data.append({
            "label": row.label,
            "income": int(row.income),
            "expense": int(row.expense)
        })
        
    return {"period": period, "data": data}

def get_category_statistics(db: Session, user_id: str, date_from: date, date_to: date, txn_type: str):
    actual_amount_expr = _actual_amount_subquery()
    
    query = (
        select(
            Category.id.label("category_id"),
            Category.name.label("name"),
            func.sum(actual_amount_expr).label("amount")
        )
        .join(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.type == txn_type,
            Transaction.transaction_date >= date_from,
            Transaction.transaction_date <= date_to
        )
        .group_by(Category.id, Category.name)
        .order_by(desc("amount"))
    )
    
    results = db.execute(query).fetchall()
    
    total_amount = sum(row.amount for row in results)
    
    categories = []
    for row in results:
        amount = int(row.amount)
        ratio = round((amount / total_amount * 100), 1) if total_amount > 0 else 0.0
        categories.append({
            "category_id": row.category_id,
            "name": row.name,
            "amount": amount,
            "ratio": ratio
        })
        
    return {
        "total_amount": int(total_amount),
        "categories": categories
    }

def get_monthly_report(db: Session, user_id: str, month: str):
    year, mon = map(int, month.split('-'))
    last_day = calendar.monthrange(year, mon)[1]
    
    date_from = date(year, mon, 1)
    date_to = date(year, mon, last_day)
    
    actual_amount_expr = _actual_amount_subquery()
    
    income_expr = func.sum(case((Transaction.type == 'INCOME', actual_amount_expr), else_=0))
    expense_expr = func.sum(case((Transaction.type == 'EXPENSE', actual_amount_expr), else_=0))
    
    current_month_query = (
        select(
            func.coalesce(income_expr, 0).label("income"),
            func.coalesce(expense_expr, 0).label("expense")
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= date_from,
            Transaction.transaction_date <= date_to
        )
    )
    
    current_month_result = db.execute(current_month_query).fetchone()
    total_income = int(current_month_result.income) if current_month_result.income else 0
    total_expense = int(current_month_result.expense) if current_month_result.expense else 0
    net = total_income - total_expense
    daily_average_expense = total_expense // last_day
    
    prev_mon = mon - 1
    prev_year = year
    if prev_mon == 0:
        prev_mon = 12
        prev_year -= 1
        
    prev_last_day = calendar.monthrange(prev_year, prev_mon)[1]
    prev_date_from = date(prev_year, prev_mon, 1)
    prev_date_to = date(prev_year, prev_mon, prev_last_day)
    
    prev_month_query = (
        select(func.coalesce(expense_expr, 0).label("expense"))
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= prev_date_from,
            Transaction.transaction_date <= prev_date_to
        )
    )
    
    prev_month_result = db.execute(prev_month_query).fetchone()
    prev_total_expense = int(prev_month_result.expense) if prev_month_result.expense else 0
    
    if prev_total_expense == 0:
        expense_change = 0.0
        message = "전월 데이터 없음"
    else:
        change_ratio = ((total_expense - prev_total_expense) / prev_total_expense) * 100
        expense_change = round(change_ratio, 1)
        if expense_change > 0:
            message = f"전월 대비 {expense_change}% 증가"
        elif expense_change < 0:
            message = f"전월 대비 {abs(expense_change)}% 감소"
        else:
            message = "전월 대비 동일"
            
    top_categories_query = (
        select(
            Category.name.label("name"),
            func.sum(actual_amount_expr).label("amount")
        )
        .join(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.type == 'EXPENSE',
            Transaction.transaction_date >= date_from,
            Transaction.transaction_date <= date_to
        )
        .group_by(Category.name)
        .order_by(desc("amount"))
        .limit(5)
    )
    
    top_categories_result = db.execute(top_categories_query).fetchall()
    top_categories = [{"name": row.name, "amount": int(row.amount)} for row in top_categories_result]
    
    return {
        "month": month,
        "total_income": total_income,
        "total_expense": total_expense,
        "net": net,
        "daily_average_expense": daily_average_expense,
        "vs_last_month": {
            "expense_change": expense_change,
            "message": message
        },
        "top_categories": top_categories
    }
