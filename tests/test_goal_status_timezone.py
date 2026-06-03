import uuid
from datetime import datetime, timedelta

from app.goals.service import determine_status
from app.goals.models import Goal


def _goal(created_at, target_date):
    return Goal(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="목표",
        target_amount=1000000,
        target_date=target_date,
        status="IN_PROGRESS",
        created_at=created_at,
    )


def test_fresh_goal_is_on_track_regardless_of_local_tz():
    # 방금 생성(UTC) + 미래 목표일 + 진행 0 → 경과율 0 → ON_TRACK.
    # 날짜 비교가 UTC 로 통일돼 서버 로컬 TZ 와 무관하게 결정적이어야 한다.
    now = datetime.utcnow()
    goal = _goal(created_at=now, target_date=(now + timedelta(days=30)).date())
    assert determine_status(goal, 0.0) == "ON_TRACK"


def test_goal_expired_uses_utc_today():
    now = datetime.utcnow()
    goal = _goal(
        created_at=now - timedelta(days=10),
        target_date=(now - timedelta(days=1)).date(),
    )
    assert determine_status(goal, 0.0) == "EXPIRED"
