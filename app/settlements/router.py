import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.dependencies import get_current_user
from . import schemas, service


router = APIRouter(prefix="/api/settlements", tags=["Settlements"])


@router.post("/")
def create_settlement(
    settlement: schemas.SettlementCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    new_settlement = service.create_settlement(db, settlement, current_user)

    if not new_settlement:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return new_settlement


@router.post("/{settlement_id}/participants")
def add_participant(
    settlement_id: uuid.UUID,
    participant: schemas.ParticipantCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return service.add_participant(db, settlement_id, participant)


@router.post("/{settlement_id}/split/equal")
def equal_split(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.split_equal(db, settlement_id)

    if not result:
        raise HTTPException(status_code=404, detail="Settlement or participants not found")

    return result


@router.get("/{settlement_id}/balance")
def view_balance(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.get_balance(db, settlement_id)

    if not result:
        raise HTTPException(status_code=404, detail="Settlement not found")

    return result

@router.get("/{settlement_id}/debts")
def get_debts(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.calculate_debts(db, settlement_id)

    if not result:
        raise HTTPException(status_code=404, detail="Settlement not found")

    return result


@router.patch("/{settlement_id}/complete")
def mark_complete(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.mark_settlement_complete(db, settlement_id, current_user)

    if not result:
        raise HTTPException(status_code=404, detail="Settlement not found or not authorized")

    return result