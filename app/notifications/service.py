"""알림 서비스 로직."""

import uuid
from typing import List, Optional, Tuple
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import Session

from app.notifications.models import Notification
from app.notifications.constants import NotificationType


def get_notifications(
    db: Session,
    user_id: uuid.UUID,
    unread: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[List[Notification], int]:
    """사용자의 알림 목록을 최신순으로 조회한다 (전체 개수와 함께).

    unread=True 면 미확인 알림만 반환한다.
    """
    conditions = [Notification.user_id == user_id]
    if unread is True:
        conditions.append(Notification.is_read.is_(False))

    total = db.scalar(
        select(func.count()).select_from(Notification).where(*conditions)
    )
    items = db.scalars(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(items), total or 0


def mark_notification_as_read(db: Session, user_id: uuid.UUID, notification_id: uuid.UUID) -> bool:
    """알림을 읽음 처리한다."""
    result = db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(is_read=True)
    )
    db.commit()
    return result.rowcount > 0


def mark_all_as_read(db: Session, user_id: uuid.UUID) -> int:
    """사용자의 모든 미확인 알림을 읽음 처리하고 처리한 개수를 반환한다."""
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return result.rowcount


def delete_notification(db: Session, user_id: uuid.UUID, notification_id: uuid.UUID) -> bool:
    """본인 소유 알림을 삭제한다."""
    result = db.execute(
        delete(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
    )
    db.commit()
    return result.rowcount > 0


def create_notification(
    db: Session,
    user_id: uuid.UUID,
    type: NotificationType,
    message: str,
    commit: bool = True,
) -> Notification:
    """새로운 알림을 생성한다.

    type 은 NotificationType 으로 검증·정규화되어 저장된다.
    commit=False 면 세션에 추가만 하고 커밋은 호출자가 담당한다 (거래 흐름처럼
    알림과 본 작업을 한 트랜잭션으로 묶을 때 사용).
    """
    notification = Notification(
        user_id=user_id,
        type=NotificationType(type).value,
        message=message,
    )
    db.add(notification)
    if commit:
        db.commit()
        db.refresh(notification)
    return notification
