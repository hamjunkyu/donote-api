import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_db
from . import schemas, service


router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/", response_model=schemas.TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_transaction(db, transaction, current_user)


@router.get("/", response_model=List[schemas.TransactionResponse])
def get_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_transactions(db, current_user)


@router.get("/{transaction_id}", response_model=schemas.TransactionResponse)
def get_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = service.get_transaction_by_id(db, transaction_id, current_user)
    if not transaction:
        raise HTTPException(status_code=404, detail="거래를 찾을 수 없습니다")
    return transaction


@router.patch("/{transaction_id}", response_model=schemas.TransactionResponse)
def update_transaction(
    transaction_id: uuid.UUID,
    transaction_update: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = service.update_transaction(db, transaction_id, transaction_update, current_user)
    if not transaction:
        raise HTTPException(status_code=404, detail="거래를 찾을 수 없습니다")
    return transaction


@router.delete("/{transaction_id}", response_model=schemas.MessageResponse)
def delete_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = service.delete_transaction(db, transaction_id, current_user)
    if not deleted:
        raise HTTPException(status_code=404, detail="거래를 찾을 수 없습니다")
    return {"message": "거래가 삭제되었습니다"}
