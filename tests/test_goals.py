import uuid
from datetime import date, timedelta

from app.goals.models import Goal
from app.notifications.models import Notification


def test_create_and_read_goal(auth_client, test_user):
    """카테고리 없이 목표를 생성하고, 초기 진행률 0 / status IN_PROGRESS 확인."""
    goal_data = {
        "name": "제주도 여행자금",
        "target_amount": 1000000,
        "target_date": str(date.today() + timedelta(days=30)),
        "description": "올해 여름 제주도 여행 저축 목표",
    }
    response = auth_client.post("/api/goals/", json=goal_data)
    assert response.status_code == 201
    res = response.json()
    assert res["name"] == "제주도 여행자금"
    assert res["current_amount"] == 0
    assert res["progress_percentage"] == 0
    assert res["remaining_amount"] == 1000000
    assert res["status"] == "IN_PROGRESS"
    assert "category_id" not in res

    list_res = auth_client.get("/api/goals/").json()
    assert list_res["total"] >= 1
    item = list_res["items"][0]
    assert item["current_amount"] == 0
    assert item["status"] == "IN_PROGRESS"


def test_contribution_progress_and_in_progress_filter(auth_client, test_user):
    """적립하면 진행률이 오르고, IN_PROGRESS 필터가 정상 동작한다 (이전엔 422)."""
    goal_id = auth_client.post("/api/goals/", json={
        "name": "비상금", "target_amount": 100000,
    }).json()["id"]

    r = auth_client.post(
        f"/api/goals/{goal_id}/contributions", json={"amount": 40000, "memo": "1차"}
    )
    assert r.status_code == 201

    goal = auth_client.get(f"/api/goals/{goal_id}").json()
    assert goal["current_amount"] == 40000
    assert goal["progress_percentage"] == 40
    assert goal["remaining_amount"] == 60000

    contribs = auth_client.get(f"/api/goals/{goal_id}/contributions").json()
    assert contribs["total"] == 1
    assert contribs["items"][0]["memo"] == "1차"

    flt = auth_client.get("/api/goals/?status=IN_PROGRESS")
    assert flt.status_code == 200
    assert flt.json()["total"] >= 1


def test_milestones_achievement_and_revert(auth_client, test_user, db):
    """적립 누적으로 마일스톤·달성 알림이 발생하고, 적립 삭제 시 복구된다."""
    goal_id = auth_client.post("/api/goals/", json={
        "name": "맥북", "target_amount": 1000000,
    }).json()["id"]
    gid = uuid.UUID(goal_id)

    # 25% 적립 → 마일스톤 알림
    auth_client.post(f"/api/goals/{goal_id}/contributions", json={"amount": 250000})
    db.expire_all()
    goal = db.query(Goal).filter(Goal.id == gid).first()
    assert goal.is_25_notified is True
    assert goal.is_50_notified is False

    milestones = db.query(Notification).filter(
        Notification.user_id == test_user.id,
        Notification.type == "GOAL_MILESTONE",
    ).all()
    assert len(milestones) == 1
    assert "25%" in milestones[0].message

    # 누적 75%
    auth_client.post(f"/api/goals/{goal_id}/contributions", json={"amount": 500000})
    db.expire_all()
    goal = db.query(Goal).filter(Goal.id == gid).first()
    assert goal.is_50_notified is True
    assert goal.is_75_notified is True
    assert goal.is_achieved_notified is False

    # 100% 달성
    last = auth_client.post(
        f"/api/goals/{goal_id}/contributions", json={"amount": 250000}
    ).json()
    db.expire_all()
    goal = db.query(Goal).filter(Goal.id == gid).first()
    assert goal.status == "ACHIEVED"
    assert goal.is_achieved_notified is True
    assert goal.achieved_at is not None
    achieved = db.query(Notification).filter(
        Notification.user_id == test_user.id,
        Notification.type == "GOAL_ACHIEVED",
    ).first()
    assert achieved is not None

    # 적립 삭제로 100% 미만 → 상태·플래그 복구
    del_res = auth_client.delete(f"/api/goals/{goal_id}/contributions/{last['id']}")
    assert del_res.status_code == 204
    db.expire_all()
    goal = db.query(Goal).filter(Goal.id == gid).first()
    assert goal.status == "IN_PROGRESS"
    assert goal.is_achieved_notified is False
    assert goal.achieved_at is None


def test_contribution_on_missing_goal_returns_404(auth_client, test_user):
    missing = uuid.uuid4()
    r = auth_client.post(f"/api/goals/{missing}/contributions", json={"amount": 1000})
    assert r.status_code == 404
