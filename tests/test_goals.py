import pytest
import uuid
from datetime import date, datetime, timedelta
from app.categories.models import Category
from app.goals.models import Goal
from app.transactions.models import Transaction
from app.notifications.models import Notification


@pytest.fixture
def test_category(db, test_user):
    """테스트용 지출 카테고리 생성 피스처."""
    category = Category(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="저축-여행자금",
        type="EXPENSE"
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def test_create_and_read_goal(auth_client, test_user, test_category):
    # 1. 목표 생성
    goal_data = {
        "name": "제주도 여행자금",
        "target_amount": 1000000,
        "target_date": str(date.today() + timedelta(days=30)),
        "category_id": str(test_category.id),
        "description": "올해 여름 제주도 여행 저축 목표"
    }
    response = auth_client.post("/api/goals/", json=goal_data)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["name"] == "제주도 여행자금"
    assert res_data["current_amount"] == 0
    assert res_data["progress_percentage"] == 0
    assert res_data["remaining_amount"] == 1000000
    assert res_data["status"] == "ON_TRACK"

    # 2. 목록 조회 및 계산 필드 검증
    list_response = auth_client.get("/api/goals/")
    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1
    goal_item = list_response.json()[0]
    assert goal_item["current_amount"] == 0
    assert goal_item["progress_percentage"] == 0
    assert goal_item["status"] == "ON_TRACK"


def test_goal_milestones_and_refiring(auth_client, test_user, test_category, db):
    # 1. 100만원 목표 생성
    goal_data = {
        "name": "맥북 구매 자금",
        "target_amount": 1000000,
        "target_date": str(date.today() + timedelta(days=10)),
        "category_id": str(test_category.id),
        "description": "맥북 프로 저축 목표"
    }
    response = auth_client.post("/api/goals/", json=goal_data)
    goal_id = response.json()["id"]

    # 2. 25만원 지출(저축) 기록 추가 -> 25% 마일스톤 도달
    tx25 = Transaction(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type="EXPENSE",
        amount=250000,
        category_id=test_category.id,
        description="맥북 저금 1차",
        transaction_date=date.today(),
        created_at=datetime.utcnow()
    )
    db.add(tx25)
    db.commit()

    # 알림 발생 로직 트리거
    from app.goals.service import check_and_notify_goal_achievement
    check_and_notify_goal_achievement(db, test_user.id, test_category.id)

    # 마일스톤 및 알림 확인
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    assert goal.is_25_notified is True
    assert goal.is_50_notified is False

    # 알림함 검증
    notifications = db.query(Notification).filter(Notification.user_id == test_user.id, Notification.type == "GOAL_MILESTONE").all()
    assert len(notifications) == 1
    assert "25%" in notifications[0].message

    # 3. 50만원 지출 추가 -> 75% 마일스톤 도달 (25 + 50 = 75)
    tx50 = Transaction(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type="EXPENSE",
        amount=500000,
        category_id=test_category.id,
        description="맥북 저금 2차",
        transaction_date=date.today(),
        created_at=datetime.utcnow()
    )
    db.add(tx50)
    db.commit()
    check_and_notify_goal_achievement(db, test_user.id, test_category.id)

    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    assert goal.is_25_notified is True
    assert goal.is_50_notified is True
    assert goal.is_75_notified is True
    assert goal.is_achieved_notified is False

    # 4. 25만원 추가 지출 -> 100% 달성
    tx100 = Transaction(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type="EXPENSE",
        amount=250000,
        category_id=test_category.id,
        description="맥북 저금 완납",
        transaction_date=date.today(),
        created_at=datetime.utcnow()
    )
    db.add(tx100)
    db.commit()
    check_and_notify_goal_achievement(db, test_user.id, test_category.id)

    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    assert goal.is_achieved_notified is True
    assert goal.status == "ACHIEVED"
    assert goal.achieved_at is not None

    # 달성 알림 생성 확인
    achieved_notif = db.query(Notification).filter(Notification.user_id == test_user.id, Notification.type == "GOAL_ACHIEVED").first()
    assert achieved_notif is not None

    # 5. 거래 삭제로 하락 유도 -> 플래그 리셋 및 재발화 테스트
    db.delete(tx100)
    db.commit()
    check_and_notify_goal_achievement(db, test_user.id, test_category.id)

    # 100% 미달로 돌아갔으므로 achieved flag reset 및 status=IN_PROGRESS 검증
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    assert goal.is_achieved_notified is False
    assert goal.status == "IN_PROGRESS"
    assert goal.achieved_at is None

    # 6. 다시 25만원 추가 지출 -> 100% 재달성 및 재알림 확인
    tx100_new = Transaction(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type="EXPENSE",
        amount=250000,
        category_id=test_category.id,
        description="맥북 저금 재완납",
        transaction_date=date.today(),
        created_at=datetime.utcnow()
    )
    db.add(tx100_new)
    db.commit()
    check_and_notify_goal_achievement(db, test_user.id, test_category.id)

    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    assert goal.is_achieved_notified is True
    assert goal.status == "ACHIEVED"


def test_goal_border_day_status(auth_client, test_user, test_category, db):
    # 오늘이 마감일인데 목표 달성액이 부족한 경우 -> BEHIND로 올바르게 상태 판정되는지 검증
    goal = Goal(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="오늘까지 마감 목표",
        target_amount=100000,
        target_date=date.today(),
        category_id=test_category.id,
        status="IN_PROGRESS",
        created_at=datetime.utcnow() # 오늘 만듦 (total_days = 0)
    )
    db.add(goal)
    db.commit()

    # 진행률 조회
    response = auth_client.get(f"/api/goals/{goal.id}/progress")
    assert response.status_code == 200
    assert response.json()["status"] == "BEHIND"
