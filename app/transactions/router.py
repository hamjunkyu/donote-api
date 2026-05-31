from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.auth.dependencies import get_current_user
from . import schemas, service


router = APIRouter(
    prefix="/api/transactions",
    tags=["Transactions"]
)


@router.post("", response_model=schemas.TransactionResponse)
def create_transaction(
    transaction: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return service.create_transaction(db, transaction, current_user)


@router.get("", response_model=List[schemas.TransactionResponse])
def get_transactions(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return service.get_transactions(db, current_user)


@router.get("/{transaction_id}", response_model=schemas.TransactionResponse)
def get_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    transaction = service.get_transaction_by_id(
        db,
        transaction_id,
        current_user
    )

    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"
        )

    return transaction


@router.patch("/{transaction_id}", response_model=schemas.TransactionResponse)
def update_transaction(
    transaction_id: uuid.UUID,
    transaction_update: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    transaction = service.update_transaction(
        db,
        transaction_id,
        transaction_update,
        current_user
    )

    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"
        )

    return transaction


@router.delete("/{transaction_id}")
def delete_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    transaction = service.delete_transaction(
        db,
        transaction_id,
        current_user
    )

    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"
        )

    return {
        "message": "Transaction deleted successfully"
    }