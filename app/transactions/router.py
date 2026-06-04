import uuid
from io import BytesIO
from typing import Optional, Literal
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_db
from app.shared.schemas import PaginatedResponse
from . import schemas, service


router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.post("/", response_model=schemas.TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_transaction(db, transaction, current_user)


@router.get("/", response_model=PaginatedResponse[schemas.TransactionResponse])
def get_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    type: Optional[Literal["INCOME", "EXPENSE"]] = Query(None),
    category_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    amount_min: Optional[int] = Query(None),
    amount_max: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from은 date_to보다 이전이어야 합니다",
        )
    if amount_min is not None and amount_max is not None and amount_min > amount_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="amount_min은 amount_max보다 작거나 같아야 합니다",
        )
    return service.get_transactions(
        db,
        current_user,
        type=type,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )


@router.get("/export")
def export_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """거래 내역을 CSV로 내보낸다 (import 포맷과 동일 컬럼)."""
    csv_content = service.export_transactions_csv(db, current_user)
    csv_bytes = csv_content.encode("utf-8-sig")
    return StreamingResponse(
        BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="transactions.csv"'},
    )


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
