import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.categories.models import Category
from app.transactions.models import Transaction
from app.settlements.models import Settlement, SettlementParticipant
from app.settlements import service as settlement_service
from app.settlements import schemas as settlement_schemas


# ---------- config: TEST_DATABASE_URL 파생 ----------

def test_test_database_url_derived_from_database_url():
    s = Settings(
        DATABASE_URL="postgresql://u:pw@host:5432/mydb",
        SECRET_KEY="x",
        TEST_DATABASE_URL="",
    )
    assert s.TEST_DATABASE_URL == "postgresql://u:pw@host:5432/mydb_test"


def test_test_database_url_explicit_value_kept():
    s = Settings(
        DATABASE_URL="postgresql://u:pw@host:5432/mydb",
        SECRET_KEY="x",
        TEST_DATABASE_URL="postgresql://u:pw@host:5432/custom",
    )
    assert s.TEST_DATABASE_URL == "postgresql://u:pw@host:5432/custom"


# ---------- settlements: add_participant 검증 실패 시 롤백 ----------

def test_add_participant_rollback_on_invalid_share(db, test_user):
    cat = Category(id=uuid.uuid4(), user_id=test_user.id, name="식비", type="EXPENSE")
    db.add(cat)
    db.commit()
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type="EXPENSE",
        amount=10000,
        category_id=cat.id,
        transaction_date=date.today(),
    )
    db.add(txn)
    db.commit()
    settlement = Settlement(
        id=uuid.uuid4(),
        transaction_id=txn.id,
        creator_id=test_user.id,
        total_amount=10000,
        split_type="EQUAL",
        status="PENDING",
    )
    db.add(settlement)
    db.commit()

    # 참여자 amount(15000) > total(10000) → creator 몫 음수 → 400
    with pytest.raises(HTTPException) as exc:
        settlement_service.add_participant(
            db,
            settlement.id,
            settlement_schemas.ParticipantCreate(display_name="친구", amount=15000),
            test_user,
        )
    assert exc.value.status_code == 400

    # 검증 실패로 flush 된 참여자는 롤백되어 저장되지 않는다
    count = db.query(SettlementParticipant).filter(
        SettlementParticipant.settlement_id == settlement.id
    ).count()
    assert count == 0
