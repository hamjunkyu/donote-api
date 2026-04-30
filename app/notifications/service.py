"""알림 서비스 로직."""

import uuid
from typing import List
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.notifications.models import Notification


def get_notifications(db: Session, user_id: uuid.UUID) -> List[Notification]:
    """사용자의 알림 목록을 최신순으로 조회한다."""
    return db.scalars(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    ).all()


def mark_notification_as_read(db: Session, user_id: uuid.UUID, notification_id: uuid.UUID) -> bool:
    """알림을 읽음 처리한다."""
    result = db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(is_read=True)
    )
    db.commit()
    return result.rowcount > 0


def create_notification(db: Session, user_id: uuid.UUID, type: str, message: str) -> Notification:
    """새로운 알림을 생성한다."""
    notification = Notification(
        user_id=user_id,
        type=type,
        message=message
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification
