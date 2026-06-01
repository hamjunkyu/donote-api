import uuid
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models, schemas
from app.auth.models import User
from app.categories.models import Category
from app.settlements import service as settlement_service
from app.budgets.service import check_and_notify_budget_threshold
from app.goals.service import check_and_notify_goal_achievement


def _validate_category(db: Session, category_id: uuid.UUID, user_id: uuid.UUID) -> Category:
    """카테고리가 시스템 기본(user_id None) 또는 본인 소유인지 검증."""
    category = db.query(Category).filter(
        Category.id == category_id,
        (Category.user_id == None) | (Category.user_id == user_id),
    ).first()
    if not category:
        raise HTTPException(
            status_code=403,
            detail="유효하지 않거나 권한이 없는 카테고리입니다",
        )
    return category


def _build_response(transaction: models.Transaction, category_name: str | None) -> dict:
    """Transaction + category_name 을 TransactionResponse 매핑용 dict 로 변환."""
    return {
        "id": transaction.id,
        "user_id": transaction.user_id,
        "type": transaction.type,
        "amount": int(transaction.amount),
        "category_id": transaction.category_id,
        "category_name": category_name,
        "description": transaction.description,
        "transaction_date": transaction.transaction_date,
        "transaction_time": transaction.transaction_time,
        "created_at": transaction.created_at,
        "updated_at": transaction.updated_at,
    }


def _response_for(db: Session, transaction: models.Transaction) -> dict:
    """단건 Transaction 의 category_name 을 조회해 응답 dict 구성."""
    category = db.get(Category, transaction.category_id)
    return _build_response(transaction, category.name if category else None)


def _notify_affected(
    db: Session,
    user_id: uuid.UUID,
    old_type: str | None,
    old_category_id: uuid.UUID | None,
    old_date,
    transaction: models.Transaction,
) -> None:
    """변경 전/후 EXPENSE 컨텍스트에 대해 budget/goal 알림 재평가.

    type EXPENSE→INCOME, category 변경, date 변경, amount 변경 모두
    이전 카테고리/날짜와 새 카테고리/날짜 양쪽을 재평가 대상으로 수집.
    """
    goal_categories: set = set()
    budget_dates: set = set()

    if old_type == "EXPENSE":
        goal_categories.add(old_category_id)
        budget_dates.add(old_date)
    if transaction.type == "EXPENSE":
        goal_categories.add(transaction.category_id)
        budget_dates.add(transaction.transaction_date)

    for category_id in goal_categories:
        check_and_notify_goal_achievement(db, user_id, category_id)
    for transaction_date in budget_dates:
        check_and_notify_budget_threshold(db, user_id, transaction_date)


def create_transaction(db: Session, transaction: schemas.TransactionCreate, current_user: User) -> dict:
    _validate_category(db, transaction.category_id, current_user.id)

    db_transaction = models.Transaction(
        user_id=current_user.id,
        type=transaction.type,
        amount=transaction.amount,
        category_id=transaction.category_id,
        description=transaction.description,
        transaction_date=transaction.transaction_date,
        transaction_time=transaction.transaction_time,
    )

    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    if db_transaction.type == "EXPENSE":
        check_and_notify_budget_threshold(db, current_user.id, db_transaction.transaction_date)
        check_and_notify_goal_achievement(db, current_user.id, db_transaction.category_id)

    return _response_for(db, db_transaction)


def get_transactions(
    db: Session,
    current_user: User,
    type: str | None = None,
    category_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    amount_min: int | None = None,
    amount_max: int | None = None,
    keyword: str | None = None,
    limit: int = 20,
    offset: int = 0
) -> dict:
    # 1. Base query 준비
    query = (
        db.query(models.Transaction, Category.name)
        .outerjoin(Category, Category.id == models.Transaction.category_id)
        .filter(models.Transaction.user_id == current_user.id)
    )

    # 2. 필터링 조건 추가
    if type is not None:
        query = query.filter(models.Transaction.type == type)
    if category_id is not None:
        query = query.filter(models.Transaction.category_id == category_id)
    if date_from is not None:
        query = query.filter(models.Transaction.transaction_date >= date_from)
    if date_to is not None:
        query = query.filter(models.Transaction.transaction_date <= date_to)
    if amount_min is not None:
        query = query.filter(models.Transaction.amount >= amount_min)
    if amount_max is not None:
        query = query.filter(models.Transaction.amount <= amount_max)
    if keyword is not None and keyword.strip() != "":
        query = query.filter(models.Transaction.description.ilike(f"%{keyword}%"))

    # 3. 전체 개수(total) 집계
    total = query.count()

    # 4. 정렬 및 페이지네이션 슬라이싱 적용
    # transaction_date DESC, created_at DESC, id DESC 순 정렬
    rows = (
        query.order_by(
            models.Transaction.transaction_date.desc(),
            models.Transaction.created_at.desc(),
            models.Transaction.id.desc()
        )
        .limit(limit)
        .offset(offset)
        .all()
    )

    items = [_build_response(transaction, category_name) for transaction, category_name in rows]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }


def get_transaction_by_id(db: Session, transaction_id: uuid.UUID, current_user: User) -> dict | None:
    transaction = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.user_id == current_user.id,
    ).first()
    if not transaction:
        return None
    return _response_for(db, transaction)


def update_transaction(
    db: Session,
    transaction_id: uuid.UUID,
    transaction_update: schemas.TransactionUpdate,
    current_user: User,
) -> dict | None:
    transaction = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.user_id == current_user.id,
    ).first()

    if not transaction:
        return None

    old_type = transaction.type
    old_category_id = transaction.category_id
    old_date = transaction.transaction_date
    old_amount = int(transaction.amount)

    # 정산은 EXPENSE 거래에만 존재. type 을 EXPENSE 에서 바꾸면 정산이 orphan 이 되므로 차단.
    if (
        transaction_update.type is not None
        and transaction_update.type != old_type
        and old_type == "EXPENSE"
        and settlement_service.get_active_settlement_by_transaction(db, transaction.id)
    ):
        raise HTTPException(
            status_code=400,
            detail="정산이 연결된 거래는 유형을 변경할 수 없습니다. 정산을 먼저 취소하세요",
        )

    if transaction_update.category_id is not None and transaction_update.category_id != transaction.category_id:
        _validate_category(db, transaction_update.category_id, current_user.id)
        transaction.category_id = transaction_update.category_id

    if transaction_update.type is not None:
        transaction.type = transaction_update.type
    if transaction_update.amount is not None:
        transaction.amount = transaction_update.amount
    if transaction_update.description is not None:
        transaction.description = transaction_update.description
    if transaction_update.transaction_date is not None:
        transaction.transaction_date = transaction_update.transaction_date
    if transaction_update.transaction_time is not None:
        transaction.transaction_time = transaction_update.transaction_time

    # amount 변경 시 연결된 정산 total + 참여자 재분배 (creator 몫 < 0 이면 400)
    if transaction_update.amount is not None and int(transaction_update.amount) != old_amount:
        settlement_service.update_settlement_total(db, transaction.id, int(transaction_update.amount))

    db.commit()
    db.refresh(transaction)

    _notify_affected(db, current_user.id, old_type, old_category_id, old_date, transaction)

    return _response_for(db, transaction)


def delete_transaction(db: Session, transaction_id: uuid.UUID, current_user: User) -> bool:
    transaction = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.user_id == current_user.id,
    ).first()

    if not transaction:
        return False

    # 연결된 정산은 FK CASCADE 로 자동 삭제 (거래 기록의 자유 원칙)
    was_expense = transaction.type == "EXPENSE"
    category_id = transaction.category_id
    transaction_date = transaction.transaction_date

    db.delete(transaction)
    db.commit()

    # 삭제로 누적 지출이 줄었으므로 영향받은 budget/goal 재평가
    if was_expense:
        check_and_notify_budget_threshold(db, current_user.id, transaction_date)
        check_and_notify_goal_achievement(db, current_user.id, category_id)

    return True
