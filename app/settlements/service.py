from sqlalchemy.orm import Session
from app.transactions import models as transaction_models
from . import models, schemas
from datetime import datetime


def create_settlement(db: Session, settlement: schemas.SettlementCreate, current_user):
    transaction = db.query(transaction_models.Transaction).filter(
        transaction_models.Transaction.id == settlement.transaction_id,
        transaction_models.Transaction.user_id == current_user.id
    ).first()

    if not transaction:
        return None

    db_settlement = models.Settlement(
        transaction_id=transaction.id,
        creator_id=current_user.id,
        total_amount=transaction.amount,
        split_type=settlement.split_type
    )

    db.add(db_settlement)
    db.commit()
    db.refresh(db_settlement)

    return db_settlement


def add_participant(db: Session, settlement_id, participant: schemas.ParticipantCreate):
    new_participant = models.SettlementParticipant(
        settlement_id=settlement_id,
        user_id=participant.user_id,
        display_name=participant.display_name,
        amount=participant.amount
    )

    db.add(new_participant)
    db.commit()
    db.refresh(new_participant)

    return new_participant


def split_equal(db: Session, settlement_id):
    settlement = db.query(models.Settlement).filter(
        models.Settlement.id == settlement_id
    ).first()

    if not settlement:
        return None

    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
    ).all()

    if not participants:
        return None

    split_amount = round(float(settlement.total_amount) / len(participants), 2)

    for p in participants:
        p.amount = split_amount  # all positive (correct per feedback)

    db.commit()

    return participants


def calculate_debts(db: Session, settlement_id):
    settlement = db.query(models.Settlement).filter(
        models.Settlement.id == settlement_id
    ).first()

    if not settlement:
        return None

    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
    ).all()

    if not participants:
        return None

    creator = next(
        (p for p in participants if p.user_id == settlement.creator_id),
        None
    )

    transactions = []

    for p in participants:
        if p.user_id == settlement.creator_id:
            continue

        transactions.append({
            "from": p.display_name,
            "to": creator.display_name if creator else "creator",
            "amount": float(p.amount)
        })

    return transactions

def mark_settlement_complete(db: Session, settlement_id, current_user):
    settlement = db.query(models.Settlement).filter(
        models.Settlement.id == settlement_id,
        models.Settlement.creator_id == current_user.id
    ).first()

    if not settlement:
        return None

    settlement.status = "COMPLETED"

    db.commit()
    db.refresh(settlement)

    return settlement


def mark_participant_settled(db: Session, participant_id, current_user):
    participant = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.id == participant_id
    ).first()

    if not participant:
        return None

    settlement = db.query(models.Settlement).filter(
        models.Settlement.id == participant.settlement_id
    ).first()

    if not settlement or settlement.creator_id != current_user.id:
        return None

    participant.status = "SETTLED"
    participant.settled_at = datetime.utcnow()

    db.commit()
    db.refresh(participant)

    return participant


def get_participants_status(db: Session, settlement_id):
    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
    ).all()

    if not participants:
        return None

    return participants


def get_balance(db: Session, settlement_id):
    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
    ).all()

    if not participants:
        return None

    return [
        {
            "name": p.display_name,
            "amount": float(p.amount),
            "status": p.status
        }
        for p in participants
    ]