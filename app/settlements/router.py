import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.dependencies import get_current_user
from . import schemas, service


router = APIRouter(prefix="/api/settlements", tags=["Settlements"])


@router.get("/", response_model=List[schemas.SettlementResponse])
def list_settlements(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return service.get_user_settlements(db, current_user)


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
    result = service.add_participant(db, settlement_id, participant, current_user)

    if not result:
        raise HTTPException(status_code=403, detail="Not authorized to add participants")

    return result


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


@router.post("/{settlement_id}/split/custom")
def custom_split(
    settlement_id: uuid.UUID,
    split_data: schemas.CustomSplitRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.split_custom(db, settlement_id, split_data)

    if not result:
        raise HTTPException(status_code=400, detail="Invalid split data or mismatch in total amount")

    return result


# ✅ NEW: edit split
@router.patch("/{settlement_id}/split/edit")
def edit_split(
    settlement_id: uuid.UUID,
    split_data: schemas.CustomSplitRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.edit_split(db, settlement_id, split_data, current_user)

    if not result:
        raise HTTPException(status_code=400, detail="Invalid split update")

    return result


@router.get("/{settlement_id}/balance")
def view_balance(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.get_balance(db, settlement_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Settlement not found")

    return result


@router.get("/{settlement_id}/debts")
def get_debts(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.calculate_debts(db, settlement_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Settlement not found")

    return result


@router.patch("/{settlement_id}/complete")
def mark_complete(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.mark_settlement_complete(db, settlement_id, current_user)

    if result == "NOT_ALL_SETTLED":
        raise HTTPException(status_code=400, detail="All participants must be settled")

    if not result:
        raise HTTPException(status_code=404, detail="Settlement not found or not authorized")

    return result



@router.patch("/{settlement_id}/revert")
def revert_settlement(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.revert_completion(db, settlement_id, current_user)

    if result == "NOT_COMPLETED":
        raise HTTPException(status_code=400, detail="Settlement is not completed")

    if not result:
        raise HTTPException(status_code=404, detail="Settlement not found or not authorized")

    return result


@router.patch("/participants/{participant_id}/settle")
def mark_participant_paid(
    participant_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.mark_participant_settled(db, participant_id, current_user)

    if not result:
        raise HTTPException(status_code=404, detail="Participant not found or not authorized")

    return result


@router.get("/{settlement_id}/participants")
def get_participants(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.get_participants_status(db, settlement_id)

    if not result:
        raise HTTPException(status_code=404, detail="Participant not found")

    return result


@router.get("/{settlement_id}")
def view_settlement(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.get_settlement(db, settlement_id)

    if not result:
        raise HTTPException(status_code=404, detail="Settlement not found")

    return result


@router.patch("/{settlement_id}")
def edit_settlement(
    settlement_id: uuid.UUID,
    update_data: schemas.SettlementUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.update_settlement(db, settlement_id, update_data, current_user)

    if not result:
        raise HTTPException(status_code=404, detail="Settlement not found or not authorized")

    return result


@router.delete("/{settlement_id}")
def delete_settlement(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = service.delete_settlement(db, settlement_id, current_user)

    if not result:
        raise HTTPException(status_code=404, detail="Settlement not found or not authorized")

    return {"message": "Settlement deleted successfully"}