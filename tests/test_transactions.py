import uuid
from datetime import date, datetime, timedelta

import pytest

from app.auth.models import User
from app.categories.models import Category
from app.goals.models import Goal
from app.transactions.models import Transaction
from app.settlements.models import Settlement, SettlementParticipant


@pytest.fixture
def expense_category(db, test_user):
    category = Category(
        id=uuid.uuid4(), user_id=test_user.id, name="식비", type="EXPENSE"
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


# ---------- 스키마 검증 / 카테고리 소유권 ----------

def test_create_transaction_success(auth_client, expense_category):
    res = auth_client.post("/transactions/", json={
        "type": "EXPENSE",
        "amount": 15000,
        "category_id": str(expense_category.id),
        "transaction_date": str(date.today()),
        "description": "점심",
    })
    assert res.status_code == 201
    body = res.json()
    assert body["amount"] == 15000
    assert body["category_name"] == "식비"
    assert body["created_at"] is not None
    assert body["updated_at"] is not None


def test_create_amount_zero_rejected(auth_client, expense_category):
    res = auth_client.post("/transactions/", json={
        "type": "EXPENSE",
        "amount": 0,
        "category_id": str(expense_category.id),
        "transaction_date": str(date.today()),
    })
    assert res.status_code == 422


def test_create_invalid_type_rejected(auth_client, expense_category):
    res = auth_client.post("/transactions/", json={
        "type": "WRONG",
        "amount": 1000,
        "category_id": str(expense_category.id),
        "transaction_date": str(date.today()),
    })
    assert res.status_code == 422


def test_create_with_others_category_forbidden(auth_client, db):
    other = User(
        id=uuid.uuid4(),
        email=f"other_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="x",
        name="타인",
    )
    db.add(other)
    db.commit()
    other_category = Category(
        id=uuid.uuid4(), user_id=other.id, name="타인지출", type="EXPENSE"
    )
    db.add(other_category)
    db.commit()

    res = auth_client.post("/transactions/", json={
        "type": "EXPENSE",
        "amount": 1000,
        "category_id": str(other_category.id),
        "transaction_date": str(date.today()),
    })
    assert res.status_code == 403


def test_update_with_others_category_forbidden(auth_client, db, test_user, expense_category):
    res = auth_client.post("/transactions/", json={
        "type": "EXPENSE",
        "amount": 1000,
        "category_id": str(expense_category.id),
        "transaction_date": str(date.today()),
    })
    txn_id = res.json()["id"]

    other = User(
        id=uuid.uuid4(),
        email=f"other_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="x",
        name="타인",
    )
    db.add(other)
    db.commit()
    other_category = Category(
        id=uuid.uuid4(), user_id=other.id, name="타인지출", type="EXPENSE"
    )
    db.add(other_category)
    db.commit()

    res = auth_client.patch(f"/transactions/{txn_id}", json={
        "category_id": str(other_category.id),
    })
    assert res.status_code == 403


# ---------- 삭제 시 goal 재평가 (B1 hook) ----------

def test_delete_transaction_resets_goal(auth_client, db, test_user, expense_category):
    goal = Goal(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="식비목표",
        target_amount=100000,
        category_id=expense_category.id,
        status="IN_PROGRESS",
        created_at=datetime.utcnow() - timedelta(seconds=1),
    )
    db.add(goal)
    db.commit()

    # 100000 지출 → 목표 100% → ACHIEVED
    res = auth_client.post("/transactions/", json={
        "type": "EXPENSE",
        "amount": 100000,
        "category_id": str(expense_category.id),
        "transaction_date": str(date.today()),
    })
    assert res.status_code == 201
    txn_id = res.json()["id"]

    db.refresh(goal)
    assert goal.status == "ACHIEVED"
    assert goal.is_achieved_notified is True

    # 거래 삭제 → goal hook 재평가 → 0% → 복구
    res = auth_client.delete(f"/transactions/{txn_id}")
    assert res.status_code == 200

    db.refresh(goal)
    assert goal.status == "IN_PROGRESS"
    assert goal.is_achieved_notified is False


# ---------- 정산 cascade (PR9 머지 후 활성화) ----------

@pytest.fixture
def expense_with_settlement(db, test_user, expense_category):
    """EXPENSE 30000 + EQUAL 정산 + 참여자 2명(각 10000, creator implicit 10000)."""
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type="EXPENSE",
        amount=30000,
        category_id=expense_category.id,
        transaction_date=date.today(),
    )
    db.add(txn)
    db.commit()

    settlement = Settlement(
        id=uuid.uuid4(),
        transaction_id=txn.id,
        creator_id=test_user.id,
        total_amount=30000,
        split_type="EQUAL",
        status="PENDING",
    )
    db.add(settlement)
    db.commit()

    p1 = SettlementParticipant(
        id=uuid.uuid4(), settlement_id=settlement.id,
        display_name="A", amount=10000, status="PENDING",
    )
    p2 = SettlementParticipant(
        id=uuid.uuid4(), settlement_id=settlement.id,
        display_name="B", amount=10000, status="PENDING",
    )
    db.add_all([p1, p2])
    db.commit()
    return txn, settlement, [p1, p2]


def test_update_amount_cascade_equal(auth_client, db, expense_with_settlement):
    txn, settlement, parts = expense_with_settlement
    res = auth_client.patch(f"/transactions/{txn.id}", json={"amount": 60000})
    assert res.status_code == 200
    db.refresh(settlement)
    assert int(settlement.total_amount) == 60000
    for p in parts:
        db.refresh(p)
        assert int(p.amount) == 20000  # 60000 // (2 + 1)


def test_update_amount_keeps_settled_participant(auth_client, db, expense_with_settlement):
    txn, settlement, parts = expense_with_settlement
    p1, p2 = parts
    p1.status = "SETTLED"
    db.commit()

    res = auth_client.patch(f"/transactions/{txn.id}", json={"amount": 60000})
    assert res.status_code == 200
    db.refresh(p1)
    db.refresh(p2)
    assert int(p1.amount) == 10000  # SETTLED 유지
    assert int(p2.amount) == 25000  # (60000 - 10000) // (1 + 1)


def test_update_amount_below_settled_blocked(auth_client, db, expense_with_settlement):
    txn, settlement, parts = expense_with_settlement
    for p in parts:
        p.status = "SETTLED"
    db.commit()  # settled 합계 20000

    res = auth_client.patch(f"/transactions/{txn.id}", json={"amount": 15000})
    assert res.status_code == 400


def test_update_type_change_with_settlement_blocked(auth_client, expense_with_settlement):
    txn, *_ = expense_with_settlement
    res = auth_client.patch(f"/transactions/{txn.id}", json={"type": "INCOME"})
    assert res.status_code == 400


def test_update_completed_settlement_blocked(auth_client, db, expense_with_settlement):
    txn, settlement, parts = expense_with_settlement
    for p in parts:
        p.status = "SETTLED"
    settlement.status = "COMPLETED"
    db.commit()

    res = auth_client.patch(f"/transactions/{txn.id}", json={"amount": 60000})
    assert res.status_code == 400


def test_delete_transaction_cascades_settlement(auth_client, db, expense_with_settlement):
    txn, settlement, parts = expense_with_settlement
    settlement_id = settlement.id

    res = auth_client.delete(f"/transactions/{txn.id}")
    assert res.status_code == 200

    assert db.get(Settlement, settlement_id) is None
    remaining = db.query(SettlementParticipant).filter(
        SettlementParticipant.settlement_id == settlement_id
    ).count()
    assert remaining == 0
