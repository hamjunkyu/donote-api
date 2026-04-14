from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.transactions import service, schemas

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.post("/", response_model=schemas.TransactionResponse)
def create_transaction(
    data: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return service.create_transaction(db, user.id, data)


@router.get("/", response_model=list[schemas.TransactionResponse])
def get_transactions(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return service.get_transactions(db, user.id)


@router.delete("/{transaction_id}")
def delete_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    result = service.delete_transaction(db, transaction_id, user.id)

    if not result:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return {"message": "deleted"}
