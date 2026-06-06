"""도메인 예외 → HTTP 응답 변환 검증.

서비스가 던진 도메인 예외가 전역 핸들러를 거쳐 기존 HTTPException 과 동일한
status_code + {"detail": ...} 형식으로 나오는지 확인 (프론트 호환 보장).
"""
import uuid
from datetime import date

from app.categories.models import Category
from app.transactions.models import Transaction


def test_category_in_use_returns_409_with_detail(auth_client, test_user, db):
    """사용 중 카테고리 삭제 → ConflictError → 409 + detail."""
    cat = Category(id=uuid.uuid4(), user_id=test_user.id, name="식비", type="EXPENSE")
    db.add(cat)
    db.commit()
    db.add(Transaction(
        id=uuid.uuid4(), user_id=test_user.id, type="EXPENSE", amount=1000,
        category_id=cat.id, transaction_date=date.today(),
    ))
    db.commit()

    r = auth_client.delete(f"/api/categories/{cat.id}")
    assert r.status_code == 409
    assert "사용 중" in r.json()["detail"]


def test_settlement_on_income_returns_400_with_detail(auth_client, test_user, db):
    """EXPENSE 아닌 거래로 정산 생성 → BadRequestError → 400 + detail."""
    cat = Category(id=uuid.uuid4(), user_id=test_user.id, name="용돈", type="INCOME")
    db.add(cat)
    db.commit()
    txn = Transaction(
        id=uuid.uuid4(), user_id=test_user.id, type="INCOME", amount=5000,
        category_id=cat.id, transaction_date=date.today(),
    )
    db.add(txn)
    db.commit()

    r = auth_client.post(
        "/api/settlements/",
        json={"transaction_id": str(txn.id), "split_type": "EQUAL"},
    )
    assert r.status_code == 400
    assert "EXPENSE" in r.json()["detail"]
