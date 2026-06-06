import pytest
import uuid
from datetime import date, datetime, timedelta
from app.categories.models import Category
from app.transactions.models import Transaction
from app.goals.models import Goal, GoalContribution


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
def transport_category(db, test_user):
    """교통비 카테고리 피스처."""
    category = Category(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="교통",
        type="EXPENSE"
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@pytest.fixture
def setup_hundred_transactions(db, test_user, my_category, transport_category):
    """100개의 테스트용 거래 데이터를 생성하는 피스처."""
    # 50개는 식비(EXPENSE), description에 '점심' 포함
    # 50개는 교통(EXPENSE), description에 '지하철' 포함
    base_date = date(2026, 5, 1)
    transactions = []
    
    for i in range(100):
        is_even = (i % 2 == 0)
        cat = my_category if is_even else transport_category
        desc = f"맛있는 점심 {i}" if is_even else f"교통 지하철 {i}"
        
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=test_user.id,
            type="EXPENSE",
            amount=1000 + i,
            category_id=cat.id,
            description=desc,
            transaction_date=base_date + timedelta(days=i // 2),  # 날짜 분산 (정렬 검증용)
            created_at=datetime.utcnow() + timedelta(minutes=i)
        )
        db.add(tx)
        transactions.append(tx)
        
    db.commit()
    return transactions


def test_transactions_pagination_and_sorting(auth_client, setup_hundred_transactions):
    # 1. limit=20 페이징 테스트 -> items 20개, total 100건 (경로 /api/transactions 로 매칭)
    response = auth_client.get("/api/transactions?limit=20&offset=0")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["total"] == 100
    assert len(res_data["items"]) == 20
    assert res_data["limit"] == 20
    assert res_data["offset"] == 0

    # 2. 정렬 순서 검증 -> transaction_date DESC, created_at DESC
    items = res_data["items"]
    for i in range(len(items) - 1):
        date_curr = date.fromisoformat(items[i]["transaction_date"])
        date_next = date.fromisoformat(items[i+1]["transaction_date"])
        assert date_curr >= date_next
        if date_curr == date_next:
            created_curr = datetime.fromisoformat(items[i]["created_at"].replace("Z", "+00:00"))
            created_next = datetime.fromisoformat(items[i+1]["created_at"].replace("Z", "+00:00"))
            assert created_curr >= created_next


def test_transactions_filters_and_keyword(auth_client, setup_hundred_transactions, my_category):
    # 1. type=EXPENSE 필터링 -> total 100
    response = auth_client.get("/api/transactions?type=EXPENSE")
    assert response.status_code == 200
    assert response.json()["total"] == 100

    # 2. category_id 필터링 -> 식비 카테고리만 (50건)
    response = auth_client.get(f"/api/transactions?category_id={my_category.id}")
    assert response.status_code == 200
    assert response.json()["total"] == 50

    # 3. keyword="점심" 검색 -> '점심' 단어 포함 지출만 (50건)
    response = auth_client.get("/api/transactions?keyword=점심")
    assert response.status_code == 200
    assert response.json()["total"] == 50

    # 4. 복합 필터 (식비 + keyword="점심" + 금액 범위 1000~1020원)
    response = auth_client.get(
        f"/api/transactions?category_id={my_category.id}&keyword=점심&amount_min=1000&amount_max=1020"
    )
    assert response.status_code == 200
    res_data = response.json()
    # 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20 번 인덱스 거래들만 해당함 -> 총 11건
    assert res_data["total"] == 11
    
    # 5. keyword="NONE" 검색 -> 빈 배열 및 total=0 반환
    response = auth_client.get("/api/transactions?keyword=NONE")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["total"] == 0
    assert len(res_data["items"]) == 0


def test_goals_pagination(auth_client, db, test_user):
    # IN_PROGRESS 목표 5개 → 상태 필터 + limit/offset 슬라이싱 검증
    for i in range(5):
        goal = Goal(
            id=uuid.uuid4(),
            user_id=test_user.id,
            name=f"목표 {i}",
            target_amount=100000,
            target_date=date.today() + timedelta(days=30),
            status="IN_PROGRESS",
            created_at=datetime.utcnow() - timedelta(days=1)
        )
        db.add(goal)
    db.commit()

    response = auth_client.get("/api/goals?status=IN_PROGRESS&limit=2&offset=0")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["total"] == 5
    assert len(res_data["items"]) == 2
    assert res_data["limit"] == 2
    assert res_data["offset"] == 0

    response = auth_client.get("/api/goals?status=IN_PROGRESS&limit=2&offset=2")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["total"] == 5
    assert len(res_data["items"]) == 2
    assert res_data["offset"] == 2


def test_goal_contributions_pagination(auth_client, db, test_user):
    # 목표 + 적립 5건 → 적립 내역 페이징 검증
    goal = Goal(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="여행 목표",
        target_amount=100000,
        target_date=date.today() + timedelta(days=10),
        status="IN_PROGRESS",
        created_at=datetime.utcnow() - timedelta(hours=1)
    )
    db.add(goal)
    db.commit()

    for i in range(5):
        contribution = GoalContribution(
            id=uuid.uuid4(),
            goal_id=goal.id,
            amount=1000,
            memo=f"적립 {i}",
            contributed_at=date.today(),
            created_at=datetime.utcnow() + timedelta(minutes=i)
        )
        db.add(contribution)
    db.commit()

    response = auth_client.get(f"/api/goals/{goal.id}/contributions?limit=3&offset=0")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["total"] == 5
    assert len(res_data["items"]) == 3
    assert res_data["limit"] == 3


def test_transactions_empty_keyword(auth_client, setup_hundred_transactions):
    # 빈 keyword="" 전달 시, description 필터링 없이 전체 100건이 조회되는지 검증
    response = auth_client.get("/api/transactions?keyword=")
    assert response.status_code == 200
    assert response.json()["total"] == 100

    # 공백만 있는 keyword="   " 전달 시에도 전체 100건이 조회되는지 검증
    response_spaces = auth_client.get("/api/transactions?keyword=%20%20%20")
    assert response_spaces.status_code == 200
    assert response_spaces.json()["total"] == 100


def test_transactions_contradictory_filters_error_400(auth_client):
    # 1. date_from > date_to 모순 입력 시 -> 400 Bad Request
    response = auth_client.get("/api/transactions?date_from=2026-05-10&date_to=2026-05-01")
    assert response.status_code == 400
    assert "date_from은 date_to보다 이전이어야 합니다" in response.json()["detail"]

    # 2. amount_min > amount_max 모순 입력 시 -> 400 Bad Request
    response = auth_client.get("/api/transactions?amount_min=5000&amount_max=1000")
    assert response.status_code == 400
    assert "amount_min은 amount_max보다 작거나 같아야 합니다" in response.json()["detail"]
