from sqlalchemy.orm import Session
from datetime import date
from . import models, schemas


def create_transaction(db: Session, transaction: schemas.TransactionCreate, current_user):
    db_transaction = models.Transaction(
        user_id=current_user.id,        #
        type="EXPENSE",                 
        amount=transaction.amount,
        category_id=transaction.category_id,  # MUST exist in DB
        description=transaction.description,
        transaction_date=date.today()
    )

    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    return db_transaction


def get_transactions(db: Session, current_user):
    return db.query(models.Transaction).filter(
        models.Transaction.user_id == current_user.id
    ).all()
        

def get_transaction_by_id(db: Session, transaction_id, current_user):
    return db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.user_id == current_user.id
    ).first()

    
            