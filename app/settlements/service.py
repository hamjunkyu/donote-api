from sqlalchemy.orm import Session
from app.transactions import models as transaction_models
from . import models, schemas


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