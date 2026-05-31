import pytest
import uuid
from datetime import date, datetime, timedelta
from app.auth.models import User
from app.categories.models import Category
from app.budgets.models import Budget
from app.transactions.models import Transaction
from app.notifications.models import Notification
from app.budgets.service import check_and_notify_budget_threshold


@pytest.fixture
def my_category(db, test_user):
    """현재 사용자가 소유한 카테고리 피스처."""
    category = Category(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="식비",
        type="EXPENSE"
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@pytest.fixture
def system_category(db):
    """시스템 기본 카테고리 피스처."""
    category = Category(
        id=uuid.uuid4(),
        user_id=None,
        name="교통",
        type="EXPENSE"
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@pytest.fixture
def other_user(db):
    """임의의 다른 사용자 생성 피스처."""
    user = User(
        id=uuid.uuid4(),
        email=f"other_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hashedpassword",
        name="다른유저"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_user_category(db, other_user):
    """다른 사용자가 소유한 카테고리 피스처."""
    category = Category(
        id=uuid.uuid4(),
        user_id=other_user.id,  # 실제 존재하는 다른 사용자 ID 연결
        name="타인의카테고리",
        type="EXPENSE"
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def test_budget_gt_zero_validation(auth_client):
    # amount = 0 으로 설정 시도 -> 422 Validation Error
    response = auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": 0,
        "category_id": None
    })
    assert response.status_code == 422

    # amount < 0 으로 설정 시도 -> 422 Validation Error
    response = auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": -50000,
        "category_id": None
    })
    assert response.status_code == 422


def test_budget_category_authorization(auth_client, my_category, system_category, other_user_category):
    # 1. 내 카테고리로 예산 설정 -> 성공 (200/201)
    response = auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": 100000,
        "category_id": str(my_category.id)
    })
    assert response.status_code in (200, 201)

    # 2. 시스템 카테고리로 예산 설정 -> 성공 (200/201)
    response = auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": 50000,
        "category_id": str(system_category.id)
    })
    assert response.status_code in (200, 201)

    # 3. 타인의 카테고리로 예산 설정 -> 403 Forbidden
    response = auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": 150000,
        "category_id": str(other_user_category.id)
    })
    assert response.status_code == 403


def test_budget_get_usage_overall_none(auth_client, my_category):
    # 전체 예산은 설정하지 않고, 카테고리 예산만 설정
    auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": 50000,
        "category_id": str(my_category.id)
    })

    # 조회 시 overall (category = None) 항목은 배열에 없어야 함
    response = auth_client.get("/api/budgets/2026-05")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["year_month"] == "2026-05"
    
    budgets = res_data["budgets"]
    assert len(budgets) == 1
    assert budgets[0]["category"] == "식비"
    assert budgets[0]["label"] == "식비"
    
    # category가 null(None)인 전체 예산은 제외되어 있어야 함
    for b in budgets:
        assert b["category"] is not None


def test_budget_upsert_race_condition(auth_client, db, test_user):
    # 동일 조건으로 여러번 upsert 호출
    # 최초 삽입
    response = auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": 100000,
        "category_id": None
    })
    assert response.status_code in (200, 201)

    # 마킹하여 알림 플래그 변경
    budget = db.query(Budget).filter(Budget.user_id == test_user.id, Budget.year_month == "2026-05").first()
    budget.is_warning_notified = True
    budget.is_exceeded_notified = True
    db.commit()

    # 다시 동일 조건 upsert (금액 변경) -> 기존에 저장된 플래그가 False로 리셋되어야 함
    response = auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": 200000,
        "category_id": None
    })
    assert response.status_code in (200, 201)

    db.refresh(budget)
    assert float(budget.amount) == 200000
    assert budget.is_warning_notified is False
    assert budget.is_exceeded_notified is False


def test_budget_notification_and_refiring(auth_client, db, test_user, my_category):
    # 1. 식비 예산 10만원 설정
    auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": 100000,
        "category_id": str(my_category.id)
    })

    # 2. 8만원 지출 추가 -> 80% 도달 (WARNING)
    tx1 = Transaction(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type="EXPENSE",
        amount=80000,
        category_id=my_category.id,
        description="식비 1차",
        transaction_date=date(2026, 5, 10),
        created_at=datetime.utcnow()
    )
    db.add(tx1)
    db.commit()

    check_and_notify_budget_threshold(db, test_user.id, date(2026, 5, 10))

    # 알림함 검증
    warn_notif = db.query(Notification).filter(
        Notification.user_id == test_user.id,
        Notification.type == "BUDGET_WARNING"
    ).all()
    assert len(warn_notif) == 1
    assert "식비" in warn_notif[0].message

    # 3. 2만원 추가 지출 -> 100% 도달 (EXCEEDED)
    tx2 = Transaction(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type="EXPENSE",
        amount=20000,
        category_id=my_category.id,
        description="식비 2차",
        transaction_date=date(2026, 5, 12),
        created_at=datetime.utcnow()
    )
    db.add(tx2)
    db.commit()

    check_and_notify_budget_threshold(db, test_user.id, date(2026, 5, 12))

    exceed_notif = db.query(Notification).filter(
        Notification.user_id == test_user.id,
        Notification.type == "BUDGET_EXCEEDED"
    ).all()
    assert len(exceed_notif) == 1
    assert "식비" in exceed_notif[0].message

    # 4. 거래 2만원 삭제 -> 소진율 하강 (100% -> 80%) -> exceeded flag reset 검증
    db.delete(tx2)
    db.commit()

    check_and_notify_budget_threshold(db, test_user.id, date(2026, 5, 12))

    budget = db.query(Budget).filter(Budget.user_id == test_user.id, Budget.category_id == my_category.id).first()
    assert budget.is_exceeded_notified is False
    assert budget.is_warning_notified is True  # 80%는 유지

    # 5. 거래 8만원 삭제 -> 0%로 하강 -> warning flag reset 검증
    db.delete(tx1)
    db.commit()

    check_and_notify_budget_threshold(db, test_user.id, date(2026, 5, 10))
    db.refresh(budget)
    assert budget.is_warning_notified is False

    # 6. 다시 8만원 지출 추가 -> 80% 재발화 알림 검증
    tx1_new = Transaction(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type="EXPENSE",
        amount=80000,
        category_id=my_category.id,
        description="식비 1차 재등록",
        transaction_date=date(2026, 5, 15),
        created_at=datetime.utcnow()
    )
    db.add(tx1_new)
    db.commit()

    check_and_notify_budget_threshold(db, test_user.id, date(2026, 5, 15))

    # warning 알림 개수 2개여야 함 (최초 1 + 재발화 1)
    warn_notif = db.query(Notification).filter(
        Notification.user_id == test_user.id,
        Notification.type == "BUDGET_WARNING"
    ).all()
    assert len(warn_notif) == 2


def test_user_requested_scenario(auth_client, db, test_user, my_category, other_user_category):
    # 1. amount=0 예산 생성 -> 422
    resp = auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": 0,
        "category_id": None
    })
    assert resp.status_code == 422

    # 2. 다른 사용자 category_id 사용 -> 403
    resp = auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": 100000,
        "category_id": str(other_user_category.id)
    })
    assert resp.status_code == 403

    # 3. 식비 예산 10만원 설정
    resp = auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": 100000,
        "category_id": str(my_category.id)
    })
    assert resp.status_code in (200, 201)

    # 8만원 거래 추가
    tx1 = Transaction(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type="EXPENSE",
        amount=80000,
        category_id=my_category.id,
        description="점심 식비",
        transaction_date=date(2026, 5, 10),
        created_at=datetime.utcnow()
    )
    db.add(tx1)
    db.commit()

    # 알림 트리거 작동 -> 80% + 카테고리별 WARNING 알림 발생
    check_and_notify_budget_threshold(db, test_user.id, date(2026, 5, 10))

    # 알림 검증
    warn_notifs = db.query(Notification).filter(
        Notification.user_id == test_user.id,
        Notification.type == "BUDGET_WARNING"
    ).all()
    assert len(warn_notifs) == 1
    assert "식비" in warn_notifs[0].message

    # 4. 8만원 거래 삭제 -> 0% 복귀, flag 리셋
    db.delete(tx1)
    db.commit()

    check_and_notify_budget_threshold(db, test_user.id, date(2026, 5, 10))

    budget = db.query(Budget).filter(
        Budget.user_id == test_user.id,
        Budget.category_id == my_category.id,
        Budget.year_month == "2026-05"
    ).first()
    assert budget.is_warning_notified is False

    # 5. 8만원 다시 추가 -> 다시 WARNING 알림 (재발화)
    tx2 = Transaction(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type="EXPENSE",
        amount=80000,
        category_id=my_category.id,
        description="저녁 식비",
        transaction_date=date(2026, 5, 12),
        created_at=datetime.utcnow()
    )
    db.add(tx2)
    db.commit()

    check_and_notify_budget_threshold(db, test_user.id, date(2026, 5, 12))

    warn_notifs = db.query(Notification).filter(
        Notification.user_id == test_user.id,
        Notification.type == "BUDGET_WARNING"
    ).all()
    assert len(warn_notifs) == 2

    # 6. 예산 10만원 -> 20만원 변경 -> flag 리셋
    resp = auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": 200000,
        "category_id": str(my_category.id)
    })
    assert resp.status_code in (200, 201)

    db.refresh(budget)
    assert budget.is_warning_notified is False
    assert budget.is_exceeded_notified is False

    # 7. overall 예산도 별개로 동작 확인
    overall_resp = auth_client.post("/api/budgets", json={
        "year_month": "2026-05",
        "amount": 200000,
        "category_id": None
    })
    assert overall_resp.status_code in (200, 201)

    other_cat = Category(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="교통",
        type="EXPENSE"
    )
    db.add(other_cat)
    
    tx3 = Transaction(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type="EXPENSE",
        amount=80000,
        category_id=other_cat.id,
        description="택시비",
        transaction_date=date(2026, 5, 14),
        created_at=datetime.utcnow()
    )
    db.add(tx3)
    db.commit()

    # 알림 트리거 작동 -> 전체 지출 16만원(80% 도달)에 대한 overall WARNING 발생
    check_and_notify_budget_threshold(db, test_user.id, date(2026, 5, 14))

    overall_budget = db.query(Budget).filter(
        Budget.user_id == test_user.id,
        Budget.category_id == None,
        Budget.year_month == "2026-05"
    ).first()
    assert overall_budget.is_warning_notified is True
