from sqlalchemy.orm import Session
from fastapi import HTTPException

from . import models, schemas
from app.settlements import models as settlement_models
from app.settlements import service as settlement_service
from app.categories import models as category_models


def create_transaction(
    db: Session,
    transaction: schemas.TransactionCreate,
    current_user
):
    category = db.query(category_models.Category).filter(
        category_models.Category.id == transaction.category_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Category not found"
        )

    if category.user_id is not None and category.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to use this category"
        )

    db_transaction = models.Transaction(
        user_id=current_user.id,
        type=transaction.type,
        amount=transaction.amount,
        category_id=transaction.category_id,
        description=transaction.description,
        transaction_date=transaction.transaction_date,
        transaction_time=transaction.transaction_time
    )

    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    return {
    **db_transaction.__dict__,
    "category_name": category.name
}


def get_transactions(db: Session, current_user):
    rows = db.query(
        models.Transaction,
        category_models.Category.name.label("category_name")
    ).join(
        category_models.Category,
        category_models.Category.id == models.Transaction.category_id
    ).filter(
        models.Transaction.user_id == current_user.id
    ).order_by(
        models.Transaction.created_at.desc()
    ).all()

    return [
        {
            **transaction.__dict__,
            "category_name": category_name
        }
        for transaction, category_name in rows
    ]


def get_transaction_by_id(db: Session, transaction_id, current_user):
    row = db.query(
        models.Transaction,
        category_models.Category.name.label("category_name")
    ).join(
        category_models.Category,
        category_models.Category.id == models.Transaction.category_id
    ).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.user_id == current_user.id
    ).first()

    if not row:
        return None

    transaction, category_name = row

    return {
        **transaction.__dict__,
        "category_name": category_name
    }


def update_transaction(
    db: Session,
    transaction_id,
    transaction_update: schemas.TransactionUpdate,
    current_user
):
    transaction = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.user_id == current_user.id
    ).first()

    if not transaction:
        return None

    old_amount = transaction.amount
    old_type = transaction.type
    old_category_id = transaction.category_id

    if transaction_update.category_id is not None:
        category = db.query(category_models.Category).filter(
            category_models.Category.id == transaction_update.category_id
        ).first()

        if not category:
            raise HTTPException(
                status_code=404,
                detail="Category not found"
            )

        if category.user_id is not None and category.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to use this category"
            )

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

    db.commit()

    settlement = db.query(settlement_models.Settlement).filter(
    settlement_models.Settlement.transaction_id == transaction.id,
    settlement_models.Settlement.status != "CANCELLED"
).first()

    if settlement and old_amount != transaction.amount:
        settlement.total_amount = transaction.amount

        participants = db.query(
            settlement_models.SettlementParticipant
        ).filter(
            settlement_models.SettlementParticipant.settlement_id == settlement.id
        ).all()

        if settlement.split_type == "EQUAL":
            total_people = len(participants) + 1
            per_person = int(transaction.amount // total_people)

            for p in participants:
                if p.status != "SETTLED":
                    p.amount = per_person

        elif settlement.split_type == "CUSTOM":
            for p in participants:
                if p.status != "SETTLED":
                    p.amount = 0

        db.commit()

    db.refresh(transaction)

    category = db.query(category_models.Category).filter(
        category_models.Category.id == transaction.category_id
    ).first()

    return {
        **transaction.__dict__,
        "category_name": category.name 
    }


def delete_transaction(db: Session, transaction_id, current_user):
    transaction = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.user_id == current_user.id
    ).first()

    if not transaction:
        return None

    db.delete(transaction)
    db.commit()

    return transaction



import csv
import io

def export_transactions_csv(db: Session, current_user):
    rows = db.query(
        models.Transaction,
        category_models.Category.name.label("category_name")
    ).join(
        category_models.Category,
        category_models.Category.id == models.Transaction.category_id
    ).filter(
        models.Transaction.user_id == current_user.id
    ).order_by(
        models.Transaction.transaction_date.desc(),
        models.Transaction.created_at.desc()
    ).all()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "날짜",
        "유형",
        "카테고리",
        "금액",
        "메모"
    ])

    type_map = {
        "INCOME": "수입",
        "EXPENSE": "지출"
    }

    for transaction, category_name in rows:
        writer.writerow([
            transaction.transaction_date,
            type_map.get(transaction.type, transaction.type),
            category_name,
            int(transaction.amount),
            transaction.description or ""
        ])

    return output.getvalue() 