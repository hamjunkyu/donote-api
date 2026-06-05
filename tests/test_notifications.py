import uuid

from app.auth.models import User
from app.notifications.constants import NotificationType
from app.notifications.service import create_notification


def _make_notifications(db, user_id, count):
    for i in range(count):
        create_notification(db, user_id, NotificationType.BUDGET_WARNING, f"알림 {i}")


def test_list_notifications_paginated(auth_client, test_user, db):
    """목록은 PaginatedResponse(items/total/limit/offset) 형태로 반환된다."""
    _make_notifications(db, test_user.id, 3)

    body = auth_client.get("/api/notifications").json()

    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["limit"] == 20 and body["offset"] == 0


def test_list_unread_filter(auth_client, test_user, db):
    """unread=true 는 미확인 알림만 반환한다."""
    _make_notifications(db, test_user.id, 2)
    first_id = auth_client.get("/api/notifications").json()["items"][0]["id"]
    auth_client.patch(f"/api/notifications/{first_id}/read")

    unread = auth_client.get("/api/notifications", params={"unread": "true"}).json()

    assert unread["total"] == 1


def test_read_all(auth_client, test_user, db):
    """read-all 은 모든 미확인 알림을 읽음 처리한다."""
    _make_notifications(db, test_user.id, 3)

    resp = auth_client.patch("/api/notifications/read-all")

    assert resp.status_code == 200
    assert auth_client.get("/api/notifications", params={"unread": "true"}).json()["total"] == 0


def test_delete_notification(auth_client, test_user, db):
    """본인 알림 삭제 후 목록에서 사라진다."""
    _make_notifications(db, test_user.id, 1)
    nid = auth_client.get("/api/notifications").json()["items"][0]["id"]

    resp = auth_client.delete(f"/api/notifications/{nid}")

    assert resp.status_code == 204
    assert auth_client.get("/api/notifications").json()["total"] == 0


def test_delete_other_users_notification_returns_404(auth_client, test_user, db):
    """다른 사용자의 알림은 삭제할 수 없다 (404)."""
    other = User(
        id=uuid.uuid4(),
        email=f"other_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hashedpassword",
        name="다른유저",
    )
    db.add(other)
    db.commit()
    notification = create_notification(db, other.id, NotificationType.BUDGET_WARNING, "남의 알림")

    resp = auth_client.delete(f"/api/notifications/{notification.id}")

    assert resp.status_code == 404
