import uuid
from datetime import date

from app.categories.models import Category
from app.transactions.models import Transaction
from app.statistics.service import get_period_summary


def test_weekly_label_uses_iso_week_year_at_boundary(db, test_user):
    """연말 거래(2025-12-29 = ISO 2026-W01)의 주간 라벨이 ISO 연도 기준으로 표기된다.

    달력 연도(YYYY) + ISO 주차(IW) 조합은 연말연초에 어긋나므로 IYYY 를 써야 한다.
    """
    cat = Category(id=uuid.uuid4(), user_id=test_user.id, name="식비", type="EXPENSE")
    db.add(cat)
    db.commit()
    db.add(Transaction(
        id=uuid.uuid4(), user_id=test_user.id, type="EXPENSE",
        amount=10000, category_id=cat.id, transaction_date=date(2025, 12, 29),
    ))
    db.commit()

    res = get_period_summary(db, test_user.id, "weekly", date(2025, 12, 1), date(2026, 1, 31))
    labels = [d["label"] for d in res["data"]]

    assert "2026-W01" in labels
    assert "2025-W01" not in labels
