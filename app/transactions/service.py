from sqlalchemy.orm import Session
from fastapi import HTTPException
from . import models, schemas
from app.settlements import models as settlement_models
from app.budgets.service import check_and_notify_budget_threshold


def create_transaction(db: Session, transaction: schemas.TransactionCreate, current_user):
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

    if db_transaction.type == "EXPENSE":
        check_and_notify_budget_threshold(db, current_user.id, db_transaction.transaction_date)

    return db_transaction


def get_transactions(db: Session, current_user):
    return db.query(models.Transaction).filter(
        models.Transaction.user_id == current_user.id
    ).order_by(models.Transaction.created_at.desc()).all()


def get_transaction_by_id(db: Session, transaction_id, current_user):
    return db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.user_id == current_user.id
    ).first()


def update_transaction(db: Session, transaction_id, transaction_update: schemas.TransactionUpdate, current_user):
    transaction = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.user_id == current_user.id
    ).first()

    if not transaction:
        return None

    if transaction_update.type is not None:  
        transaction.type = transaction_update.type

    if transaction_update.amount is not None:
        transaction.amount = transaction_update.amount

    if transaction_update.category_id is not None:
        transaction.category_id = transaction_update.category_id

    if transaction_update.description is not None:
        transaction.description = transaction_update.description

    if transaction_update.transaction_date is not None:  
        transaction.transaction_date = transaction_update.transaction_date

    if transaction_update.transaction_time is not None:  
        transaction.transaction_time = transaction_update.transaction_time

    db.commit()
    db.refresh(transaction)

    if transaction.type == "EXPENSE":
        check_and_notify_budget_threshold(db, current_user.id, transaction.transaction_date)

    return transaction


def delete_transaction(db: Session, transaction_id, current_user):
    transaction = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.user_id == current_user.id
    ).first()

    if not transaction:
        return None

   
    settlement = db.query(settlement_models.Settlement).filter(
        settlement_models.Settlement.transaction_id == transaction_id
    ).first()

    if settlement:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete transaction linked to settlement"
        )

    db.delete(transaction)
    db.commit()

    return transaction
