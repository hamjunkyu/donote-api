from sqlalchemy.orm import Session
from app.transactions import models as transaction_models
from . import models, schemas


def create_settlement(db: Session, settlement: schemas.SettlementCreate, current_user):
    #Get transaction and verify ownership
    transaction = db.query(transaction_models.Transaction).filter(
        transaction_models.Transaction.id == settlement.transaction_id,
        transaction_models.Transaction.user_id == current_user.id
    ).first()

    if not transaction:
        return None


      # create settlement record
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

    split_amount = settlement.total_amount / len(participants)

    for p in participants:
        if p.user_id == settlement.creator_id:
            # creator gets money back (negative)
            p.amount = split_amount - float(settlement.total_amount)
        else:
            # others owe money (positive)
            p.amount = split_amount

    db.commit()

    return participants


def calculate_debts(db: Session, settlement_id):
    participants = db.query(models.SettlementParticipant).filter(
        models.SettlementParticipant.settlement_id == settlement_id
    ).all()

    if not participants:
        return None

    creditors = []
    debtors = []

  
    for p in participants:
        amount = float(p.amount)

        if amount < 0:
            creditors.append({
                "name": p.display_name,
                "amount": abs(amount)
            })
        else:
            debtors.append({
                "name": p.display_name,
                "amount": amount
            })

    transactions = []

    # match debtors to creditors
    for debtor in debtors:
        for creditor in creditors:
            if debtor["amount"] == 0:
                break
            if creditor["amount"] == 0:
                continue

            pay_amount = min(debtor["amount"], creditor["amount"])

            transactions.append({
                "from": debtor["name"],
                "to": creditor["name"],
                "amount": pay_amount
            })

            debtor["amount"] -= pay_amount
            creditor["amount"] -= pay_amount

    return transactions


