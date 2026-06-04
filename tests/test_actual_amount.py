import uuid
from datetime import date

import pytest

from app.categories.models import Category
from app.transactions.models import Transaction
from app.settlements.models import Settlement, SettlementParticipant
from app.budgets.models import Budget


TXN_DATE = date(2026, 5, 15)
YEAR_MONTH = "2026-05"


@pytest.fixture
def expense_category(db, test_user):
    category = Category(
        id=uuid.uuid4(), user_id=test_user.id, name="식비", type="EXPENSE"
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def _make_expense(db, user, category, amount=9000):
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        type="EXPENSE",
        amount=amount,
        category_id=category.id,
        transaction_date=TXN_DATE,
    )
    db.add(txn)
    db.commit()
    return txn


def _add_settlement(db, txn, user, total=9000, participant_amounts=(3000, 3000)):
    """EQUAL 정산 + 참여자 N명(각 PENDING). creator 몫은 total - 참여자합."""
    settlement = Settlement(
        id=uuid.uuid4(),
        transaction_id=txn.id,
        creator_id=user.id,
        total_amount=total,
        split_type="EQUAL",
        status="PENDING",
    )
    db.add(settlement)
    db.commit()
    parts = []
    for i, amt in enumerate(participant_amounts):
        p = SettlementParticipant(
            id=uuid.uuid4(),
            settlement_id=settlement.id,
            display_name=f"친구{i}",
            amount=amt,
            status="PENDING",
        )
        db.add(p)
        parts.append(p)
    db.commit()
    return settlement, parts


def _actual_amount_in_list(auth_client, txn_id):
    res = auth_client.get("/api/transactions")
    assert res.status_code == 200
    for item in res.json()["items"]:
        if item["id"] == str(txn_id):
            return item["actual_amount"]
    raise AssertionError("거래가 목록에 없음")


# ---------- TransactionResponse.actual_amount ----------

def test_actual_amount_equals_amount_without_settlement(auth_client, db, test_user, expense_category):
    txn = _make_expense(db, test_user, expense_category, 9000)
    assert _actual_amount_in_list(auth_client, txn.id) == 9000


def test_actual_amount_pending_not_deducted(auth_client, db, test_user, expense_category):
    txn = _make_expense(db, test_user, expense_category, 9000)
    _add_settlement(db, txn, test_user)
    # 참여자 전원 PENDING → 실부담액은 amount 그대로
    assert _actual_amount_in_list(auth_client, txn.id) == 9000


def test_actual_amount_settled_deducted(auth_client, db, test_user, expense_category):
    txn = _make_expense(db, test_user, expense_category, 9000)
    settlement, parts = _add_settlement(db, txn, test_user)

    parts[0].status = "SETTLED"
    db.commit()
    assert _actual_amount_in_list(auth_client, txn.id) == 6000  # 9000 - 3000

    parts[1].status = "SETTLED"
    db.commit()
    assert _actual_amount_in_list(auth_client, txn.id) == 3000  # 9000 - 6000 (creator 몫)


def test_single_transaction_actual_amount(auth_client, db, test_user, expense_category):
    txn = _make_expense(db, test_user, expense_category, 9000)
    _, parts = _add_settlement(db, txn, test_user)
    parts[0].status = "SETTLED"
    db.commit()

    res = auth_client.get(f"/api/transactions/{txn.id}")
    assert res.status_code == 200
    body = res.json()
    assert body["amount"] == 9000
    assert body["actual_amount"] == 6000


# ---------- Budget spent = 실부담액 ----------

def test_budget_spent_uses_actual_amount(auth_client, db, test_user, expense_category):
    budget = Budget(
        id=uuid.uuid4(),
        user_id=test_user.id,
        year_month=YEAR_MONTH,
        category_id=None,
        amount=100000,
    )
    db.add(budget)
    txn = _make_expense(db, test_user, expense_category, 9000)
    _, parts = _add_settlement(db, txn, test_user)
    db.commit()

    def spent():
        res = auth_client.get(f"/api/budgets/{YEAR_MONTH}")
        assert res.status_code == 200
        return res.json()["budgets"][0]["spent"]

    assert spent() == 9000  # 전원 PENDING

    parts[0].status = "SETTLED"
    db.commit()
    assert spent() == 6000  # 1명 SETTLED

    parts[1].status = "SETTLED"
    db.commit()
    assert spent() == 3000  # 2명 SETTLED


# ---------- Statistics = 실부담액 ----------

def test_statistics_category_uses_actual_amount(auth_client, db, test_user, expense_category):
    txn = _make_expense(db, test_user, expense_category, 9000)
    _, parts = _add_settlement(db, txn, test_user)
    parts[0].status = "SETTLED"
    parts[1].status = "SETTLED"
    db.commit()

    res = auth_client.get(
        "/api/statistics/categories?date_from=2026-05-01&date_to=2026-05-31&type=EXPENSE"
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total_expense"] == 3000
    assert "total_income" not in body  # exclude_none 으로 무관 필드 제외
    assert body["categories"][0]["amount"] == 3000


# ---------- 기간 요약 / 월간 리포트 = 실부담액 ----------

def test_summary_uses_actual_amount(auth_client, db, test_user, expense_category):
    txn = _make_expense(db, test_user, expense_category, 9000)
    _, parts = _add_settlement(db, txn, test_user)

    def monthly_expense():
        res = auth_client.get(
            "/api/statistics/summary?period=monthly&date_from=2026-05-01&date_to=2026-05-31"
        )
        assert res.status_code == 200
        entry = next(d for d in res.json()["data"] if d["label"] == "2026-05")
        return entry["expense"]

    assert monthly_expense() == 9000  # 전원 PENDING → 차감 안 함

    parts[0].status = "SETTLED"
    parts[1].status = "SETTLED"
    db.commit()
    assert monthly_expense() == 3000  # 2명 SETTLED → 실부담액


def test_monthly_report_uses_actual_amount(auth_client, db, test_user, expense_category):
    txn = _make_expense(db, test_user, expense_category, 9000)
    _, parts = _add_settlement(db, txn, test_user)
    parts[0].status = "SETTLED"
    parts[1].status = "SETTLED"
    db.commit()

    res = auth_client.get("/api/statistics/monthly-report?month=2026-05")
    assert res.status_code == 200
    body = res.json()
    assert body["total_expense"] == 3000
    assert body["top_categories"][0]["amount"] == 3000


# ---------- INCOME 거래는 정산이 없어 실부담액 == amount ----------

def test_actual_amount_income_equals_amount(auth_client, db, test_user):
    category = Category(
        id=uuid.uuid4(), user_id=test_user.id, name="급여", type="INCOME"
    )
    db.add(category)
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type="INCOME",
        amount=500000,
        category_id=category.id,
        transaction_date=TXN_DATE,
    )
    db.add(txn)
    db.commit()

    res = auth_client.get(f"/api/transactions/{txn.id}")
    assert res.status_code == 200
    assert res.json()["actual_amount"] == 500000
