from sqlalchemy.orm import Session
from app.transactions.models import Transaction
from uuid import UUID


def create_transaction(db: Session, user_id: UUID, data):
    transaction = Transaction(
        user_id=user_id,
        type=data.type,
        amount=data.amount,
        category_id=data.category_id,
        description=data.description,
        transaction_date=data.transaction_date,
        transaction_time=data.transaction_time,
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def get_transactions(db: Session, user_id: UUID):
    return db.query(Transaction).filter(Transaction.user_id == user_id).all()


def delete_transaction(db: Session, transaction_id: UUID, user_id: UUID):
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == user_id
    ).first()

    if not transaction:
        return None

    db.delete(transaction)
    db.commit()
    return transaction
