import csv
import io
import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.shared.exceptions import BadRequestError, ForbiddenError

from . import models, schemas
from .helpers import actual_spent_subquery
from app.auth.models import User
from app.categories.models import Category
from app.settlements import service as settlement_service
from app.budgets.service import check_and_notify_budget_threshold


def _validate_category(db: Session, category_id: uuid.UUID, user_id: uuid.UUID) -> Category:
    """카테고리가 시스템 기본(user_id None) 또는 본인 소유인지 검증."""
    category = db.query(Category).filter(
        Category.id == category_id,
        (Category.user_id == None) | (Category.user_id == user_id),
    ).first()
    if not category:
        raise ForbiddenError("유효하지 않거나 권한이 없는 카테고리입니다")
    return category


def _build_response(transaction: models.Transaction, category_name: str | None, actual_amount: int) -> dict:
    """Transaction + category_name + 실부담액 을 TransactionResponse 매핑용 dict 로 변환."""
    return {
        "id": transaction.id,
        "user_id": transaction.user_id,
        "type": transaction.type,
        "amount": int(transaction.amount),
        "actual_amount": int(actual_amount),
        "category_id": transaction.category_id,
        "category_name": category_name,
        "description": transaction.description,
        "transaction_date": transaction.transaction_date,
        "transaction_time": transaction.transaction_time,
        "created_at": transaction.created_at,
        "updated_at": transaction.updated_at,
    }


def _response_for(db: Session, transaction: models.Transaction) -> dict:
    """단건 Transaction 의 category_name + 실부담액 을 조회해 응답 dict 구성."""
    category = db.get(Category, transaction.category_id)
    actual_amount = db.query(actual_spent_subquery()).filter(
        models.Transaction.id == transaction.id
    ).scalar()
    return _build_response(transaction, category.name if category else None, actual_amount)


def _notify_affected(
    db: Session,
    user_id: uuid.UUID,
    old_type: str | None,
    old_date,
    transaction: models.Transaction,
    commit: bool = True,
) -> None:
    """변경 전/후 EXPENSE 컨텍스트에 대해 budget 알림 재평가.

    type EXPENSE→INCOME, date 변경, amount 변경 모두
    이전 날짜와 새 날짜 양쪽을 재평가 대상으로 수집.
    """
    budget_dates: set = set()

    if old_type == "EXPENSE":
        budget_dates.add(old_date)
    if transaction.type == "EXPENSE":
        budget_dates.add(transaction.transaction_date)

    # 동시 거래 간 데드락 방지를 위해 정렬된 순서로 처리.
    for transaction_date in sorted(budget_dates):
        check_and_notify_budget_threshold(db, user_id, transaction_date, commit=commit)


def create_transaction(db: Session, transaction: schemas.TransactionCreate, current_user: User) -> dict:
    category = _validate_category(db, transaction.category_id, current_user.id)
    if category.type != transaction.type:
        raise BadRequestError("카테고리 타입이 거래 타입과 일치하지 않습니다")

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
    db.flush()  # ID 확보. commit 은 알림까지 끝낸 뒤 한 번만.

    if db_transaction.type == "EXPENSE":
        check_and_notify_budget_threshold(db, current_user.id, db_transaction.transaction_date, commit=False)

    db.commit()
    db.refresh(db_transaction)

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
        db.query(models.Transaction, Category.name, actual_spent_subquery())
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

    items = [
        _build_response(transaction, category_name, actual_amount)
        for transaction, category_name, actual_amount in rows
    ]

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
    old_date = transaction.transaction_date
    old_amount = int(transaction.amount)

    # 정산은 EXPENSE 거래에만 존재. type 을 EXPENSE 에서 바꾸면 정산이 orphan 이 되므로 차단.
    if (
        transaction_update.type is not None
        and transaction_update.type != old_type
        and old_type == "EXPENSE"
        and settlement_service.get_active_settlement_by_transaction(db, transaction.id)
    ):
        raise BadRequestError("정산이 연결된 거래는 유형을 변경할 수 없습니다. 정산을 먼저 취소하세요")

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

    # type 또는 category 변경 시 최종 카테고리 타입과 거래 타입 일치 검증
    if transaction_update.type is not None or transaction_update.category_id is not None:
        category = db.get(Category, transaction.category_id)
        if category and category.type != transaction.type:
            raise BadRequestError("카테고리 타입이 거래 타입과 일치하지 않습니다")

    # amount 변경 시 연결된 정산 total + 참여자 재분배 (creator 몫 < 0 이면 400)
    if transaction_update.amount is not None and int(transaction_update.amount) != old_amount:
        settlement_service.update_settlement_total(db, transaction.id, int(transaction_update.amount))

    db.flush()  # 변경 사항 반영. commit 은 알림까지 끝낸 뒤 한 번만.

    _notify_affected(db, current_user.id, old_type, old_date, transaction, commit=False)

    db.commit()
    db.refresh(transaction)

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
    transaction_date = transaction.transaction_date

    db.delete(transaction)
    db.flush()  # FK CASCADE 로 연결 정산 삭제 반영. commit 은 알림 후 한 번만.

    # 삭제로 누적 지출이 줄었으므로 영향받은 budget 재평가
    if was_expense:
        check_and_notify_budget_threshold(db, current_user.id, transaction_date, commit=False)

    db.commit()

    return True


def export_transactions_csv(db: Session, current_user) -> str:
    """사용자 거래를 CSV 문자열로 변환한다 (import 포맷과 동일 컬럼)."""
    rows = (
        db.query(models.Transaction, Category.name.label("category_name"))
        .join(Category, Category.id == models.Transaction.category_id)
        .filter(models.Transaction.user_id == current_user.id)
        .order_by(
            models.Transaction.transaction_date.desc(),
            models.Transaction.created_at.desc(),
        )
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["날짜", "유형", "카테고리", "금액", "메모"])

    type_map = {"INCOME": "수입", "EXPENSE": "지출"}
    for transaction, category_name in rows:
        writer.writerow([
            transaction.transaction_date,
            type_map.get(transaction.type, transaction.type),
            category_name,
            int(transaction.amount),
            transaction.description or "",
        ])

    return output.getvalue()
